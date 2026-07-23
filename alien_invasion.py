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
from coin import Coin
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
        pygame.display.set_caption("Alien Invasion")

        self.stats = GameStats(self)
        self.sb = Scoreboard(self)

        self.ship = Ship(self)
        self.bullets = pygame.sprite.Group()
        self.missiles = pygame.sprite.Group()
        self.aliens = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.boss_bullets = pygame.sprite.Group()
        self.coins = pygame.sprite.Group()
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
        self._update_available = None      # (version, url) when update found

        # Bell notification fonts
        self._font_small_bell = pygame.font.SysFont(None, 14)
        self._font_title_bell = pygame.font.SysFont(None, 36, bold=True)
        self._font_row_bell = pygame.font.SysFont(None, 20)

        # Start background music
        self.sound.play_bgm()

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

                # Fail animation (highest priority, freezes all other updates)
                if self.game_over_frames > 0:
                    self.game_over_frames -= 1
                    self.particles.update()
                    if self.game_over_frames == 0:
                        self._return_to_menu()
                elif self.ship_death_frames > 0:
                    self.ship_death_frames -= 1
                    self.particles.update()
                    if self.ship_death_frames == 0:
                        self.game_over_frames = self.settings.fail_banner_duration
                elif self.clover_push_frames > 0:
                    self._update_clover_push()
                    self.ship.update()
                    self._update_bullets()
                    self._update_missiles()
                    if self.boss is not None:
                        self.boss.update()
                    self.coins.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self._spawn_meteor()
                    self.particles.update()
                elif self.hit_cooldown > 0:
                    # Cooldown: update aliens (with flash animation), boss bullets and particles, no collision detection
                    self.aliens.update()
                    self._update_boss_bullets()
                    if self.boss is not None:
                        self.boss.update()
                    self.coins.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self.meteors.update()
                    self.meteor_fragments.update()
                    self._update_meteor_collisions(skip_ship=True)
                    self._spawn_meteor()
                    self.particles.update()
                    self.hit_cooldown -= 1
                    if self.hit_cooldown == 0:
                        # Flash ends: destroy the colliding alien (explode at collision pos, not current pos)
                        if self.flashing_alien is not None and self.flashing_alien.alive():
                            explosion_pos = (self.flashing_alien_pos
                                             if self.flashing_alien_pos
                                             else self.flashing_alien.rect.center)
                            self._create_explosion(explosion_pos)
                            self._maybe_drop_coin(*explosion_pos)
                            self.flashing_alien.kill()
                            self.sound.play_explosion()
                            self._award_points(1)
                        self.flashing_alien = None
                        self.flashing_alien_pos = None
                else:
                    self.ship.update()
                    self._update_bullets()
                    self._update_missiles()
                    self._update_boss_bullets()
                    if self.boss is not None:
                        self.boss.update()
                    self._update_aliens()
                    self.coins.update()
                    self._update_magnet()
                    self._check_coin_pickup()
                    self.meteors.update()
                    self.meteor_fragments.update()
                    self._update_meteor_collisions(skip_ship=False)
                    self._spawn_meteor()
                    self.particles.update()

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
            changed, action = shop.handle_shop_click(
                mouse_pos, self.stats, self.settings)
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
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.meteor_timer = self.settings.meteor_spawn_interval
        self.boss = None

        # Create fleet, position ship
        self._create_fleet()
        self.ship.center_ship()

        # Switch to game state
        self.state = GameState.PLAYING
        self.sound.set_bgm_volume(self.settings.bgm_volume)

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
        self.meteors.empty()
        self.meteor_fragments.empty()
        self.boss = None
        self.boss_warning_frames = 0
        self.ship_death_frames = 0
        self.game_over_frames = 0
        self.death_position = None
        self.state = GameState.MENU
        self.sound.set_bgm_volume(self.settings.bgm_volume)

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
            'version': 3,  # Save format version
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
                'high_score': self.stats.high_score,
            },
            'settings': {
                'ship_speed': self.settings.ship_speed,
                'bullet_speed': self.settings.bullet_speed,
                'alien_speed': self.settings.alien_speed,
                'bullet_allowed': self.settings.bullet_allowed,
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
        # future v3 -> v4 appended here
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
        self.stats.high_score = s['high_score']

        # --- Restore dynamic settings ---
        ss = data['settings']
        self.settings.ship_speed = min(ss['ship_speed'], self.settings.ship_speed_max)
        self.settings.bullet_speed = ss['bullet_speed']
        self.settings.alien_speed = min(ss['alien_speed'], self.settings.alien_speed_max)
        self.settings.bullet_allowed = ss['bullet_allowed']

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

    def _check_keydown_events(self, event):
        """Handle key press (routed by current state)"""
        # -------- All states --------
        if event.key == pygame.K_q:
            self._quit_game()

        # -------- MENU state --------
        elif self.state == GameState.MENU:
            if self.show_notifications:
                if event.key == pygame.K_ESCAPE:
                    self.show_notifications = False
                elif event.key == pygame.K_c:
                    self.notifications.clear()
                    self.show_notifications = False
            elif event.key == pygame.K_ESCAPE:
                self._quit_game()

        # -------- PLAYING state --------
        elif self.state == GameState.PLAYING:
            # Disable pause and game actions during death/fail sequence
            is_dead = self.ship_death_frames > 0 or self.game_over_frames > 0
            if is_dead:
                return
            if event.key == pygame.K_ESCAPE:
                # Pause and clear movement flags
                self.ship.moving_right = False
                self.ship.moving_left = False
                self.save_disabled = False
                self.state = GameState.PAUSED
                self.sound.set_bgm_volume(self.settings.bgm_pause_volume)
            elif event.key == pygame.K_RIGHT:
                self.ship.moving_right = True
            elif event.key == pygame.K_LEFT:
                self.ship.moving_left = True
            elif event.key == pygame.K_SPACE:
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
        """Handle bullet-alien collisions: damage, explode on death, score"""
        # dokill1=False: damage system instead of direct removal
        collisions = pygame.sprite.groupcollide(self.aliens, self.bullets, False, True)
        for alien, bullets in collisions.items():
            # Multiple bullets hitting same alien in one frame stack damage
            total_damage = self.settings.bullet_damage * len(bullets)
            if alien.take_damage(total_damage):
                self._create_explosion(alien.rect.center)
                self._maybe_drop_coin(*alien.rect.center)
                self.sound.play_explosion()
                self._award_points(1)
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
        for alien in self.aliens.sprites():
            if blast_center.distance_to(alien.rect.center) <= self.settings.missile_blast_radius:
                if alien.take_damage(self.settings.missile_damage):
                    self._create_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    destroyed += 1
                    self.sound.play_explosion()
                else:
                    self.sound.play_hurt()
        # Also check if boss is in blast radius
        if self.boss is not None and self.boss.hp > 0:
            if blast_center.distance_to(self.boss.rect.center) <= self.settings.missile_blast_radius:
                if self.boss.take_damage(self.settings.missile_damage):
                    self._create_explosion(self.boss.rect.center)
                    self._maybe_drop_coin(*self.boss.rect.center)
                    destroyed += 1
                    self.sound.play_explosion()
                else:
                    self.sound.play_hurt()
        if destroyed:
            self._award_points(destroyed)

    def _award_points(self, alien_count):
        """Award points by alien count and update displays"""
        self.stats.score += self.settings.alien_points * alien_count
        self.stats.kills += alien_count
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
        # Missile direct hit on boss body
        for missile in self.missiles.sprites():
            # Missile hits boss
            if missile.rect.colliderect(self.boss.rect):
                if self.boss.take_damage(self.settings.missile_damage):
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
                if self.boss.take_damage(self.settings.bullet_damage):
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
                self._create_fleet()
                self.settings.increase_speed()
        elif not self.aliens:
            # Normal level: all aliens dead clears level
            self.bullets.empty()
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
                    self._create_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
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
                    self._create_explosion(alien.rect.center)
                    self._maybe_drop_coin(*alien.rect.center)
                    self.sound.play_explosion()
                    self._award_points(1)
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
            if bullet_hits and meteor.take_damage(len(bullet_hits)):
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

    def _draw_game_scene(self):
        """Draw all game entities (excluding pause/menu overlays)"""
        self._active_bg().draw()

        is_dead = self.ship_death_frames > 0 or self.game_over_frames > 0

        for bullet in self.bullets.sprites():
            bullet.draw_bullet()
        self.missiles.draw(self.screen)
        if not is_dead:
            self.ship.blitme()
        self.aliens.draw(self.screen)
        for alien in self.aliens.sprites():
            alien.draw_hp_bar()
        self.boss_bullets.draw(self.screen)
        if self.boss is not None:
            self.screen.blit(self.boss.image, self.boss.rect)
            self.boss.draw_hp_bar()
        self.coins.draw(self.screen)
        self.meteors.draw(self.screen)
        self.meteor_fragments.draw(self.screen)
        self.particles.draw(self.screen)

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

    def _update_screen(self):
        """Update screen image (render routed by current state)"""
        if self.state == GameState.MENU:
            self.menu_bg.draw()
            save_exists = Path(self.settings.save_file).exists()
            self.menu_system.draw_start_screen(
                pygame.mouse.get_pos(), save_exists=save_exists)
            self.notification_bell_rect = self._draw_notification_bell()

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
            shop.draw_shop(self.screen, self.stats, self.settings)

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
        return max(1, math.ceil(base_damage * (1.0 - pct)))

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
        else:
            self.ship.invulnerable_frames = self.settings.invulnerable_duration

            self.bullets.empty()
            self.missiles.empty()
            self.aliens.empty()
            self._create_fleet()
            self.ship.center_ship()
if __name__ == "__main__":
    # Create game instance and run
    ai = AlienInvasion()
    ai.run_game()
