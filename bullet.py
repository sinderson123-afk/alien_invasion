"""Bullet module: green energy bullet with gradient glow texture"""

import pygame
from pygame.sprite import Sprite


class Bullet(Sprite):
    """Class for ship bullets (green energy bullet material)"""

    def __init__(self, ai_game):
        """Create bullet at ship current position"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.color = self.settings.bullet_color

        # Bullet size
        self.rect = pygame.Rect(
            0, 0, self.settings.bullet_width, self.settings.bullet_height)
        self.rect.midtop = ai_game.ship.rect.midtop

        # Store bullet position as float
        self.y = float(self.rect.y)

        # Pre-rendered bullet texture (with gradient and glow)
        self.image = self._build_texture()

    def _build_texture(self):
        """Build green energy texture: capsule shape + gradient + white core + outer glow"""
        w = self.settings.bullet_width
        h = self.settings.bullet_height
        # Enlarge canvas for glow
        pad = 4
        surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

        cx = (w + pad * 2) // 2
        radius = w // 2

        # 1. Outer glow (soft spread)
        glow_colors = [
            (0, 255, 80, 25),    # Outermost: very faint green
            (0, 255, 80, 50),    # Mid layer
            (0, 255, 80, 80),    # Inner layer
        ]
        for i, (r, g, b, a) in enumerate(glow_colors):
            glow_r = radius + (3 - i) * 2
            glow_rect = pygame.Rect(
                cx - glow_r, pad - (3 - i),
                glow_r * 2, h + (3 - i) * 2)
            pygame.draw.rect(surf, (r, g, b, a), glow_rect,
                             border_radius=glow_r)

        # 2. Main capsule (vertical gradient: bright bottom -> dimmer top)
        for py_offset in range(h):
            # Bright to dim from bottom to top (simulates energy emission from tail)
            ratio = py_offset / h
            brightness = 1.0 - ratio * 0.25  # Top slightly dimmer 75%
            r = int(max(0, min(255, self.color[0] * brightness)))
            g = int(max(0, min(255, self.color[1] * brightness)))
            b = int(max(0, min(255, self.color[2] * brightness)))

            # Horizontal: bright center, dark edges
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

        # 3. White core line (energy beam center)
        core_width = max(1, w // 2)
        core_rect = pygame.Rect(cx - core_width // 2, pad, core_width, h)
        pygame.draw.rect(surf, (200, 255, 220, 180), core_rect,
                         border_radius=core_width // 2)

        # 4. Tip highlight (bullet point)
        tip_y = pad + 2
        tip_rect = pygame.Rect(cx - 1, tip_y, 2, h // 4)
        pygame.draw.rect(surf, (255, 255, 255, 220), tip_rect, border_radius=1)

        return surf

    def update(self):
        """Move bullet upward"""
        self.y -= self.settings.bullet_speed
        self.rect.y = self.y

    def draw_bullet(self):
        """Draw bullet texture on screen"""
        # Texture offset (canvas larger than rect, center draw)
        offset_x = (self.image.get_width() - self.rect.width) // 2
        offset_y = (self.image.get_height() - self.rect.height) // 2
        self.screen.blit(self.image,
                         (self.rect.x - offset_x, self.rect.y - offset_y))
