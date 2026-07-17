import pygame
import random
from pygame.sprite import Sprite

class Particle(Sprite):
    """表示单个爆炸粒子的类"""

    def __init__(self, ai_game, x, y):
        """在指定的位置创建一个粒子"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings

        # 随机大小（半径）
        self.size = random.randint(
            self.settings.particle_min_size,
            self.settings.particle_max_size
        )
        self.base_color = random.choice(self.settings.particle_colors)

        # 创建带透明通道的 Surface（直径 x 直径）
        diameter = self.size * 2
        self.image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))

        # 存储浮点数坐标
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # 随机速度和方向
        angle = random.uniform(0, 2 * 3.14159)
        speed = random.uniform(1.5, 4.0)
        self.velocity_x = speed * pygame.math.Vector2(1, 0).rotate_rad(angle).x
        self.velocity_y = speed * pygame.math.Vector2(1, 0).rotate_rad(angle).y

        # 生命周期
        self.lifetime = self.settings.particle_lifetime
        self.max_lifetime = self.lifetime

        # 初始绘制
        self._redraw()

    def _redraw(self):
        """根据当前透明度重新绘制粒子（逐帧重绘，避免 set_alpha 兼容性问题）"""
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        if alpha < 0:
            alpha = 0
        faded_color = (*self.base_color, alpha)
        self.image.fill((0, 0, 0, 0))  # 清空为透明
        pygame.draw.circle(
            self.image, faded_color,
            (self.size, self.size), self.size
        )

    def update(self):
        """更新粒子的位置和透明度"""
        # 应用重力和速度
        self.velocity_y += self.settings.particle_gravity
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        # 衰减生命周期
        self.lifetime -= 1

        # 重绘以更新透明度
        self._redraw()

        # 生命周期结束，移除粒子
        if self.lifetime <= 0:
            self.kill()
