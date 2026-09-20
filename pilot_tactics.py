"""Precise spatial features from public observations, plus offline teaching labels.

No game state, saves, RNG, or private enemy intent is accessed here. The labels
are used only during training; the live player still selects neural logits.
"""

import random

import numpy as np

TACTICAL_DIM = 20


def spatial_features(state, velocities, ship_speed, bullet_speed):
    width, height = state['screen']['width'], state['screen']['height']
    ship = state.get('ship')
    if not ship:
        return np.zeros(TACTICAL_DIM, dtype=np.float32)
    sx = (ship['x'] + ship['width'] / 2) / width
    sy = (ship['y'] + ship['height'] / 2) / height
    muzzle_y = ship['y'] / height
    half_ship = ship['width'] / width / 2
    enemies, pickups, hazards = [], [], []
    for obj in state.get('objects', []):
        x = (obj['x'] + obj['width'] / 2) / width
        y = (obj['y'] + obj['height'] / 2) / height
        vx, vy = velocities.get(obj['id'], (0., 0.))
        kind = obj['kind']
        if kind in ('alien', 'boss') and y < sy:
            # Estimate where an upward shot meets a visible moving enemy.
            # Limit extrapolation: dives/turns cannot be known in advance.
            flight = min(120., max(0., (muzzle_y - y) / max(.001, bullet_speed + vy)))
            edge = obj['width'] / width / 2
            predicted = x + vx * flight
            span = max(.01, 1 - 2 * edge)
            folded = (predicted - edge) % (2 * span)
            aim = edge + (folded if folded <= span else 2 * span - folded)
            enemies.append((abs(aim - sx) + max(0., muzzle_y - y) * .15,
                            x - sx, aim - sx, sy - y, vx * 100, vy * 100,
                            obj['width'] / width))
        if kind in ('coin', 'gem'):
            pickups.append((x, y, vx, vy, kind))
        if kind in ('alien', 'boss', 'hostile_bullet', 'hostile_missile', 'meteor', 'meteor_fragment'):
            hazards.append((x, y, vx, vy, obj['width'] / width / 2,
                            obj['height'] / height / 2))

    def risk(destination, horizon=45):
        danger = 0.
        for x, y, vx, vy, hw, hh in hazards:
            for frames in (0, 12, 24, horizon):
                px = sx + max(-ship_speed * frames, min(ship_speed * frames, destination - sx))
                dx = abs(x + vx * frames - px)
                dy = abs(y + vy * frames - sy)
                if dx < half_ship + hw + .025 and dy < ship['height'] / height / 2 + hh + .025:
                    danger += (1 - frames / (horizon * 2)) / 4
        return min(3., danger)

    result = np.zeros(TACTICAL_DIM, dtype=np.float32)
    if enemies:
        target = min(enemies)
        result[:8] = [1., *target[1:], min(1., len(enemies) / 20)]
    if pickups:
        # Prefer reachable low drops, with a small bonus for visible gems.
        # No hidden disappearance timers or gem attributes are consulted.
        candidates = []
        for x, y, vx, vy, kind in pickups:
            travel = abs(x - sx) / max(.0005, ship_speed)
            wait = max(0., (sy - y - .08) / max(.001, vy))
            route_risk = risk(x)
            cost = max(travel, wait) / 180 + route_risk * 3 - (.15 if kind == 'gem' else 0)
            candidates.append((cost, x, y, vx, vy, route_risk))
        _, x, y, vx, vy, route_risk = min(candidates)
        result[8:16] = [1., x - sx, sy - y, vx * 100, vy * 100,
                        float(sy - y < .32), route_risk, min(1., len(pickups) / 20)]
    result[16:] = [risk(max(half_ship, sx - .18)), risk(min(1 - half_ship, sx + .18)),
                   risk(sx), ship_speed * 100]
    return result


def spatial_action(features, ship_x, previous_direction):
    """Training target: dodge immediate hazards, collect safe drops, then aim."""
    f = features
    if f[18] > 0:
        if f[16] < f[17] and ship_x > .055:
            return 0
        if f[17] < f[16] and ship_x < .945:
            return 1
        return 0 if ship_x > .5 else 1
    if f[8] and f[14] == 0 and (f[13] or not f[0]):
        delta, tolerance = f[9], .018
    elif f[0]:
        delta, tolerance = f[2], min(.02, max(.008, f[6] * .2))
    else:
        if ship_x < .14:
            return 1
        if ship_x > .86:
            return 0
        return 0 if previous_direction < 0 else 1
    if abs(delta) <= tolerance:
        return 2
    return 0 if delta < 0 else 1


class BehaviorMetrics:
    """Diagnostics from visible HUD and observations, never scoring mutations."""
    def __init__(self):
        self.single_target_steps = self.misaligned_stop_steps = 0
        self.safe_pickup_steps = self.pickup_approach_steps = 0
        self.coins_earned = 0

    def record(self, state, features, action, next_state):
        if not state.get('accepts_controls'):
            return
        if features[0] and features[7] <= .05:
            self.single_target_steps += 1
            if abs(features[2]) > .04 and action in (2, 5):
                self.misaligned_stop_steps += 1
        if features[8] and features[13] and features[14] == 0 and abs(features[9]) > .04:
            self.safe_pickup_steps += 1
            if (features[9] < 0 and action in (0, 3)) or (features[9] > 0 and action in (1, 4)):
                self.pickup_approach_steps += 1
        self.coins_earned += max(0, next_state.get('hud', {}).get('coins', 0)
                                 - state.get('hud', {}).get('coins', 0))

    def report(self):
        return vars(self).copy()


def tactical_cases(seed, count):
    """Synthetic API-shaped observations for spatial drills, not playable games.

    These do not touch a game or generate/upload a score. Separate seeds are
    used to test neural action generalization after training.
    """
    rng = random.Random(seed)
    for index in range(count):
        category = ('single', 'moving', 'pickup', 'mixed', 'hazard')[index % 5]
        sx = rng.uniform(.06, .94)
        direction = rng.choice((-1, 1))
        objects = []

        def actor(identity, kind, x, y, w, h, vx=0., vy=0.):
            objects.append(({'id': identity, 'kind': kind, 'x': x * 1200 - w / 2,
                             'y': y * 800 - h / 2, 'width': w, 'height': h}, vx, vy))

        if category != 'pickup':
            actor('enemy', 'alien', rng.uniform(.06, .94), rng.uniform(.12, .66),
                  48, 32, rng.uniform(-.0015, .0015) if category == 'moving' else 0)
        if category in ('pickup', 'mixed', 'hazard'):
            px = rng.uniform(.06, .94)
            actor('drop', rng.choice(('coin', 'coin', 'gem')), px, rng.uniform(.68, .94), 16, 16,
                  vy=rng.choice((0, .0025)))
        if category == 'hazard':
            actor('danger', 'hostile_bullet', sx + rng.uniform(-.07, .07), .82, 12, 20, vy=.004)
        pair = []
        for frame in (100, 106):
            rendered = []
            for obj, vx, vy in objects:
                rendered.append(dict(obj, x=obj['x'] + vx * (frame - 106) * 1200,
                                     y=obj['y'] + vy * (frame - 106) * 800))
            pair.append({'frame': frame, 'screen': {'width': 1200, 'height': 800},
                         'ship': {'x': sx * 1200 - 48, 'y': 704, 'width': 96, 'height': 96},
                         'hud': {'hp': 30, 'max_hp': 30, 'score': 0, 'coins': 0, 'level': 1},
                         'state': 'playing', 'accepts_controls': True, 'actions': [],
                         'objects': rendered})
        yield category, direction, pair
