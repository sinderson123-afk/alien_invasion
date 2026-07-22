"""JSON 文件加密/解密 — 防篡改、原子写、自动备份（stdlib only）

- 写入：先写 .tmp → 校验通过后 rename → 旧文件自动备份为 .bak
- 读取：优先读原文件 → 失败则回退 .bak
- 加密：SHA256 密钥派生 + XOR 混淆 + CRC32 完整性校验
"""

import json
import struct
import hashlib
import zlib
from pathlib import Path

_KEY = b"AlienInvasion2026\x14\xa3\xf2\xc7\x1b_\xdd\xe8\x99\x04\x52"


def _derive_key() -> bytes:
    return hashlib.sha256(_KEY).digest()


def _encrypt(raw: bytes) -> bytes:
    key = _derive_key()
    encrypted = bytes(b ^ key[i % 32] for i, b in enumerate(raw))
    crc = struct.pack('<I', zlib.crc32(raw) & 0xFFFFFFFF)
    return crc + encrypted


def _decrypt(data: bytes) -> bytes | None:
    if len(data) < 4:
        return None
    crc_stored = struct.unpack('<I', data[:4])[0]
    encrypted = data[4:]
    key = _derive_key()
    raw = bytes(b ^ key[i % 32] for i, b in enumerate(encrypted))
    if zlib.crc32(raw) != crc_stored:
        return None
    return raw


def encrypt_json(data: dict, filepath: Path) -> bool:
    """加密 JSON 数据，原子写入（.tmp → rename），旧文件自动 .bak 备份"""
    try:
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        blob = _encrypt(raw)

        tmp_path = filepath.with_suffix(filepath.suffix + '.tmp')
        tmp_path.write_bytes(blob)

        # 验证刚写入的 .tmp 可读
        check = _decrypt(tmp_path.read_bytes())
        if check is None or check != raw:
            tmp_path.unlink(missing_ok=True)
            return False

        # 旧文件 → .bak 备份
        if filepath.exists():
            bak_path = filepath.with_suffix(filepath.suffix + '.bak')
            try:
                filepath.replace(bak_path)
            except OSError:
                bak_path.unlink(missing_ok=True)
                filepath.replace(bak_path)

        # .tmp → 正式文件（原子 rename）
        tmp_path.replace(filepath)
        return True
    except Exception:
        return False


def decrypt_json(filepath: Path) -> dict | None:
    """解密 JSON 文件。主文件失败自动回退 .bak，都失败返回 None"""
    for path in (filepath, filepath.with_suffix(filepath.suffix + '.bak')):
        if not path.exists():
            continue
        try:
            raw = _decrypt(path.read_bytes())
            if raw is not None:
                return json.loads(raw.decode('utf-8'))
        except Exception:
            continue
    return None
