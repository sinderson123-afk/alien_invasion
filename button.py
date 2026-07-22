"""Menu button component: hover highlight, rounded corners, text shadow, custom size"""

import pygame


class Button:
    """Button class for game (enhanced: hover, rounded, variable size)"""

    def __init__(self, ai_game, msg, width=200, height=50,
                 button_color=(0, 135, 0), text_color=(255, 255, 255),
                 font_size=48, border_radius=10, hover_color=None):
        """Initialize button attributes"""
        self.screen = ai_game.screen
        self.screen_rect = ai_game.screen.get_rect()

        # Button size and style
        self.width = width
        self.height = height
        self.button_color = button_color
        self.text_color = text_color
        self.shadow_color = (20, 20, 20)
        self.border_radius = border_radius
        self.font = pygame.font.SysFont(None, font_size)
        self.hover_color = hover_color or self._brighten(button_color)
        self.msg = msg  # Save text for shadow re-render

        # Create button rect and center it
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.rect.center = self.screen_rect.center

        # Currently hovered
        self._hovered = False

        # Pre-render button label
        self._prep_msg(msg)

    @staticmethod
    def _brighten(color, factor=0.2):
        """Brighten color by specified ratio"""
        return tuple(min(255, int(c * (1 + factor))) for c in color)

    def _prep_msg(self, msg):
        """Render msg as image and center on button"""
        # Text without bg color (transparent), for overlaying on button color
        self.msg_image = self.font.render(msg, True, self.text_color)
        self.msg_image_rect = self.msg_image.get_rect()
        self.msg_image_rect.center = self.rect.center

        # Shadow text (dark offset version)
        self.shadow_image = self.font.render(msg, True, self.shadow_color)
        self.shadow_rect = self.shadow_image.get_rect()
        self.shadow_rect.center = (self.rect.centerx + 1, self.rect.centery + 1)

    def check_hover(self, mouse_pos):
        """Update hover state, return whether hovered"""
        self._hovered = self.rect.collidepoint(mouse_pos)
        return self._hovered

    def is_clicked(self, mouse_pos):
        """Check if button is clicked"""
        return self.rect.collidepoint(mouse_pos)

    def draw_button(self, mouse_pos=None):
        """Draw button (hover highlight, rounded corners, text shadow)"""
        if mouse_pos is not None:
            self.check_hover(mouse_pos)

        color = self.hover_color if self._hovered else self.button_color

        # Draw button body (rounded rect)
        pygame.draw.rect(self.screen, color, self.rect,
                         border_radius=self.border_radius)

        # Draw border (slightly brighter)
        border_color = self._brighten(color, 0.25)
        pygame.draw.rect(self.screen, border_color, self.rect,
                         width=2, border_radius=self.border_radius)

        # Draw text shadow (offset 1px down-right)
        self.screen.blit(self.shadow_image, self.shadow_rect)

        # Draw text
        self.screen.blit(self.msg_image, self.msg_image_rect)
