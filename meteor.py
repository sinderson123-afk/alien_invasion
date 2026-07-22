"""Meteor obstacle: falls from top, spawns fragments on collision"""

import math
import random
import pygame
from pygame.sprite import Sprite


class Meteor(Sprite):
    """Meteor: random size, angle, speed; shatters into MeteorFragment"""

    def __init__(self, ai_game):
        """Create meteor at random position near screen top"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        screen_rect = ai_game.screen.get_rect()

        # Random size
        self.radius = random.randint(
            self.settings.meteor_size_min, self.settings.meteor_size_max)
        self.hp = self.settings.meteor_hp

        # Meteor texture (pre-rendered)
        self.image = self._build_texture()
        self.rect = self.image.get_rect()

        # Initial position: random x, above screen top
        self.rect.centerx = random.randint(self.radius, screen_rect.width - self.radius)
        self.rect.bottom = random.randint(-60, -10)

        # Float coordinates
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # Random direction (vertical downward +/- 90 degrees = 180-degree fan)
        base_angle = math.radians(90)  # Vertical downward
        deviation = math.radians(random.uniform(
            -self.settings.meteor_angle_range, self.settings.meteor_angle_range))
        angle = base_angle + deviation

        # Random speed
        speed = random.uniform(
            self.settings.meteor_speed_min, self.settings.meteor_speed_max)
        self.velocity_x = math.cos(angle) * speed
        self.velocity_y = math.sin(angle) * speed

        # Rotation speed (visual)
        self.rotation = random.uniform(-2, 2)
        self.angle = random.uniform(0, 360)

    def _build_texture(self):
        """Procedurally generate irregular rock texture"""
        d = self.radius * 2
        surf = pygame.Surface((d + 6, d + 6), pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2

        # Rock base color (random gray/brown)
        r_var = random.randint(-30, 20)
        base_color = (
            max(40, min(180, 120 + r_var)),
            max(30, min(100, 70 + r_var // 2)),
            max(20, min(60, 40 + r_var // 3)),
        )

        # Body: irregular polygon
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

        # Surface texture: highlight spots + dark cracks
        for _ in range(random.randint(2, 4)):
            hx = cx + random.randint(-self.radius // 2, self.radius // 2)
            hy = cy + random.randint(-self.radius // 2, self.radius // 2)
            hr = random.randint(2, max(3, self.radius // 4))
            hl_color = tuple(min(255, c + 40) for c in base_color)
            pygame.draw.circle(surf, hl_color, (hx, hy), hr)

        # Edge dark outline
        if len(points) >= 3:
            pygame.draw.polygon(surf, (30, 25, 20), points, width=2)

        return surf

    def take_damage(self, amount):
        """Take damage, return True if destroyed"""
        self.hp -= amount
        return self.hp <= 0

    def update(self):
        """Move by velocity, self-destruct off screen"""
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        # Rotation (visual only)
        self.angle = (self.angle + self.rotation) % 360

        # Remove when past screen bottom
        screen_h = self.screen.get_rect().height
        if self.rect.top > screen_h + 50:
            self.kill()


class MeteorFragment(Sprite):
    """Meteor fragment: spawns when meteor shatters, still damaging, has lifetime"""

    def __init__(self, ai_game, x, y):
        """Create fragment at position with random scatter direction"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.hp = self.settings.meteor_fragment_hp
        self.lifetime = self.settings.meteor_fragment_lifetime

        # Random small size
        self.radius = random.randint(4, 10)

        # Texture
        self.image = self._build_fragment_texture()
        self.rect = self.image.get_rect(center=(x, y))

        # Float coordinates
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # Random scatter direction and speed
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 4.5)
        self.velocity_x = math.cos(angle) * speed
        self.velocity_y = math.sin(angle) * speed

    def _build_fragment_texture(self):
        """Draw small fragment texture"""
        d = self.radius * 2 + 2
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        cx, cy = d // 2, d // 2

        # Random gray tone
        rv = random.randint(-30, 30)
        color = (
            max(50, min(200, 130 + rv)),
            max(30, min(110, 80 + rv // 2)),
            max(10, min(70, 50 + rv // 3)),
        )
        pygame.draw.circle(surf, color, (cx, cy), self.radius)
        # Edge dark
        pygame.draw.circle(surf, (40, 35, 25), (cx, cy), self.radius, width=1)

        return surf

    def update(self):
        """Move fragment, decrement lifetime"""
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
