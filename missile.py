import math
import pygame
from pygame.sprite import Sprite


def create_missile_image(width=10, height=26):
    """Draw upward-facing missile image (shared with scoreboard icon)"""
    image = pygame.Surface((width, height), pygame.SRCALPHA)
    body_color = (90, 90, 100)
    nose_color = (200, 60, 60)
    flame_color = (255, 160, 0)

    nose_height = height // 3
    flame_height = height // 6
    margin = max(1, width // 5)
    body_rect = pygame.Rect(margin, nose_height,
                            width - 2 * margin, height - nose_height - flame_height)
    # Body
    pygame.draw.rect(image, body_color, body_rect)
    # Warhead
    pygame.draw.polygon(image, nose_color,
                        [(body_rect.left, nose_height), (body_rect.right, nose_height),
                         (width // 2, 0)])
    # Exhaust
    pygame.draw.polygon(image, flame_color,
                        [(body_rect.left, body_rect.bottom), (body_rect.right, body_rect.bottom),
                         (width // 2, height - 1)])
    return image


class Missile(Sprite):
    """Homing missile tracking nearest alien with AoE damage"""

    def __init__(self, ai_game):
        """Create an upward-flying missile at ship top"""
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.aliens = ai_game.aliens
        self.ai_game = ai_game

        self.base_image = create_missile_image()
        self.image = self.base_image
        self.rect = self.image.get_rect(midbottom=ai_game.ship.rect.midtop)

        # Store missile center and velocity as floats
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.velocity = pygame.math.Vector2(0, -self.settings.missile_speed)

    def update(self):
        """Steer toward nearest alien with limited turn rate"""
        target = self._find_nearest_alien()
        if target:
            desired = pygame.math.Vector2(target.rect.center) - pygame.math.Vector2(self.x, self.y)
            if desired.length_squared() > 0:
                desired.scale_to_length(self.settings.missile_speed)
                # Limited steering: gradually turn toward target each frame for arc path
                self.velocity += (desired - self.velocity) * self.settings.missile_turn_rate
                if self.velocity.length_squared() > 0:
                    self.velocity.scale_to_length(self.settings.missile_speed)

        self.x += self.velocity.x
        self.y += self.velocity.y

        # Rotate missile image based on flight direction
        angle = math.degrees(math.atan2(-self.velocity.y, self.velocity.x)) - 90
        self.image = pygame.transform.rotate(self.base_image, angle)
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def _find_nearest_alien(self):
        """Return nearest target (alien or boss), or None if no targets"""
        position = pygame.math.Vector2(self.x, self.y)
        targets = list(self.aliens.sprites())

        boss = getattr(self, 'ai_game', None)
        if boss is not None:
            boss = boss.boss
        if boss is not None and boss.hp > 0:
            targets.append(boss)

        if not targets:
            return None
        return min(targets,
                   key=lambda t: position.distance_squared_to(t.rect.center))
