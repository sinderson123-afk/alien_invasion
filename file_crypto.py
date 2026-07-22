"""JSON file encryption/decryption - tamper-proof, atomic write, auto backup, multi-key (stdlib only)

File format:
  [4B CRC32] [4B format_version] [encrypted data]

Write: .tmp -> verify -> rename -> old auto .bak
Read: main -> .bak fallback
"""

import json
import struct
import hashlib
import zlib
from pathlib import Path

# Current encryption format version
_FORMAT_VERSION = 1

# Key pool: old keys retained for decryption, current key for encryption
# Format: {version: key_bytes}
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
        # Try decrypting with current key (for old format without fmt_version header)
        if fmt_version != _FORMAT_VERSION:
            raw2 = bytes(b ^ _derive_key(_FORMAT_VERSION)[i % 32]
                         for i, b in enumerate(encrypted))
            if zlib.crc32(raw2) == crc_stored:
                return raw2
        return None
    return raw


def encrypt_json(data: dict, filepath: Path) -> bool:
    """Encrypt JSON data, atomic write (.tmp -> rename), old file auto .bak backup"""
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
    """Decrypt JSON file. Fallback to .bak if main fails, return None if both fail"""
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
