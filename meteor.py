"""陨石障碍物：从屏幕顶部下落，碰撞后碎裂产生碎片"""

import math
import random
import pygame
from pygame.sprite import Sprite


class Meteor(Sprite):
    """陨石：随机尺寸、角度、速度，碰撞后碎裂为 MeteorFragment"""

    def __init__(self, ai_game):
        """在屏幕顶部随机位置生成一个陨石"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        screen_rect = ai_game.screen.get_rect()

        # 随机尺寸
        self.radius = random.randint(
            self.settings.meteor_size_min, self.settings.meteor_size_max)
        self.hp = self.settings.meteor_hp

        # 陨石纹理（预渲染）
        self.image = self._build_texture()
        self.rect = self.image.get_rect()

        # 初始位置：屏幕顶部外随机x
        self.rect.centerx = random.randint(self.radius, screen_rect.width - self.radius)
        self.rect.bottom = random.randint(-60, -10)

        # 浮点坐标
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # 随机方向（垂直向下 ±90° = 总共180°扇形）
        base_angle = math.radians(90)  # 垂直向下
        deviation = math.radians(random.uniform(
            -self.settings.meteor_angle_range, self.settings.meteor_angle_range))
        angle = base_angle + deviation

        # 随机速度
        speed = random.uniform(
            self.settings.meteor_speed_min, self.settings.meteor_speed_max)
        self.velocity_x = math.cos(angle) * speed
        self.velocity_y = math.sin(angle) * speed

        # 旋转速度（视觉效果）
        self.rotation = random.uniform(-2, 2)
        self.angle = random.uniform(0, 360)

    def _build_texture(self):
        """程序化生成不规则岩石纹理"""
        d = self.radius * 2
        surf = pygame.Surface((d + 6, d + 6), pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2

        # 岩石底色（随机灰/棕色系）
        r_var = random.randint(-30, 20)
        base_color = (
            max(40, min(180, 120 + r_var)),
            max(30, min(100, 70 + r_var // 2)),
            max(20, min(60, 40 + r_var // 3)),
        )

        # 主体：不规则多边形
        n_points = random.randint(7, 11)
        points = []
        for i in range(n_points):
            angle = 2 * math.pi * i / n_points + random.uniform(-0.2, 0.2)
            dist = self.radius * random.uniform(0.7, 1.0)
            px = cx + math.cos(angle) * dist
            py = cy + math.sin(angle) * dist
            points.append((px, py))

        if len(points) >= 3:
            pygame.draw.polygon(surf, base_color, points)

        # 表面纹理：几个小高光圆斑 + 暗色裂纹
        for _ in range(random.randint(2, 4)):
            hx = cx + random.randint(-self.radius // 2, self.radius // 2)
            hy = cy + random.randint(-self.radius // 2, self.radius // 2)
            hr = random.randint(2, max(3, self.radius // 4))
            hl_color = tuple(min(255, c + 40) for c in base_color)
            pygame.draw.circle(surf, hl_color, (hx, hy), hr)

        # 边缘暗色描边
        if len(points) >= 3:
            pygame.draw.polygon(surf, (30, 25, 20), points, width=2)

        return surf

    def take_damage(self, amount):
        """受到伤害，返回 True 表示被摧毁"""
        self.hp -= amount
        return self.hp <= 0

    def update(self):
        """按速度和方向移动，超出屏幕则自毁"""
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        # 旋转（纯视觉）
        self.angle = (self.angle + self.rotation) % 360

        # 超出屏幕底部则清除
        screen_h = self.screen.get_rect().height
        if self.rect.top > screen_h + 50:
            self.kill()


class MeteorFragment(Sprite):
    """陨石碎片：主陨石碎裂后产生，仍具伤害性，有生命周期"""

    def __init__(self, ai_game, x, y):
        """在指定位置创建一个碎片，随机散射方向"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.hp = self.settings.meteor_fragment_hp
        self.lifetime = self.settings.meteor_fragment_lifetime

        # 随机小尺寸
        self.radius = random.randint(4, 10)

        # 纹理
        self.image = self._build_fragment_texture()
        self.rect = self.image.get_rect(center=(x, y))

        # 浮点坐标
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # 随机散射方向和速度
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 4.5)
        self.velocity_x = math.cos(angle) * speed
        self.velocity_y = math.sin(angle) * speed

    def _build_fragment_texture(self):
        """绘制小碎块纹理"""
        d = self.radius * 2 + 2
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        cx, cy = d // 2, d // 2

        # 随机灰色调
        rv = random.randint(-30, 30)
        color = (
            max(50, min(200, 130 + rv)),
            max(30, min(110, 80 + rv // 2)),
            max(10, min(70, 50 + rv // 3)),
        )
        pygame.draw.circle(surf, color, (cx, cy), self.radius)
        # 边缘暗
        pygame.draw.circle(surf, (40, 35, 25), (cx, cy), self.radius, width=1)

        return surf

    def update(self):
        """移动碎片，生命周期递减"""
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
