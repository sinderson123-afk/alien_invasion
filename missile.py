import math
import pygame
from pygame.sprite import Sprite


def create_missile_image(width=10, height=26):
    """绘制一枚竖直向上的导弹图像（导弹本体与记分牌图标共用）"""
    image = pygame.Surface((width, height), pygame.SRCALPHA)
    body_color = (90, 90, 100)
    nose_color = (200, 60, 60)
    flame_color = (255, 160, 0)

    nose_height = height // 3
    flame_height = height // 6
    margin = max(1, width // 5)
    body_rect = pygame.Rect(margin, nose_height,
                            width - 2 * margin, height - nose_height - flame_height)
    # 弹体
    pygame.draw.rect(image, body_color, body_rect)
    # 弹头
    pygame.draw.polygon(image, nose_color,
                        [(body_rect.left, nose_height), (body_rect.right, nose_height),
                         (width // 2, 0)])
    # 尾焰
    pygame.draw.polygon(image, flame_color,
                        [(body_rect.left, body_rect.bottom), (body_rect.right, body_rect.bottom),
                         (width // 2, height - 1)])
    return image


class Missile(Sprite):
    """追踪最近的外星人并造成范围伤害的导弹"""

    def __init__(self, ai_game):
        """在飞船顶部创建一枚向上飞行的导弹"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        # 保存外星人编组的引用，以便每帧寻找追踪目标
        self.aliens = ai_game.aliens

        self.base_image = create_missile_image()
        self.image = self.base_image
        self.rect = self.image.get_rect(midbottom=ai_game.ship.rect.midtop)

        # 用浮点数存储导弹的中心位置和速度向量
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.velocity = pygame.math.Vector2(0, -self.settings.missile_speed)

    def update(self):
        """朝最近的外星人有限转向并移动"""
        target = self._find_nearest_alien()
        if target:
            desired = pygame.math.Vector2(target.rect.center) - pygame.math.Vector2(self.x, self.y)
            if desired.length_squared() > 0:
                desired.scale_to_length(self.settings.missile_speed)
                # 有限转向：逐帧向目标方向偏转，形成追踪弧线
                self.velocity += (desired - self.velocity) * self.settings.missile_turn_rate
                if self.velocity.length_squared() > 0:
                    self.velocity.scale_to_length(self.settings.missile_speed)

        self.x += self.velocity.x
        self.y += self.velocity.y

        # 根据飞行方向旋转导弹图像
        angle = math.degrees(math.atan2(-self.velocity.y, self.velocity.x)) - 90
        self.image = pygame.transform.rotate(self.base_image, angle)
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def _find_nearest_alien(self):
        """返回距离导弹最近的外星人，没有外星人时返回None"""
        aliens = self.aliens.sprites()
        if not aliens:
            return None
        position = pygame.math.Vector2(self.x, self.y)
        return min(aliens,
                   key=lambda alien: position.distance_squared_to(alien.rect.center))
