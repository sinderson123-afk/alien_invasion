import random
import pygame
from pygame.sprite import Sprite
from settings import resource_path

class Alien(Sprite):
    """Alien class: gather toward ship, slowly descend, dive on schedule"""

    def __init__(self,ai_game):
        """Initialize alien and set starting position"""
        super().__init__()
        self.ai_game = ai_game            # For accessing sprite groups like meteors
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        # Store ship reference for gathering target and dive lock-on
        self.ship = ai_game.ship
        self.stats = ai_game.stats

        # Calculate HP based on current level
        self.max_hp = self.settings.alien_base_hp + (
            self.stats.level - 1) * self.settings.alien_hp_per_level
        self.hp = self.max_hp

        # Load alien image and scale
        self.image = pygame.image.load(resource_path('resource/images/alien.bmp'))
        original_width, original_height = self.image.get_size()
        # Scale alien width to 6% of screen width
        new_width = int(ai_game.screen.get_rect().width * 0.06)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # Each alien starts near top-left of screen
        self.rect.x = self.rect.width
        self.rect.y = self.rect.height

        # Store alien exact position
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # State machine: 'swarm' (gather descend) / 'dive' / 'climb'
        self.state = 'swarm'
        # Personal gather offset: target = ship x + offset, avoids stacking
        self.gather_offset = random.uniform(-self.settings.alien_gather_offset_range,
                                            self.settings.alien_gather_offset_range)
        # Cruise altitude for climb return
        self.cruise_y = random.uniform(self.settings.alien_cruise_y_min,
                                       self.settings.alien_cruise_y_max)
        # Dive velocity (locked at windup end) and windup countdown
        self.dive_velocity = None
        self.windup = 0

        # Hit flash timer (frames)
        self.flash_frames = 0

    def update(self):
        """Update position by current state and handle flash effect"""
        # Flash: toggle alpha every 6 frames
        if self.flash_frames > 0:
            self.flash_frames -= 1
            if (self.flash_frames // 6) % 2 == 0:
                self.image.set_alpha(60)
            else:
                self.image.set_alpha(255)
        else:
            self.image.set_alpha(255)

        if self.state == 'swarm':
            self._update_swarm()
        elif self.state == 'dive':
            self._update_dive()
        elif self.state == 'climb':
            self._update_climb()

        self.rect.x = self.x
        self.rect.y = self.y

    def take_damage(self, amount):
        """Take damage, return True if alien dies"""
        self.hp -= amount
        if self.hp <= 0:
            self.kill()
            return True
        return False

    def draw_hp_bar(self):
        """Draw HP bar above alien (only when damaged)"""
        if self.hp >= self.max_hp:
            return

        bar_width = self.settings.hp_bar_width
        bar_height = self.settings.hp_bar_height
        # Center HP bar above alien top
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.top - self.settings.hp_bar_offset_y

        # Background (dark gray)
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (40, 40, 40), bg_rect)

        # Current HP (green->yellow->red gradient)
        ratio = self.hp / self.max_hp
        if ratio > 0.5:
            color = (int(255 * (1 - ratio) * 2), 255, 0)   # green->yellow
        else:
            color = (255, int(255 * ratio * 2), 0)           # yellow->red
        hp_rect = pygame.Rect(bar_x, bar_y, int(bar_width * ratio), bar_height)
        pygame.draw.rect(self.screen, color, hp_rect)

    def start_dive(self):
        """Enter dive windup: freeze for N frames, then lock on ship and dive"""
        self.state = 'dive'
        self.windup = self.settings.alien_dive_windup
        self.dive_velocity = None

    def _update_swarm(self):
        """Move horizontally toward personal offset above ship, avoid meteors, descend slowly"""
        speed = self.settings.alien_speed
        target_x = self.ship.rect.centerx + self.gather_offset - self.rect.width / 2
        dx = target_x - self.x

        # ---- Meteor avoidance ----
        threat_detected = False
        avoid_force = 0.0
        safety_margin = self.rect.width * 2  # Trajectory collision safety distance
        ax, ay = self.rect.centerx, self.rect.centery

        for meteor in self.ai_game.meteors:
            mx, my = meteor.rect.centerx, meteor.rect.centery

            # Only consider meteors above (potential collision), ignore past ones
            if my >= ay:
                continue

            # Predict meteor x position when it reaches this alien's height
            dy = ay - my
            if meteor.velocity_y <= 0:
                continue  # Meteor not falling, skip
            time_to_reach = dy / meteor.velocity_y
            predicted_x = mx + meteor.velocity_x * time_to_reach

            # Predicted position within safety margin -> threat
            if abs(predicted_x - ax) < safety_margin:
                threat_detected = True
                # Strong evasion: escape laterally from meteor path
                escape_dir = 1.0 if (predicted_x - ax) >= 0 else -1.0
                avoid_force += escape_dir * speed * 1.5
            else:
                # Not on path but still near -> weak repulsion
                dist_sq = (mx - ax) ** 2 + (my - ay) ** 2
                if dist_sq < self.settings.meteor_avoid_radius ** 2 and dist_sq > 0:
                    dist = dist_sq ** 0.5
                    force = (1.0 - dist / self.settings.meteor_avoid_radius) * 0.5
                    avoid_force += (ax - mx) / dist * force * speed

        # Horizontal: evade when threatened (gather weight drops to 0.2), else normal gather
        if threat_detected:
            self.x += max(-speed * 1.5, min(speed * 1.5, dx * 0.2 + avoid_force))
        else:
            self.x += max(-speed, min(speed, dx + avoid_force))

        # Clamp within screen
        self.x = max(0.0, min(self.x, self.settings.screen_width - self.rect.width))
        # Swarm pressure: continuous slow descent
        self.y += speed * self.settings.alien_descend_factor

    def _update_dive(self):
        """Windup freeze, then dive along locked direction, climb after pull-up line"""
        if self.windup > 0:
            self.windup -= 1
            if self.windup == 0:
                # Lock ship position at windup end, giving player dodge window
                desired = (pygame.math.Vector2(self.ship.rect.center)
                           - pygame.math.Vector2(self.rect.center))
                if desired.length_squared() == 0:
                    desired = pygame.math.Vector2(0, 1)
                self.dive_velocity = desired.normalize() * (
                    self.settings.alien_speed * self.settings.alien_dive_speed_factor)
            return

        self.x += self.dive_velocity.x
        self.y += self.dive_velocity.y
        # Clamp within screen to prevent dives from overshooting bottom
        self.y = min(self.y, self.settings.screen_height - self.rect.height)

        # Reach pull-up line: switch to climb, re-roll cruise height
        pullup_y = self.settings.screen_height - self.settings.alien_pullup_margin
        if self.y + self.rect.height >= pullup_y:
            self.state = 'climb'
            self.cruise_y = random.uniform(self.settings.alien_cruise_y_min,
                                           self.settings.alien_cruise_y_max)

    def _update_climb(self):
        """Vertical climb, rejoin swarm at cruise altitude"""
        self.y -= self.settings.alien_speed * self.settings.alien_climb_factor
        if self.y <= self.cruise_y:
            self.state = 'swarm'
            # Re-roll gather offset to avoid stacking after multiple dives
            self.gather_offset = random.uniform(-self.settings.alien_gather_offset_range,
                                                self.settings.alien_gather_offset_range)
