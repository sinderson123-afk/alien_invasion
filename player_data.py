"""玩家数据持久化：金币、道具、技能等级、认证信息（加密存储）"""

import sys
import os
from pathlib import Path
from file_crypto import encrypt_json, decrypt_json


_DEFAULTS = {
    'coins': 0,
    'items': {'magnet': 0, 'shield': 0},
    'skills': {'speed': 0, 'ammo': 0, 'vitality': 0},
    'token': '',
    'username': '',
    'email': '',
}


class PlayerData:
    """读写 player_data.json，管理跨会话持久化数据"""

    def __init__(self, file_path=None):
        if file_path is None:
            saves_dir = Path(os.path.dirname(sys.argv[0])) / "saves"
            saves_dir.mkdir(exist_ok=True)
            file_path = str(saves_dir / "player_data.dat")
        self.file_path = Path(file_path)

    def load(self):
        data = decrypt_json(self.file_path)
        if data is None:
            return dict(_DEFAULTS)
        return {
            'coins': data.get('coins', 0),
            'items': data.get('items', {'magnet': 0, 'shield': 0}),
            'skills': data.get('skills', {'speed': 0, 'ammo': 0, 'vitality': 0}),
            'token': data.get('token', ''),
            'username': data.get('username', ''),
            'email': data.get('email', ''),
        }

    def save(self, coins, items, skills, token='', username='', email=''):
        data = {'coins': coins, 'items': items, 'skills': skills}
        existing = self.load()
        if token:
            data['token'] = token
            data['username'] = username
        else:
            data['token'] = existing.get('token', '')
            data['username'] = existing.get('username', '')
        if email:
            data['email'] = email
        else:
            data['email'] = existing.get('email', '')
        encrypt_json(data, self.file_path)

    def save_auth(self, token: str, username: str):
        existing = self.load()
        self.save(
            existing['coins'], existing['items'], existing['skills'],
            token=token, username=username, email=existing['email'],
        )

    def save_email(self, email: str):
        existing = self.load()
        self.save(
            existing['coins'], existing['items'], existing['skills'],
            token=existing['token'], username=existing['username'],
            email=email,
        )

    def get_token(self) -> str:
        return self.load()['token']

    def get_username(self) -> str:
        return self.load()['username']

    def get_email(self) -> str:
        return self.load()['email']

    def is_authenticated(self) -> bool:
        return bool(self.load()['token'])
