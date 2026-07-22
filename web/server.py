"""Alien Invasion 云端服务器 — 邮箱验证码认证 + 排行榜 + 数据持久化
Cloud Run 部署触发推送
谷歌云部署（Cloud Run）：
    gunicorn -w 2 -b 0.0.0.0:$PORT server:app
本地开发（需 Firestore 仿真器或服务账号密钥）：
    python server.py
"""

import os
import re
import secrets
import hashlib
import logging
from pathlib import Path
from datetime import timezone

import bcrypt
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.cloud import firestore

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).parent.resolve()
os.chdir(_BASE_DIR)

RESEND_API_KEY = os.environ.get(
    'RESEND_API_KEY', 're_L5Jw76Mj_2uHhgxTjCa3zfwwSBkgjB4hn')
RESEND_FROM = "Alien Invasion <onboarding@resend.dev>"
CODE_EXPIRE_SECONDS = 600  # 10 分钟
CODE_MAX_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

app = Flask(__name__, static_folder=str(_BASE_DIR), static_url_path='')
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)

db = firestore.Client()

# ---------------------------------------------------------------------------
# 跨域隔离头
# ---------------------------------------------------------------------------
@app.after_request
def set_isolation_headers(response):
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'credentialless'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# ---------------------------------------------------------------------------
# 校验工具
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{2,20}$')
_PASSWORD_MIN = 4
_ANTI_CHEAT_RATIO = 10000


def _validate_email(email: str) -> bool:
    return isinstance(email, str) and bool(_EMAIL_RE.match(email))


def _validate_username(name: str) -> bool:
    return isinstance(name, str) and bool(_USERNAME_RE.match(name))


def _validate_password(pw: str) -> bool:
    return isinstance(pw, str) and len(pw) >= _PASSWORD_MIN


def _validate_score(score: int, level: int) -> bool:
    return isinstance(score, int) and isinstance(level, int) \
        and score >= 0 and level >= 0 \
        and score <= max(level, 1) * _ANTI_CHEAT_RATIO


# ---------------------------------------------------------------------------
# Resend 邮件发送
# ---------------------------------------------------------------------------
def _send_verification_email(to_email: str, code: str, purpose: str) -> bool:
    """通过 Resend API 发送验证码邮件"""
    subject_map = {
        'register': '注册验证码 - Alien Invasion',
        'reset': '密码重置验证码 - Alien Invasion',
    }
    purpose_map = {
        'register': '注册新账号',
        'reset': '重置密码',
    }
    try:
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {RESEND_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'from': RESEND_FROM,
                'to': [to_email],
                'subject': subject_map.get(purpose, '验证码 - Alien Invasion'),
                'html': f'''<div style="font-family:sans-serif;padding:24px;max-width:400px;">
                    <h2 style="color:#333;">{purpose_map.get(purpose, '')}验证</h2>
                    <p>您好！您的验证码是：</p>
                    <h1 style="color:#4f46e5;font-size:36px;letter-spacing:5px;">{code}</h1>
                    <p style="color:#888;font-size:13px;">10 分钟内有效。如非本人操作请忽略。</p>
                </div>''',
            },
            timeout=8,
        )
        result = resp.json()
        if resp.status_code == 200:
            logging.info("邮件已发送: %s -> %s", to_email, result.get('id', ''))
            return True
        logging.error("Resend 失败: %s", result)
        return False
    except Exception as e:
        logging.error("Resend 请求异常: %s", e)
        return False


