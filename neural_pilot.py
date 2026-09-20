"""Train on isolated practice games; compete through the public text API only."""

import argparse
from collections import deque
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical

from file_crypto import decrypt_json, encrypt_json
from game_control import GameClient

OFFERS = ['buy_item:magnet', 'buy_item:shield', 'buy_item:clover',
          'buy_armor:silver', 'buy_armor:gold', 'buy_armor:mithril',
          'buy_armor:galvorn', 'buy_armor:tilkal',
          'upgrade_skill:speed', 'upgrade_skill:ammo',
          'upgrade_skill:vitality', 'upgrade_skill:damage']
ACTIONS = ['left_fire', 'right_fire', 'stop_fire', 'left', 'right', 'stop',
           'missile', 'magnet', 'clover', 'shop', 'back'] + OFFERS
HAZARDS = ('alien', 'boss', 'hostile_bullet', 'hostile_missile', 'meteor', 'meteor_fragment')
OBS_DIM = 90


def command(action):
    if action < 6:
        return {'move': ('left', 'right', 'stop')[action % 3],
                'fire': action < 3, 'lease_ms': 1000}
    if action >= 11:
        return {'action': 'purchase', 'offer': ACTIONS[action]}
    return {'action': ACTIONS[action]}


class Predictor(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(9, 64), nn.Tanh(), nn.Linear(64, 32),
                                 nn.Tanh(), nn.Linear(32, 2))
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, x):
        # Learn changes to motion, with constant velocity as the initial model.
        return x[..., 2:4] * 30 + self.net(x)


class Policy(nn.Module):
    def __init__(self):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(OBS_DIM, 128), nn.Tanh(),
                                  nn.Linear(128, 128), nn.Tanh())
        self.actor = nn.Linear(128, len(ACTIONS))
        self.critic = nn.Linear(128, 1)

    def forward(self, x, mask):
        h = self.body(x)
        return self.actor(h).masked_fill(~mask, -1e9), self.critic(h).squeeze(-1)


