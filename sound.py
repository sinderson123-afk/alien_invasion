"""Sound management: load or synthesize sound effects + background music"""

import math
import struct
import pygame
from settings import resource_path


def _synth_tone(frequency, duration_ms, volume=0.4, wave_type='square'):
    """合成简单的音效（无需外部音频文件）"""
    sample_rate = 22050
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        # 渐隐包络
        envelope = max(0.0, 1.0 - i / n_samples)
        if wave_type == 'square':
            sample = 1.0 if math.sin(2 * math.pi * frequency * t) >= 0 else -1.0
        else:
            sample = math.sin(2 * math.pi * frequency * t)
        value = int(127 * volume * envelope * sample)
        buf.extend(struct.pack('b', value))
    return pygame.mixer.Sound(buffer=bytes(buf))


def _synth_noise(duration_ms, volume=0.4):
    """合成白噪声（爆炸音效）"""
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
    """管理游戏中的所有音效"""

    def __init__(self, enabled=True):
        """初始化音效（优先加载外部文件，否则使用合成音效）"""
        self.enabled = enabled
        if not enabled:
            return

        # 尝试加载 resource/sounds/ 目录下的音频文件，不存在则合成
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
        """尝试加载文件，不存在则合成"""
        try:
            return pygame.mixer.Sound(path)
        except (FileNotFoundError, pygame.error):
            return synth_func()

    def play_shoot(self):
        """播放射击音效"""
        if self.enabled:
            self.shoot.play()

    def play_explosion(self):
        """播放爆炸音效"""
        if self.enabled:
            self.explosion.play()

    def play_missile(self):
        """播放导弹发射音效"""
        if self.enabled:
            self.missile_launch.play()

    def play_levelup(self):
        """播放升级音效"""
        if self.enabled:
            self.levelup.play()

    def play_hit(self):
        """播放飞船受击音效"""
        if self.enabled:
            self.hit.play()

    def play_hurt(self):
        """播放外星人受伤音效"""
        if self.enabled:
            self.hurt.play()

    # ------------------------------------------------------------------
    # 背景音乐 (BGM)
    # ------------------------------------------------------------------

    def play_bgm(self, path=None):
        if path is None:
            path = resource_path('resource/sounds/Departure_From_The_Last_Moon.mp3')
        """加载并循环播放背景音乐"""
        if not self.enabled:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)  # -1 = 无限循环
        except (FileNotFoundError, pygame.error) as e:
            print(f"Warning: Could not load BGM ({e})")

    def stop_bgm(self):
        """停止背景音乐"""
        if self.enabled:
            pygame.mixer.music.stop()

    def set_bgm_volume(self, volume):
        """设置背景音乐音量 (0.0-1.0)"""
        if self.enabled:
            pygame.mixer.music.set_volume(volume)

    # ------------------------------------------------------------------
    # 新增音效
    # ------------------------------------------------------------------

    def play_boss_destroy(self):
        """播放 Boss 击破音效"""
        if not self.enabled:
            return
        # 懒加载：首次调用时才加载
        if not hasattr(self, '_boss_destroy'):
            self._boss_destroy = self._load_or_synth(
                resource_path('resource/sounds/boss_destroy.mp3'),
                lambda: _synth_noise(400, 0.7))
        self._boss_destroy.play()

    def play_alarm(self):
        """播放 Boss 出场警告音效"""
        if not self.enabled:
            return
        if not hasattr(self, '_alarm'):
            self._alarm = self._load_or_synth(
                resource_path('resource/sounds/alarm.wav'),
                lambda: _synth_tone(440, 500, 0.5, 'square'))
        self._alarm.play()


def _synth_chord(frequencies, duration_ms, volume=0.4):
    """合成和弦（用于升级等正面事件）"""
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
