class GameStats:
    """跟踪游戏的统计信息"""

    def __init__(self,ai_game):
        """初始化统计信息"""
        self.settings = ai_game.settings
        self.reset_stats()

    def reset_stats(self):
        """初始化游戏在运行期间可能变化的统计信息"""
        self.ship_left = self.settings.ship_limit