class Observer:
    """Features use only current/past exported observations, never game objects."""
    def __init__(self, predictor=None):
        self.previous = {}
        self.velocities = {}
        self.previous_frame = None
        self.direction = -1
        self.economy = {}
        self.last_shop = -1000
        self.predictor = predictor
        self.tracks = []
        self.cached = None

    def encode(self, s):
        frame = s['frame']
        if self.previous_frame == frame and self.cached is not None:
            return self.cached
        elapsed = max(1, frame - (self.previous_frame or frame - 6))
        width, height = s['screen']['width'], s['screen']['height']
        ship = s.get('ship') or {'x': width / 2, 'y': height * .9, 'width': 0, 'height': 0}
        sx = (ship['x'] + ship['width'] / 2) / width
        sy = (ship['y'] + ship['height'] / 2) / height
        hud = s.get('hud', {})
        if 'shop' in s:
            self.economy = s['shop']
        mask = np.zeros(len(ACTIONS), dtype=bool)
        if s.get('accepts_controls'):
            mask[:6] = True
            for i in range(6, 10):
                mask[i] = ACTIONS[i] in s['actions']
            mask[9] &= frame - self.last_shop >= 300 and hud.get('coins', 0) >= 3
        if s['state'] == 'shop':
            mask[10] = True
            offers = {o['id'] for o in s['shop']['offers']}
            for i in range(11, len(ACTIONS)):
                mask[i] = ACTIONS[i] in offers
        if not mask.any():
            mask[5] = True  # Caller waits during cinematic/death, never sends it.
        bins = np.zeros((12, 4), dtype=np.float32)
        nearest = []
        current, velocity, self.tracks = {}, {}, []
        for o in s.get('objects', []):
            x = (o['x'] + o['width'] / 2) / width
            y = (o['y'] + o['height'] / 2) / height
            old = self.previous.get(o['id'], (x, y))
            vx, vy = (x - old[0]) / elapsed, (y - old[1]) / elapsed
            pvx, pvy = self.velocities.get(o['id'], (vx, vy))
            current[o['id']], velocity[o['id']] = (x, y), (vx, vy)
            kind = o['kind']
            if kind in HAZARDS:
                f = [x, y, vx * 100, vy * 100, sx, HAZARDS.index(kind) / 5,
                     pvx * 100, pvy * 100, elapsed / 60]
                self.tracks.append((o['id'], f, x, y))
                nearest.append((abs(y - sy) + abs(x - sx) * .4, x - sx, sy - y, vx * 100, vy * 100))
            col = min(11, max(0, int(x * 12)))
            if kind in HAZARDS:
                proximity = max(0, 1 - abs(sy - y) * 2)
                bins[col, 0] += proximity
                predicted_x = min(.999, max(0, x + vx * 30))
                bins[int(predicted_x * 12), 1] += max(0, 1 - abs(sy - (y + vy * 30)) * 2)
            if kind in ('alien', 'boss'):
                bins[col, 2] += .2
            if kind in ('coin', 'gem'):
                bins[col, 3] += max(.1, y) * .2
        if self.predictor is not None and self.tracks:
            with torch.no_grad():
                predictions = self.predictor(torch.tensor([t[1] for t in self.tracks], dtype=torch.float32)).numpy() / 100
            bins[:, 1] = 0
            for (_, _, x, y), (dx, dy) in zip(self.tracks, predictions):
                px = min(.999, max(0, x + float(dx)))
                bins[int(px * 12), 1] += max(0, 1 - abs(sy - (y + float(dy))) * 2)
        nearest.sort()
        near = [v for entry in nearest[:6] for v in entry[1:]]
        near += [0.] * (24 - len(near))
        skills, items = self.economy.get('skills', {}), self.economy.get('items', {})
        armor = ['silver', 'gold', 'mithril', 'galvorn', 'tilkal']
        armor_level = armor.index(self.economy['armor']) + 1 if self.economy.get('armor') in armor else 0
        obs = [sx, hud.get('hp', 0) / max(1, hud.get('max_hp', 30)),
               hud.get('hp', 0) / 100, hud.get('score', 0) / 67600,
               hud.get('level', 1) / 50, hud.get('coins', 0) / 100,
               hud.get('missiles', 0) / 20, self.direction,
               float(s['state'] == 'playing'), float(s['state'] == 'shop')]
        obs += bins.flatten().tolist() + near
        obs += [skills.get(k, 0) / 5 for k in ('speed', 'ammo', 'vitality', 'damage')]
        obs += [items.get(k, 0) / 5 for k in ('magnet', 'shield', 'clover')] + [armor_level / 5]
        self.previous, self.velocities, self.previous_frame = current, velocity, frame
        self.cached = np.clip(np.asarray(obs, dtype=np.float32), -5, 5), mask
        return self.cached

    def used(self, action, frame):
        if action < 6:
            self.direction = (-1, 1, 0)[action % 3]
        if action == 9:
            self.last_shop = frame


