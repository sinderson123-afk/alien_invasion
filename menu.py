"""Menu system: start screen, pause overlay, tutorial screen"""

import pygame
from button import Button


class MenuSystem:
    """Manages all menu screens: start screen, pause overlay, tutorial"""

    def __init__(self, ai_game):
        """Initialize the menu system"""
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.screen_rect = self.screen.get_rect()
        self.settings = ai_game.settings

        # Fonts
        self.title_font = pygame.font.SysFont(None, self.settings.menu_title_font_size)
        self.subtitle_font = pygame.font.SysFont(None, 28)
        self.hint_font = pygame.font.SysFont(None, 22)
        self.pause_title_font = pygame.font.SysFont(None, 60)
        self.tutorial_title_font = pygame.font.SysFont(None, 56)
        self.tutorial_key_font = pygame.font.SysFont(None, 36)
        self.tutorial_desc_font = pygame.font.SysFont(None, 30)
        self.stats_font = pygame.font.SysFont(None, 26)

        # Create buttons for each screen
        self._create_menu_buttons()
        self._create_pause_buttons()
        self._create_tutorial_buttons()

    # ------------------------------------------------------------------
    # Button creation
    # ------------------------------------------------------------------

    def _create_menu_buttons(self):
        """Create the main menu buttons (resume, start, shop, tutorial, leaderboard)"""
        cx = self.screen_rect.centerx
        btn_w = 300
        btn_h = 70
        gap = 78
        start_y = self.screen_rect.centery - 68

        self.btn_resume = Button(
            self.ai_game, "Resume Game",
            width=btn_w, height=btn_h,
            button_color=(200, 150, 40),
            hover_color=(240, 180, 60),
            font_size=self.settings.menu_button_font_size,
            border_radius=12)
        self.btn_resume.rect.center = (cx, start_y)
        self.btn_resume._prep_msg("Resume Game")

        self.btn_start = Button(
            self.ai_game, "Start Game",
            width=btn_w, height=btn_h,
            button_color=self.settings.menu_start_color,
            hover_color=self.settings.menu_start_hover,
            font_size=self.settings.menu_button_font_size,
            border_radius=12)
        self.btn_start.rect.center = (cx, start_y + gap)
        self.btn_start._prep_msg("Start Game")

        self.btn_shop = Button(
            self.ai_game, "Shop",
            width=btn_w, height=btn_h,
            button_color=self.settings.menu_shop_color,
            hover_color=self.settings.menu_shop_hover,
            font_size=self.settings.menu_button_font_size,
            border_radius=12)
        self.btn_shop.rect.center = (cx, start_y + gap * 2)
        self.btn_shop._prep_msg("Shop")

        self.btn_tutorial = Button(
            self.ai_game, "Tutorial",
            width=btn_w, height=btn_h,
            button_color=self.settings.menu_tutorial_color,
            hover_color=self.settings.menu_tutorial_hover,
            font_size=self.settings.menu_button_font_size,
            border_radius=12)
        self.btn_tutorial.rect.center = (cx, start_y + gap * 3)
        self.btn_tutorial._prep_msg("Tutorial")

        self.btn_leaderboard = Button(
            self.ai_game, "Leaderboard",
            width=btn_w, height=btn_h,
            button_color=(180, 110, 50),
            hover_color=(220, 140, 70),
            font_size=self.settings.menu_button_font_size,
            border_radius=12)
        self.btn_leaderboard.rect.center = (cx, start_y + gap * 4)
        self.btn_leaderboard._prep_msg("Leaderboard")
        self.btn_tutorial._prep_msg("Tutorial")

    def _create_pause_buttons(self):
        """Create pause overlay buttons"""
        cx = self.screen_rect.centerx
        cy = self.screen_rect.centery
        btn_w = 280
        btn_h = 60
        gap = 70

        self.btn_resume = Button(
            self.ai_game, "Resume",
            width=btn_w, height=btn_h,
            button_color=self.settings.menu_resume_color,
            hover_color=self.settings.menu_resume_hover,
            font_size=40, border_radius=10)
        self.btn_resume.rect.center = (cx, cy - int(gap * 1.5))
        self.btn_resume._prep_msg("Resume")

        self.btn_save = Button(
            self.ai_game, "Save Game",
            width=btn_w, height=btn_h,
            button_color=(40, 120, 200),
            hover_color=(60, 160, 240),
            font_size=40, border_radius=10)
        self.btn_save.rect.center = (cx, cy - int(gap * 0.5))
        self.btn_save._prep_msg("Save Game")

        self.btn_quit_to_menu = Button(
            self.ai_game, "Main Menu",
            width=btn_w, height=btn_h,
            button_color=self.settings.menu_return_color,
            hover_color=self.settings.menu_return_hover,
            font_size=40, border_radius=10)
        self.btn_quit_to_menu.rect.center = (cx, cy + int(gap * 0.5))
        self.btn_quit_to_menu._prep_msg("Main Menu")

        self.btn_exit = Button(
            self.ai_game, "Quit Game",
            width=btn_w, height=btn_h,
            button_color=self.settings.menu_quit_color,
            hover_color=self.settings.menu_quit_hover,
            font_size=40, border_radius=10)
        self.btn_exit.rect.center = (cx, cy + int(gap * 1.5))
        self.btn_exit._prep_msg("Quit Game")

    def _create_tutorial_buttons(self):
        """Create tutorial screen instructions"""
        # Control instructions
        self.tutorial_controls = [
            ("Arrow Keys",  "Move ship left / right"),
            ("Space",       "Fire bullets"),
            ("E",           "Launch homing missile"),
            ("M",           "Open / Close shop"),
            ("N",           "Activate magnet (auto-pickup coins)"),
            ("C",           "Activate clover (push enemies upward)"),
            ("F5",          "Quick save game"),
            ("ESC",         "Pause / Save Game"),
        ]

        # System explanations
        self.tutorial_tips = [
            "Armor tiers (Shop): Silver -> Gold -> Mithril -> Galvorn -> Tilkal",
            "Higher tier = more damage reduction. Trade-in old armor for 50% off.",
            "HP bar replaces hearts. Vitality skill adds +1 HP slot (x10).",
            "Clover (C key): panic button - blows aliens & meteors to the top.",
            "Shield items block one full hit — buy them in the Shop!",
        ]

    # ------------------------------------------------------------------
    # Start screen
    # ------------------------------------------------------------------

    def draw_start_screen(self, mouse_pos=None, save_exists=False):
        """Draw the start screen: title + buttons (resume if save exists)"""
        cx = self.screen_rect.centerx

        # Title — positioned above the first visible button
        first_button = self.btn_resume if save_exists else self.btn_start

        title_img = self.title_font.render("ALIEN INVASION", True, (255, 215, 0))
        title_rect = title_img.get_rect()
        title_rect.centerx = cx
        title_rect.bottom = first_button.rect.top - 40
        self.screen.blit(title_img, title_rect)

        # Subtitle
        sub_img = self.subtitle_font.render(
            "A Space Shooter", True, (180, 180, 200))
        sub_rect = sub_img.get_rect()
        sub_rect.centerx = cx
        sub_rect.top = title_rect.bottom + 5
        self.screen.blit(sub_img, sub_rect)

        # Buttons
        if save_exists:
            self.btn_resume.draw_button(mouse_pos)
        self.btn_start.draw_button(mouse_pos)
        self.btn_shop.draw_button(mouse_pos)
        self.btn_tutorial.draw_button(mouse_pos)
        self.btn_leaderboard.draw_button(mouse_pos)

        # Bottom stats
        stats = self.ai_game.stats
        coins_str = f"Coins: ${stats.coins}"
        hs_str = f"High Score: {stats.high_score:,}"
        info_img = self.stats_font.render(
            f"{coins_str}    |    {hs_str}", True, (160, 160, 180))
        info_rect = info_img.get_rect()
        info_rect.centerx = cx
        info_rect.bottom = self.screen_rect.bottom - 25
        self.screen.blit(info_img, info_rect)

    def handle_menu_click(self, mouse_pos):
        """Handle mouse clicks on the start screen, return action type"""
        if self.btn_resume.is_clicked(mouse_pos):
            return 'resume'
        if self.btn_start.is_clicked(mouse_pos):
            return 'start'
        if self.btn_shop.is_clicked(mouse_pos):
            return 'shop'
        if self.btn_tutorial.is_clicked(mouse_pos):
            return 'tutorial'
        if self.btn_leaderboard.is_clicked(mouse_pos):
            return 'leaderboard'
        return None

    # ------------------------------------------------------------------
    # Pause overlay
    # ------------------------------------------------------------------

    def draw_pause_overlay(self, mouse_pos=None, save_disabled=False):
        """Draw pause overlay (semi-transparent mask + buttons)"""
        # Semi-transparent dark overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, self.settings.pause_overlay_alpha))
        self.screen.blit(overlay, (0, 0))

        # Title
        title_img = self.pause_title_font.render("PAUSED", True, (255, 255, 255))
        title_rect = title_img.get_rect()
        title_rect.centerx = self.screen_rect.centerx
        title_rect.bottom = self.btn_resume.rect.top - 30
        self.screen.blit(title_img, title_rect)

        # Buttons
        self.btn_resume.draw_button(mouse_pos)

        if save_disabled:
            self.btn_save._prep_msg("Saved")
            saved_colors = (self.btn_save.button_color, self.btn_save.hover_color,
                            self.btn_save.text_color)
            self.btn_save.button_color = (80, 80, 80)
            self.btn_save.hover_color = (80, 80, 80)
            self.btn_save.text_color = (140, 140, 140)
            self.btn_save.draw_button(None)
            self.btn_save.button_color = saved_colors[0]
            self.btn_save.hover_color = saved_colors[1]
            self.btn_save.text_color = saved_colors[2]
            self.btn_save._prep_msg("Save Game")
        else:
            self.btn_save.draw_button(mouse_pos)

        self.btn_quit_to_menu.draw_button(mouse_pos)
        self.btn_exit.draw_button(mouse_pos)

        # Hint
        hint = self.hint_font.render("Press ESC to Resume", True, (160, 160, 180))
        hint_rect = hint.get_rect()
        hint_rect.centerx = self.screen_rect.centerx
        hint_rect.bottom = self.screen_rect.bottom - 20
        self.screen.blit(hint, hint_rect)

    def handle_pause_click(self, mouse_pos):
        """Handle mouse clicks on pause overlay, return action type"""
        if self.btn_resume.is_clicked(mouse_pos):
            return 'resume'
        if self.btn_save.is_clicked(mouse_pos):
            return 'save'
        if self.btn_quit_to_menu.is_clicked(mouse_pos):
            return 'quit_to_menu'
        if self.btn_exit.is_clicked(mouse_pos):
            return 'exit'
        return None

    # ------------------------------------------------------------------
    # Tutorial screen
    # ------------------------------------------------------------------

    def draw_tutorial(self, mouse_pos=None):
        """Draw tutorial screen: controls panel + tips + back button"""
        panel_w, panel_h = 620, 640
        panel = pygame.Surface((panel_w, panel_h))
        panel.fill((35, 35, 55))
        panel_rect = panel.get_rect(center=self.screen_rect.center)
        self.screen.blit(panel, panel_rect)

        px, py = panel_rect.topleft

        title_img = self.tutorial_title_font.render("Controls", True, (255, 215, 0))
        title_rect = title_img.get_rect(centerx=px + panel_w // 2, top=py + 25)
        self.screen.blit(title_img, title_rect)

        row_y = py + 80
        for key_name, description in self.tutorial_controls:
            key_img = self.tutorial_key_font.render(key_name, True, (100, 200, 255))
            key_rect = key_img.get_rect(right=px + 160, centery=row_y + 12)
            self.screen.blit(key_img, key_rect)

            sep_img = self.tutorial_key_font.render("-", True, (120, 120, 150))
            sep_rect = sep_img.get_rect(centerx=px + 178, centery=row_y + 12)
            self.screen.blit(sep_img, sep_rect)

            desc_img = self.tutorial_desc_font.render(description, True, (220, 220, 220))
            self.screen.blit(desc_img, (px + 196, row_y))

            row_y += 48

        # Separator line
        row_y += 8
        pygame.draw.line(self.screen, (60, 60, 80),
                         (px + 40, row_y), (px + panel_w - 40, row_y), 1)
        row_y += 16

        # Tips section title
        tips_title = self.tutorial_title_font.render("Tips", True, (255, 215, 0))
        tips_title_rect = tips_title.get_rect(centerx=px + panel_w // 2, top=row_y)
        self.screen.blit(tips_title, tips_title_rect)
        row_y += 45

        # Tips rows
        for tip in self.tutorial_tips:
            tip_img = self.hint_font.render(tip, True, (180, 180, 200))
            tip_rect = tip_img.get_rect(centerx=px + panel_w // 2, centery=row_y + 8)
            self.screen.blit(tip_img, tip_rect)
            row_y += 30

        hint = self.hint_font.render("Press ESC to Return", True, (140, 140, 160))
        hint_rect = hint.get_rect()
        hint_rect.centerx = self.screen_rect.centerx
        hint_rect.bottom = self.screen_rect.bottom - 20
        self.screen.blit(hint, hint_rect)

    def handle_tutorial_click(self, mouse_pos):
        """No buttons on tutorial screen — ESC only."""
        return None