# ---------------------------------------------------------------------------
# 认证路由
# ---------------------------------------------------------------------------
@app.route('/api/auth/send-code', methods=['POST'])
@limiter.limit("5 per minute")
def send_code():
    """发送邮箱验证码（注册或重置密码）"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    purpose = (data.get('purpose') or 'register').strip()

    if not _validate_email(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if purpose not in ('register', 'reset'):
        return jsonify({"error": "无效的验证目的"}), 400

    # 对于 'reset' 校验邮箱是否已注册
    if purpose == 'reset':
        users_ref = db.collection('users')
        exists = list(users_ref.where('email', '==', email).limit(1).get())
        if not exists:
            return jsonify({"error": "该邮箱未注册"}), 404

    code = ''.join(secrets.choice('0123456789') for _ in range(6))
    now = int(os.environ.get('_SERVER_TIME', __import__('time').time()))

    db.collection('codes').document(email).set({
        'code': code,
        'purpose': purpose,
        'expires_at': now + CODE_EXPIRE_SECONDS,
        'attempts': 0,
        'created_at': now,
    })

    if _send_verification_email(email, code, purpose):
        return jsonify({"success": True, "message": "验证码已发送"}), 200
    return jsonify({"error": "邮件发送失败，请稍后重试"}), 500


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not _validate_email(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({"error": "无效的验证码"}), 400
    if not _validate_username(username):
        return jsonify({"error": "用户名须为 2-20 位字母/数字/下划线/连字符"}), 400
    if not _validate_password(password):
        return jsonify({"error": "密码至少 4 位"}), 400

    # 校验验证码
    code_doc = db.collection('codes').document(email).get()
    if not code_doc.exists:
        return jsonify({"error": "请先获取验证码"}), 400

    code_data = code_doc.to_dict()
    now = int(os.environ.get('_SERVER_TIME', __import__('time').time()))

    if now > code_data['expires_at']:
        code_doc.reference.delete()
        return jsonify({"error": "验证码已过期"}), 400

    attempts = code_data.get('attempts', 0) + 1
    code_doc.reference.update({'attempts': attempts})

    if attempts > CODE_MAX_ATTEMPTS:
        code_doc.reference.delete()
        return jsonify({"error": "验证码尝试次数过多，请重新获取"}), 400

    if code_data['code'] != code:
        return jsonify({"error": "验证码错误"}), 400

    if code_data.get('purpose') != 'register':
        return jsonify({"error": "验证码用途不匹配"}), 400

    # 验证码通过，删除之
    code_doc.reference.delete()

    # 检查用户名唯一性
    users_ref = db.collection('users')
    dup = list(users_ref.where('username', '==', username).limit(1).get())
    if dup:
        return jsonify({"error": "用户名已被注册"}), 409

    # 检查邮箱是否已注册
    dup_email = list(users_ref.where('email', '==', email).limit(1).get())
    if dup_email:
        return jsonify({"error": "该邮箱已注册，请直接登录"}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    token = secrets.token_hex(32)

    user_ref = users_ref.document()
    user_ref.set({
        'email': email,
        'username': username,
        'password_hash': pw_hash,
        'tokens': [token],
        'created_at': firestore.SERVER_TIMESTAMP,
    })

    logging.info("新用户注册: %s (%s)", username, email)
    return jsonify({
        "status": "success",
        "token": token,
        "username": username,
        "email": email,
    }), 201


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------
@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    identifier = (data.get('identifier') or '').strip()
    password = data.get('password') or ''

    if not identifier or not _validate_password(password):
        return jsonify({"error": "用户名/邮箱或密码错误"}), 401

    users_ref = db.collection('users')

    # 尝试按用户名查找
    docs = list(users_ref.where('username', '==', identifier).limit(1).get())
    if not docs:
        # 尝试按邮箱查找
        docs = list(users_ref.where('email', '==', identifier.lower()).limit(1).get())

    if not docs:
        return jsonify({"error": "用户名/邮箱或密码错误"}), 401

    user_doc = docs[0]
    user_data = user_doc.to_dict()

    if not bcrypt.checkpw(password.encode(), user_data['password_hash'].encode()):
        return jsonify({"error": "用户名/邮箱或密码错误"}), 401

    token = secrets.token_hex(32)
    tokens = user_data.get('tokens', [])
    tokens.append(token)
    tokens = tokens[-10:]
    user_doc.reference.update({'tokens': tokens})

    logging.info("用户登录: %s", user_data['username'])
    return jsonify({
        "status": "success",
        "token": token,
        "username": user_data['username'],
        "email": user_data['email'],
    }), 200


# ---------------------------------------------------------------------------
# 重置密码
# ---------------------------------------------------------------------------
@app.route('/api/auth/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    new_password = data.get('new_password') or ''

    if not _validate_email(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({"error": "无效的验证码"}), 400
    if not _validate_password(new_password):
        return jsonify({"error": "密码至少 4 位"}), 400

    # 校验验证码
    code_doc = db.collection('codes').document(email).get()
    if not code_doc.exists:
        return jsonify({"error": "请先获取验证码"}), 400

    code_data = code_doc.to_dict()
    now = int(os.environ.get('_SERVER_TIME', __import__('time').time()))

    if now > code_data['expires_at']:
        code_doc.reference.delete()
        return jsonify({"error": "验证码已过期"}), 400

    attempts = code_data.get('attempts', 0) + 1
    code_doc.reference.update({'attempts': attempts})

    if attempts > CODE_MAX_ATTEMPTS:
        code_doc.reference.delete()
        return jsonify({"error": "验证码尝试次数过多，请重新获取"}), 400

    if code_data['code'] != code:
        return jsonify({"error": "验证码错误"}), 400

    if code_data.get('purpose') != 'reset':
        return jsonify({"error": "验证码用途不匹配"}), 400

    code_doc.reference.delete()

    # 查找用户
    users_ref = db.collection('users')
    docs = list(users_ref.where('email', '==', email).limit(1).get())
    if not docs:
        return jsonify({"error": "该邮箱未注册"}), 404

    user_doc = docs[0]
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    user_doc.reference.update({
        'password_hash': new_hash,
        'tokens': [],  # 重置所有 token，强制重新登录
    })

    logging.info("密码重置: %s", email)
    return jsonify({"success": True, "message": "密码已重置，请重新登录"}), 200


# ---------------------------------------------------------------------------
# Token 校验
# ---------------------------------------------------------------------------
def _require_auth(request_obj):
    auth_header = request_obj.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, jsonify({"error": "未提供认证令牌"}), 401
    token = auth_header[7:].strip()
    if not token:
        return None, jsonify({"error": "令牌为空"}), 401

    users_ref = db.collection('users')
    docs = users_ref.where('tokens', 'array_contains', token).limit(1).get()
    docs_list = list(docs)
    if not docs_list:
        return None, jsonify({"error": "令牌无效或已过期"}), 401

    user_doc = docs_list[0]
    user_data = user_doc.to_dict()
    return (user_doc.id, user_data['username'], user_data.get('email', '')), None, None


# ---------------------------------------------------------------------------
# 战绩上传
# ---------------------------------------------------------------------------
@app.route('/api/stats', methods=['POST'])
@limiter.limit("30 per minute")
def upload_stats():
    auth_result, error, status = _require_auth(request)
    if error:
        return error, status

    user_id, username, email = auth_result
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    score = data.get('score')
    level = data.get('level')
    kills = data.get('kills', 0)
    coins = data.get('coins', 0)

    if not _validate_score(score, level):
        logging.warning("拦截异常数据: user=%s score=%s level=%s", username, score, level)
        return jsonify({"error": "数据超出合理范围"}), 400

    now = int(os.environ.get('_SERVER_TIME', __import__('time').time()))
    lb_ref = db.collection('leaderboard').document(user_id)
    doc = lb_ref.get()

    if doc.exists:
        old_data = doc.to_dict()
        new_score = max(score, old_data.get('score', 0))
        new_level = max(level, old_data.get('level', 0))
        new_kills = max(kills, old_data.get('kills', 0))
        new_coins = max(coins, old_data.get('coins', 0))
    else:
        new_score, new_level, new_kills, new_coins = score, level, kills, coins

    lb_ref.set({
        'user_id': user_id,
        'username': username,
        'score': new_score,
        'level': new_level,
        'kills': new_kills,
        'coins': new_coins,
        'updated_at': now,
    })

    all_docs = db.collection('leaderboard').order_by(
        'score', direction=firestore.Query.DESCENDING).get()
    rank = next((i + 1 for i, d in enumerate(all_docs) if d.id == user_id), None)

    logging.info("战绩: %s score=%s level=%s rank=%s", username, new_score, new_level, rank)
    return jsonify({
        "status": "success",
        "rank": rank,
        "score_kept": new_score,
        "level_kept": new_level,
    }), 200


# ---------------------------------------------------------------------------
# 排行榜
# ---------------------------------------------------------------------------
@app.route('/api/leaderboard', methods=['GET'])
@limiter.limit("60 per minute")
def get_leaderboard():
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = max(1, min(limit, 100))
    except (ValueError, TypeError):
        limit = 20

    docs = db.collection('leaderboard').order_by(
        'score', direction=firestore.Query.DESCENDING).limit(limit).get()

    entries = []
    for doc in docs:
        d = doc.to_dict()
        entries.append({
            "username": d.get('username', '?'),
            "score": d.get('score', 0),
            "level": d.get('level', 1),
            "kills": d.get('kills', 0),
        })

    total_docs = list(db.collection('leaderboard').get())
    total = len(total_docs)
    highest = max((d.to_dict().get('score', 0) for d in total_docs), default=0)

    return jsonify({
        "status": "success",
        "leaderboard": entries,
        "total_players": total,
        "highest_score": highest,
    }), 200


# ---------------------------------------------------------------------------
# 健康检查 / 静态文件
# ---------------------------------------------------------------------------
@app.route('/health')
def health():
    return 'ok', 200


SAFE_EXTENSIONS = frozenset({
    '.html', '.js', '.wasm', '.data', '.json', '.css',
    '.png', '.jpg', '.jpeg', '.ico', '.svg', '.woff2',
    '.zip', '.gz', '.pygbag', '.apk',
})


@app.route('/')
def index():
    return send_from_directory(str(_BASE_DIR), 'index.html')


@app.route('/<path:path>')
def static_files(path):
    if '..' in path or path.startswith('/'):
        return '', 404
    ext = Path(path).suffix.lower()
    if ext not in SAFE_EXTENSIONS and path != 'index.html':
        return '', 404
    return send_from_directory(str(_BASE_DIR), path)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