def teacher(s, obs, mask, observer, skill_drills=False, aim_drills=False):
    """Warm-start demonstrations. This is a baseline, not the trained network."""
    hud = s.get('hud', {})
    if s['state'] == 'shop':
        skills = s['shop']['skills']
        items = s['shop']['items']
        priorities = []
        if skill_drills:
            for item in ('clover', 'magnet', 'shield'):
                if items.get(item, 0) == 0:
                    priorities.append('buy_item:' + item)
        if hud.get('hp', 30) < hud.get('max_hp', 30) * .7:
            priorities.append('upgrade_skill:vitality')
        if skills.get('ammo', 0) < 2:
            priorities.append('upgrade_skill:ammo')
        if skills.get('speed', 0) < 2:
            priorities.append('upgrade_skill:speed')
        priorities += ['upgrade_skill:damage', 'buy_armor:silver', 'buy_armor:gold',
                       'buy_armor:mithril', 'buy_armor:galvorn', 'buy_armor:tilkal',
                       'upgrade_skill:ammo', 'upgrade_skill:speed']
        if items.get('magnet', 0) == 0:
            priorities.append('buy_item:magnet')
        if items.get('shield', 0) < 1:
            priorities.append('buy_item:shield')
        if items.get('clover', 0) < 1:
            priorities.append('buy_item:clover')
        for name in priorities:
            a = ACTIONS.index(name)
            if mask[a]:
                return a
        return 10
    bins = obs[10:58].reshape(12, 4)
    sx = obs[0]
    danger = max(bins[min(11, max(0, int(sx * 12))), :2])
    if mask[8] and danger > (.3 if skill_drills else .8):
        return 8
    if mask[6] and (sum(o['kind'] == 'alien' for o in s.get('objects', [])) >= 3
                    or any(o['kind'] == 'boss' for o in s.get('objects', []))):
        return 6
    if mask[7] and sum(o['kind'] in ('coin', 'gem') for o in s.get('objects', [])) >= (1 if skill_drills else 2):
        return 7
    if mask[9] and (hud.get('coins', 0) >= 10 or (hud.get('hp', 30) < 20 and hud.get('coins', 0) >= 8)):
        return 9
    direction = observer.direction or -1
    if sx < .14:
        direction = 1
    elif sx > .86:
        direction = -1
    col = min(11, max(0, int(sx * 12)))
    left, right = max(0, col - 1), min(11, col + 1)
    if danger > .4:
        lrisk, rrisk = sum(bins[left, :2]), sum(bins[right, :2])
        if lrisk + .2 < rrisk and sx > .14:
            direction = -1
        elif rrisk + .2 < lrisk and sx < .86:
            direction = 1
    elif aim_drills:
        enemies = [o for o in s.get('objects', []) if o['kind'] in ('alien', 'boss')]
        bosses = [o for o in enemies if o['kind'] == 'boss']
        targets = bosses or (enemies if len(enemies) <= 3 else [])
        if targets:
            target = min(targets, key=lambda o: abs((o['x'] + o['width'] / 2) / s['screen']['width'] - sx))
            target_x = (target['x'] + target['width'] / 2) / s['screen']['width']
            if abs(target_x - sx) < .02:
                return 2  # Hold the firing lane until visible danger approaches.
            return 0 if target_x < sx else 1
    return 0 if direction < 0 else 1


class Practice:
    """Original run_game, original rendering/physics, temporary unauthenticated saves.

    A clock boundary returns control after six normal frames. Only the real-time
    sleep is omitted. This class is never used for ranked play.
    """
    def __init__(self, seed):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
        import pygame
        from alien_invasion import AlienInvasion
        from game_stats import GameState

        class OfflineGame(AlienInvasion):
            def _start_update_check(self):
                pass

            def _upload_current_stats(self):
                pass

        self.folder = tempfile.TemporaryDirectory(prefix='alien-practice-')
        self.old_argv = sys.argv[:]
        sys.argv = [str(Path(self.folder.name) / 'practice.py')]
        random.seed(seed)
        self.game = OfflineGame(0, Path(self.folder.name) / 'session.dat')
        self.game.state = GameState.MENU
        self.game.login_overlay = None
        pygame.key.stop_text_input()
        self.game._update_screen()
        self.control = self.game.text_control

        class Boundary(Exception):
            pass

        self.boundary = Boundary

        class Clock:
            remaining = 6

            def tick(self, _fps):
                self.remaining -= 1
                if self.remaining <= 0:
                    raise Boundary()

        self.game.clock = Clock()

    def reset(self):
        self.game._start_new_game()
        return self.state()

    def state(self):
        self.control.publish(force=True, advance_frame=False)
        return json.loads(self.control._snapshot)

    def step(self, action):
        s = self.state()
        if s.get('accepts_controls') or s['state'] == 'shop':
            from text_control import validate_command
            self.control.apply(validate_command(command(action)))
        self.game.clock.remaining = 6
        try:
            self.game.run_game()
        except self.boundary:
            pass
        return self.state()

    def close(self):
        import pygame
        self.control.close()
        pygame.quit()
        sys.argv = self.old_argv
        self.folder.cleanup()


