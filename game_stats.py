import json
from enum import Enum, auto
from pathlib import Path
from player_data import PlayerData
from file_crypto import encrypt_json, decrypt_json


class GameState(Enum):
    """Game state machine, replacing old game_active bool and shop_open flag"""
    LOGIN = auto()         # Login/Registration screen
    MENU = auto()          # Start screen
    PLAYING = auto()       # Playing
    PAUSED = auto()        # Paused
    SHOP = auto()          # Shop screen
    TUTORIAL = auto()      # Tutorial screen
    LEADERBOARD = auto()   # Leaderboard


class GameStats:
    """Track game statistics"""

    def __init__(self,ai_game):
        """Initialize statistics"""
        self.settings = ai_game.settings

        # Load persistent data (coins, items, skills, armor)
        self.player_data = PlayerData()
        saved = self.player_data.load()
        self.coins = saved['coins']
        self.items = saved['items']
        self.skills = saved['skills']
        self.armor_tier = saved['armor']

        self.reset_stats()

        # Load high score from file
        self.high_score = self._load_high_score()

    def reset_stats(self):
        """Initialize stats that change during gameplay"""
        self.max_hp = self._calc_max_hp()
        self.ship_hp = self.max_hp
        self.score = 0
        self.kills = 0                     # Cumulative kills (for level calculation)
        # Missile stock and total awarded by score (to check new thresholds)
        self.missiles = 0
        self.missiles_awarded = 0
        # coins/items/skills/armor are persistent, not reset per session

    def _calc_max_hp(self):
        """Calculate max HP: base HP * multiplier + vitality skill bonus"""
        return (self.settings.ship_limit + self.skills['vitality']) * self.settings.ship_hp_multiplier

    def save_player_data(self):
        """Save persistent data"""
        self.player_data.save(self.coins, self.items, self.skills, armor=self.armor_tier)

    @property
    def level(self):
        """Calculate current level from cumulative kills"""
        return self.kills // self.settings.kills_per_level + 1

    def _load_high_score(self):
        """Load high score from file, return 0 if missing or corrupt"""
        data = decrypt_json(Path(self.settings.high_score_file))
        if data is None:
            return 0
        return data.get('high_score', 0)

    def save_high_score(self):
        """Write high score to encrypted file"""
        encrypt_json({'high_score': self.high_score}, Path(self.settings.high_score_file))
