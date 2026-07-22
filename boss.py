import pygame
from pygame.sprite import Sprite
from settings import resource_path


class Boss(Sprite):
    """Boss alien: high HP, horizontal movement, periodic red bullets"""

    def __init__(self, ai_game):
        """Initialize boss and set starting position"""
        super().__init__()
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.stats = ai_game.stats
        # Store boss_bullets group reference for firing
        self.boss_bullets = ai_game.boss_bullets

        # Load boss image and scale
        self.image = pygame.image.load(resource_path('resource/images/boss.bmp'))
        original_width, original_height = self.image.get_size()
        new_width = int(ai_game.screen.get_rect().width * 0.15)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # Initial position: centered at screen top
        self.rect.midtop = ai_game.screen.get_rect().midtop
        self.rect.y = 80
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # Boss HP = current level alien HP x 20
        base_hp = self.settings.alien_base_hp + (
            self.stats.level - 1) * self.settings.alien_hp_per_level
        self.max_hp = base_hp * self.settings.boss_hp_multiplier
        self.hp = self.max_hp

        # Movement direction: 1 right, -1 left
        self.direction = 1
        # Fire timer
        self.fire_timer = self.settings.boss_fire_interval

        # Flash timer (used during ship collision)
        self.flash_frames = 0

        # Death animation state
        self.dying = False              # Whether in death animation
        self.death_timer = 0            # Death animation countdown
        self._death_exploded = False    # Whether explosion triggered (prevent duplicate)

    def update(self):
        """Move horizontally and fire periodically (only flash during death)"""
        if self.dying:
            self._update_death_animation()
            return

        # Flash handling
        if self.flash_frames > 0:
            self.flash_frames -= 1
            if (self.flash_frames // 6) % 2 == 0:
                self.image.set_alpha(60)
            else:
                self.image.set_alpha(255)
        else:
            self.image.set_alpha(255)

        # Horizontal movement
        speed = self.settings.alien_speed * self.settings.boss_speed_factor
        self.x += speed * self.direction
        self.rect.x = int(self.x)

        # Bounce off screen edges (must check after rect update)
        if self.rect.right >= self.settings.screen_width:
            self.direction = -1
        elif self.rect.left <= 0:
            self.direction = 1

        # Fire
        self.fire_timer -= 1
        if self.fire_timer <= 0:
            self._fire()
            self.fire_timer = self.settings.boss_fire_interval

    def _update_death_animation(self):
        """Death animation: hover -> accelerated flash -> final explosion"""
        self.death_timer -= 1

        elapsed = self.settings.boss_death_flash_frames - self.death_timer

        if elapsed < self.settings.boss_death_slow_frames:
            # Hover phase: stay visible, no flash
            self.image.set_alpha(255)
        else:
            # Accelerated flash: toggle every 3 frames (normal is 6)
            if (self.death_timer // 3) % 2 == 0:
                self.image.set_alpha(40)
            else:
                self.image.set_alpha(255)

    def _fire(self):
        """Fire a bullet from bottom-center of boss"""
        from boss_bullet import BossBullet
        bullet = BossBullet(self.ai_game, self.rect.centerx, self.rect.bottom)
        self.boss_bullets.add(bullet)

    def take_damage(self, amount):
        """Take damage, return True when boss is killed (enters death animation)"""
        self.hp -= amount
        if self.hp <= 0 and not self.dying:
            self.hp = 0
            self.dying = True
            self.death_timer = self.settings.boss_death_flash_frames
            self._death_exploded = False
            return True
        return False

    def draw_hp_bar(self):
        """Draw HP bar above boss"""
        bar_width = self.settings.boss_hp_bar_width
        bar_height = self.settings.boss_hp_bar_height
        bar_x = self.rect.centerx - bar_width // 2
        bar_y = self.rect.top - self.settings.boss_hp_bar_offset_y

        # Background
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (40, 40, 40), bg_rect)

        # Current HP (green->yellow->red)
        ratio = self.hp / self.max_hp
        if ratio > 0.5:
            color = (int(255 * (1 - ratio) * 2), 255, 0)
        else:
            color = (255, int(255 * ratio * 2), 0)
        hp_rect = pygame.Rect(bar_x, bar_y, int(bar_width * ratio), bar_height)
        pygame.draw.rect(self.screen, color, hp_rect)