def save_checkpoint(path, policy, predictor, metrics):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'version': 1, 'actions': ACTIONS, 'metrics': metrics,
            'policy': {k: v.detach().cpu().tolist() for k, v in policy.state_dict().items()},
            'predictor': {k: v.detach().cpu().tolist() for k, v in predictor.state_dict().items()}}
    if not encrypt_json(data, path):
        raise OSError('Could not save checkpoint')


def load_checkpoint(path):
    data = decrypt_json(Path(path))
    if not data or data['version'] != 1 or data['actions'] != ACTIONS:
        raise ValueError('Invalid/incompatible pilot checkpoint')
    policy, predictor = Policy(), Predictor()
    policy.load_state_dict({k: torch.tensor(v) for k, v in data['policy'].items()})
    predictor.load_state_dict({k: torch.tensor(v) for k, v in data['predictor'].items()})
    return policy.eval(), predictor.eval(), data['metrics']


def train(args):
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    policy, predictor = Policy(), Predictor()
    practice = Practice(args.seed)
    demos, masks, labels, tracks_x, tracks_y = [], [], [], [], []
    scores, metrics = [], {'seed': args.seed, 'target_score': 67600}
    started = time.monotonic()
    try:
        for episode in range(args.episodes):
            s = practice.reset()
            obsr = Observer()
            past = deque()
            last_score = 0
            for step in range(args.steps):
                obs, mask = obsr.encode(s)
                if not s.get('accepts_controls') and s['state'] != 'shop':
                    if s.get('phase') in ('dying', 'game_over') or s['state'] == 'menu':
                        break
                    s = practice.step(5)
                    continue
                a = teacher(s, obs, mask, obsr)
                demos.append(obs); masks.append(mask); labels.append(a)
                # Supervised prediction labels come from LATER visible observations.
                current = {t[0]: t for t in obsr.tracks}
                past.append((s['frame'], list(obsr.tracks)))
                while past and s['frame'] - past[0][0] >= 30:
                    old_frame, old_tracks = past.popleft()
                    if s['frame'] - old_frame <= 42 and s['state'] == 'playing':
                        for identity, f, x, y in old_tracks:
                            if identity in current:
                                new = current[identity]
                                tracks_x.append(f)
                                scale = 30 / (s['frame'] - old_frame)
                                tracks_y.append([(new[2] - x) * 100 * scale, (new[3] - y) * 100 * scale])
                obsr.used(a, s['frame'])
                s = practice.step(a)
                last_score = s.get('hud', {}).get('score', last_score)
            scores.append(last_score)
            print(f'demo episode={episode + 1} score={last_score} samples={len(demos)} seconds={time.monotonic()-started:.1f}', flush=True)
        x = torch.tensor(np.asarray(demos)); m = torch.tensor(np.asarray(masks)); y = torch.tensor(labels)
        optimizer = torch.optim.Adam(policy.parameters(), lr=1e-3)
        # Class balancing prevents rare shop and item decisions vanishing in a
        # dataset dominated by held movement/fire frames.
        counts = torch.bincount(y, minlength=len(ACTIONS)).clamp(min=1)
        weights = (len(y) / counts.float()).sqrt().clamp(max=30)
        for epoch in range(25):
            order = torch.randperm(len(x))
            for ix in order.split(512):
                logits, _ = policy(x[ix], m[ix])
                loss = nn.functional.cross_entropy(logits, y[ix], weight=weights)
                optimizer.zero_grad(); loss.backward(); optimizer.step()
        with torch.no_grad():
            accuracy = (policy(x, m)[0].argmax(-1) == y).float().mean().item()
        metrics.update(demonstration_scores=scores, demonstration_samples=len(x), imitation_training_accuracy=accuracy)
        tx, ty = torch.tensor(np.asarray(tracks_x), dtype=torch.float32), torch.tensor(np.asarray(tracks_y), dtype=torch.float32)
        split = int(len(tx) * .8)
        opt = torch.optim.Adam(predictor.parameters(), lr=1e-3)
        for epoch in range(20):
            for ix in torch.randperm(split).split(1024):
                loss = nn.functional.smooth_l1_loss(predictor(tx[ix]), ty[ix])
                opt.zero_grad(); loss.backward(); opt.step()
        with torch.no_grad():
            metrics['prediction_samples'] = len(tx)
            metrics['prediction_validation_mae_normalized'] = float((predictor(tx[split:]) - ty[split:]).abs().mean() / 100)
            # Constant-velocity extrapolation is a meaningful prediction baseline.
            baseline = tx[split:, 2:4] * 30
            metrics['velocity_baseline_mae_normalized'] = float((baseline - ty[split:]).abs().mean() / 100)
        print('Supervised metrics:', json.dumps(metrics), flush=True)
        save_checkpoint(args.output, policy, predictor, metrics)
        save_checkpoint(str(args.output) + '.imitation.dat', policy, predictor, metrics)
        # PPO-Clip fine tuning on the same real game rules.
        opt = torch.optim.Adam(policy.parameters(), lr=2e-4)
        s = practice.reset(); obsr = Observer(predictor)
        rl_scores = []; episode_score = 0
        for iteration in range(args.ppo):
            batch = []
            for _ in range(512):
                obs, mask = obsr.encode(s)
                while not s.get('accepts_controls') and s['state'] != 'shop':
                    if s.get('phase') in ('dying', 'game_over') or s['state'] == 'menu':
                        rl_scores.append(episode_score)
                        s = practice.reset(); obsr = Observer(predictor); episode_score = 0
                    else:
                        s = practice.step(5)
                    obs, mask = obsr.encode(s)
                with torch.no_grad():
                    logits, value = policy(torch.tensor(obs), torch.tensor(mask))
                    dist = Categorical(logits=logits)
                    act = dist.sample()
                hud = s.get('hud', {})
                obsr.used(int(act), s['frame'])
                next_s = practice.step(int(act))
                nh = next_s.get('hud', {})
                done = next_s.get('phase') in ('dying', 'game_over') or next_s['state'] == 'menu'
                score = nh.get('score', hud.get('score', episode_score))
                # Shop screens do not display score; retain it across visits.
                reward = max(0, score - episode_score) / 100
                reward += min(0, nh.get('hp', hud.get('hp', 30)) - hud.get('hp', 30)) / 10
                reward -= .005 + (2 if done else 0)
                batch.append((obs, mask, int(act), float(dist.log_prob(act)), float(value), reward, done))
                episode_score = score
                s = next_s
            next_obs, next_mask = obsr.encode(s)
            with torch.no_grad():
                bootstrap = float(policy(torch.tensor(next_obs), torch.tensor(next_mask))[1])
            advantage, advantages, last_value = 0, [], bootstrap
            for row in reversed(batch):
                nonterminal = 1 - row[6]
                delta = row[5] + .99 * last_value * nonterminal - row[4]
                advantage = delta + .99 * .95 * nonterminal * advantage
                advantages.append(advantage); last_value = row[4]
            advantages = torch.tensor(advantages[::-1])
            bx = torch.tensor(np.asarray([b[0] for b in batch])); bm = torch.tensor(np.asarray([b[1] for b in batch]))
            ba = torch.tensor([b[2] for b in batch]); oldp = torch.tensor([b[3] for b in batch])
            returns = advantages + torch.tensor([b[4] for b in batch])
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
            for _ in range(4):
                for ix in torch.randperm(len(batch)).split(128):
                    logits, value = policy(bx[ix], bm[ix]); dist = Categorical(logits=logits)
                    ratio = (dist.log_prob(ba[ix]) - oldp[ix]).exp()
                    actor_loss = -torch.minimum(ratio * advantages[ix], ratio.clamp(.8, 1.2) * advantages[ix]).mean()
                    loss = actor_loss + .5 * (value - returns[ix]).square().mean() - .01 * dist.entropy().mean()
                    opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(policy.parameters(), .5); opt.step()
            metrics.update(ppo_iterations=iteration + 1, ppo_completed_scores=rl_scores,
                           training_seconds=time.monotonic() - started)
            save_checkpoint(args.output, policy, predictor, metrics)
            print(f'PPO iteration={iteration+1} current_score={episode_score} completed={rl_scores} seconds={time.monotonic()-started:.1f}', flush=True)
    finally:
        practice.close()


