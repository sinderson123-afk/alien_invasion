"""Menu bg video player: loop gameplay footage with Gaussian blur"""

import random
import math
import pygame
from settings import resource_path


class VideoBackground:
    """Loop gameplay footage on menu bg with Gaussian blur.
    Prefer opencv-python for video; fallback to procedural sim on failure."""

    def __init__(self, ai_game):
        """Initialize video background player"""
        self.ai_game = ai_game
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.width = self.settings.screen_width
        self.height = self.settings.screen_height

        self.use_video = False          # Whether video loaded successfully
        self.cap = None                 # cv2.VideoCapture object
        self.blurred_frame = None       # Current blurred frame (Pygame Surface)
        self.frame_counter = 0          # Frame counter (for frame-skip reading)

        # Try loading video
        self._init_video()

        # If video fails, init procedural background
        if not self.use_video:
            self._init_fallback()

    # ------------------------------------------------------------------
    # Video background
    # ------------------------------------------------------------------

    def _init_video(self):
        """Try loading video file with OpenCV"""
        try:
            import cv2
        except ImportError:
            print("Warning: opencv-python not installed, using procedural menu bg")
            return

        path = self.settings.menu_video_path
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"Warning: cannot open video file: {path}, using procedural menu bg")
            return

        self.cap = cap
        self.use_video = True
        self._cv2 = cv2
        print(f"Menu bg video loaded: {path}")

    def _update_video(self):
        """Read next video frame and apply Gaussian blur"""
        if self.cap is None or not self.use_video:
            return

        self.frame_counter += 1
        if self.frame_counter % self.settings.menu_video_frame_skip != 0:
            return  # Frame skip to reduce overhead

        ret, frame = self.cap.read()
        if not ret:
            # Video ended, loop to start
            self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                self.use_video = False
                return

        # Scale to screen size
        frame = self._cv2.resize(frame, (self.width, self.height))

        # Gaussian blur
        k = self.settings.menu_blur_strength
        if k % 2 == 0:
            k += 1  # Ensure kernel size is odd
        blurred = self._cv2.GaussianBlur(frame, (k, k), 0)

        # BGR → RGB
        rgb = self._cv2.cvtColor(blurred, self._cv2.COLOR_BGR2RGB)

        # Convert to Pygame Surface
        self.blurred_frame = pygame.image.frombuffer(
            rgb.tobytes(), (self.width, self.height), 'RGB')

    # ------------------------------------------------------------------
    # Procedural fallback background
    # ------------------------------------------------------------------

    def _init_fallback(self):
        """Initialize procedural simulation bg (when video unavailable)"""
        # Low-res render target (scale down then up = natural blur)
        self.fb_scale = 4
        self.fb_small_w = self.width // self.fb_scale
        self.fb_small_h = self.height // self.fb_scale
        self.fb_surface = pygame.Surface((self.fb_small_w, self.fb_small_h))
        self.fb_cache = None       # Cached blur result
        self.fb_update_every = 3   # Update every N frames
        self.fb_counter = 0

        # Load sprites (low opacity)
        self.fb_alien_img = self._fb_load_sprite(resource_path('resource/images/alien.bmp'), 0.06, 0.35)
        self.fb_ship_img = self._fb_load_sprite(resource_path('resource/images/ship.bmp'), 0.08, 0.30)
        self.fb_boss_img = self._fb_load_sprite(resource_path('resource/images/boss.bmp'), 0.12, 0.25)

        # Background decoration entities
        self.fb_aliens = []
        self._fb_spawn_aliens(14)

        self.fb_ship_x = float(self.fb_small_w // 2)
        self.fb_ship_vx = 0.15

        self.fb_boss = None
        self.fb_boss_timer = random.randint(180, 360)

        self.fb_particles = []
        self.fb_particle_colors = [
            (255, 200, 0), (255, 100, 0),
            (255, 50, 0),  (255, 255, 0),
        ]

    def _fb_load_sprite(self, path, size_ratio, alpha):
        """Load sprite image, scale to small render surface size, set alpha"""
        img = pygame.image.load(path)
        w = int(self.fb_small_w * size_ratio)
        ratio = w / img.get_width()
        h = int(img.get_height() * ratio)
        img = pygame.transform.scale(img, (w, h))
        img.set_alpha(int(255 * alpha))
        return img

    def _fb_spawn_aliens(self, count):
        """Randomly spawn bg aliens on small render surface"""
        for _ in range(count):
            self.fb_aliens.append({
                'x': random.uniform(0, self.fb_small_w - self.fb_alien_img.get_width()),
                'y': random.uniform(5, self.fb_small_h * 0.45),
                'vx': random.uniform(0.1, 0.4) * random.choice([-1, 1]),
                'vy': random.uniform(0.02, 0.08),
            })

    def _fb_spawn_particles(self, x, y, count=5):
        """Spawn a burst of particles at position"""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.2, 1.0)
            self.fb_particles.append({
                'x': float(x), 'y': float(y),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': random.randint(15, 30),
                'max_life': 30,
                'color': random.choice(self.fb_particle_colors),
            })

    def _fb_update_entities(self):
        """Update positions of all procedural bg entities"""
        # Alien movement (bounce off edges)
        for a in self.fb_aliens:
            a['x'] += a['vx']
            a['y'] += a['vy']
            aw = self.fb_alien_img.get_width()
            if a['x'] <= 0 or a['x'] >= self.fb_small_w - aw:
                a['vx'] *= -1
            if a['y'] <= 5 or a['y'] >= self.fb_small_h * 0.45:
                a['vy'] *= -1

        # Ship horizontal drift
        self.fb_ship_x += self.fb_ship_vx
        sw = self.fb_ship_img.get_width()
        if self.fb_ship_x <= 30 or self.fb_ship_x >= self.fb_small_w - 30:
            self.fb_ship_vx *= -1

        # Boss timed patrol
        self.fb_boss_timer -= 1
        if self.fb_boss_timer <= 0:
            if self.fb_boss is None:
                self.fb_boss = {
                    'x': float(random.randint(30, self.fb_small_w - 80)),
                    'vx': random.uniform(0.15, 0.3) * random.choice([-1, 1]),
                }
            else:
                self.fb_boss = None
            self.fb_boss_timer = random.randint(180, 360)

        if self.fb_boss is not None:
            self.fb_boss['x'] += self.fb_boss['vx']
            bw = self.fb_boss_img.get_width()
            if self.fb_boss['x'] <= 0 or self.fb_boss['x'] >= self.fb_small_w - bw:
                self.fb_boss['vx'] *= -1

        # Update particles
        for p in self.fb_particles[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 1
            if p['life'] <= 0:
                self.fb_particles.remove(p)

        # Random particle bursts
        if random.random() < 0.04:
            x = random.randint(20, self.fb_small_w - 20)
            y = random.randint(10, self.fb_small_h // 2)
            self._fb_spawn_particles(x, y, random.randint(3, 8))

    def _fb_render(self):
        """Render procedural bg to small Surface, then scale up (blur effect)"""
        self.fb_surface.fill((10, 10, 25))

        # Draw aliens
        for a in self.fb_aliens:
            self.fb_surface.blit(self.fb_alien_img, (int(a['x']), int(a['y'])))

        # Draw ship
        ship_y = self.fb_small_h - 50
        self.fb_surface.blit(
            self.fb_ship_img,
            (int(self.fb_ship_x - self.fb_ship_img.get_width() / 2), ship_y))

        # Draw Boss
        if self.fb_boss is not None:
            self.fb_surface.blit(self.fb_boss_img, (int(self.fb_boss['x']), 20))

        # Draw particles
        for p in self.fb_particles:
            alpha = int(255 * (p['life'] / p['max_life']))
            color = (*p['color'], alpha)
            r = 2
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (r, r), r)
            self.fb_surface.blit(surf, (int(p['x'] - r), int(p['y'] - r)))

        # Scale down then up for blur
        self.fb_cache = pygame.transform.smoothscale(
            self.fb_surface, (self.width, self.height))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self):
        """Called each frame, update bg frame"""
        if self.use_video:
            self._update_video()
        else:
            self.fb_counter += 1
            self._fb_update_entities()
            if self.fb_counter >= self.fb_update_every:
                self.fb_counter = 0
                self._fb_render()

    def draw(self):
        """Draw blurred background to screen"""
        if self.use_video and self.blurred_frame is not None:
            self.screen.blit(self.blurred_frame, (0, 0))
        elif not self.use_video and self.fb_cache is not None:
            self.screen.blit(self.fb_cache, (0, 0))
        else:
            # No frame on first call, fill dark background
            self.screen.fill((10, 10, 25))

        # Dark semi-transparent overlay (improves text readability)
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, self.settings.menu_overlay_alpha))
        self.screen.blit(overlay, (0, 0))
