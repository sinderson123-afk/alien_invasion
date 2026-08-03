import sys
import random
import math
import json
import threading
from pathlib import Path
import pygame

from settings import Settings, GAME_VERSION, IS_DEV_BUILD
from ship import Ship
from bullet import Bullet
from missile import Missile
from alien import Alien
from particle import Particle
from game_stats import GameStats, GameState
from scoreboard import Scoreboard
from sound import SoundManager
from boss import Boss
from boss_bullet import BossBullet
from boss_missile import BossMissile
from coin import Coin
from gem import GemPickup, generate_gem, upgrade_gem, get_gem_bonuses, init_gem_id_counter
from scrolling_background import ScrollingBackground
from video_background import VideoBackground
from menu import MenuSystem
from meteor import Meteor, MeteorFragment
import shop
from web_client import WebClient
from file_crypto import encrypt_json, decrypt_json
from login_ui import LoginOverlay

class AlienInvasion:
    """Main game class managing all resources and behavior"""
    def __init__(self):
        """Initialize game and create resources"""
        pygame.init()
        # Disable SDL text input to prevent IME from intercepting keys
        # (otherwise pressing E triggers IME composition, eating subsequent arrow keys)
        pygame.key.stop_text_input()
        self.sound = SoundManager()
        self.clock = pygame.time.Clock()
        self.settings = Settings()
        self.screen = pygame.display.set_mode((self.settings.screen_width, self.settings.screen_height))
        self.screen_rect = self.screen.get_rect()
        pygame.display.set_caption("Alien Invasion")

        self.stats = GameStats(self)
        init_gem_id_counter(self.stats.equipped_gems, self.stats.gem_storage)
        self.sb = Scoreboard(self)

        self.ship = Ship(self)
        self.bullets = pygame.sprite.Group()
        self.missiles = pygame.sprite.Group()
        self.aliens = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.boss_bullets = pygame.sprite.Group()
        self.boss_missiles = pygame.sprite.Group()
        self.coins = pygame.sprite.Group()
        self.gems = pygame.sprite.Group()
        self.meteors = pygame.sprite.Group()
        self.meteor_fragments = pygame.sprite.Group()
        self.boss = None                    # Boss reference (not None during boss level)

        # State machine (replaces old game_active and shop_open)
        self.state = GameState.MENU
        self.previous_state = GameState.MENU

        # Network client
        self.web_client = WebClient(self.settings.server_url)

        # Login overlay (skipped if already authenticated)
        self.login_overlay = None
        if not self.stats.player_data.is_authenticated():
            self.login_overlay = LoginOverlay(
                self.screen, self.web_client, self.stats.player_data)
            if not self.login_overlay.done:
                self.state = GameState.LOGIN

        # Leaderboard data cache
        self.leaderboard_data = None

        # Menu system
        self.menu_bg = VideoBackground(self)
        self.menu_system = MenuSystem(self)

        # Scrolling background (3 images, cycled by level range)
        self.bg_instances = [
            ScrollingBackground(self, path, speed=self.settings.bg_scroll_speed)
            for path in self.settings.bg_images
        ]

        self.hit_cooldown = 0          # Hit cooldown frames (no diving or double collision during this)
        self.flashing_alien = None     # Currently flashing alien (removed after cooldown)
        self.flashing_alien_pos = None # Position at time of collision (for explosion)
        self.levelup_anim_frames = 0   # Frames remaining for level-up animation
        self.magnet_active = False        # Whether magnet is active
        self.magnet_timer = 0             # Magnet remaining time
        self._boss_secondary_burst = None # Boss secondary explosion (x, y, delay)
        self.meteor_timer = 0              # Meteor spawn countdown
        self.boss_warning_frames = 0       # Boss entrance warning countdown
        self.ship_death_frames = 0         # Ship death animation countdown
        self.game_over_frames = 0          # Fail banner countdown
        self.death_position = None         # Ship death position
        self.save_notification_frames = 0  # Save notification countdown
        self.save_disabled = False         # Whether already saved during this pause
        self._notification_text = ''       # Notification text
        self.notifications = []            # Notification history
        self.show_notifications = False    # Whether notification panel is shown
        self.clover_flash_frames = 0       # Clover screen flash countdown
        self.clover_push_frames = 0        # Clover push animation countdown
        self.firing = False                # Spacebar held for auto-fire
        self._fire_cooldown = 0            # Auto-fire frame timer
        self._crit_rings = []               # Crit shockwave rings: {x,y,radius,life,max_life}
        self._update_available = None      # (version, url) when update found
        self.in_transition = False         # Level transition cinematic active
        self.transition_stage = ''         # 'rise', 'hover', 'exit', 'enter'
        self.transition_frames = 0         # Remaining frames in current stage
        self.transition_level_text = ''    # "Entering Earth Orbit" etc.
        self.transition_blackout = 0       # Fade-to-black alpha (0.0-1.0)
        self._last_bg_instance = None      # Previous bg instance for zone-change detection

        # Bell notification fonts
        self._font_small_bell = pygame.font.SysFont(None, 14)
        self._font_title_bell = pygame.font.SysFont(None, 36, bold=True)
        self._font_row_bell = pygame.font.SysFont(None, 20)
        self._account_confirm = False       # Account-switch confirmation dialog open
        self._account_confirm_rects = []    # (action, rect) for dialog buttons

        # Start background music (menu theme)
        self.sound.play_menu_bgm()

        # Background update check (non-blocking)
        if not IS_DEV_BUILD:
            self._start_update_check()

    def run_game(self):
        """Start the main game loop"""
        while True:
            self._check_events()

            if self.state == GameState.PLAYING:
                self._active_bg().update()

                # Boss entrance warning countdown
                if self.boss_warning_frames > 0:
                    self.boss_warning_frames -= 1
                    if self.boss_warning_frames == 0:
                        self.boss = Boss(self)

                # Clover flash countdown
                if self.clover_flash_frames > 0:
                    self.clover_flash_frames -= 1

                # Level transition cinematic (freezes all gameplay)
                if self.in_transition:
                    self._update_transition()
                    self.particles.update()
                    self._update_crit_rings()
                elif self.game_over_frames > 0:
                    self.game_over_frames -= 1
                    self.particles.update()
                    self._update_crit_rings()
                    if self.game_over_frames == 0:
                        self._return_to_menu()
                elif self.ship_death_frames > 0:
                    self.ship_death_frames -= 1
                    self.particles.update()
                    self._update_crit_rings()
                    if self.ship_death_frames == 0:
                        self.game_over_frames = self.settings.fail_banner_duration
                elif self.clover_push_frames > 0:
                    self._update_clover_push()
                    self.ship.update()
                    if self.firing:
                        if self._fire_cooldown > 0:
                            self._fire_cooldown -= 1
                        else:
                            self._fire_bullet()
                            self._fire_cooldown = self.settings.bullet_fire_cooldown
                    self._update_bullets()
                    self._update_missiles()
                    if self.boss is not None:
                        self.boss.update()
                    self.coins.update()
                    self.gems.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self._check_gem_pickup()
                    self._spawn_meteor()
                    self.particles.update()
                    self._update_crit_rings()
                elif self.hit_cooldown > 0:
                    # Cooldown: update aliens (with flash animation), boss bullets and particles, no collision detection
                    self.aliens.update()
                    self._update_boss_bullets()
                    self._update_boss_missiles()
                    if self.boss is not None:
                        self.boss.update()
                    self.coins.update()
                    self.gems.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self._check_gem_pickup()
                    self.meteors.update()
                    self.meteor_fragments.update()
                    self._update_meteor_collisions(skip_ship=True)
                    self._spawn_meteor()
                    self.particles.update()
                    self._update_crit_rings()
                    self.hit_cooldown -= 1
                    if self.hit_cooldown == 0:
                        # Flash ends: destroy the colliding alien (explode at collision pos, not current pos)
                        if self.flashing_alien is not None and self.flashing_alien.alive():
                            explosion_pos = (self.flashing_alien_pos
                                             if self.flashing_alien_pos
                                             else self.flashing_alien.rect.center)
                            self._create_alien_explosion(explosion_pos)
                            self._maybe_drop_coin(*explosion_pos)
                            self.flashing_alien.kill()
                            self.sound.play_explosion()
                            self._award_points(
                                1, kill_count=0 if getattr(self.flashing_alien, 'summoned', False) else 1)
                        self.flashing_alien = None
                        self.flashing_alien_pos = None
                else:
                    self.ship.update()
                    if self.firing:
                        if self._fire_cooldown > 0:
                            self._fire_cooldown -= 1
                        else:
                            self._fire_bullet()
                            self._fire_cooldown = self.settings.bullet_fire_cooldown
                    self._update_bullets()
                    self._update_missiles()
                    self._update_boss_bullets()
                    self._update_boss_missiles()
                    if self.boss is not None:
                        self.boss.update()
                    self._update_aliens()
                    self.coins.update()
                    self.gems.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self._check_gem_pickup()
                    self.meteors.update()
                    self.meteor_fragments.update()
                    self._update_meteor_collisions(skip_ship=False)
                    self._spawn_meteor()
                    self.particles.update()
                    self._update_crit_rings()

                    # Boss secondary explosion
                    if self._boss_secondary_burst is not None:
                        bx, by, delay = self._boss_secondary_burst
                        delay -= 1
                        if delay <= 0:
                            s = self.settings
                            for _ in range(s.boss_secondary_count):
                                p = Particle(self, bx, by,
                                             size_mult=s.boss_particle_size_mult * 0.7,
                                             speed_mult=s.boss_particle_speed_mult * 1.2,
                                             lifetime_mult=s.boss_particle_lifetime_mult * 0.7,
                                             colors=s.boss_particle_colors)
                                self.particles.add(p)
                            self._boss_secondary_burst = None
                        else:
                            self._boss_secondary_burst = (bx, by, delay)

            elif self.state == GameState.MENU:
                self.menu_bg.update()

            elif self.state == GameState.TUTORIAL:
                self.menu_bg.update()

            elif self.state == GameState.SHOP:
                # Continue bg update when entering shop from menu; freeze when from game
                if self.previous_state == GameState.MENU:
                    self.menu_bg.update()

            elif self.state == GameState.LOGIN:
                if self.login_overlay:
                    self.login_overlay.update()

            elif self.state == GameState.LEADERBOARD:
                pass  # Leaderboard is static, no update needed

            # PAUSED: no entity updates

            if self.save_notification_frames > 0:
                self.save_notification_frames -= 1
                if self.save_notification_frames == 0:
                    self._notification_text = ''

            self._update_screen()
            self.clock.tick(60)

    def _check_events(self):
        """Handle keyboard and mouse events (routed by current state)"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit_game()

            # Menu theme track ended → play next
            if event.type == self.sound.MUSIC_END_EVENT:
                self.sound._advance_menu_theme()
                continue

            # LOGIN state: events handled by login overlay
            if self.state == GameState.LOGIN and self.login_overlay:
                self.login_overlay.handle_event(event)
                if self.login_overlay.done:
                    self.state = GameState.MENU
                    self.login_overlay = None
                    pygame.key.stop_text_input()
                continue

            if event.type == pygame.KEYDOWN:
                self._check_keydown_events(event)
            elif event.type == pygame.KEYUP:
                self._check_keyup_events(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                self._check_mouse_click(mouse_pos)

    def _check_mouse_click(self, mouse_pos):
        """Route mouse clicks by current state"""
        # When notification panel is open: click anywhere to close
        if self.show_notifications:
            self.show_notifications = False
            return

        if self.state == GameState.MENU:
            # Update banner click (before menu buttons)
            if self._update_available is not None and \
                    hasattr(self, '_update_banner_rect') and \
                    self._update_banner_rect.collidepoint(mouse_pos):
                WebClient.open_release_page(self._update_available[1])
                return

            # Bell click (detected before menu buttons)
            if hasattr(self, 'notification_bell_rect') and \
                    self.notification_bell_rect.collidepoint(mouse_pos):
                self.show_notifications = True
                return

            # Gear click (switch account)
            if hasattr(self, 'gear_button_rect') and \
                    self.gear_button_rect.collidepoint(mouse_pos):
                if self.stats.player_data.is_authenticated():
                    self._account_confirm = True
                else:
                    self._switch_account()
                return

            # Account-switch confirmation dialog
            if self._account_confirm:
                clicked_dialog = False
                for action, rect in self._account_confirm_rects:
                    if rect.collidepoint(mouse_pos):
                        clicked_dialog = True
                        self._account_confirm = False
                        if action == 'yes':
                            self._switch_account()
                        break
                if not clicked_dialog:
                    self._account_confirm = False
                return

            action = self.menu_system.handle_menu_click(mouse_pos)
            if action == 'start':
                self._start_new_game()
            elif action == 'resume':
                self._resume_game()
            elif action == 'shop':
                self.previous_state = GameState.MENU
                self.state = GameState.SHOP
            elif action == 'tutorial':
                self.state = GameState.TUTORIAL
            elif action == 'leaderboard':
                if not self.stats.player_data.is_authenticated():
                    self.login_overlay = LoginOverlay(
                        self.screen, self.web_client, self.stats.player_data)
                    if not self.login_overlay.done:
                        self.state = GameState.LOGIN
                    else:
                        self._fetch_leaderboard()
                        self.state = GameState.LEADERBOARD
                else:
                    self._fetch_leaderboard()
                    self.state = GameState.LEADERBOARD

        elif self.state == GameState.PAUSED:
            action = self.menu_system.handle_pause_click(mouse_pos)
            if action == 'resume':
                self.state = GameState.PLAYING
                self.ship.moving_right = False
                self.ship.moving_left = False
                self.sound.set_bgm_volume(self.settings.bgm_volume)
            elif action == 'save' and not self.save_disabled:
                self.save_game()
                self._notification_text = 'Game Saved!'
                self.save_notification_frames = 60
                self.save_disabled = True
            elif action == 'quit_to_menu':
                self._return_to_menu()
            elif action == 'exit':
                self._quit_game()

        elif self.state == GameState.SHOP:
            result = shop.handle_shop_click(
                mouse_pos, self.stats, self.settings, ai_game=self)
            if isinstance(result, tuple) and len(result) == 3 and result[1] == 'tab_switch':
                self._shop_tab = result[2]
            else:
                changed, action = result
                if action == 'close':
                    self.state = self.previous_state
                elif changed:
                    self.sb.prep_coins()
                    self._apply_skills()

        elif self.state == GameState.TUTORIAL:
            action = self.menu_system.handle_tutorial_click(mouse_pos)
            if action == 'back':
                self.state = GameState.MENU

        elif self.state == GameState.LEADERBOARD:
            self.state = GameState.MENU

        # Mouse clicks ignored in PLAYING state

    def _apply_skills(self):
        """Adjust game settings by skill levels (called after initialize_dynamic_settings)"""
        skills = self.stats.skills
        s = self.settings
        s.ship_speed *= (1 + skills['speed'] * 0.1)
        if s.ship_speed > s.ship_speed_max:
            s.ship_speed = s.ship_speed_max
        s.bullet_allowed = 3 + skills['ammo']
        # vitality (max HP) already handled in GameStats.reset_stats
        # damage boost: +20% per level
        dmg_mult = 1 + skills.get('damage', 0) * 0.2
        s.bullet_damage = round(s.bullet_damage_base * dmg_mult, 2)
        s.missile_damage = round(s.missile_damage_base * dmg_mult, 2)
        self._pre_gem_bullet_dmg = s.bullet_damage
        self._pre_gem_missile_dmg = s.missile_damage
        self._apply_gems()

    def _apply_gems(self):
        """Apply gem stat bonuses to settings and cache them."""
        bonuses = get_gem_bonuses(self.stats.equipped_gems)
        self._gem_bonuses = bonuses
        s = self.settings

        hp_bonus = bonuses['hp']
        def_bonus = bonuses['defense']
        dmg_pct = 1 + bonuses['damage'] / 100.0
        gold_bonus = bonuses['gold'] / 100.0

        base_bullet = getattr(self, '_pre_gem_bullet_dmg', s.bullet_damage_base)
        base_missile = getattr(self, '_pre_gem_missile_dmg', s.missile_damage_base)
        s.bullet_damage = round(base_bullet * dmg_pct, 2)
        s.missile_damage = round(base_missile * dmg_pct, 2)
        s.coin_drop_rate = s.coin_drop_rate_base + gold_bonus

        self._gem_defense_pct = def_bonus / 100.0
        self._gem_hp_bonus = int(hp_bonus)

        self.stats.max_hp = self.stats._calc_max_hp() + self._gem_hp_bonus
        if self.stats.ship_hp > self.stats.max_hp:
            self.stats.ship_hp = self.stats.max_hp

    def _get_crit_chance(self):
        """Get current crit rate (capped)."""
        bonuses = getattr(self, '_gem_bonuses', {})
        rate = (self.settings.crit_rate_base
                + (self.stats.level - 1) * self.settings.crit_rate_per_level
                + bonuses.get('crit_rate', 0) / 100.0)
        return min(rate, self.settings.crit_rate_cap)

    def _get_crit_multiplier(self):
        """Get current crit damage multiplier (capped)."""
        bonuses = getattr(self, '_gem_bonuses', {})
        return min(self.settings.crit_dmg_base
                   + (self.stats.level - 1) * self.settings.crit_dmg_per_level
                   + bonuses.get('crit_dmg', 0) / 100.0,
                   self.settings.crit_dmg_cap)

    def _get_pen_chance(self):
        """Get current bullet penetration chance."""
        bonuses = getattr(self, '_gem_bonuses', {})
        return bonuses.get('penetration', 0) / 100.0

    def _roll_crit(self):
        """Check if this hit is a crit; return (is_crit, damage_multiplier)."""
        if random.random() < self._get_crit_chance():
            return True, self._get_crit_multiplier()
        return False, 1.0

    def _draw_account_confirm(self):
        """Draw account-switch confirmation dialog (prevents accidental logout)."""
        screen_w = self.screen_rect.width
        screen_h = self.screen_rect.height
        panel_w, panel_h = 440, 170
        panel = pygame.Surface((panel_w, panel_h))
        panel.fill((35, 38, 58))
        panel_rect = panel.get_rect(center=(screen_w // 2, screen_h // 2))
        pygame.draw.rect(panel, (90, 90, 120), panel.get_rect(), 2)
        self.screen.blit(panel, panel_rect)
        px, py = panel_rect.topleft

        font_title = self._font_title_bell
        font_text = self._font_row_bell

        username = self.stats.player_data.get_username() or 'Unknown'
        title = font_title.render("Switch Account?", True, (255, 215, 0))
        self.screen.blit(title, (px + panel_w // 2 - title.get_width() // 2, py + 20))

        info = font_text.render(f"Current account: {username}", True, (200, 200, 220))
        self.screen.blit(info, (px + panel_w // 2 - info.get_width() // 2, py + 62))

        hint = font_text.render("You will need to log in again.", True, (150, 150, 170))
        self.screen.blit(hint, (px + panel_w // 2 - hint.get_width() // 2, py + 88))

        self._account_confirm_rects = []

        btn_w, btn_h = 120, 40
        yes_rect = pygame.Rect(px + 90, py + 112, btn_w, btn_h)
        pygame.draw.rect(self.screen, (100, 200, 100), yes_rect, border_radius=8)
        yes_txt = font_text.render("Yes", True, (20, 20, 20))
        self.screen.blit(yes_txt, (yes_rect.centerx - yes_txt.get_width() // 2,
                                   yes_rect.centery - yes_txt.get_height() // 2))
        self._account_confirm_rects.append(('yes', yes_rect))

        no_rect = pygame.Rect(px + 230, py + 112, btn_w, btn_h)
        pygame.draw.rect(self.screen, (160, 70, 70), no_rect, border_radius=8)
        no_txt = font_text.render("No", True, (255, 255, 255))
        self.screen.blit(no_txt, (no_rect.centerx - no_txt.get_width() // 2,
                                  no_rect.centery - no_txt.get_height() // 2))
        self._account_confirm_rects.append(('no', no_rect))

    def _switch_account(self):
        """Log out current account and show the login overlay to switch accounts."""
        self.stats.player_data.logout()
        self.login_overlay = LoginOverlay(
            self.screen, self.web_client, self.stats.player_data)
        self.state = GameState.LOGIN

    def _quit_game(self):
        """Save high score and player data, then quit"""
        self.sound.stop_bgm()
        self.stats.save_high_score()
        self.stats.save_player_data()
        sys.exit()

    def _start_new_game(self):
        """Start new game: reset all game state and switch to PLAYING"""
        # Delete old save
        save_path = Path(self.settings.save_file)
        if save_path.exists():
            save_path.unlink()

        self.settings.initialize_dynamic_settings()
        self.stats.reset_stats()
        self._apply_skills()
        # Gem HP bonus raises max_hp after reset_stats — start at full HP
        self.stats.ship_hp = self.stats.max_hp
        self.hit_cooldown = 0
        self.flashing_alien = None
        self.flashing_alien_pos = None
        self.boss_warning_frames = 0
        self.ship_death_frames = 0
        self.game_over_frames = 0
        self.clover_push_frames = 0
        self.clover_flash_frames = 0
        self.death_position = None
        self.ship.invulnerable_frames = 0
        self.sb.prep_score()
        self.sb.prep_missiles()
        self.sb.prep_level()
        self.sb.prep_coins()

        # Clear all game entities
        self.bullets.empty()
        self.missiles.empty()
        self.aliens.empty()
        self.boss_bullets.empty()
        self.boss_missiles.empty()
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.meteor_timer = self.settings.meteor_spawn_interval
        self.boss = None

        # Create fleet, position ship
        self._create_fleet()
        self.ship.center_ship()
        self._last_bg_instance = self._active_bg()
        self.in_transition = False
        self.transition_stage = ''
        self.transition_blackout = 0
        self.firing = False
        self._fire_cooldown = 0

        # Switch to game state
        self.state = GameState.PLAYING
        self.sound.set_bgm_volume(self.settings.bgm_volume)
        self.sound.play_level_bgm(self.stats.level)

    def _return_to_menu(self):
        """Return to main menu: save data, clean entities, switch state"""
        self._upload_current_stats()
        self.stats.save_high_score()
        self.stats.score = 0
        self.stats.kills = 0
        self.bullets.empty()
        self.missiles.empty()
        self.aliens.empty()
        self.boss_bullets.empty()
        self.boss_missiles.empty()
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.boss = None
        self.boss_warning_frames = 0
        self.ship_death_frames = 0
        self.game_over_frames = 0
        self.death_position = None
        self.in_transition = False
        self.transition_stage = ''
        self.transition_blackout = 0
        self.firing = False
        self._fire_cooldown = 0
        self.state = GameState.MENU
        self.sound.set_bgm_volume(self.settings.bgm_volume)
        self.sound.play_menu_bgm()

    # ------------------------------------------------------------------
    # Save system
    # ------------------------------------------------------------------

    def save_game(self):
        """Save current game state to JSON file"""
        aliens_list = self.aliens.sprites()
        flashing_alien_id = None
        if self.flashing_alien is not None:
            try:
                flashing_alien_id = aliens_list.index(self.flashing_alien)
            except ValueError:
                flashing_alien_id = None

        data = {
            'version': 6,  # Save format version
            'stats': {
                'score': self.stats.score,
                'kills': self.stats.kills,
                'ship_hp': self.stats.ship_hp,
                'max_hp': self.stats.max_hp,
                'missiles': self.stats.missiles,
                'missiles_awarded': self.stats.missiles_awarded,
                'coins': self.stats.coins,
                'items': dict(self.stats.items),
                'skills': dict(self.stats.skills),
                'armor_tier': self.stats.armor_tier,
                'equipped_gems': [g if g else None for g in self.stats.equipped_gems],
                'gem_storage': list(self.stats.gem_storage),
                'high_score': self.stats.high_score,
            },
            'settings': {
                'ship_speed': self.settings.ship_speed,
                'bullet_speed': self.settings.bullet_speed,
                'alien_speed': self.settings.alien_speed,
                'bullet_allowed': self.settings.bullet_allowed,
                'bullet_damage': self.settings.bullet_damage,
                'missile_damage': self.settings.missile_damage,
            },
            'ship': {
                'x': self.ship.x,
                'invulnerable_frames': self.ship.invulnerable_frames,
                'moving_right': self.ship.moving_right,
                'moving_left': self.ship.moving_left,
            },
            'game': {
                'hit_cooldown': self.hit_cooldown,
                'flashing_alien_id': flashing_alien_id,
                'flashing_alien_pos': list(self.flashing_alien_pos)
                    if self.flashing_alien_pos else None,
                'levelup_anim_frames': self.levelup_anim_frames,
                'magnet_active': self.magnet_active,
                'magnet_timer': self.magnet_timer,
                'boss_secondary_burst': list(self._boss_secondary_burst)
                    if self._boss_secondary_burst else None,
                'meteor_timer': self.meteor_timer,
                'dive_timer': self.dive_timer,
                'boss_warning_frames': self.boss_warning_frames,
                'ship_death_frames': self.ship_death_frames,
                'game_over_frames': self.game_over_frames,
                'death_position': list(self.death_position)
                    if self.death_position else None,
            },
            'scoreboard': {
                'last_displayed_level': self.sb.last_displayed_level,
            },
            'backgrounds': [
                {'y1': bg.y1, 'y2': bg.y2} for bg in self.bg_instances
            ],
            'entities': {
                'aliens': [],
                'boss': None,
                'bullets': [],
                'missiles': [],
                'boss_bullets': [],
                'boss_missiles': [],
                'coins': [],
                'meteors': [],
                'meteor_fragments': [],
            },
        }

        for alien in aliens_list:
            dv = (alien.dive_velocity.x, alien.dive_velocity.y) \
                if alien.dive_velocity is not None else None
            data['entities']['aliens'].append({
                'x': alien.x, 'y': alien.y,
                'hp': alien.hp,
                'state': alien.state,
                'gather_offset': alien.gather_offset,
                'cruise_y': alien.cruise_y,
                'dive_velocity': dv,
                'windup': alien.windup,
                'flash_frames': alien.flash_frames,
            })

        if self.boss is not None:
            b = self.boss
            data['entities']['boss'] = {
                'x': b.x, 'y': b.y,
                'hp': b.hp,
                'direction': b.direction,
                'fire_timer': b.fire_timer,
                'flash_frames': b.flash_frames,
                'dying': b.dying,
                'death_timer': b.death_timer,
                '_death_exploded': b._death_exploded,
                'summoned': b.summoned,
                'summoned2': b.summoned2,
                'missile_timer': b.missile_timer,
            }

        for bullet in self.bullets.sprites():
            data['entities']['bullets'].append({
                'x': bullet.rect.x, 'y': bullet.y,
            })

        for missile in self.missiles.sprites():
            data['entities']['missiles'].append({
                'x': missile.x, 'y': missile.y,
                'vx': missile.velocity.x, 'vy': missile.velocity.y,
            })

        for bb in self.boss_bullets.sprites():
            data['entities']['boss_bullets'].append({
                'x': bb.rect.x, 'y': bb.y,
            })

        for bm in self.boss_missiles.sprites():
            data['entities']['boss_missiles'].append({
                'x': bm.x, 'y': bm.y,
                'vx': bm.velocity.x, 'vy': bm.velocity.y,
            })

        for coin in self.coins.sprites():
            data['entities']['coins'].append({
                'x': coin.rect.x, 'y': coin.y,
                'state': coin.state,
                'hover_timer': coin.hover_timer,
                'flash_timer': coin.flash_timer,
            })

        for meteor in self.meteors.sprites():
            data['entities']['meteors'].append({
                'x': meteor.x, 'y': meteor.y,
                'hp': meteor.hp,
                'vx': meteor.velocity_x, 'vy': meteor.velocity_y,
                'radius': meteor.radius,
                'rotation': meteor.rotation,
                'angle': meteor.angle,
            })

        for frag in self.meteor_fragments.sprites():
            data['entities']['meteor_fragments'].append({
                'x': frag.x, 'y': frag.y,
                'hp': frag.hp,
                'vx': frag.velocity_x, 'vy': frag.velocity_y,
                'radius': frag.radius,
                'lifetime': frag.lifetime,
            })

        encrypt_json(data, Path(self.settings.save_file))

    @staticmethod
    def _migrate_save(data: dict) -> dict:
        """Migrate old save format to latest. Returns migrated data."""
        save_ver = data.get('version', 1)
        if save_ver < 2:
            # v1 -> v2: ensure all fields exist (give defaults for new fields)
            data.setdefault('version', 2)
            save_ver = 2
        if save_ver < 3:
            # v2 -> v3: ship_left -> ship_hp/max_hp, add armor_tier
            s = data.setdefault('stats', {})
            s.setdefault('armor_tier', None)
            if 'ship_left' in s:
                s['ship_hp'] = s['ship_left']
                s['max_hp'] = s['ship_left']
                del s['ship_left']
            data.setdefault('version', 3)
            save_ver = 3
        if save_ver < 4:
            # v3 -> v4: store bullet_damage / missile_damage in settings
            ss = data.setdefault('settings', {})
            ss.setdefault('bullet_damage', 1)
            ss.setdefault('missile_damage', 5)
            data.setdefault('version', 4)
            save_ver = 4
        if save_ver < 5:
            # v4 -> v5: add equipped_gems / gem_storage
            s = data.setdefault('stats', {})
            s.setdefault('equipped_gems', [None] * 5)
            s.setdefault('gem_storage', [])
            data.setdefault('version', 5)
            save_ver = 5
        if save_ver < 6:
            # v5 -> v6: boss summon/missile state + boss_missiles entity list
            e = data.setdefault('entities', {})
            e.setdefault('boss_missiles', [])
            b = e.get('boss')
            if isinstance(b, dict):
                b.setdefault('summoned', False)
                b.setdefault('summoned2', False)
                b.setdefault('missile_timer', 300)
            data.setdefault('version', 6)
            save_ver = 6
        # future v6 -> v7 appended here
        return data

    def _resume_game(self):
        """Load game state from encrypted file and resume"""
        path = Path(self.settings.save_file)
        data = decrypt_json(path)
        if data is None:
            return
        data = AlienInvasion._migrate_save(data)

        # --- Restore stats ---
        s = data['stats']
        self.stats.score = s['score']
        self.stats.kills = s['kills']
        self.stats.ship_hp = s.get('ship_hp', s.get('ship_left', self.stats.max_hp))
        self.stats.max_hp = s.get('max_hp', self.stats._calc_max_hp())
        self.stats.missiles = s['missiles']
        self.stats.missiles_awarded = s['missiles_awarded']
        self.stats.coins = s['coins']
        self.stats.items = s['items']
        self.stats.skills = s['skills']
        self.stats.armor_tier = s.get('armor_tier', None)
        self.stats.equipped_gems = s.get('equipped_gems', [None] * 5)
        if not isinstance(self.stats.equipped_gems, list) or len(self.stats.equipped_gems) < 5:
            self.stats.equipped_gems = [None] * 5
        self.stats.gem_storage = s.get('gem_storage', [])
        if not isinstance(self.stats.gem_storage, list):
            self.stats.gem_storage = []
        init_gem_id_counter(self.stats.equipped_gems, self.stats.gem_storage)
        self.stats.high_score = s['high_score']

        # --- Restore dynamic settings ---
        ss = data['settings']
        self.settings.ship_speed = min(ss['ship_speed'], self.settings.ship_speed_max)
        self.settings.bullet_speed = ss['bullet_speed']
        self.settings.alien_speed = min(ss['alien_speed'], self.settings.alien_speed_max)
        self.settings.bullet_allowed = ss['bullet_allowed']
        self.settings.bullet_damage = ss.get('bullet_damage',
                                             self.settings.bullet_damage_base)
        self.settings.missile_damage = ss.get('missile_damage',
                                              self.settings.missile_damage_base)

        # --- Restore ship ---
        sh = data['ship']
        self.ship.x = sh['x']
        self.ship.rect.x = int(self.ship.x)
        self.ship.rect.midbottom = self.ship.screen_rect.midbottom
        self.ship.invulnerable_frames = sh['invulnerable_frames']
        self.ship.moving_right = sh['moving_right']
        self.ship.moving_left = sh['moving_left']

        # --- Restore game state ---
        g = data['game']
        self.hit_cooldown = g['hit_cooldown']
        self.flashing_alien_pos = tuple(g['flashing_alien_pos']) \
            if g['flashing_alien_pos'] else None
        self.levelup_anim_frames = g['levelup_anim_frames']
        self.magnet_active = g['magnet_active']
        self.magnet_timer = g['magnet_timer']
        self._boss_secondary_burst = tuple(g['boss_secondary_burst']) \
            if g['boss_secondary_burst'] else None
        self.meteor_timer = g['meteor_timer']
        self.dive_timer = g['dive_timer']
        self.boss_warning_frames = g['boss_warning_frames']
        self.ship_death_frames = g['ship_death_frames']
        self.game_over_frames = g['game_over_frames']
        self.death_position = tuple(g['death_position']) \
            if g['death_position'] else None

        # --- Restore scoreboard ---
        self.sb.last_displayed_level = data['scoreboard']['last_displayed_level']

        # --- Restore background scroll position ---
        for i, bg_data in enumerate(data['backgrounds']):
            self.bg_instances[i].y1 = bg_data['y1']
            self.bg_instances[i].y2 = bg_data['y2']

        # --- Clear all entity groups ---
        self.bullets.empty()
        self.missiles.empty()
        self.aliens.empty()
        self.boss_bullets.empty()
        self.boss_missiles.empty()
        self.coins.empty()
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.particles.empty()
        self.boss = None
        self.flashing_alien = None

        e = data['entities']

        # --- Rebuild aliens ---
        aliens_list = []
        for a_data in e['aliens']:
            alien = Alien(self)
            alien.x = a_data['x']
            alien.y = a_data['y']
            alien.rect.x = int(alien.x)
            alien.rect.y = int(alien.y)
            alien.hp = a_data['hp']
            alien.state = a_data['state']
            alien.gather_offset = a_data['gather_offset']
            alien.cruise_y = a_data['cruise_y']
            dv_data = a_data['dive_velocity']
            alien.dive_velocity = pygame.math.Vector2(*dv_data) if dv_data else None
            alien.windup = a_data['windup']
            alien.flash_frames = a_data['flash_frames']
            self.aliens.add(alien)
            aliens_list.append(alien)

        flashing_id = g['flashing_alien_id']
        if flashing_id is not None and flashing_id < len(aliens_list):
            self.flashing_alien = aliens_list[flashing_id]

        # --- Rebuild boss ---
        if e['boss'] is not None:
            b_data = e['boss']
            boss = Boss(self)
            boss.x = b_data['x']
            boss.y = b_data['y']
            boss.rect.x = int(boss.x)
            boss.rect.y = int(boss.y)
            boss.hp = b_data['hp']
            boss.direction = b_data['direction']
            boss.fire_timer = b_data['fire_timer']
            boss.flash_frames = b_data['flash_frames']
            boss.dying = b_data['dying']
            boss.death_timer = b_data['death_timer']
            boss._death_exploded = b_data['_death_exploded']
            boss.summoned = b_data.get('summoned', False)
            boss.summoned2 = b_data.get('summoned2', False)
            boss.missile_timer = b_data.get('missile_timer', self.settings.boss_missile_interval)
            self.boss = boss

        # --- Rebuild bullets ---
        for b_data in e['bullets']:
            bullet = Bullet(self)
            bullet.y = b_data['y']
            bullet.rect.y = int(bullet.y)
            bullet.rect.x = b_data['x']
            self.bullets.add(bullet)

        # --- Rebuild missiles ---
        for m_data in e['missiles']:
            missile = Missile(self)
            missile.x = m_data['x']
            missile.y = m_data['y']
            missile.velocity = pygame.math.Vector2(m_data['vx'], m_data['vy'])
            missile.rect.center = (int(missile.x), int(missile.y))
            angle = math.degrees(
                math.atan2(-missile.velocity.y, missile.velocity.x)) - 90
            missile.image = pygame.transform.rotate(missile.base_image, angle)
            self.missiles.add(missile)

        # --- Rebuild boss bullets ---
        for b_data in e['boss_bullets']:
            bb = BossBullet(self, b_data['x'], b_data['y'])
            bb.y = b_data['y']
            bb.rect.y = int(bb.y)
            self.boss_bullets.add(bb)

        # --- Rebuild boss missiles ---
        for m_data in e.get('boss_missiles', []):
            bm = BossMissile(self, m_data['x'], m_data['y'])
            bm.x = m_data['x']
            bm.y = m_data['y']
            bm.velocity = pygame.math.Vector2(m_data['vx'], m_data['vy'])
            bm.rect.center = (int(bm.x), int(bm.y))
            self.boss_missiles.add(bm)

        # --- Rebuild coins ---
        for c_data in e['coins']:
            coin = Coin(self, c_data['x'], c_data['y'])
            coin.y = c_data['y']
            coin.rect.y = int(coin.y)
            coin.state = c_data['state']
            coin.hover_timer = c_data['hover_timer']
            coin.flash_timer = c_data['flash_timer']
            self.coins.add(coin)

        # --- Rebuild meteors ---
        for m_data in e['meteors']:
            meteor = Meteor(self)
            meteor.x = m_data['x']
            meteor.y = m_data['y']
            meteor.rect.x = int(meteor.x)
            meteor.rect.y = int(meteor.y)
            meteor.hp = m_data['hp']
            meteor.velocity_x = m_data['vx']
            meteor.velocity_y = m_data['vy']
            meteor.radius = m_data['radius']
            meteor.rotation = m_data['rotation']
            meteor.angle = m_data['angle']
            meteor.image = meteor._build_texture()
            self.meteors.add(meteor)

        # --- Rebuild meteor fragments ---
        for f_data in e['meteor_fragments']:
            frag = MeteorFragment(self, f_data['x'], f_data['y'])
            frag.x = f_data['x']
            frag.y = f_data['y']
            frag.rect.x = int(frag.x)
            frag.rect.y = int(frag.y)
            frag.hp = f_data['hp']
            frag.velocity_x = f_data['vx']
            frag.velocity_y = f_data['vy']
            frag.radius = f_data['radius']
            frag.lifetime = f_data['lifetime']
            frag.image = frag._build_texture()
            self.meteor_fragments.add(frag)

        # --- Rebuild scoreboard display ---
        self.sb.prep_score()
        self.sb.prep_missiles()
        self.sb.prep_level()
        self.sb.prep_coins()
        self.sb.check_high_score()

        # --- Double-check: score not overwritten by any intermediate step ---
        self.stats.score = s['score']
        self.stats.ship_hp = s.get('ship_hp', self.stats.max_hp)
        self.sb.prep_score()

        # Switch to game state
        self.state = GameState.PLAYING
        self.sound.set_bgm_volume(self.settings.bgm_volume)
        self.sound.play_level_bgm(self.stats.level)

    def _check_keydown_events(self, event):
        """Handle key press (routed by current state)"""
        # -------- All states --------
        if event.key == pygame.K_q:
            self._quit_game()

        # -------- MENU state --------
        elif self.state == GameState.MENU:
            if self._account_confirm:
                if event.key == pygame.K_ESCAPE:
                    self._account_confirm = False
            elif self.show_notifications:
                if event.key == pygame.K_ESCAPE:
                    self.show_notifications = False
                elif event.key == pygame.K_c:
                    self.notifications.clear()
                    self.show_notifications = False
            elif event.key == pygame.K_ESCAPE:
                self._quit_game()

        # -------- PLAYING state --------
        elif self.state == GameState.PLAYING:
            # Disable pause and game actions during death/fail/transition sequence
            is_dead = self.ship_death_frames > 0 or self.game_over_frames > 0 or self.in_transition
            if is_dead:
                return
            if event.key == pygame.K_ESCAPE:
                # Pause and clear movement flags
                self.ship.moving_right = False
                self.ship.moving_left = False
                self.firing = False
                self._fire_cooldown = 0
                self.save_disabled = False
                self.state = GameState.PAUSED
                self.sound.set_bgm_volume(self.settings.bgm_pause_volume)
            elif event.key == pygame.K_RIGHT:
                self.ship.moving_right = True
            elif event.key == pygame.K_LEFT:
                self.ship.moving_left = True
            elif event.key == pygame.K_SPACE:
                self.firing = True
                self._fire_bullet()
            elif event.key == pygame.K_e:
                self._fire_missile()
            elif event.key == pygame.K_m:
                self.previous_state = GameState.PLAYING
                self.state = GameState.SHOP
            elif event.key == pygame.K_n:
                self._activate_magnet()
            elif event.key == pygame.K_c:
                self._activate_clover()
            elif event.key == pygame.K_F5:
                self.save_game()
                self._notification_text = 'Game Saved!'
                self.save_notification_frames = 60

        # -------- PAUSED state --------
        elif self.state == GameState.PAUSED:
            if event.key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
                self.sound.set_bgm_volume(self.settings.bgm_volume)

        # -------- SHOP state --------
        elif self.state == GameState.SHOP:
            if event.key in (pygame.K_m, pygame.K_ESCAPE):
                self.state = self.previous_state

        # -------- TUTORIAL state --------
        elif self.state == GameState.TUTORIAL:
            if event.key == pygame.K_ESCAPE:
                self.state = GameState.MENU

        # -------- LEADERBOARD state --------
        elif self.state == GameState.LEADERBOARD:
            if event.key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def _check_keyup_events(self, event):
        """Handle key release (only movement keys in PLAYING)"""
        if self.state == GameState.PLAYING:
            if event.key == pygame.K_RIGHT:
                self.ship.moving_right = False
            elif event.key == pygame.K_LEFT:
                self.ship.moving_left = False
            elif event.key == pygame.K_SPACE:
                self.firing = False
                self._fire_cooldown = 0
        else:
            # Clear firing on key release regardless of state
            if event.key == pygame.K_SPACE:
                self.firing = False

    def _update_bullets(self):
        """Update bullet positions and remove off-screen bullets"""
        # Update bullet positions
        self.bullets.update()

        # Remove off-screen bullets
        for bullet in self.bullets.copy():
            if bullet.rect.bottom <= 0:
                self.bullets.remove(bullet)

        self._check_bullet_alien_collisions()
        self._check_bullet_boss_collisions()

    def _check_bullet_alien_collisions(self):
        """Handle bullet-alien collisions with crit (+ penetration)。"""
        pen_chance = self._get_pen_chance()
        collisions = pygame.sprite.groupcollide(self.aliens, self.bullets, False, False)
        for alien, bullet_list in collisions.items():
            total_damage = 0.0
            for bullet in bullet_list:
                dmg = self.settings.bullet_damage
                is_crit, crit_mult = self._roll_crit()
                if is_crit:
                    dmg *= crit_mult
                    self._create_crit_burst(alien.rect.center)
                    self.stats.crit_count += 1
                total_damage += dmg

                if pen_chance <= 0 or random.random() >= pen_chance:
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)

            if alien.take_damage(round(total_damage, 2)):
                self._create_alien_explosion(alien.rect.center)
                self._maybe_drop_coin(*alien.rect.center)
                self._maybe_drop_gem(*alien.rect.center)
                self.sound.play_explosion()
                self._award_points(
                    1, kill_count=0 if getattr(alien, 'summoned', False) else 1)
            else:
                self.sound.play_hurt()

        self._check_fleet_cleared()

    def _update_missiles(self):
        """Update missile positions and remove off-screen missiles"""
        self.missiles.update()

        # Remove off-screen missiles
        screen_rect = self.screen.get_rect()
        for missile in self.missiles.copy():
            if not screen_rect.colliderect(missile.rect):
                self.missiles.remove(missile)

        self._check_missile_alien_collisions()
        self._check_missile_boss_collisions()

    def _update_boss_bullets(self):
        """Update boss bullet positions and remove off-screen"""
        self.boss_bullets.update()
        for bullet in self.boss_bullets.copy():
            if bullet.rect.top > self.settings.screen_height:
                self.boss_bullets.remove(bullet)

    def _update_boss_missiles(self):
        """Update boss missile positions and remove off-screen"""
        self.boss_missiles.update()
        for missile in self.boss_missiles.copy():
            if (missile.rect.top > self.settings.screen_height + 40
                    or missile.rect.right < -40
                    or missile.rect.left > self.settings.screen_width + 40):
                self.boss_missiles.remove(missile)

    def _check_missile_alien_collisions(self):
        """Handle missile-alien collisions: AoE damage to aliens in blast radius"""
        collisions = pygame.sprite.groupcollide(self.missiles, self.aliens, True, False)
        for missile in collisions:
            self._explode_missile(missile.rect.center)

        self._check_fleet_cleared()

    def _explode_missile(self, center):
        """Damage aliens and boss in blast radius, spawn particles and score on kill"""
        # Large explosion particles at missile impact point
        self._create_missile_explosion(center)

        blast_center = pygame.math.Vector2(center)
        destroyed = 0
        summoned_destroyed = 0
        for alien in self.aliens.sprites():
            if blast_center.distance_to(alien.rect.center) <= self.settings.missile_blast_radius:
                dmg = self.settings.missile_damage
                is_crit, crit_mult = self._roll_crit()
                if is_crit:
                    dmg *= crit_mult
                    self._create_crit_burst(alien.rect.center)
                    self.stats.crit_count += 1
                if alien.take_damage(round(dmg, 2)):
                    self._create_alien_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self._maybe_drop_gem(*alien.rect.center)
                    destroyed += 1
                    if getattr(alien, 'summoned', False):
                        summoned_destroyed += 1
                    self.sound.play_explosion()
                else:
                    self.sound.play_hurt()
        # Also check if boss is in blast radius
        if self.boss is not None and self.boss.hp > 0:
            if blast_center.distance_to(self.boss.rect.center) <= self.settings.missile_blast_radius:
                dmg = self.settings.missile_damage
                is_crit, crit_mult = self._roll_crit()
                if is_crit:
                    dmg *= crit_mult
                    self._create_crit_burst(self.boss.rect.center)
                    self.stats.crit_count += 1
                if self.boss.take_damage(round(dmg, 2)):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    destroyed += 1
                    self.sound.play_explosion()
                else:
                    self.sound.play_hurt()
        if destroyed:
            self._award_points(destroyed, kill_count=destroyed - summoned_destroyed)

    def _award_points(self, alien_count, kill_count=None):
        """Award points by alien count and update displays.
        kill_count: kills added to progression (summoned aliens award score but no kills)."""
        self.stats.score += self.settings.alien_points * alien_count
        if kill_count is None:
            kill_count = alien_count
        self.stats.kills += kill_count
        self.sb.prep_score()
        self.sb.check_high_score()
        self._check_missile_award()
        self._check_level_up()

    def _check_missile_award(self):
        """Award missiles whenever score crosses a new multiple of missile_score_step"""
        earned = self.stats.score // self.settings.missile_score_step
        if earned > self.stats.missiles_awarded:
            self.stats.missiles += earned - self.stats.missiles_awarded
            self.stats.missiles_awarded = earned
            self.sb.prep_missiles()

    def _check_level_up(self):
        """Check if kills cross level threshold; if so, update scoreboard and start animation"""
        if self.stats.level > self.sb.last_displayed_level:
            self.sb.prep_level()
            self.levelup_anim_frames = 60   # 1-second animation
            self.sound.play_levelup()

    def _draw_levelup_animation(self):
        """Draw fading, expanding level-up text at screen center"""
        self.levelup_anim_frames -= 1
        ratio = self.levelup_anim_frames / 60

        # Calculate alpha (opaque first 80%, fade last 20%)
        alpha = 255 if ratio > 0.2 else int(255 * ratio / 0.2)

        # Calculate scale (1.0 -> 1.5 gradual enlargement)
        scale = 1.0 + (1 - ratio) * 0.5

        font = pygame.font.SysFont(None, int(72 * scale))
        level_str = f"Level {self.stats.level}!"
        text_image = font.render(level_str, True, (255, 215, 0))
        text_image.set_alpha(alpha)
        text_rect = text_image.get_rect(center=self.screen.get_rect().center)
        # Offset upward to avoid blocking center of gameplay
        text_rect.y -= 40
        self.screen.blit(text_image, text_rect)

    def _draw_boss_warning(self):
        """Boss entrance: red WARNING banner flash"""
        ratio = self.boss_warning_frames / self.settings.boss_warning_duration
        # Flash effect: toggle visibility every 15 frames
        flash_on = (self.boss_warning_frames // 15) % 2 == 0
        if not flash_on:
            return

        # Calculate alpha (decreasing over time)
        alpha = int(255 * ratio)
        scale = 1.0 + (1 - ratio) * 0.3

        font = pygame.font.SysFont(None, int(80 * scale))
        text = font.render("WARNING", True, (255, 30, 30))
        text.set_alpha(alpha)
        text_rect = text.get_rect(center=self.screen.get_rect().center)
        text_rect.y -= 60

        # Red background bar
        bar_w = text_rect.width + 80
        bar_h = text_rect.height + 30
        bar = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        bar.fill((180, 20, 20, min(alpha, 120)))
        bar_rect = bar.get_rect(center=self.screen.get_rect().center)
        bar_rect.y -= 60
        self.screen.blit(bar, bar_rect)

        self.screen.blit(text, text_rect)

    def _draw_fail_banner(self):
        """Game over: red FAIL banner fade-out"""
        ratio = self.game_over_frames / self.settings.fail_banner_duration
        alpha = 255 if ratio > 0.3 else int(255 * ratio / 0.3)
        scale = 1.0 + (1 - ratio) * 0.4

        # Semi-transparent dark overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, min(int(100 * ratio), 100)))
        self.screen.blit(overlay, (0, 0))

        font = pygame.font.SysFont(None, int(90 * scale))
        text = font.render("FAIL", True, (220, 40, 40))
        text.set_alpha(alpha)
        text_rect = text.get_rect(center=self.screen.get_rect().center)
        self.screen.blit(text, text_rect)

    def _draw_clover_flash(self):
        """Clover activated: green screen flash fade-out"""
        ratio = self.clover_flash_frames / self.settings.clover_flash_duration
        alpha = min(120, int(180 * ratio))
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((80, 255, 120, alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_shield(self):
        """Draw a pulsing golden sphere shield around the ship."""
        s = self.settings
        pulse = math.sin(pygame.time.get_ticks() * s.shield_pulse_speed * 0.01) * 0.25 + 0.7
        ship_center = self.ship.rect.center

        alpha = int(pulse * 160)
        surf = pygame.Surface((s.shield_outer_radius * 2 + 16, s.shield_outer_radius * 2 + 16),
                              pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2

        r, g, b = s.shield_color
        # Outer glow (thicker, brighter)
        alpha_outer = int(pulse * 100)
        pygame.draw.circle(surf, (r, g, b, alpha_outer), (cx, cy), s.shield_outer_radius + 6, 4)
        pygame.draw.circle(surf, (r, g, b, alpha_outer // 2), (cx, cy), s.shield_outer_radius, 2)

        # Inner shell (solid core)
        alpha_inner = int(pulse * 140)
        pygame.draw.circle(surf, (r, g, b, alpha_inner), (cx, cy), s.shield_inner_radius, 3)

        # Core fill (subtle)
        alpha_fill = int(pulse * 40)
        pygame.draw.circle(surf, (r, g, b, alpha_fill), (cx, cy), s.shield_inner_radius - 4)

        self.screen.blit(surf, (ship_center[0] - cx, ship_center[1] - cy))

    def _draw_near_death_vignette(self):
        """Draw a red gradient vignette at screen edges when HP is critical."""
        alpha = self.settings.vignette_max_alpha
        w, h = self.screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)

        for i in range(8):
            r = 200 + i * 20
            a = alpha - i * 6
            if a <= 0:
                break
            pygame.draw.rect(overlay, (160, 20, 20, a), (i * 3, i * 3, w - i * 6, h - i * 6), 3)

        self.screen.blit(overlay, (0, 0))

    def _draw_transition_overlay(self):
        """Draw transition cinematic overlay with visual effects."""
        s = self.settings
        screen_w = self.screen_rect.width
        screen_h = self.screen_rect.height
        color = self._transition_zone_color

        # Blackout fade (covers game scene)
        if hasattr(self, 'transition_blackout') and self.transition_blackout > 0:
            overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            alpha = int(self.transition_blackout * 255)
            overlay.fill((0, 0, 0, min(alpha, 255)))
            self.screen.blit(overlay, (0, 0))

        # Star streaks
        for st in self._trans_streaks:
            y1 = max(0, st['y'] - st['height'])
            y2 = min(screen_h, st['y'])
            streak_surf = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            pygame.draw.line(streak_surf,
                             (220, 230, 255, st['alpha']),
                             (st['x'], y1), (st['x'], y2), 2)
            self.screen.blit(streak_surf, (0, 0))

        # Engine trail particles
        for t in self._trans_trails:
            ratio = t['life'] / t['max_life']
            alpha = int(ratio * 200)
            size = int(t['size'] * ratio)
            if size < 1:
                continue
            trail_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(trail_surf, (*color, alpha),
                               (size, size), size)
            self.screen.blit(trail_surf,
                             (int(t['x']) - size, int(t['y']) - size))

        # Ship glow during hover
        if self.transition_stage == 'hover':
            glow_surf = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            cx = self.ship.rect.centerx
            cy = self.ship.rect.centery
            for r in range(60, 20, -8):
                alpha = int(15 * (1 - (r - 20) / 40))
                if alpha <= 0:
                    continue
                pygame.draw.circle(glow_surf, (*color, alpha),
                                   (int(cx), int(cy)), r)
            self.screen.blit(glow_surf, (0, 0))

        # White flash on warp entry
        if self._transition_flash_frames > 0:
            ratio = self._transition_flash_frames / s.transition_flash_frames
            flash = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(ratio * 200)))
            self.screen.blit(flash, (0, 0))

        # Zone entry text
        if self.transition_stage in ('hover', 'exit'):
            ratio = min(1.0, max(0, self.transition_frames / s.transition_hover_frames))
            if self.transition_stage == 'exit':
                ratio = 0.3
            alpha = int(ratio * 220)
            scale = 1.0 + (1 - ratio) * 0.15

            glow_font = pygame.font.SysFont(None, int(58 * scale))
            glow_text = glow_font.render(self.transition_level_text, True,
                                         (*color, min(alpha, 80)))
            glow_rect = glow_text.get_rect(
                center=(screen_w // 2 + 2, screen_h // 2 - 80 + 2))
            self.screen.blit(glow_text, glow_rect)

            font = pygame.font.SysFont(None, int(56 * scale))
            text_img = font.render(self.transition_level_text, True, color)
            text_img.set_alpha(alpha)
            text_rect = text_img.get_rect(
                center=(screen_w // 2, screen_h // 2 - 80))
            self.screen.blit(text_img, text_rect)

    def _draw_update_banner(self):
        """Draw an 'Update available' banner on the main menu."""
        ver, url = self._update_available
        font = pygame.font.SysFont(None, 24)
        text = f"Update available: {ver}  -  Click to download"
        img = font.render(text, True, (255, 215, 0))
        self._update_banner_rect = img.get_rect()
        self._update_banner_rect.centerx = self.screen.get_rect().centerx
        self._update_banner_rect.bottom = self.screen.get_rect().bottom - 28

        # Subtle background strip
        bg = pygame.Surface((img.get_width() + 30, img.get_height() + 12), pygame.SRCALPHA)
        bg.fill((30, 30, 50, 180))
        bg_rect = bg.get_rect(center=self._update_banner_rect.center)
        self.screen.blit(bg, bg_rect)
        self.screen.blit(img, (bg_rect.x + 15, bg_rect.y + 6))

    # ------------------------------------------------------------------
    # Network: upload stats / fetch leaderboard
    # ------------------------------------------------------------------

    def _upload_current_stats(self):
        """Upload current stats to server (silent: non-blocking on failure)"""
        token = self.stats.player_data.get_token()
        if not token:
            return
        try:
            result = self.web_client.upload_stats(
                token,
                score=self.stats.score,
                level=self.stats.level,
                kills=self.stats.kills,
                coins=self.stats.coins,
            )
            if result.get('status') == 'error':
                self._show_notification(result.get('message', 'Upload failed'))
        except Exception:
            self._show_notification('Network error, cached locally')

    def _fetch_leaderboard(self):
        """Fetch leaderboard data from server"""
        try:
            self.leaderboard_data = self.web_client.get_leaderboard()
        except Exception:
            self.leaderboard_data = {'status': 'error', 'message': 'Could not connect to server'}

    def _start_update_check(self):
        """Launch a daemon thread to check GitHub for newer releases."""
        def _check():
            new_ver, url = self.web_client.check_update(GAME_VERSION)
            if new_ver:
                self._update_available = (new_ver, url)
                self._show_notification(f"New version {new_ver} available!")
        threading.Thread(target=_check, daemon=True).start()

    def _show_notification(self, message):
        """Show notification at screen bottom and log to history"""
        self._notification_text = message
        self.save_notification_frames = 90
        import time
        self.notifications.append({
            'text': message,
            'time': time.strftime('%H:%M:%S'),
        })
        if len(self.notifications) > 20:
            self.notifications = self.notifications[-20:]

    def _draw_leaderboard(self):
        """Draw leaderboard overlay"""
        # Semi-transparent overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        font_title = pygame.font.SysFont(None, 48)
        font_header = pygame.font.SysFont(None, 26)
        font_row = pygame.font.SysFont(None, 24)
        font_hint = pygame.font.SysFont(None, 20)

        gold = (255, 215, 0)
        white = (255, 255, 255)
        gray = (160, 160, 180)
        red = (220, 80, 80)

        screen_rect = self.screen.get_rect()
        screen_w = screen_rect.width
        title = font_title.render("LEADERBOARD", True, gold)
        title_rect = title.get_rect(centerx=screen_w // 2, top=40)
        self.screen.blit(title, title_rect)

        data = self.leaderboard_data
        if data is None or data.get('status') == 'error':
            msg = (data or {}).get('message', 'Loading...')
            err = font_row.render(msg, True, red)
            err_rect = err.get_rect(center=screen_rect.center)
            self.screen.blit(err, err_rect)
        else:
            entries = data.get('leaderboard', [])
            if not entries:
                empty = font_row.render("No player data yet", True, gray)
                self.screen.blit(empty, empty.get_rect(center=screen_rect.center))
            else:
                # Header
                y = 105
                header_texts = [("RANK", 60), ("NAME", 260), ("SCORE", 100), ("LEVEL", 60)]
                x_start = screen_w // 2 - 240
                for h_text, h_width in header_texts:
                    h = font_header.render(h_text, True, gold)
                    self.screen.blit(h, (x_start, y))
                    x_start += h_width

                # Separator line
                y += 30
                pygame.draw.line(self.screen, (60, 60, 80),
                                 (screen_w // 2 - 240, y),
                                 (screen_w // 2 + 240, y), 1)

                # Row
                for i, entry in enumerate(entries):
                    y += 32
                    if y > screen_rect.height - 60:
                        break

                    rank_color = gold if i < 3 else white
                    rank = font_row.render(f"#{i + 1}", True, rank_color)
                    name = font_row.render(
                        entry.get('username', '?')[:16], True, white)
                    score = font_row.render(
                        str(entry.get('score', 0)), True, white)
                    level = font_row.render(
                        str(entry.get('level', 1)), True, gray)

                    x_start = screen_w // 2 - 240
                    self.screen.blit(rank, (x_start, y))
                    x_start += 60
                    self.screen.blit(name, (x_start, y))
                    x_start += 260
                    self.screen.blit(score, (x_start, y))
                    x_start += 100
                    self.screen.blit(level, (x_start, y))

                # Bottom stats
                total = data.get('total_players', 0)
                highest = data.get('highest_score', 0)
                stats = font_hint.render(
                    f"Total Players: {total}    Highest Score: {highest:,}",
                    True, gray)
                stats_rect = stats.get_rect(
                    centerx=screen_w // 2, bottom=screen_rect.bottom - 25)
                self.screen.blit(stats, stats_rect)

        # Hint
        hint = font_hint.render("Press ESC to return", True, gray)
        hint_rect = hint.get_rect(
            centerx=screen_w // 2, bottom=screen_rect.bottom - 55)
        self.screen.blit(hint, hint_rect)

    def _draw_notification_bell(self):
        """Draw notification bell at top-right of main menu"""
        bell_x = self.screen.get_rect().right - 55
        bell_y = 15
        bell_r = 18
        # Bell body
        pygame.draw.circle(self.screen, (200, 160, 60), (bell_x, bell_y + bell_r), bell_r)
        pygame.draw.circle(self.screen, (240, 200, 80), (bell_x, bell_y + bell_r), bell_r - 4)
        # Bell bottom
        pygame.draw.rect(self.screen, (180, 140, 50),
                         (bell_x - 8, bell_y + bell_r - 8, 16, 6), border_radius=2)
        # Clapper
        pygame.draw.circle(self.screen, (140, 100, 30),
                           (bell_x, bell_y + bell_r + 8), 3)

        # Unread badge
        if self.notifications:
            badge = self._font_small_bell.render(str(len(self.notifications)),
                                                 True, (255, 255, 255))
            badge_bg = badge.get_rect()
            badge_bg.center = (bell_x + 14, bell_y + 4)
            badge_bg = badge_bg.inflate(10, 6)
            pygame.draw.rect(self.screen, (220, 50, 50), badge_bg, border_radius=8)
            self.screen.blit(badge, (badge_bg.x + 5, badge_bg.y + 1))

        return pygame.Rect(bell_x - bell_r, bell_y, bell_r * 2, bell_r * 2 + 15)

    def _draw_account_gear(self):
        """Draw gear button below notification bell (switch account)"""
        gx = self.screen_rect.right - 55
        gy = 88
        r = 13
        color = (165, 165, 175)

        # Teeth (8 small circles around the gear)
        for i in range(8):
            angle = math.radians(i * 45)
            tx = gx + int(math.cos(angle) * (r + 4))
            ty = gy + int(math.sin(angle) * (r + 4))
            pygame.draw.circle(self.screen, color, (tx, ty), 4)

        # Gear body
        pygame.draw.circle(self.screen, color, (gx, gy), r)
        pygame.draw.circle(self.screen, (75, 75, 92), (gx, gy), r - 4)
        # Center hole
        pygame.draw.circle(self.screen, (215, 215, 225), (gx, gy), 4)

        return pygame.Rect(gx - r - 6, gy - r - 6, (r + 6) * 2, (r + 6) * 2)

    def _draw_notifications_panel(self):
        """Draw notification panel overlay"""
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        screen_rect = self.screen.get_rect()
        panel_w, panel_h = 460, 360
        panel = pygame.Surface((panel_w, panel_h))
        panel.fill((30, 35, 55))
        panel_rect = panel.get_rect(center=screen_rect.center)
        self.screen.blit(panel, panel_rect)

        px, py = panel_rect.topleft
        cx = px + panel_w // 2

        font_title = self._font_title_bell
        title = font_title.render("Notifications", True, (255, 215, 0))
        self.screen.blit(title, (cx - title.get_width() // 2, py + 15))

        font_row = self._font_row_bell

        if not self.notifications:
            empty = font_row.render("No notifications", True, (140, 140, 160))
            self.screen.blit(empty, empty.get_rect(center=panel_rect.center))
        else:
            y = py + 55
            for note in reversed(self.notifications[-10:]):
                time_str = font_row.render(note['time'], True, (120, 120, 140))
                text_str = font_row.render(note['text'][:42], True, (220, 220, 220))
                self.screen.blit(time_str, (px + 25, y))
                self.screen.blit(text_str, (px + 100, y))
                y += 26
                if y > py + panel_h - 55:
                    break

        # Close / Clear buttons
        hint = font_row.render("Click anywhere to close  |  C = Clear all",
                               True, (140, 140, 160))
        hint_rect = hint.get_rect(centerx=cx, bottom=py + panel_h - 12)
        self.screen.blit(hint, hint_rect)

    def _draw_save_notification(self):
        """Show notification at screen bottom, fading"""
        ratio = self.save_notification_frames / 60
        alpha = 255 if ratio > 0.5 else int(255 * ratio / 0.5)

        font = pygame.font.SysFont(None, 30)
        msg = self._notification_text or "Game Saved!"
        text = font.render(msg, True, (100, 220, 100))
        text.set_alpha(alpha)
        text_rect = text.get_rect()
        text_rect.centerx = self.screen.get_rect().centerx
        text_rect.bottom = self.screen.get_rect().bottom - 20
        self.screen.blit(text, text_rect)

    def _check_missile_boss_collisions(self):
        """Check if missile explosion hits boss"""
        if self.boss is None or self.boss.hp <= 0:
            return
        for missile in self.missiles.sprites():
            if missile.rect.colliderect(self.boss.rect):
                dmg = self.settings.missile_damage
                is_crit, crit_mult = self._roll_crit()
                if is_crit:
                    dmg *= crit_mult
                    self._create_crit_burst(missile.rect.center)
                    self.stats.crit_count += 1
                if self.boss.take_damage(round(dmg, 2)):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
                else:
                    self.sound.play_hurt()
                self.missiles.remove(missile)
                self._check_fleet_cleared()
                break

    def _check_bullet_boss_collisions(self):
        """Check if bullets hit boss"""
        if self.boss is None or self.boss.hp <= 0:
            return
        for bullet in self.bullets.sprites():
            if bullet.rect.colliderect(self.boss.rect):
                self.bullets.remove(bullet)
                dmg = self.settings.bullet_damage
                is_crit, crit_mult = self._roll_crit()
                if is_crit:
                    dmg *= crit_mult
                    self._create_crit_burst(bullet.rect.center)
                    self.stats.crit_count += 1
                if self.boss.take_damage(round(dmg, 2)):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
                    self._check_fleet_cleared()
                else:
                    self.sound.play_hurt()
                break  # Only process one hit per frame

    def _check_boss_bullet_ship_collisions(self):
        """Check if boss bullets hit the ship"""
        if self.ship.invulnerable_frames > 0:
            return
        for bullet in self.boss_bullets.sprites():
            if bullet.rect.colliderect(self.ship.rect):
                self.boss_bullets.remove(bullet)
                self._ship_hit(self.settings.boss_bullet_damage)
                break

    def _check_boss_missile_ship_collisions(self):
        """Check if boss missiles hit the ship"""
        if self.ship.invulnerable_frames > 0:
            return
        for missile in self.boss_missiles.sprites():
            if missile.rect.colliderect(self.ship.rect):
                self.boss_missiles.remove(missile)
                self._create_explosion(missile.rect.center)
                self._ship_hit(self.settings.boss_missile_damage)
                break

    def _check_fleet_cleared(self):
        """Start new wave after fleet (or boss) is eliminated"""
        if self.boss_warning_frames > 0:
            return
        if self.boss is not None:
            # Boss level: when boss HP reaches 0 enters death animation, clears level after
            if self.boss.dying and self.boss.death_timer <= 0:
                # Trigger explosions and sound effects
                self.sound.play_boss_destroy()
                self._create_boss_explosion(self.boss.rect.center)
                self._maybe_drop_coin(*self.boss.rect.center)
                self._drop_gem(*self.boss.rect.center)
                self.boss.kill()
                self.boss = None
                # Boss kill reward: supplement score and kills to exit level
                self.stats.score += self.settings.boss_points
                threshold = self.stats.level * self.settings.kills_per_level
                if self.stats.kills < threshold:
                    self.stats.kills = threshold
                self.sb.prep_score()
                self.sb.check_high_score()
                self._check_missile_award()
                self._check_level_up()
                self.bullets.empty()
                self.boss_bullets.empty()
                self.boss_missiles.empty()
                self.aliens.empty()  # Clear summoned fleet alongside boss
                if self._maybe_switch_level_bgm():
                    return
                self._create_fleet()
                self.settings.increase_speed()
        elif not self.aliens:
            # Normal level: all aliens dead clears level
            self.bullets.empty()
            if self._maybe_switch_level_bgm():
                return
            self._create_fleet()
            self.settings.increase_speed()


    def _fire_bullet(self):
        """Create a bullet and add to bullets group"""
        if len(self.bullets) < self.settings.bullet_allowed:
            new_bullet = Bullet(self)
            self.bullets.add(new_bullet)
            self.sound.play_shoot()

    def _fire_missile(self):
        """If missile stock remains, fire a homing missile"""
        if self.state == GameState.PLAYING and self.stats.missiles > 0:
            self.missiles.add(Missile(self))
            self.stats.missiles -= 1
            self.sound.play_missile()
            self.sb.prep_missiles()

    def _create_fleet(self):
        """Randomly scatter an alien fleet at top (boss levels only spawn boss)"""
        # Boss level: every 5 levels, show warning banner then spawn boss
        if self.stats.level % 5 == 0:
            self.boss_warning_frames = self.settings.boss_warning_duration
            self.sound.play_alarm()
        else:
            self.boss = None
            alien = Alien(self)
            alien_width = alien.rect.width
            for _ in range(self.settings.aliens_per_wave):
                x_position = random.randint(0, self.settings.screen_width - alien_width)
                y_position = random.randint(self.settings.alien_spawn_y_min,
                                            self.settings.alien_spawn_y_max)
                self._create_alien(x_position, y_position)

        # Reset dive scheduler timer at start of each wave
        self.dive_timer = self.settings.alien_dive_cooldown

    def _create_alien(self,x_position, y_position):
        """Create an alien at specified position"""
        new_alien = Alien(self)
        new_alien.x = float(x_position)
        new_alien.y = float(y_position)
        new_alien.rect.x = x_position
        new_alien.rect.y = y_position
        self.aliens.add(new_alien)
        return new_alien

    def _summon_boss_fleet(self):
        """Boss summon: scatter a full alien wave at the top (like a normal wave)."""
        s = self.settings
        alien = Alien(self)
        alien_width = alien.rect.width
        for _ in range(s.aliens_per_wave):
            x_position = random.randint(0, s.screen_width - alien_width)
            y_position = random.randint(s.alien_spawn_y_min, s.alien_spawn_y_max)
            a = self._create_alien(x_position, y_position)
            a.summoned = True  # Summoned aliens don't count toward level kills
        self.dive_timer = s.alien_dive_cooldown

    def _activate_magnet(self):
        """Activate magnet item"""
        if self.stats.items.get('magnet', 0) > 0 and not self.magnet_active:
            self.stats.items['magnet'] -= 1
            self.magnet_active = True
            self.magnet_timer = self.settings.magnet_duration
            self.stats.save_player_data()

    def _activate_clover(self):
        """Activate clover: push aliens, meteors, boss bullets upward (not boss)"""
        if self.state != GameState.PLAYING:
            return
        if self.stats.items.get('clover', 0) <= 0:
            return
        self.stats.items['clover'] -= 1
        self.stats.save_player_data()
        self._do_clover_effect()

    def _do_clover_effect(self):
        """Start clover effect: push animation + green flash"""
        self.clover_push_frames = self.settings.clover_push_duration
        self.clover_flash_frames = self.settings.clover_flash_duration
        self.sound.play_levelup()

    def _update_clover_push(self):
        """Push affected entities upward each frame (skip normal AI/movement)"""
        push_speed = self.settings.clover_push_speed
        for alien in self.aliens.sprites():
            alien.y -= push_speed
            alien.rect.y = int(alien.y)
        for meteor in self.meteors.sprites():
            meteor.y -= push_speed
            meteor.rect.y = int(meteor.y)
        for frag in self.meteor_fragments.sprites():
            frag.y -= push_speed
            frag.rect.y = int(frag.y)
        for bullet in self.boss_bullets.sprites():
            bullet.y -= push_speed
            bullet.rect.y = int(bullet.y)
        for missile in self.boss_missiles.sprites():
            missile.y -= push_speed
            missile.rect.y = int(missile.y)

        self.clover_push_frames -= 1
        if self.clover_push_frames <= 0:
            target_y = self.settings.clover_teleport_y
            for alien in self.aliens.sprites():
                alien.y = float(target_y)
                alien.rect.y = int(alien.y)
                alien.state = 'swarm'
                alien.dive_velocity = None
                alien.windup = 0
            for meteor in self.meteors.sprites():
                meteor.y = float(target_y)
                meteor.rect.y = int(meteor.y)
            for frag in self.meteor_fragments.sprites():
                frag.y = float(target_y)
                frag.rect.y = int(frag.y)
            for bullet in self.boss_bullets.sprites():
                bullet.y = float(target_y)
                bullet.rect.y = int(bullet.y)
            for missile in self.boss_missiles.sprites():
                missile.y = float(target_y)
                missile.rect.y = int(missile.y)

    def _update_magnet(self):
        """Update magnet state: countdown + attract nearby coins"""
        if not self.magnet_active:
            return
        self.magnet_timer -= 1
        if self.magnet_timer <= 0:
            self.magnet_active = False
            return
        # Coins within radius fly toward ship
        ship_center = pygame.math.Vector2(self.ship.rect.center)
        for coin in self.coins.sprites():
            dist = ship_center.distance_to(coin.rect.center)
            if dist <= self.settings.magnet_pickup_radius:
                # Coin flies toward ship
                direction = ship_center - pygame.math.Vector2(coin.rect.center)
                if direction.length_squared() > 0:
                    direction.normalize_ip()
                    coin.y += direction.y * 5
                    coin.rect.y = int(coin.y)
                    coin.rect.x += int(direction.x * 5)

    def _check_coin_pickup(self):
        """Check if ship picked up coins"""
        picked = pygame.sprite.spritecollide(self.ship, self.coins, True)
        if picked:
            self.stats.coins += len(picked)
            self.sb.prep_coins()

    def _maybe_drop_coin(self, x, y):
        """Drop coin at position with probability"""
        if random.random() < self.settings.coin_drop_rate:
            self.coins.add(Coin(self, x, y))

    def _maybe_drop_gem(self, x, y):
        """Drop gem on alien kill (very low chance)."""
        if random.random() < self.settings.gem_alien_drop_rate:
            gem_data = generate_gem(self.settings)
            self.gems.add(GemPickup(self, x, y, gem_data))

    def _drop_gem(self, x, y):
        """Guaranteed gem drop (boss kill)."""
        for _ in range(self.settings.gem_boss_drop_count):
            gem_data = generate_gem(self.settings)
            self.gems.add(GemPickup(self, x, y, gem_data))

    def _check_gem_pickup(self):
        """Check if ship picked up gems."""
        picked = pygame.sprite.spritecollide(self.ship, self.gems, True)
        for gem_sprite in picked:
            self.stats.gem_storage.append(gem_sprite.gem_data)
            self.stats.save_player_data()

    # ------------------------------------------------------------------
    # Meteor system
    # ------------------------------------------------------------------

    def _spawn_meteor(self):
        """Spawn new meteor at top when timer reaches 0"""
        self.meteor_timer -= 1
        if self.meteor_timer <= 0:
            self.meteors.add(Meteor(self))
            self.meteor_timer = self.settings.meteor_spawn_interval

    def _update_meteor_collisions(self, skip_ship=False):
        """Check meteor and fragment collisions with all entities"""
        s = self.settings

        # ---- Meteor <-> Ship ----
        if not skip_ship and self.ship.invulnerable_frames <= 0:
            hit = pygame.sprite.spritecollideany(self.ship, self.meteors)
            if hit:
                self._meteor_break(hit)
                self._ship_hit(s.meteor_damage)

        # ---- Fragment <-> Ship ----
        if not skip_ship and self.ship.invulnerable_frames <= 0:
            hit_frag = pygame.sprite.spritecollideany(self.ship, self.meteor_fragments)
            if hit_frag:
                hit_frag.kill()
                self._ship_hit(s.meteor_fragment_damage)

        # ---- Meteor + Fragment <-> Alien ----
        for meteor in self.meteors:
            collisions = pygame.sprite.spritecollide(meteor, self.aliens, False)
            for alien in collisions:
                self._meteor_break(meteor)
                if alien.take_damage(s.meteor_alien_damage):
                    self._create_alien_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self.sound.play_explosion()
                    self._award_points(
                        1, kill_count=0 if getattr(alien, 'summoned', False) else 1)
                else:
                    self.sound.play_hurt()
                break  # Meteor destroyed, break inner loop
            else:
                continue
            break  # Meteor destroyed, break outer loop

        for frag in self.meteor_fragments:
            collisions = pygame.sprite.spritecollide(frag, self.aliens, False)
            for alien in collisions:
                frag.kill()
                if alien.take_damage(s.meteor_fragment_damage):
                    self._create_alien_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self.sound.play_explosion()
                    self._award_points(
                        1, kill_count=0 if getattr(alien, 'summoned', False) else 1)
                else:
                    self.sound.play_hurt()
                break

        # ---- Meteor + Fragment <-> Boss ----
        if self.boss is not None and not self.boss.dying:
            for meteor in self.meteors:
                if meteor.rect.colliderect(self.boss.rect):
                    self._meteor_break(meteor)
                    self.boss.take_damage(s.meteor_boss_damage)
                    self.sound.play_hurt()
                    break

            for frag in self.meteor_fragments:
                if frag.rect.colliderect(self.boss.rect):
                    frag.kill()
                    self.boss.take_damage(s.meteor_fragment_damage)
                    self.sound.play_hurt()
                    break

        # ---- Meteor <-> Bullet ----
        for meteor in self.meteors:
            bullet_hits = pygame.sprite.spritecollide(meteor, self.bullets, True)
            if bullet_hits and meteor.take_damage(s.bullet_damage * len(bullet_hits)):
                self._meteor_break(meteor)
                self.stats.score += s.meteor_points
                self.sb.prep_score()
                self.sb.check_high_score()

        # ---- Fragment <-> Bullet ----
        pygame.sprite.groupcollide(
            self.meteor_fragments, self.bullets, True, True)

        # ---- Meteor <-> Missile explosion ----
        for missile in self.missiles:
            for meteor in self.meteors:
                if missile.rect.colliderect(meteor.rect):
                    if meteor.take_damage(s.missile_damage):
                        self._meteor_break(meteor)
                        self.stats.score += s.meteor_points
                        self.sb.prep_score()
                        self.sb.check_high_score()

    def _meteor_break(self, meteor):
        """Meteor shatter: spawn fragments + particle sparks + sound"""
        cx, cy = meteor.rect.center
        s = self.settings

        # Spawn fragments
        for _ in range(s.meteor_fragment_count):
            self.meteor_fragments.add(MeteorFragment(self, cx, cy))

        # Particle sparks
        rock_colors = [(180, 140, 100), (150, 120, 80), (200, 160, 120), (120, 90, 60)]
        for _ in range(s.particle_count):
            p = Particle(self, cx, cy,
                         size_mult=1.5, speed_mult=1.2,
                         colors=rock_colors)
            self.particles.add(p)

        self.sound.play_explosion()
        meteor.kill()

    # ------------------------------------------------------------------
    # Explosions
    # ------------------------------------------------------------------

    def _create_explosion(self, position):
        """Create explosion particles at position (for bullet kills)"""
        for _ in range(self.settings.particle_count):
            particle = Particle(self, position[0], position[1])
            self.particles.add(particle)

    def _create_alien_explosion(self, position):
        """Create blue/cyan explosion particles for alien deaths (distinct from crit gold)."""
        for _ in range(self.settings.particle_count):
            particle = Particle(self, position[0], position[1],
                                colors=self.settings.alien_particle_colors)
            self.particles.add(particle)

    def _create_crit_burst(self, position):
        """Crit hit effect: golden spark particles + expanding shockwave ring."""
        s = self.settings
        for _ in range(s.crit_particle_count):
            p = Particle(self, position[0], position[1],
                         size_mult=s.crit_particle_size_mult,
                         speed_mult=s.crit_particle_speed_mult,
                         lifetime_mult=s.crit_particle_lifetime_mult,
                         colors=s.crit_particle_colors)
            self.particles.add(p)
        self._crit_rings.append({
            'x': int(position[0]), 'y': int(position[1]),
            'radius': 4.0, 'life': s.crit_ring_lifetime,
            'max_life': s.crit_ring_lifetime,
        })

    def _update_crit_rings(self):
        """Grow radius and decay life of crit shockwave rings."""
        s = self.settings
        for ring in self._crit_rings[:]:
            ring['life'] -= 1
            prog = 1.0 - ring['life'] / ring['max_life']
            ring['radius'] = 4.0 + (s.crit_ring_max_radius - 4.0) * prog
            if ring['life'] <= 0:
                self._crit_rings.remove(ring)

    def _draw_crit_rings(self):
        """Draw crit shockwave rings (fading golden outline)."""
        s = self.settings
        for ring in self._crit_rings:
            ratio = ring['life'] / ring['max_life']
            alpha = int(ratio * 220)
            r = int(ring['radius'])
            if r < 1 or alpha <= 0:
                continue
            size = r * 2 + 6
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*s.crit_ring_color, alpha),
                               (size // 2, size // 2), r, 2)
            self.screen.blit(surf,
                             (ring['x'] - size // 2, ring['y'] - size // 2))

    def _create_missile_explosion(self, position):
        """Create large explosion particles at missile impact"""
        s = self.settings
        for _ in range(s.missile_particle_count):
            p = Particle(self, position[0], position[1],
                         size_mult=s.missile_particle_size_mult,
                         speed_mult=s.missile_particle_speed_mult,
                         colors=s.missile_particle_colors)
            self.particles.add(p)

    def _create_boss_explosion(self, position):
        """Boss kill explosion: main blast + delayed second wave"""
        s = self.settings
        # Main explosion
        for _ in range(s.boss_particle_count):
            p = Particle(self, position[0], position[1],
                         size_mult=s.boss_particle_size_mult,
                         speed_mult=s.boss_particle_speed_mult,
                         lifetime_mult=s.boss_particle_lifetime_mult,
                         colors=s.boss_particle_colors)
            self.particles.add(p)
        # Record delayed second wave
        self._boss_secondary_burst = (position[0], position[1],
                                       s.boss_secondary_delay)

    def _active_bg(self):
        """Return active scrolling bg by level (earth:1-10, moon:11-20, space:21-30, cycles every 30)"""
        idx = ((self.stats.level - 1) // 10) % 3
        return self.bg_instances[idx]

    def _maybe_switch_level_bgm(self):
        """Switch BGM and trigger transition cinematic if zone changed.
        Returns True if a transition was started."""
        old = self._last_bg_instance
        self.sound.play_level_bgm(self.stats.level)
        new = self._active_bg()
        self._last_bg_instance = new
        if old is not None and old is not new:
            zones = ['Earth', 'Moon', 'Space']
            idx = ((self.stats.level - 1) // 10) % 3
            self.transition_level_text = f"Entering {zones[idx]} Orbit"
            self._start_transition()
            return True
        return False

    def _start_transition(self):
        """Begin the level-transition cinematic."""
        self.in_transition = True
        self.transition_stage = 'rise'
        self.transition_frames = self.settings.transition_rise_frames
        self._transition_ship_start_y = self.ship.rect.y
        self._transition_center_y = self.screen_rect.centery
        self._transition_flash_frames = 0
        self._transition_trail_timer = 0
        self._trans_trails = []
        self._trans_streaks = []
        self._transition_zone_color = {
            'Earth': (80, 200, 220),
            'Moon': (200, 200, 210),
            'Space': (140, 120, 240),
        }.get(self._transition_zone_name(), (200, 220, 255))

    def _transition_zone_name(self):
        """Get the zone name for the current transition."""
        zones = ['Earth', 'Moon', 'Space']
        idx = ((self.stats.level - 1) // 10) % 3
        return zones[idx]

    def _update_transition(self):
        """Advance the transition cinematic one frame."""
        s = self.settings
        self.transition_frames -= 1

        if self.transition_stage == 'rise':
            prog = 1.0 - self.transition_frames / s.transition_rise_frames
            target_y = self._transition_center_y
            self.ship.rect.y = int(self._transition_ship_start_y
                                   + (target_y - self._transition_ship_start_y) * prog)
            self._transition_spawn_trail()
            self._transition_update_trails()
            if self.transition_frames <= 0:
                self.transition_stage = 'hover'
                self.transition_frames = s.transition_hover_frames

        elif self.transition_stage == 'hover':
            bob = math.sin(self.transition_frames * 0.15) * 3
            self.ship.rect.y = int(self._transition_center_y + bob)
            self._transition_update_trails()
            if self.transition_frames <= 0:
                self.transition_stage = 'exit'
                self.transition_frames = s.transition_exit_frames
                self.ship.rect.centerx = self.screen_rect.centerx

        elif self.transition_stage == 'exit':
            self.ship.rect.y -= s.transition_ship_exit_speed
            self.transition_blackout = 1.0 - self.transition_frames / s.transition_exit_frames
            self._transition_spawn_trail()
            self._transition_update_trails()
            self._transition_spawn_streaks()
            self._transition_update_streaks()
            if self.transition_frames <= 0:
                self.transition_stage = 'enter'
                self.transition_frames = s.transition_enter_frames
                self.ship.rect.centerx = self.screen_rect.centerx
                self.ship.rect.bottom = self.screen_rect.height + 20
                self.bullets.empty()
                self.missiles.empty()
                self.aliens.empty()
                self.boss_bullets.empty()
                self.boss_missiles.empty()
                self._transition_flash_frames = s.transition_flash_frames
                self._trans_trails.clear()
                self._trans_streaks.clear()

        elif self.transition_stage == 'enter':
            self.transition_blackout = max(0, self.transition_frames / s.transition_enter_frames)
            prog = 1.0 - self.transition_frames / s.transition_enter_frames
            self.ship.rect.y = int((self.screen_rect.height + 20)
                                   + (self._transition_center_y - (self.screen_rect.height + 20)) * prog)
            self._transition_spawn_trail()
            self._transition_update_trails()
            self._transition_update_streaks()
            if self._transition_flash_frames > 0:
                self._transition_flash_frames -= 1
            if self.transition_frames <= 0:
                self.in_transition = False
                self.transition_stage = ''
                self.transition_blackout = 0
                self.firing = False
                self._fire_cooldown = 0
                self.ship.center_ship()
                self._create_fleet()
                self.settings.increase_speed()

    def _transition_spawn_trail(self):
        """Spawn engine trail particles behind the ship."""
        self._transition_trail_timer -= 1
        if self._transition_trail_timer > 0:
            return
        self._transition_trail_timer = self.settings.transition_trail_interval

        cx = self.ship.rect.centerx
        cy = self.ship.rect.bottom - 4
        for _ in range(2):
            trail = {
                'x': cx + random.uniform(-6, 6),
                'y': cy + random.uniform(-2, 6),
                'life': random.randint(12, 22),
                'max_life': 22,
                'size': random.randint(2, 5),
            }
            self._trans_trails.append(trail)

    def _transition_update_trails(self):
        """Decay and remove engine trail particles."""
        for t in self._trans_trails[:]:
            t['life'] -= 1
            t['y'] += random.uniform(-0.5, 0.8)
            if self.transition_stage == 'exit':
                t['y'] += random.uniform(1.0, 3.0)
            if t['life'] <= 0:
                self._trans_trails.remove(t)

    def _transition_spawn_streaks(self):
        """Spawn vertical star streaks during warp ascent."""
        if random.random() < 0.5:
            return
        screen_w = self.screen_rect.width
        streak = {
            'x': random.randint(20, screen_w - 20),
            'y': random.randint(-80, -10),
            'height': random.randint(40, 150),
            'alpha': random.randint(40, 140),
            'speed': random.uniform(6.0, 14.0),
        }
        self._trans_streaks.append(streak)

    def _transition_update_streaks(self):
        """Move and remove star streaks."""
        for st in self._trans_streaks[:]:
            st['y'] += st['speed']
            if self.transition_stage == 'enter':
                st['alpha'] = max(0, st['alpha'] - 4)
            if st['y'] - st['height'] > self.screen_rect.height or st['alpha'] <= 0:
                self._trans_streaks.remove(st)

    def _draw_game_scene(self):
        """Draw all game entities (excluding pause/menu overlays)"""
        self._active_bg().draw()

        is_dead = self.ship_death_frames > 0 or self.game_over_frames > 0

        for bullet in self.bullets.sprites():
            bullet.draw_bullet()
        self.missiles.draw(self.screen)
        if not is_dead:
            # Shield effect: golden sphere around ship
            if self.stats.items.get('shield', 0) > 0:
                self._draw_shield()
            self.ship.blitme()
        self.aliens.draw(self.screen)
        for alien in self.aliens.sprites():
            alien.draw_hp_bar()
        self.boss_bullets.draw(self.screen)
        self.boss_missiles.draw(self.screen)
        if self.boss is not None:
            self.screen.blit(self.boss.image, self.boss.rect)
            self.boss.draw_hp_bar()
        self.coins.draw(self.screen)
        self.gems.draw(self.screen)
        self.meteors.draw(self.screen)
        self.meteor_fragments.draw(self.screen)
        self.particles.draw(self.screen)
        self._draw_crit_rings()

        # Show score info
        self.sb.show_score()

        # Level-up animation
        if self.levelup_anim_frames > 0:
            self._draw_levelup_animation()

        # Boss entrance warning
        if self.boss_warning_frames > 0:
            self._draw_boss_warning()

        # Fail banner
        if self.game_over_frames > 0:
            self._draw_fail_banner()

        # Clover flash overlay
        if self.clover_flash_frames > 0:
            self._draw_clover_flash()

        # Near-death vignette
        if self.stats.ship_hp <= self.settings.critical_hp_threshold:
            self._draw_near_death_vignette()

        # Level transition overlay
        if self.in_transition:
            self._draw_transition_overlay()

    def _update_screen(self):
        """Update screen image (render routed by current state)"""
        if self.state == GameState.MENU:
            self.menu_bg.draw()
            save_exists = Path(self.settings.save_file).exists()
            self.menu_system.draw_start_screen(
                pygame.mouse.get_pos(), save_exists=save_exists)
            self.notification_bell_rect = self._draw_notification_bell()
            self.gear_button_rect = self._draw_account_gear()
            if self._account_confirm:
                self._draw_account_confirm()

            # Update available banner
            if self._update_available is not None:
                self._draw_update_banner()

            # Version number
            ver_font = pygame.font.SysFont('Arial', 16)
            ver_text = f"v{GAME_VERSION}"
            if IS_DEV_BUILD:
                ver_text += " DEV"
            ver_img = ver_font.render(ver_text, True, (120, 120, 140))
            ver_rect = ver_img.get_rect(bottom=self.screen.get_rect().bottom - 8,
                                        left=12)
            self.screen.blit(ver_img, ver_rect)

        elif self.state in (GameState.PLAYING, GameState.PAUSED):
            self._draw_game_scene()
            if self.state == GameState.PAUSED:
                self.menu_system.draw_pause_overlay(
                    pygame.mouse.get_pos(), save_disabled=self.save_disabled)

        elif self.state == GameState.SHOP:
            # Shop bg: freeze frame from game, video bg from menu
            if self.previous_state == GameState.PLAYING:
                self._draw_game_scene()
            else:
                self.menu_bg.draw()
            shop.draw_shop(self.screen, self.stats, self.settings,
                           ai_game=self, tab=getattr(self, '_shop_tab', 'shop'))

        elif self.state == GameState.TUTORIAL:
            self.menu_bg.draw()
            self.menu_system.draw_tutorial(pygame.mouse.get_pos())

        elif self.state == GameState.LOGIN:
            self.menu_bg.draw()
            if self.login_overlay:
                self.login_overlay.draw()

        elif self.state == GameState.LEADERBOARD:
            self.menu_bg.draw()
            self._draw_leaderboard()

        # Notification panel (covers everything)
        if self.show_notifications:
            self._draw_notifications_panel()

        # Bottom hint
        if self.save_notification_frames > 0:
            self._draw_save_notification()

        pygame.display.flip()

    def _update_aliens(self):
        """Update all alien positions and schedule dive attacks"""
        self.aliens.update()
        self._update_alien_dives()

        # Check boss bullet-ship collisions
        self._check_boss_bullet_ship_collisions()

        # Check boss missile-ship collisions
        self._check_boss_missile_ship_collisions()

        # Check alien-ship collisions (not during invulnerability)
        if self.ship.invulnerable_frames == 0:
            colliding_alien = pygame.sprite.spritecollideany(self.ship, self.aliens)
            if colliding_alien:
                self._ship_hit(self.settings.alien_collision_damage, colliding_alien)

        # Check if any alien reached bottom edge
        self._check_aliens_bottom()

    def _update_alien_dives(self):
        """Density scheduling: after cooldown, lowest alien in densest cluster initiates dive"""
        # No diving during hit cooldown
        if self.hit_cooldown > 0:
            return
        self.dive_timer -= 1
        if self.dive_timer > 0:
            return

        # If max simultaneous divers reached, retry later
        divers = sum(1 for alien in self.aliens.sprites() if alien.state == 'dive')
        if divers >= self.settings.alien_max_divers:
            self.dive_timer = self.settings.alien_dive_retry
            return

        # Only swarm-state aliens above dive height line are eligible
        swarm = [alien for alien in self.aliens.sprites() if alien.state == 'swarm']
        eligible = [alien for alien in swarm
                    if alien.rect.bottom <= self.settings.alien_dive_max_start_y]

        # Find eligible alien with most neighboring swarm aliens
        radius_sq = self.settings.alien_cluster_radius ** 2
        best_alien, best_neighbors = None, []
        for alien in eligible:
            center = pygame.math.Vector2(alien.rect.center)
            neighbors = [other for other in swarm if other is not alien
                         and center.distance_squared_to(other.rect.center) <= radius_sq]
            if best_alien is None or len(neighbors) > len(best_neighbors):
                best_alien, best_neighbors = alien, neighbors

        if best_alien is not None and len(best_neighbors) >= self.settings.alien_cluster_size:
            # Lowest eligible member of that cluster initiates dive
            cluster = [best_alien] + [alien for alien in best_neighbors
                                      if alien in eligible]
            diver = max(cluster, key=lambda alien: alien.rect.bottom)
            diver.start_dive()
            self.dive_timer = self.settings.alien_dive_cooldown
        else:
            # No cluster meets density threshold, retry later
            self.dive_timer = self.settings.alien_dive_retry

    def _calc_ship_damage(self, base_damage):
        """Calculate actual ship damage based on current armor (percentage reduction, min 1)"""
        armor_tier = self.stats.armor_tier
        pct = 0.0
        if armor_tier:
            for key, name, def_pct, price in self.settings.armor_tiers:
                if key == armor_tier:
                    pct = def_pct
                    break
        return max(1.0, round(base_damage * (1.0 - pct), 2))

    def _ship_hit(self, base_damage, colliding_alien=None):
        """Handle ship taking damage (from aliens, boss bullets, meteors, etc.)"""
        # Shield interception: consume one shield, negate this hit
        if self.stats.items.get('shield', 0) > 0:
            self.stats.items['shield'] -= 1
            self.stats.save_player_data()
            self.ship.invulnerable_frames = self.settings.invulnerable_duration
            self.sound.play_hit()
            return

        damage = self._calc_ship_damage(base_damage)
        self.stats.ship_hp -= damage

        if self.stats.ship_hp <= 0:
            self.stats.ship_hp = 0
            self._start_ship_death()
            return

        # Start ship flashing
        self.ship.invulnerable_frames = self.settings.invulnerable_duration

        # Collision source flash (no source for boss bullets, only ship flash + reset)
        if colliding_alien is not None:
            colliding_alien.flash_frames = self.settings.invulnerable_duration
            self.flashing_alien = colliding_alien
            self.flashing_alien_pos = colliding_alien.rect.center
            # Enter cooldown (no diving or double collision, fleet unchanged)
            self.hit_cooldown = self.settings.invulnerable_duration
        else:
            # Boss bullet/meteor hit: only HP loss + flash, no fleet reset
            self.flashing_alien = None
            self.hit_cooldown = self.settings.invulnerable_duration

        self.sound.play_hit()

    def _start_ship_death(self):
        """Ship death: play explosion anim, then fail banner, then return to menu"""
        self.ship_death_frames = self.settings.ship_death_duration
        self.death_position = self.ship.rect.center
        self._create_explosion(self.death_position)
        self.ship.invulnerable_frames = self.settings.ship_death_duration
        self.sound.play_explosion()

    def _check_aliens_bottom(self):
        """Check if any swarm-state alien reached screen bottom edge"""
        # Diving/climbing aliens managed by pull-up line, no bottom check
        for alien in self.aliens.sprites():
            if alien.state == 'swarm' and alien.rect.bottom >= self.settings.screen_height:
                # Alien reached bottom: fleet reset (different from collision flash)
                self._aliens_reached_bottom()
                break

    def _aliens_reached_bottom(self):
        """Alien reached bottom: lose HP and reset fleet"""
        damage = self._calc_ship_damage(self.settings.aliens_bottom_damage)
        self.stats.ship_hp -= damage

        if self.stats.ship_hp <= 0:
            self.stats.ship_hp = 0
            self._start_ship_death()
            return

        self.ship.invulnerable_frames = self.settings.invulnerable_duration

        self.bullets.empty()
        self.missiles.empty()
        self.aliens.empty()
        if self.boss is not None:
            # Boss fight: summoned fleet breached the line — clear it but keep the boss fight going
            pass
        else:
            self._create_fleet()
            self.ship.center_ship()
if __name__ == "__main__":
    # Create game instance and run
    ai = AlienInvasion()
    ai.run_game()