def play(args):
    torch.set_num_threads(1)
    policy, predictor, metrics = load_checkpoint(args.output)
    client = GameClient(args.session_file)
    obsr = Observer(predictor)
    s = client.state()
    if s['state'] == 'menu' and args.start:
        client.act(action='start'); time.sleep(.1)
    elif s['state'] == 'paused':
        client.act(action='resume'); time.sleep(.1)
    elif s['state'] != 'playing':
        raise ValueError('Need a playing game or --start from menu')
    deadline = time.monotonic() + args.seconds
    next_report = 0
    best_seen = 0
    counts = {}
    try:
        while time.monotonic() < deadline:
            s = client.state()
            if time.time() - s['observed_at'] > 1:
                raise ValueError('Stale observation')
            score = s.get('hud', {}).get('score', 0)
            best_seen = max(best_seen, score)
            if time.monotonic() >= next_report:
                print(json.dumps({'state': s['state'], 'hud': s.get('hud'), 'max_score_seen': best_seen,
                                  'actions': counts}), flush=True)
                next_report = time.monotonic() + 5
            if s['state'] == 'menu':
                break
            if not s.get('accepts_controls') and s['state'] != 'shop':
                time.sleep(.1); continue
            obs, mask = obsr.encode(s)
            with torch.no_grad():
                logits, _ = policy(torch.tensor(obs), torch.tensor(mask))
                a = int(logits.argmax())
            try:
                client.act(**command(a))
                obsr.used(a, s['frame'])
                counts[ACTIONS[a]] = counts.get(ACTIONS[a], 0) + 1
            except ValueError as exc:
                if 'HTTP 409' not in str(exc):
                    raise
            time.sleep(.1)
    finally:
        try:
            s = client.state()
            if s['state'] == 'shop':
                client.act(action='back'); time.sleep(.1); s = client.state()
            if s.get('accepts_controls'):
                client.act(move='stop', fire=False); client.act(action='pause')
        except (OSError, ValueError):
            pass
    print('LIVE_RESULT', json.dumps({'max_score_seen': best_seen, 'actions': counts}), flush=True)


