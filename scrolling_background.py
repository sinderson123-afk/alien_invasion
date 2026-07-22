import pygame

class ScrollingBackground:
    """Class managing seamless scrolling background"""
    def __init__(self, ai_game, image_path, speed=2):
        self.screen = ai_game.screen
        self.screen_rect = self.screen.get_rect()
        
        # Load background image and get its rect
        self.image = pygame.image.load(image_path).convert_alpha()
        self.rect = self.image.get_rect()
        
        # Ensure image width covers screen (height can be larger)
        self.bg_height = self.rect.height
        
        # Set initial y coordinates for two images
        self.y1 = 0.0
        self.y2 = -float(self.bg_height)
        
        # Background scroll speed
        self.speed = speed

    def update(self):
        """Scroll background downward"""
        self.y1 += self.speed
        self.y2 += self.speed

        # If image 1 exceeds bottom, wrap it above image 2
        if self.y1 >= self.screen_rect.height:
            self.y1 = self.y2 - self.bg_height

        # If image 2 exceeds bottom, wrap it above image 1
        if self.y2 >= self.screen_rect.height:
            self.y2 = self.y1 - self.bg_height

    def draw(self):
        """Draw both background images on screen"""
        self.screen.blit(self.image, (0, self.y1))
        self.screen.blit(self.image, (0, self.y2))