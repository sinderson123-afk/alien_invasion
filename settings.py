import sys
import os
from pathlib import Path


GAME_VERSION = "1.1.1"

try:
    from _build_info import DEV_BUILD as IS_DEV_BUILD
except ImportError:
    IS_DEV_BUILD = False


def resource_path(relative_path):
    """Get absolute path for resource files, compatible with PyInstaller onefile"""
    if hasattr(sys, '_MEIPASS'):
        return str(Path(sys._MEIPASS) / relative_path)
    return str(Path(relative_path))


class Settings:
    """Class storing all settings for the game"""
    def __init__(self):
        """Initialize game settings"""
        # Screen settings
        self.screen_width = 1200
        self.screen_height = 800
        self.bg_color = (230, 230, 230)

        # Ship settings
        self.ship_speed = 1.5
        self.ship_limit = 3

        # Bullet settings
        self.bullet_speed = 2.5
        self.bullet_width = 3
        self.bullet_height = 15
        self.bullet_color = (0, 255, 80)        # Bright green
        self.bullet_allowed = 3

        # Alien settings
        self.alien_speed = 1.0

        # Alien swarm behavior (rates as multiples of alien_speed, scaled by increase_speed)
        self.aliens_per_wave = 22             # Number of aliens per wave
        self.alien_spawn_y_min = 60           # Spawn band (rect.y range)
        self.alien_spawn_y_max = 240
        self.alien_descend_factor = 0.1       # Swarm descend rate factor
        self.alien_dive_speed_factor = 5.0    # Dive speed factor
        self.alien_climb_factor = 2.0         # Climb speed factor
        self.alien_gather_offset_range = 140  # Gather target = ship x +/- random offset
        self.alien_cruise_y_min = 100         # Cruise altitude band for climb return (rect.y, randomized each time)
        self.alien_cruise_y_max = 280

        # Dive scheduling settings
        self.alien_cluster_radius = 90        # Density check radius (pixels)
        self.alien_cluster_size = 3           # Threshold for number of other swarm aliens within radius
        self.alien_dive_cooldown = 180        # Frames between dive triggers
        self.alien_dive_retry = 30            # Retry interval when no eligible cluster
        self.alien_max_divers = 2             # Max simultaneous divers
        self.alien_dive_windup = 20           # Windup frames before dive (lock target at windup end)
        self.alien_dive_max_start_y = 440     # Only aliens with rect.bottom not below this line can dive
        self.alien_pullup_margin = 40         # Pull-up line = screen_height - this value

        # Particle (explosion effect) settings
        self.particle_count = 20        # Number of particles per explosion
        self.particle_min_size = 2      # Particle min size
        self.particle_max_size = 5      # Particle max size
        self.particle_lifetime = 30     # Particle lifetime in frames (60fps ~ 0.5s)
        self.particle_gravity = 0.05   # Downward gravity for particles
        self.particle_colors = [        # Explosion colors (yellow->orange->red->gold)
            (255, 200, 0),
            (255, 100, 0),
            (255, 50, 0),
            (255, 255, 0),
        ]

        # Missile impact particles (larger and brighter than normal)
        self.missile_particle_count = 35
        self.missile_particle_size_mult = 1.6
        self.missile_particle_speed_mult = 1.5
        self.missile_particle_colors = [
            (255, 80, 0), (255, 30, 0), (255, 180, 0), (255, 255, 100)
        ]

        # Boss death particles (spectacular large explosion)
        self.boss_particle_count = 80
        self.boss_particle_size_mult = 2.5
        self.boss_particle_speed_mult = 2.0
        self.boss_particle_lifetime_mult = 2.0
        self.boss_particle_colors = [
            (255, 215, 0), (255, 100, 0), (255, 50, 0),
            (255, 255, 200), (255, 255, 50), (200, 100, 255)
        ]
        self.boss_secondary_count = 40        # Secondary burst particle count
        self.boss_secondary_delay = 15        # Secondary burst delay frames

        # Boss death animation
        self.boss_death_flash_frames = 90     # Death flash total frames
        self.boss_death_slow_frames = 30      # Hover no-flash frames (then accelerated flashing starts)

        # --- Meteor settings ---
        self.meteor_spawn_interval = 180      # Spawn interval (frames, 180=3s)
        self.meteor_speed_min = 1.5           # Min fall speed
        self.meteor_speed_max = 4.0           # Max fall speed
        self.meteor_angle_range = 90          # Angle deviation from vertical (total 180 degrees)
        self.meteor_size_min = 15             # Min radius (pixels)
        self.meteor_size_max = 38             # Max radius (pixels)
        self.meteor_hp = 3                    # HP (bullet damage=1, needs 3 hits)
        self.meteor_alien_damage = 10         # Main meteor collision damage to aliens (heavy)
        self.meteor_boss_damage = 8           # Main meteor collision damage to boss (heavy)
        self.meteor_fragment_damage = 3       # Fragment damage (slightly higher than bullet=1)
        self.meteor_fragment_hp = 1           # Fragment HP (1 bullet destroys)
        self.meteor_fragment_count = 12       # Number of fragments on shatter
        self.meteor_fragment_lifetime = 90    # Fragment lifetime in frames (90 frames = 1.5s)
        self.meteor_points = 25               # Points for meteor destruction
        self.meteor_avoid_radius = 80         # Alien avoidance detection radius
        self.meteor_avoid_strength = 1.5      # Avoidance force strength

        # Speed increase settings
        self.speedup_scale = 1.1

        # Scoring settings
        self.alien_points = 50
        self.boss_points = 500              # Boss kill points

        # Missile settings
        self.missile_score_step = 500   # Award 1 missile per 500 points
        self.missile_speed = 4.0        # Missile flight speed
        self.missile_turn_rate = 0.08   # Turn ratio toward target per frame (higher = more agile)
        self.missile_blast_radius = 120 # Blast radius (pixels)

        # Damage and HP settings
        self.alien_base_hp = 1          # Alien base HP (level 1)
        self.alien_hp_per_level = 1     # HP increase per level
        self.bullet_damage = 1          # Bullet damage
        self.missile_damage = 5         # Missile explosion damage

        # Level settings
        self.kills_per_level = 30       # Kills required per level

        # Ship hit flash settings
        self.invulnerable_duration = 60     # Total frames of flash/invulnerability/no-dive (60 frames = 1s)

        # Boss settings
        self.boss_hp_multiplier = 20        # Boss HP = current level alien HP x this value
        self.boss_speed_factor = 0.5        # Boss speed factor (relative to alien_speed)
        self.boss_bullet_speed = 1.5        # Boss bullet speed
        self.boss_bullet_radius = 6         # Boss bullet radius (pixels)
        self.boss_bullet_color = (220, 50, 50)  # Red
        self.boss_fire_interval = 120       # Boss fire interval (frames, 120=2s)
        self.boss_hp_bar_width = 80         # Boss HP bar width (pixels)
        self.boss_hp_bar_height = 5         # Boss HP bar height
        self.boss_hp_bar_offset_y = 12      # Boss HP bar vertical offset from top

        # Coin settings
        self.coin_drop_rate = 0.3           # Coin drop rate on alien kill
        self.coin_fall_speed = 2.0          # Coin fall speed
        self.coin_hover_y_margin = 60       # Coin hover distance from bottom
        self.coin_hover_duration = 180      # Hover duration (frames, 3s)
        self.coin_flash_duration = 60       # Flash duration (frames, 1s)
        self.coin_radius = 8                # Coin radius (pixels)

        # Alien HP bar settings
        self.hp_bar_width = 30              # HP bar width (pixels)
        self.hp_bar_height = 3              # HP bar height
        self.hp_bar_offset_y = 6            # HP bar vertical offset from alien top

        # Item prices
        self.magnet_item_cost = 5           # Magnet purchase price
        self.shield_item_cost = 10          # Shield purchase price
        self.clover_item_cost = 8           # Clover purchase price
        self.magnet_duration = 600          # Magnet duration (10s)
        self.magnet_pickup_radius = 300     # Magnet pickup radius

        # Clover effect settings
        self.clover_flash_duration = 15     # Screen green flash duration (frames)
        self.clover_teleport_y = 0          # Final exit y coordinate
        self.clover_push_duration = 35      # Push animation duration (frames)
        self.clover_push_speed = 20         # Push speed (pixels/frame)

        # --- Armor System ---
        # Armor tiers: name -> (defense_pct, full_price)
        # defense_pct is damage reduction percentage (0.0~1.0)
        self.armor_tiers = [
            ('silver',   'Silver',   0.15, 10),
            ('gold',     'Gold',     0.25, 20),
            ('mithril',  'Mithril',  0.40, 40),
            ('galvorn',  'Galvorn',  0.55, 80),
            ('tilkal',   'Tilkal',   0.70, 160),
        ]
        self.armor_trade_in_ratio = 0.5  # Old armor trade-in ratio

        # Ship HP settings
        self.ship_hp_multiplier = 10       # HP per life slot = 10

        # Base ship hit damage (before armor reduction)
        self.alien_collision_damage = 5
        self.boss_bullet_damage = 8
        self.meteor_damage = 10
        self.meteor_fragment_damage = 4
        self.aliens_bottom_damage = 5      # Alien bottom-reach damage

        # Skill costs (5 levels)
        self.skill_costs = {
            'speed':    [3, 6, 12, 24, 48],
            'ammo':     [5, 10, 20, 40, 80],
            'vitality': [8, 16, 32, 64, 128],
        }
        self.skill_max_level = 5

        # --- Menu interface settings ---
        self.menu_title_font_size = 72
        self.menu_button_font_size = 42
        self.menu_video_path = resource_path('resource/videos/gameplay.mp4')
        self.menu_blur_strength = 15          # Gaussian blur kernel size (must be odd)
        self.menu_video_frame_skip = 3        # Read video frame every N frames
        self.menu_overlay_alpha = 100         # Menu video dark overlay alpha (0-255)
        self.pause_overlay_alpha = 140        # Pause overlay alpha

        # Menu button colors (R, G, B)
        self.menu_start_color = (40, 140, 60)
        self.menu_start_hover = (60, 180, 80)
        self.menu_shop_color = (60, 120, 200)
        self.menu_shop_hover = (90, 160, 240)
        self.menu_tutorial_color = (120, 80, 180)
        self.menu_tutorial_hover = (150, 110, 210)
        self.menu_resume_color = (40, 140, 60)
        self.menu_resume_hover = (60, 180, 80)
        self.menu_return_color = (180, 60, 60)
        self.menu_return_hover = (220, 80, 80)
        self.menu_quit_color = (120, 50, 50)
        self.menu_quit_hover = (160, 70, 70)

        # --- Audio settings ---
        self.bgm_volume = 0.6              # BGM normal volume (0.0-1.0)
        self.bgm_pause_volume = 0.15       # BGM volume when paused
        self.sfx_volume = 0.8              # SFX volume

        # --- Scrolling background settings ---
        self.bg_images = [
            resource_path('resource/images/bg_earth.png'),
            resource_path('resource/images/bg_moon.png'),
            resource_path('resource/images/bg_space.png'),
        ]
        self.bg_scroll_speed = 2

        # --- Animation durations ---
        self.boss_warning_duration = 90     # Boss entrance warning banner frames
        self.ship_death_duration = 60       # Ship death explosion frames
        self.fail_banner_duration = 90      # Fail banner display frames

        # --- Save settings ---
        self._saves_dir = Path(os.path.dirname(sys.argv[0])) / "saves"
        self._saves_dir.mkdir(exist_ok=True)
        self.save_file = str(self._saves_dir / "savegame.dat")
        self.high_score_file = str(self._saves_dir / "high_score.dat")

        # --- Server settings ---
        self.server_url = "https://alien-invasion-1018096304579.asia-east1.run.app"

        self.initialize_dynamic_settings()

    def initialize_dynamic_settings(self):
        """Initialize settings that change during gameplay"""
        self.ship_speed = 1.5
        self.bullet_speed = 2.5
        self.alien_speed = 1.0

    def increase_speed(self):
        """Increase speed values"""
        self.ship_speed *= self.speedup_scale
        self.bullet_speed *= self.speedup_scale
        self.alien_speed *= self.speedup_scale
