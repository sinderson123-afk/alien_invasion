import pygame
from settings import resource_path

class Ship:
    """Class to manage the ship"""
    def __init__(self,ai_game):
        """Initialize ship and set starting position"""
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.screen_rect = ai_game.screen.get_rect()

        # Load ship image and scale
        self.image = pygame.image.load(resource_path("resource/images/ship.bmp"))
        original_width, original_height = self.image.get_size()
        # Scale ship width to 8% of screen width
        new_width = int(self.screen_rect.width * 0.08)
        new_height = int(original_height * (new_width / original_width))
        self.image = pygame.transform.scale(self.image, (new_width, new_height))
        self.rect = self.image.get_rect()

        # Each new ship is placed centered at screen bottom
        self.rect.midbottom =self.screen_rect.midbottom

        # Store a float for the ship's x attribute
        self.x = float(self.rect.x)

        # Movement flags
        self.moving_right = False
        self.moving_left = False

        # Hit flash timer (frames)
        self.invulnerable_frames = 0

    def update(self):
        """Update ship position by movement flags"""
        if self.moving_right and self.rect.right < self.screen_rect.right:
            self.x += self.settings.ship_speed
        if self.moving_left and self.rect.left > 0:
            self.x -= self.settings.ship_speed

        # Update rect object from self.x
        self.rect.x = self.x

    def blitme(self):
        """Draw ship at position (flash on hit)"""
        if self.invulnerable_frames > 0:
            self.invulnerable_frames -= 1
            # Toggle visibility every 6 frames
            if (self.invulnerable_frames // 6) % 2 == 0:
                return
        self.screen.blit(self.image, self.rect)

    def center_ship(self):
        """Place ship centered at screen bottom"""
        self.rect.midbottom = self.screen_rect.midbottom
        self.x = float(self.rect.x)