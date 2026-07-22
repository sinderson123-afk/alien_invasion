"""桌面游戏 HTTP 客户端 — 零外部依赖（只用 stdlib）

API:
  - send_code(email, purpose)    发送邮箱验证码
  - register(email, code, username, password)  注册
  - login(identifier, password)              登录（用户名或邮箱）
  - reset_password(email, code, new_password)  重置密码
  - upload_stats(token, ...)     上传战绩
  - get_leaderboard()            获取排行榜
"""

import json
import sys
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin


_CACHE_FILE = Path(os.path.dirname(sys.argv[0])) / "upload_cache.json"
_TIMEOUT = 8


class WebClient:
    """游戏 API 客户端"""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self._pending_uploads = self._load_cache()

    # ------------------------------------------------------------------
    # 本地缓存
    # ------------------------------------------------------------------
    def _load_cache(self) -> list:
        try:
            return json.loads(_CACHE_FILE.read_text())
        except (OSError, ValueError):
            return []

    def _save_cache(self):
        try:
            _CACHE_FILE.write_text(json.dumps(self._pending_uploads))
        except OSError:
            pass

    # ------------------------------------------------------------------
    # HTTP 封装
    # ------------------------------------------------------------------
    def _post(self, endpoint: str, data: dict, token: str | None = None):
        url = urljoin(self.server_url, endpoint)
        body = json.dumps(data).encode()
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        req = Request(url, data=body, headers=headers, method='POST')
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    def _get(self, endpoint: str):
        url = urljoin(self.server_url, endpoint)
        with urlopen(url, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    # ------------------------------------------------------------------
    # 认证：发送验证码
    # ------------------------------------------------------------------
    def send_code(self, email: str, purpose: str = 'register') -> dict:
        """发送邮箱验证码，返回 {success, message} 或 {error}"""
        return self._post('/api/auth/send-code', {
            'email': email.strip().lower(),
            'purpose': purpose,
        })

    # ------------------------------------------------------------------
    # 认证：注册
    # ------------------------------------------------------------------
    def register(self, email: str, code: str, username: str,
                 password: str) -> dict:
        """注册新账号，返回 {token, username, email} 或 {error}"""
        return self._post('/api/auth/register', {
            'email': email.strip().lower(),
            'code': code.strip(),
            'username': username.strip(),
            'password': password,
        })

    # ------------------------------------------------------------------
    # 认证：登录
    # ------------------------------------------------------------------
    def login(self, identifier: str, password: str) -> dict:
        """登录（用户名或邮箱），返回 {token, username, email} 或 {error}"""
        return self._post('/api/auth/login', {
            'identifier': identifier.strip(),
            'password': password,
        })

    # ------------------------------------------------------------------
    # 认证：重置密码
    # ------------------------------------------------------------------
    def reset_password(self, email: str, code: str,
                       new_password: str) -> dict:
        """重置密码，返回 {success, message} 或 {error}"""
        return self._post('/api/auth/reset-password', {
            'email': email.strip().lower(),
            'code': code.strip(),
            'new_password': new_password,
        })

    # ------------------------------------------------------------------
    # 战绩
    # ------------------------------------------------------------------
    def upload_stats(self, token: str, score: int, level: int,
                     kills: int = 0, coins: int = 0) -> dict:
        data = {'score': score, 'level': level, 'kills': kills, 'coins': coins}
        try:
            result = self._post('/api/stats', data, token=token)
        except (URLError, HTTPError, OSError, json.JSONDecodeError):
            self._pending_uploads.append({
                'score': score, 'level': level, 'kills': kills, 'coins': coins,
                'time': int(time.time()),
            })
            self._save_cache()
            return {'status': 'error', 'message': '上传失败，已缓存到本地'}
        self._retry_cache(token)
        return result

    def _retry_cache(self, token: str):
        if not self._pending_uploads:
            return
        remaining = []
        for entry in self._pending_uploads:
            try:
                self._post('/api/stats', {
                    'score': entry['score'], 'level': entry['level'],
                    'kills': entry['kills'], 'coins': entry['coins'],
                }, token=token)
            except (URLError, HTTPError, OSError, json.JSONDecodeError):
                remaining.append(entry)
        self._pending_uploads = remaining
        self._save_cache()

    # ------------------------------------------------------------------
    # 排行榜
    # ------------------------------------------------------------------
    def get_leaderboard(self, limit: int = 20) -> dict:
        return self._get(f'/api/leaderboard?limit={limit}')
