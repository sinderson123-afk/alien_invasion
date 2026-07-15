import pygame
from pygame.sprite import Sprite

class Alien(Sprite):
    """表示外星人的类"""

    def __init__(self,ai_game):
        """初始化外星人并设置其起始位置"""
        super().__init__()
        self.screen = ai_game.screen

        # 加载外星人图像并缩放
        self.image = pygame.image.load('images/alien.bmp')
        original_width, original_height = self.image.get_size()
        # 将外星人宽度缩放到屏幕宽度的 6%
        new_width = int(ai_game.screen.get_rect().width * 0.06)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # 每个外星人最初都在屏幕的左上角附近
        self.rect.x = self.rect.width
        self.rect.y = self.rect.height

        # 存储外星人的精确水平位置
        self.x = float(self.rect.x)
