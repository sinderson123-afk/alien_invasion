import pygame
from pygame.sprite import Sprite


class BossBullet(Sprite):
    """Boss 发射的红色圆形子弹"""

    def __init__(self, ai_game, x, y):
        """在指定位置创建一颗 Boss 子弹"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings

        # 红色圆形
        radius = self.settings.boss_bullet_radius
        diameter = radius * 2
        self.image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.settings.boss_bullet_color,
                           (radius, radius), radius)
        self.rect = self.image.get_rect(center=(x, y))

        # 浮点坐标
        self.y = float(self.rect.y)

    def update(self):
        """向下移动"""
        self.y += self.settings.boss_bullet_speed
        self.rect.y = int(self.y)
