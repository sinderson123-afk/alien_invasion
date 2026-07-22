"""JSON 文件加密/解密 — 防篡改、原子写、自动备份、多密钥管理（stdlib only）

文件格式:
  [4B CRC32] [4B format_version] [encrypted data]

写入: .tmp → 校验 → rename → 旧文件自动 .bak
读取: 主文件 → .bak 回退
"""

import json
import struct
import hashlib
import zlib
from pathlib import Path

# 当前加密格式版本
_FORMAT_VERSION = 1

# 密钥池：旧密钥保留用于解密，当前密钥用于加密
# 格式: {version: key_bytes}
_KEYS = {
    1: b"AlienInvasion2026\x14\xa3\xf2\xc7\x1b_\xdd\xe8\x99\x04\x52",
}


def _derive_key(version: int = None) -> bytes:
    if version is None:
        version = _FORMAT_VERSION
    key_bytes = _KEYS.get(version, _KEYS[_FORMAT_VERSION])
    return hashlib.sha256(key_bytes).digest()


def _encrypt(raw: bytes) -> bytes:
    key = _derive_key()
    encrypted = bytes(b ^ key[i % 32] for i, b in enumerate(raw))
    crc = struct.pack('<I', zlib.crc32(raw) & 0xFFFFFFFF)
    fmt = struct.pack('<I', _FORMAT_VERSION)
    return crc + fmt + encrypted


def _decrypt(data: bytes) -> bytes | None:
    if len(data) < 8:
        return None
    crc_stored = struct.unpack('<I', data[:4])[0]
    fmt_version = struct.unpack('<I', data[4:8])[0]
    encrypted = data[8:]

    key = _derive_key(fmt_version)
    raw = bytes(b ^ key[i % 32] for i, b in enumerate(encrypted))

    if zlib.crc32(raw) != crc_stored:
        # 尝试用当前密钥解密（旧格式没有 fmt_version 头的情况）
        if fmt_version != _FORMAT_VERSION:
            raw2 = bytes(b ^ _derive_key(_FORMAT_VERSION)[i % 32]
                         for i, b in enumerate(encrypted))
            if zlib.crc32(raw2) == crc_stored:
                return raw2
        return None
    return raw


def encrypt_json(data: dict, filepath: Path) -> bool:
    """加密 JSON 数据，原子写入（.tmp → rename），旧文件自动 .bak 备份"""
    try:
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        blob = _encrypt(raw)

        tmp_path = filepath.with_suffix(filepath.suffix + '.tmp')
        tmp_path.write_bytes(blob)

        check = _decrypt(tmp_path.read_bytes())
        if check is None or check != raw:
            tmp_path.unlink(missing_ok=True)
            return False

        if filepath.exists():
            bak_path = filepath.with_suffix(filepath.suffix + '.bak')
            try:
                filepath.replace(bak_path)
            except OSError:
                bak_path.unlink(missing_ok=True)
                filepath.replace(bak_path)

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
