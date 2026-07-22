"""子弹模块：绿色能量弹，带渐变发光纹理"""

import pygame
from pygame.sprite import Sprite


class Bullet(Sprite):
    """管理飞船发射子弹的类（绿色能量弹材质）"""

    def __init__(self, ai_game):
        """在飞船的当前位置创建一个子弹对象"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.color = self.settings.bullet_color

        # 子弹尺寸
        self.rect = pygame.Rect(
            0, 0, self.settings.bullet_width, self.settings.bullet_height)
        self.rect.midtop = ai_game.ship.rect.midtop

        # 储存用浮点数表示的子弹位置
        self.y = float(self.rect.y)

        # 预渲染子弹纹理（带渐变和光晕）
        self.image = self._build_texture()

    def _build_texture(self):
        """构建绿色能量弹纹理：胶囊形状 + 渐变 + 白色核心 + 外发光"""
        w = self.settings.bullet_width
        h = self.settings.bullet_height
        # 加大画布以容纳光晕
        pad = 4
        surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

        cx = (w + pad * 2) // 2
        radius = w // 2

        # 1. 外发光（柔光扩散）
        glow_colors = [
            (0, 255, 80, 25),    # 最外层：极淡绿色
            (0, 255, 80, 50),    # 中层
            (0, 255, 80, 80),    # 内层
        ]
        for i, (r, g, b, a) in enumerate(glow_colors):
            glow_r = radius + (3 - i) * 2
            glow_rect = pygame.Rect(
                cx - glow_r, pad - (3 - i),
                glow_r * 2, h + (3 - i) * 2)
            pygame.draw.rect(surf, (r, g, b, a), glow_rect,
                             border_radius=glow_r)

        # 2. 主体胶囊（垂直方向渐变：底部亮 → 顶部稍暗）
        for py_offset in range(h):
            # 从底部到顶部由亮变暗（模拟能量从尾部喷出）
            ratio = py_offset / h
            brightness = 1.0 - ratio * 0.25  # 顶部稍暗 75%
            r = int(max(0, min(255, self.color[0] * brightness)))
            g = int(max(0, min(255, self.color[1] * brightness)))
            b = int(max(0, min(255, self.color[2] * brightness)))

            # 水平方向：中心亮、边缘暗
            for px in range(w):
                dist_from_center = abs(px - w // 2)
                edge_falloff = 1.0 - (dist_from_center / (w // 2)) * 0.35
                if edge_falloff < 0:
                    continue

                er = int(r * edge_falloff)
                eg = int(g * edge_falloff)
                eb = int(b * edge_falloff)
                alpha = int(255 * edge_falloff)
                surf.set_at((px + pad, py_offset + pad), (er, eg, eb, alpha))

        # 3. 白色核心线（能量束中心）
        core_width = max(1, w // 2)
        core_rect = pygame.Rect(cx - core_width // 2, pad, core_width, h)
        pygame.draw.rect(surf, (200, 255, 220, 180), core_rect,
                         border_radius=core_width // 2)

        # 4. 顶部亮点（子弹尖端）
        tip_y = pad + 2
        tip_rect = pygame.Rect(cx - 1, tip_y, 2, h // 4)
        pygame.draw.rect(surf, (255, 255, 255, 220), tip_rect, border_radius=1)

        return surf

    def update(self):
        """向上移动子弹"""
        self.y -= self.settings.bullet_speed
        self.rect.y = self.y

    def draw_bullet(self):
        """在屏幕上绘制子弹纹理"""
        # 贴图偏移（因为画布比 rect 大，居中绘制）
        offset_x = (self.image.get_width() - self.rect.width) // 2
        offset_y = (self.image.get_height() - self.rect.height) // 2
        self.screen.blit(self.image,
                         (self.rect.x - offset_x, self.rect.y - offset_y))
