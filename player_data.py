"""玩家数据持久化：金币、道具、技能等级"""

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
            }
        except (OSError, ValueError):
            return {
                'coins': 0,
                'items': {'magnet': 0, 'shield': 0},
                'skills': {'speed': 0, 'ammo': 0, 'vitality': 0},
            }

    def save(self, coins, items, skills):
        """保存玩家数据"""
        data = {
            'coins': coins,
            'items': items,
            'skills': skills,
        }
        try:
            self.file_path.write_text(json.dumps(data))
        except OSError:
            pass  # 写入失败不影响游戏运行
