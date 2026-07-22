"""Sound management: load or synthesize sound effects + background music"""

import math
import struct
import pygame
from settings import resource_path


def _synth_tone(frequency, duration_ms, volume=0.4, wave_type='square'):
    """Synthesize simple sound effects (no external audio files)"""
    sample_rate = 22050
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        # Fade envelope
        envelope = max(0.0, 1.0 - i / n_samples)
        if wave_type == 'square':
            sample = 1.0 if math.sin(2 * math.pi * frequency * t) >= 0 else -1.0
        else:
            sample = math.sin(2 * math.pi * frequency * t)
        value = int(127 * volume * envelope * sample)
        buf.extend(struct.pack('b', value))
    return pygame.mixer.Sound(buffer=bytes(buf))


def _synth_noise(duration_ms, volume=0.4):
    """Synthesize white noise (explosion sound)"""
    import random
    sample_rate = 22050
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = bytearray()
    for i in range(n_samples):
        envelope = max(0.0, 1.0 - i / n_samples)
        sample = random.uniform(-1.0, 1.0)
        value = int(127 * volume * envelope * sample)
        buf.extend(struct.pack('b', value))
    return pygame.mixer.Sound(buffer=bytes(buf))


class SoundManager:
    """Manage all game sound effects"""

    def __init__(self, enabled=True):
        """Initialize sounds (prefer external files, fallback to synthesis)"""
        self.enabled = enabled
        if not enabled:
            return

        # Try loading audio files from resource/sounds/, synthesize if missing
        self.shoot = self._load_or_synth(
            resource_path('resource/sounds/blaster.ogg'), lambda: _synth_tone(880, 80, 0.3, 'square'))
        self.explosion = self._load_or_synth(
            resource_path('resource/sounds/enemy_destroy.ogg'), lambda: _synth_noise(200, 0.5))
        self.missile_launch = self._load_or_synth(
            resource_path('resource/sounds/missile.wav'), lambda: _synth_tone(220, 150, 0.4, 'square'))
        self.levelup = self._load_or_synth(
            resource_path('resource/sounds/weapon_change.ogg'), lambda: _synth_chord([523, 659, 784], 400, 0.35))
        self.hit = self._load_or_synth(
            resource_path('resource/sounds/enemy_attack.ogg'), lambda: _synth_tone(120, 250, 0.5, 'square'))
        self.hurt = self._load_or_synth(
            resource_path('resource/sounds/enemy_hurt.ogg'), lambda: _synth_tone(200, 100, 0.3, 'square'))

    def _load_or_synth(self, path, synth_func):
        """Try loading file, synthesize if missing"""
        try:
            return pygame.mixer.Sound(path)
        except (FileNotFoundError, pygame.error):
            return synth_func()

    def play_shoot(self):
        """Play shoot sound"""
        if self.enabled:
            self.shoot.play()

    def play_explosion(self):
        """Play explosion sound"""
        if self.enabled:
            self.explosion.play()

    def play_missile(self):
        """Play missile launch sound"""
        if self.enabled:
            self.missile_launch.play()

    def play_levelup(self):
        """Play level-up sound"""
        if self.enabled:
            self.levelup.play()

    def play_hit(self):
        """Play ship hit sound"""
        if self.enabled:
            self.hit.play()

    def play_hurt(self):
        """Play alien hurt sound"""
        if self.enabled:
            self.hurt.play()

    # ------------------------------------------------------------------
    # Background Music (BGM)
    # ------------------------------------------------------------------

    def play_bgm(self, path=None):
        if path is None:
            path = resource_path('resource/sounds/Departure_From_The_Last_Moon.mp3')
        """Load and loop background music"""
        if not self.enabled:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)  # -1 = Loop indefinitely
        except (FileNotFoundError, pygame.error) as e:
            print(f"Warning: Could not load BGM ({e})")

    def stop_bgm(self):
        """Stop background music"""
        if self.enabled:
            pygame.mixer.music.stop()

    def set_bgm_volume(self, volume):
        """Set BGM volume (0.0-1.0)"""
        if self.enabled:
            pygame.mixer.music.set_volume(volume)

    # ------------------------------------------------------------------
    # Additional sound effects
    # ------------------------------------------------------------------

    def play_boss_destroy(self):
        """Play boss destroyed sound"""
        if not self.enabled:
            return
        # Lazy load: only load on first call
        if not hasattr(self, '_boss_destroy'):
            self._boss_destroy = self._load_or_synth(
                resource_path('resource/sounds/boss_destroy.mp3'),
                lambda: _synth_noise(400, 0.7))
        self._boss_destroy.play()

    def play_alarm(self):
        """Play boss entrance alarm sound"""
        if not self.enabled:
            return
        if not hasattr(self, '_alarm'):
            self._alarm = self._load_or_synth(
                resource_path('resource/sounds/alarm.wav'),
                lambda: _synth_tone(440, 500, 0.5, 'square'))
        self._alarm.play()


def _synth_chord(frequencies, duration_ms, volume=0.4):
    """Synthesize chord (for level-up and other positive events)"""
    sample_rate = 22050
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        envelope = max(0.0, 1.0 - i / n_samples)
        sample = sum(math.sin(2 * math.pi * f * t) for f in frequencies) / len(frequencies)
        value = int(127 * volume * envelope * sample)
        buf.extend(struct.pack('b', value))
    return pygame.mixer.Sound(buffer=bytes(buf))
