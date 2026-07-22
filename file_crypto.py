"""JSON 文件加密/解密 — 防篡改（stdlib only，无外部依赖）

使用 SHA256 密钥派生 + XOR 混淆 + CRC32 完整性校验。
"""

import json
import struct
import hashlib
import zlib
from pathlib import Path

# 固定密钥（编译打包后不可见，但反编译可提取 — 仅防普通篡改）
_KEY = b"AlienInvasion2026\x14\xa3\xf2\xc7\x1b_\xdd\xe8\x99\x04\x52"


def _derive_key() -> bytes:
    """从固定密钥派生出 32 字节加密密钥"""
    return hashlib.sha256(_KEY).digest()


def encrypt_json(data: dict, filepath: Path) -> bool:
    """加密 JSON 数据并写入文件。失败返回 False。"""
    try:
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        key = _derive_key()
        encrypted = bytes(b ^ key[i % 32] for i, b in enumerate(raw))
        crc = struct.pack('<I', zlib.crc32(raw) & 0xFFFFFFFF)
        filepath.write_bytes(crc + encrypted)
        return True
    except Exception:
        return False


def decrypt_json(filepath: Path) -> dict | None:
    """解密并解析 JSON 文件。文件不存在或篡改返回 None。"""
    if not filepath.exists():
        return None
    try:
        data = filepath.read_bytes()
        if len(data) < 4:
            return None
        crc_stored = struct.unpack('<I', data[:4])[0]
        encrypted = data[4:]
        key = _derive_key()
        raw = bytes(b ^ key[i % 32] for i, b in enumerate(encrypted))
        if zlib.crc32(raw) != crc_stored:
            return None
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return None