def evaluate(args):
    torch.set_num_threads(1)
    policy, predictor, _ = load_checkpoint(args.output)
    results = []
    for episode in range(args.episodes):
        practice = Practice(args.seed + episode)
        counts = {}
        try:
            s = practice.reset()
            obsr = Observer(predictor)
            score, hp = 0, 30
            for step in range(args.steps):
                if s.get('phase') in ('dying', 'game_over') or s['state'] == 'menu':
                    break
                obs, mask = obsr.encode(s)
                if s.get('accepts_controls') or s['state'] == 'shop':
                    if args.baseline:
                        a = teacher(s, obs, mask, obsr)
                    else:
                        with torch.no_grad():
                            a = int(policy(torch.tensor(obs), torch.tensor(mask))[0].argmax())
                    obsr.used(a, s['frame'])
                    counts[ACTIONS[a]] = counts.get(ACTIONS[a], 0) + 1
                else:
                    a = 5
                s = practice.step(a)
                score = s.get('hud', {}).get('score', score)
                hp = s.get('hud', {}).get('hp', hp)
            row = {'seed': args.seed + episode, 'score': score, 'hp': hp, 'steps': step + 1,
                   'truncated': step + 1 >= args.steps, 'actions': counts}
            results.append(row)
            print('EVAL', json.dumps(row), flush=True)
        finally:
            practice.close()
    print('EVAL_SUMMARY', json.dumps({'mean': float(np.mean([r['score'] for r in results])),
                                     'best': max(r['score'] for r in results)}), flush=True)
    report = Path(str(args.output) + ('.baseline-evaluation.dat' if args.baseline else '.evaluation.dat'))
    encrypt_json({'results': results}, report)


