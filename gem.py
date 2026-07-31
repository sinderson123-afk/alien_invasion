"""Gem system: generation, upgrade, stat aggregation, pickup sprite"""
import random
import pygame
from pygame.sprite import Sprite

ALL_STATS = ['hp', 'defense', 'damage', 'crit_rate', 'crit_dmg', 'gold', 'penetration']

STAT_LABELS = {
    'hp': 'HP',
    'defense': 'DEF',
    'damage': 'DMG',
    'crit_rate': 'Crit%',
    'crit_dmg': 'CritDmg%',
    'gold': 'Gold%',
    'penetration': 'Pierce%',
}

STAT_FORMATS = {
    'hp': lambda v: f"+{v:.0f}",
    'defense': lambda v: f"+{v:.1f}%",
    'damage': lambda v: f"+{v:.1f}%",
    'crit_rate': lambda v: f"+{v:.1f}%",
    'crit_dmg': lambda v: f"+{v:.1f}%",
    'gold': lambda v: f"+{v:.1f}%",
    'penetration': lambda v: f"+{v:.1f}%",
}

COLORS = {
    'hp': (220, 60, 60),
    'defense': (60, 140, 220),
    'damage': (220, 140, 40),
    'crit_rate': (255, 200, 40),
    'crit_dmg': (255, 100, 40),
    'gold': (255, 215, 0),
    'penetration': (180, 120, 255),
}

_next_gem_id = 0


def init_gem_id_counter(equipped_gems, gem_storage):
    """Set the global ID counter based on existing gems."""
    global _next_gem_id
    max_id = 0
    for g in equipped_gems:
        if g and g.get('id', 0) > max_id:
            max_id = g['id']
    for g in gem_storage:
        if g.get('id', 0) > max_id:
            max_id = g['id']
    _next_gem_id = max_id + 1


def generate_gem(settings):
    """Generate a random gem: 1 main stat + 2 sub stats (mutually exclusive)."""
    global _next_gem_id
    gem_id = _next_gem_id
    _next_gem_id += 1

    name = random.choice(settings.gem_names)

    main_stat_type = random.choice(ALL_STATS)
    base_val = settings.gem_base_values[main_stat_type]
    main_value = base_val

    remaining = [s for s in ALL_STATS if s != main_stat_type]
    sub_types = random.sample(remaining, 2)
    sub_stats = []
    for st in sub_types:
        sub_base = settings.gem_base_values[st]
        sub_value = round(sub_base * random.uniform(0.4, 0.6) * settings.gem_sub_stat_ratio * 2, 1)
        if sub_value < 0.1:
            sub_value = 0.1
        sub_stats.append([st, sub_value])

    return {
        'id': gem_id,
        'name': name,
        'main_stat': [main_stat_type, main_value],
        'sub_stats': sub_stats,
        'level': 1,
    }


def upgrade_gem(gem, settings):
    """Upgrade gem: increase main stat value linearly with level, sub stats unchanged."""
    gem['level'] += 1
    stat_type = gem['main_stat'][0]
    base_val = settings.gem_base_values[stat_type]
    gem['main_stat'][1] = round(base_val * gem['level'], 1)

    return gem['level'] * settings.gem_upgrade_cost_base


def get_gem_bonuses(equipped_gems):
    """Aggregate all stat bonuses from equipped gems. Returns dict."""
    bonuses = {s: 0 for s in ALL_STATS}

    for gem in equipped_gems:
        if gem is None:
            continue
        ms_type, ms_val = gem['main_stat']
        bonuses[ms_type] += ms_val
        for st, val in gem['sub_stats']:
            bonuses[st] += val

    return bonuses


class GemPickup(Sprite):
    """A gem dropped on the map that the player can collect."""

    def __init__(self, ai_game, x, y, gem_data):
        super().__init__()
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.ai_game = ai_game
        self.gem_data = gem_data
        self.state = 'falling'

        color = COLORS.get(gem_data['main_stat'][0], (200, 180, 255))
        self.size = 12
        self.image = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pts = [
            (self.size, 0), (self.size * 2, self.size),
            (self.size, self.size * 2), (0, self.size),
        ]
        pygame.draw.polygon(self.image, (*color, 220), pts)
        pygame.draw.polygon(self.image, (255, 255, 255, 140), pts, 1)

        self.rect = self.image.get_rect(center=(x, y))
        self.y = float(self.rect.y)
        screen_h = self.screen.get_rect().height
        self.hover_y = screen_h - 60
        self.hover_timer = 180
        self.flash_timer = 60

    def update(self):
        if self.state == 'falling':
            self.y += self.settings.coin_fall_speed
            if self.y >= self.hover_y:
                self.y = self.hover_y
                self.state = 'hovering'
        elif self.state == 'hovering':
            self.hover_timer -= 1
            if self.hover_timer <= 0:
                self.state = 'flashing'
        elif self.state == 'flashing':
            self.flash_timer -= 1
            if (self.flash_timer // 6) % 2 == 0:
                self.image.set_alpha(60)
            else:
                self.image.set_alpha(255)
            if self.flash_timer <= 0:
                self.kill()
                return
        self.rect.y = int(self.y)
