import pygame
import pygame.font

from missile import create_missile_image


class Scoreboard:
    """Class to display score info"""

    def __init__(self, ai_game):
        """Initialize score display attributes"""
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.screen_rect = self.screen.get_rect()
        self.settings = ai_game.settings
        self.stats = ai_game.stats

        # Font settings for score display
        self.text_color = (30, 30, 30)
        self.font = pygame.font.SysFont(None, 48)
        self.small_font = pygame.font.SysFont(None, 32)
        self.tiny_font = pygame.font.SysFont(None, 22)

        # Missile stock icon drawn only once
        self.missile_icon = create_missile_image(10, 22)

        # Record last displayed level to detect level-up
        self.last_displayed_level = 1

        # Prepare initial score, high score, health, missile stock images
        self.prep_score()
        self.prep_high_score()
        self.prep_missiles()
        self.prep_level()
        self.prep_coins()

    def prep_score(self):
        """Render score as image"""
        score_str = f"{self.stats.score:,}"
        self.score_image = self.font.render(score_str, True,
                                            self.text_color, self.settings.bg_color)

        # Show score at top-right of screen
        self.score_rect = self.score_image.get_rect()
        self.score_rect.right = self.screen_rect.right - 20
        self.score_rect.top = 20

    def prep_high_score(self):
        """Render high score as image"""
        high_score_str = f"{self.stats.high_score:,}"
        self.high_score_image = self.font.render(high_score_str, True,
                                                  self.text_color, self.settings.bg_color)

        # Place high score at top-center of screen
        self.high_score_rect = self.high_score_image.get_rect()
        self.high_score_rect.centerx = self.screen_rect.centerx
        self.high_score_rect.top = self.score_rect.top

    def prep_missiles(self):
        """Render missile stock as icon + count (below HP bar)"""
        self.missile_icon_rect = self.missile_icon.get_rect()
        self.missile_icon_rect.topleft = (16, 62)

        count_str = f"x {self.stats.missiles}"
        self.missile_count_image = self.small_font.render(count_str, True,
                                                           self.text_color, self.settings.bg_color)
        self.missile_count_rect = self.missile_count_image.get_rect()
        self.missile_count_rect.midleft = (self.missile_icon_rect.right + 8,
                                            self.missile_icon_rect.centery)

    def prep_coins(self):
        """Render coin count as image"""
        coins_str = f"$ {self.stats.coins}"
        self.coins_image = self.small_font.render(coins_str, True,
                                                    (218, 165, 32), self.settings.bg_color)
        self.coins_rect = self.coins_image.get_rect()
        self.coins_rect.topleft = (16, 86)

    def prep_level(self):
        """Render level as image"""
        self.last_displayed_level = self.stats.level
        level_str = f"Level {self.stats.level}"
        self.level_image = self.small_font.render(level_str, True,
                                                    self.text_color, self.settings.bg_color)
        self.level_rect = self.level_image.get_rect()
        self.level_rect.right = self.screen_rect.right - 20
        self.level_rect.top = self.score_rect.bottom + 5

    def check_high_score(self):
        """Check if new high score was achieved"""
        if self.stats.score > self.stats.high_score:
            self.stats.high_score = self.stats.score
            self.prep_high_score()

    def _draw_hp_bar(self):
        """Draw HP bar and numeric value at top-left"""
        bar_x, bar_y = 16, 20
        bar_w, bar_h = 200, 18

        max_hp = self.stats.max_hp
        cur_hp = max(0, self.stats.ship_hp)
        ratio = cur_hp / max_hp if max_hp > 0 else 0

        # Background
        pygame.draw.rect(self.screen, (20, 20, 20),
                         (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(self.screen, (40, 40, 40),
                         (bar_x, bar_y, bar_w, bar_h))

        # HP color: green->yellow->red
        if ratio > 0.6:
            color = (int(255 * (1 - ratio) / 0.4 * 0.5),
                     220, int(80 * (1 - ratio) / 0.4))
        elif ratio > 0.3:
            color = (255, int(220 * (ratio - 0.3) / 0.3 * 0.8 + 40), 40)
        else:
            color = (220, 50, 40)

        pygame.draw.rect(self.screen, color,
                         (bar_x, bar_y, int(bar_w * ratio), bar_h))

        # HP value
        hp_text = f"HP: {cur_hp}/{max_hp}"
        hp_img = self.tiny_font.render(hp_text, True, (220, 220, 220))
        hp_rect = hp_img.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2))
        self.screen.blit(hp_img, hp_rect)

    def show_score(self):
        """Show score, high score, HP bar, missiles, coins, item status on screen"""
        self.screen.blit(self.score_image, self.score_rect)
        self.screen.blit(self.high_score_image, self.high_score_rect)
        self._draw_hp_bar()

        # Armor indicator
        if self.stats.armor_tier:
            armor_name = self.stats.armor_tier.capitalize()
            from shop import _get_armor_pct
            pct = _get_armor_pct(self.stats.armor_tier, self.settings)
            armor_text = f"{armor_name} ({int(pct * 100)}%)"
            armor_img = self.tiny_font.render(armor_text, True,
                                               (100, 180, 255), self.settings.bg_color)
            armor_rect = armor_img.get_rect(topleft=(16, 42))
            self.screen.blit(armor_img, armor_rect)
        else:
            armor_img = self.tiny_font.render("No Armor", True,
                                               (120, 120, 140), self.settings.bg_color)
            armor_rect = armor_img.get_rect(topleft=(16, 42))
            self.screen.blit(armor_img, armor_rect)

        self.screen.blit(self.missile_icon, self.missile_icon_rect)
        self.screen.blit(self.missile_count_image, self.missile_count_rect)
        self.screen.blit(self.level_image, self.level_rect)
        self.screen.blit(self.coins_image, self.coins_rect)

        # Shield icon (if any)
        if self.stats.items.get('shield', 0) > 0:
            shield_img = self.small_font.render(
                f"Shield: {self.stats.items['shield']}", True,
                (100, 200, 255), self.settings.bg_color)
            self.screen.blit(shield_img, (16, 110))

        # Clover icon (if any)
        if self.stats.items.get('clover', 0) > 0:
            clv_y = 130 if self.stats.items.get('shield', 0) > 0 else 110
            clover_img = self.small_font.render(
                f"Clover: {self.stats.items['clover']}", True,
                (100, 255, 100), self.settings.bg_color)
            self.screen.blit(clover_img, (16, clv_y))

        # Magnet timer (if active)
        if self.ai_game.magnet_active:
            mag_y = 150 if self.stats.items.get('shield', 0) > 0 else 130
            if self.stats.items.get('clover', 0) > 0:
                mag_y += 20
            mag_img = self.small_font.render(
                f"Magnet: {self.ai_game.magnet_timer // 60 + 1}s", True,
                (255, 200, 100), self.settings.bg_color)
            self.screen.blit(mag_img, (16, mag_y))
