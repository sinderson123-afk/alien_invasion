"""Explosion particle system: customizable size/speed/color"""

import math
import random
import pygame
from pygame.sprite import Sprite


class Particle(Sprite):
    """Single explosion particle class (multipliers and custom colors)"""

    def __init__(self, ai_game, x, y,
                 size_mult=1.0,
                 speed_mult=1.0,
                 lifetime_mult=1.0,
                 colors=None):
        """
        Create a particle at the specified position.
        Args:
            size_mult: Size multiplier (default 1.0)
            speed_mult: Speed multiplier (default 1.0)
            lifetime_mult: Lifetime multiplier (default 1.0)
            colors: Custom color list, None uses settings default
        """
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings

        # Colors
        palette = colors if colors else self.settings.particle_colors
        self.base_color = random.choice(palette)

        # Random size (with multiplier)
        base_min = self.settings.particle_min_size
        base_max = self.settings.particle_max_size
        self.size = int(random.randint(base_min, base_max) * size_mult)
        if self.size < 1:
            self.size = 1

        # Create Surface with alpha channel
        diameter = self.size * 2
        self.image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))

        # Store float coordinates
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # Random speed and direction (with multiplier)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 4.0) * speed_mult
        self.velocity_x = speed * pygame.math.Vector2(1, 0).rotate_rad(angle).x
        self.velocity_y = speed * pygame.math.Vector2(1, 0).rotate_rad(angle).y

        # Lifetime (with multiplier)
        self.lifetime = int(self.settings.particle_lifetime * lifetime_mult)
        self.max_lifetime = self.lifetime

        # Initial draw
        self._redraw()

    def _redraw(self):
        """Redraw particle based on current alpha (per-frame, avoids set_alpha)"""
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        if alpha < 0:
            alpha = 0
        faded_color = (*self.base_color, alpha)
        self.image.fill((0, 0, 0, 0))  # Clear to transparent
        pygame.draw.circle(
            self.image, faded_color,
            (self.size, self.size), self.size
        )

    def update(self):
        """Update particle position and transparency"""
        # Apply gravity and velocity
        self.velocity_y += self.settings.particle_gravity
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        # Decay lifetime
        self.lifetime -= 1

        # Redraw to update transparency
        self._redraw()

        # Lifetime ended, remove particle
        if self.lifetime <= 0:
            self.kill()
