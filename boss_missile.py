"""Hostile homing missile fired by the Space boss (low tracking)."""
import math
import pygame
from pygame.sprite import Sprite
from missile import create_missile_image


class BossMissile(Sprite):
    """Downward-flying missile that slowly homes toward the ship."""

    def __init__(self, ai_game, x, y):
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.ai_game = ai_game

        # Downward-pointing missile (player missile rotated 180 deg)
        self.base_image = pygame.transform.rotate(create_missile_image(), 180)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=(x, y))

        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.velocity = pygame.math.Vector2(0, self.settings.boss_missile_speed)

    def update(self):
        """Slowly steer toward the ship (low turn rate)."""
        ship_pos = pygame.math.Vector2(self.ai_game.ship.rect.center)
        desired = ship_pos - pygame.math.Vector2(self.x, self.y)
        if desired.length_squared() > 0:
            desired.scale_to_length(self.settings.boss_missile_speed)
            self.velocity += (desired - self.velocity) * self.settings.boss_missile_turn_rate
            if self.velocity.length_squared() > 0:
                self.velocity.scale_to_length(self.settings.boss_missile_speed)

        self.x += self.velocity.x
        self.y += self.velocity.y

        angle = math.degrees(math.atan2(-self.velocity.y, self.velocity.x)) - 90
        self.image = pygame.transform.rotate(self.base_image, angle)
        self.rect = self.image.get_rect(center=(self.x, self.y))
