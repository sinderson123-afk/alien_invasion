"""玩家数据持久化：金币、道具、技能等级、认证信息"""

import json
from pathlib import Path


class PlayerData:
    """读写 player_data.json，管理跨会话持久化数据"""

    def __init__(self, file_path="player_data.json"):
        self.file_path = Path(file_path)

    def load(self):
        """加载玩家数据，文件不存在时返回默认值"""
        try:
            text = self.file_path.read_text()
            data = json.loads(text)
            return {
                'coins': data.get('coins', 0),
                'items': data.get('items', {'magnet': 0, 'shield': 0}),
                'skills': data.get('skills', {'speed': 0, 'ammo': 0, 'vitality': 0}),
                'token': data.get('token', ''),
                'username': data.get('username', ''),
                'email': data.get('email', ''),
            }
        except (OSError, ValueError):
            return {
                'coins': 0,
                'items': {'magnet': 0, 'shield': 0},
                'skills': {'speed': 0, 'ammo': 0, 'vitality': 0},
                'token': '',
                'username': '',
                'email': '',
            }

    def save(self, coins, items, skills, token='', username='', email=''):
        data = {'coins': coins, 'items': items, 'skills': skills}
        if token:
            data['token'] = token
            data['username'] = username
        if email:
            data['email'] = email
        try:
            existing = {}
            if self.file_path.exists():
                try:
                    existing = json.loads(self.file_path.read_text())
                except (OSError, ValueError):
                    pass
            if not token:
                data['token'] = existing.get('token', '')
                data['username'] = existing.get('username', '')
            if not email:
                data['email'] = existing.get('email', '')
            self.file_path.write_text(json.dumps(data))
        except OSError:
            pass

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
