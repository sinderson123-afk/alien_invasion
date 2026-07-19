import pygame
import random
from pygame.sprite import Sprite


class Coin(Sprite):
    """金币：从外星人死亡位置掉落，悬停在屏幕底部，超时闪烁后消失"""

    def __init__(self, ai_game, x, y):
        """在指定位置创建一枚金币"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings

        # 金色圆形
        radius = self.settings.coin_radius
        diameter = radius * 2
        self.image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 215, 0), (radius, radius), radius)
        # 高光
        pygame.draw.circle(self.image, (255, 255, 200),
                           (radius - 2, radius - 2), radius // 3)
        self.rect = self.image.get_rect(center=(x, y))

        self.y = float(self.rect.y)

        # 状态：falling → hovering → flashing → kill()
        self.state = 'falling'
        self.hover_timer = self.settings.coin_hover_duration
        self.flash_timer = self.settings.coin_flash_duration
        self.hover_y = self.settings.screen_height - self.settings.coin_hover_y_margin

    def update(self):
        """根据状态更新位置和外观"""
        if self.state == 'falling':
            self.y += self.settings.coin_fall_speed
            if self.y >= self.hover_y:
                self.y = self.hover_y
                self.state = 'hovering'
        elif self.state == 'hovering':
            self.hover_timer -= 1
            if self.hover_timer <= 0:
                self.state = 'flashing'
        elif self.state == 'flashing':
            self.flash_timer -= 1
            # 闪烁：每6帧切换可见性
            if (self.flash_timer // 6) % 2 == 0:
                self.image.set_alpha(60)
            else:
                self.image.set_alpha(255)
            if self.flash_timer <= 0:
                self.kill()
                return

        self.rect.y = int(self.y)