def refine(args):
    """DAgger: label states actually visited by the learner, including mistakes."""
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    policy, predictor, metrics = load_checkpoint(args.output)
    policy.train()
    optimizer = torch.optim.Adam(policy.parameters(), lr=3e-4)
    xs, ms, ys, importance = [], [], [], []
    scores = []
    action_counts = {}
    for episode in range(args.episodes):
        env = Practice(args.seed + episode)
        try:
            s = env.reset(); obsr = Observer(predictor); score = 0
            for step in range(args.steps):
                if s.get('phase') in ('dying', 'game_over') or s['state'] == 'menu':
                    break
                obs, mask = obsr.encode(s)
                if s.get('accepts_controls') or s['state'] == 'shop':
                    target = teacher(s, obs, mask, obsr, skill_drills=args.skill_drills,
                                     aim_drills=args.aim_drills)
                    with torch.no_grad():
                        predicted = int(policy(torch.tensor(obs), torch.tensor(mask))[0].argmax())
                    xs.append(obs); ms.append(mask); ys.append(target)
                    # Recovery decisions and item/shop decisions are uncommon
                    # but important; explicitly upweight their demonstrations.
                    importance.append(8. if target != predicted or target >= 6 else 1.)
                    mixture = .8 if args.skill_drills and (target >= 6 or s['state'] == 'shop') else .2
                    if args.aim_drills and any(o['kind'] == 'boss' for o in s.get('objects', [])):
                        mixture = .8
                    a = target if random.random() < mixture else predicted
                    obsr.used(a, s['frame'])
                    action_counts[ACTIONS[a]] = action_counts.get(ACTIONS[a], 0) + 1
                else:
                    a = 5
                s = env.step(a)
                score = s.get('hud', {}).get('score', score)
            scores.append(score)
        finally:
            env.close()
        if (episode + 1) % 2 == 0 or episode == args.episodes - 1:
            x = torch.tensor(np.asarray(xs)); m = torch.tensor(np.asarray(ms))
            y = torch.tensor(ys); weights = torch.tensor(importance)
            for _ in range(10):
                for ix in torch.randperm(len(x)).split(256):
                    logits, _ = policy(x[ix], m[ix])
                    loss = (nn.functional.cross_entropy(logits, y[ix], reduction='none') * weights[ix]).mean()
                    optimizer.zero_grad(); loss.backward(); optimizer.step()
            metrics.update(dagger_episodes=episode + 1, dagger_samples=len(x),
                           dagger_rollout_scores=scores, dagger_seed=args.seed,
                           refinement_action_counts=action_counts, skill_drills=args.skill_drills)
            metrics['aim_drills'] = args.aim_drills
            save_checkpoint(args.output, policy, predictor, metrics)
        print('DAGGER', json.dumps({'episode': episode + 1, 'score': score, 'samples': len(xs), 'actions': action_counts}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['train', 'play', 'evaluate', 'refine'])
    parser.add_argument('--output', type=Path, default=Path('training_runs/pilot.dat'))
    parser.add_argument('--seed', type=int, default=20260920)
    parser.add_argument('--episodes', type=int, default=6)
    parser.add_argument('--steps', type=int, default=1800)
    parser.add_argument('--ppo', type=int, default=6)
    parser.add_argument('--seconds', type=int, default=900)
    parser.add_argument('--session-file')
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--skill-drills', action='store_true')
    parser.add_argument('--aim-drills', action='store_true')
    args = parser.parse_args()
    if args.episodes < 1 or args.steps < 50 or args.ppo < 0 or args.seconds < 1:
        parser.error('episodes/seconds must be positive, steps >= 50, ppo >= 0')
    if args.mode == 'train':
        train(args)
    elif args.mode == 'evaluate':
        evaluate(args)
    elif args.mode == 'refine':
        refine(args)
    else:
        play(args)


if __name__ == '__main__':
    main()
