import pygame
from pygame.sprite import Sprite


class BossBullet(Sprite):
    """Red circular bullet fired by boss"""

    def __init__(self, ai_game, x, y):
        """Create a boss bullet at specified position"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings

        # Red circle
        radius = self.settings.boss_bullet_radius
        diameter = radius * 2
        self.image = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.settings.boss_bullet_color,
                           (radius, radius), radius)
        self.rect = self.image.get_rect(center=(x, y))

        # Float coordinates
        self.y = float(self.rect.y)

    def update(self):
        """Move downward"""
        self.y += self.settings.boss_bullet_speed
        self.rect.y = int(self.y)
