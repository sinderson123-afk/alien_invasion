import json
from enum import Enum, auto
from pathlib import Path
from player_data import PlayerData
from file_crypto import encrypt_json, decrypt_json


class GameState(Enum):
    """游戏主状态机，替代原有的 game_active 布尔值和 shop_open 标志"""
    LOGIN = auto()         # 登录/注册画面
    MENU = auto()          # 开始画面
    PLAYING = auto()       # 游戏中
    PAUSED = auto()        # 暂停
    SHOP = auto()          # 商店界面
    TUTORIAL = auto()      # 教程画面
    LEADERBOARD = auto()   # 排行榜


class GameStats:
    """跟踪游戏的统计信息"""

    def __init__(self,ai_game):
        """初始化统计信息"""
        self.settings = ai_game.settings

        # 加载持久化数据（金币、道具、技能）
        self.player_data = PlayerData()
        saved = self.player_data.load()
        self.coins = saved['coins']
        self.items = saved['items']
        self.skills = saved['skills']

        self.reset_stats()

        # 从文件中读取历史最高分
        self.high_score = self._load_high_score()

    def reset_stats(self):
        """初始化游戏在运行期间可能变化的统计信息"""
        self.ship_left = self.settings.ship_limit + self.skills['vitality']
        self.score = 0
        self.kills = 0                     # 累计击杀数（用于计算关卡）
        # 导弹库存，以及已按分数发放的导弹总数（用于判断是否跨过新的奖励门槛）
        self.missiles = 0
        self.missiles_awarded = 0
        # coins/items/skills 是持久化数据，不在每局重置

    def save_player_data(self):
        """保存持久化数据"""
        self.player_data.save(self.coins, self.items, self.skills)

    @property
    def level(self):
        """根据累计击杀数自动计算当前关卡"""
        return self.kills // self.settings.kills_per_level + 1

    def _load_high_score(self):
        """从文件中读取最高分，文件不存在或损坏时返回0"""
        data = decrypt_json(Path(self.settings.high_score_file))
        if data is None:
            return 0
        return data.get('high_score', 0)

    def save_high_score(self):
        """将最高分写入加密文件"""
        encrypt_json({'high_score': self.high_score}, Path(self.settings.high_score_file))
