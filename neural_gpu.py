"""CUDA learner with parallel, isolated original-game environments.

Workers run ordinary game frames on CPU. Only the learner creates a CUDA
context. No worker authenticates, uploads a result, or edits a live save.
"""

import argparse
from collections import deque
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
import traceback

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical

from neural_pilot import (ACTIONS, Observer, Policy, Practice, TACTICAL_OBS_DIM,
                          load_checkpoint, save_checkpoint, teacher)
from pilot_tactics import spatial_action, tactical_cases


def worker(connection, source, seed):
    """One SDL/game instance per spawned process, separate temporary save dir."""
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    torch.set_num_threads(1)
    env = None
    try:
        _, predictor, _ = load_checkpoint(source)
        episode = 0

        def reset():
            nonlocal env, episode
            if env is not None:
                env.close()
            env = Practice(seed + episode)
            episode += 1
            return env.reset(), Observer(predictor, TACTICAL_OBS_DIM)

        def ready(state):
            for _ in range(1000):
                if state.get('accepts_controls') or state['state'] == 'shop':
                    return state
                if state.get('phase') in ('dying', 'game_over') or state['state'] == 'menu':
                    return state
                state = env.step(5)
            raise RuntimeError('Practice environment stuck in a noninteractive phase')

        def observation(state):
            obs, mask = observer.encode(state)
            label = teacher(state, obs, mask, observer, tactics_drills=True)
            return {'obs': obs, 'mask': mask, 'label': label}

        state, observer = reset()
        state = ready(state)
        score = coins_earned = steps = 0
        hp = state['hud'].get('hp', 30)
        connection.send(observation(state))
        while True:
            action = connection.recv()
            if action is None:
                break
            before = state.get('hud', {})
            observer.used(action, state['frame'])
            state = ready(env.step(action))
            after = state.get('hud', {})
            new_score = after.get('score', score)
            new_hp = after.get('hp', hp)
            earned = max(0, after.get('coins', before.get('coins', 0)) - before.get('coins', 0))
            dead = state.get('phase') in ('dying', 'game_over') or state['state'] == 'menu'
            # Observed outcomes only: actual score/coins, damage, elapsed action,
            # and death. Shop purchases and healing do not yield free reward.
            reward = max(0, new_score - score) / 400 + earned * .08
            reward += min(0, new_hp - hp) / 15 - .002 - (2. if dead else 0.)
            score, hp = new_score, new_hp
            coins_earned += earned
            steps += 1
            completed = None
            if dead:
                completed = {'seed': seed + episode - 1, 'score': score,
                             'coins': coins_earned, 'steps': steps}
                state, observer = reset()
                state = ready(state)
                score = coins_earned = steps = 0
                hp = state['hud'].get('hp', 30)
            response = observation(state)
            response.update(reward=reward, done=dead, completed=completed)
            connection.send(response)
    except (EOFError, BrokenPipeError):
        pass
    except BaseException:
        try:
            connection.send({'error': traceback.format_exc()})
        except (EOFError, BrokenPipeError):
            pass
    finally:
        if env is not None:
            env.close()
        connection.close()


class Environments:
    def __init__(self, count, source, seed):
        self.connections, self.processes = [], []
        context = mp.get_context('spawn')
        try:
            for index in range(count):
                parent, child = context.Pipe()
                process = context.Process(target=worker, args=(child, str(source), seed + index * 10000))
                process.start()
                child.close()
                self.connections.append(parent)
                self.processes.append(process)
            self.states = self.receive()
        except BaseException:
            self.close()
            raise

    def receive(self):
        responses = []
        for connection in self.connections:
            if not connection.poll(120):
                raise TimeoutError('Practice worker did not respond within 120 seconds')
            result = connection.recv()
            if 'error' in result:
                raise RuntimeError(result['error'])
            responses.append(result)
        return responses

    def step(self, actions):
        if len(actions) != len(self.connections):
            raise ValueError('One action is required for each practice worker')
        for connection, action in zip(self.connections, actions):
            connection.send(int(action))
        self.states = self.receive()
        return self.states

    def close(self):
        for connection in self.connections:
            try:
                connection.send(None)
            except (EOFError, BrokenPipeError, OSError):
                pass
        for process in self.processes:
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
        for connection in self.connections:
            connection.close()


def advantages(rewards, values, dones, bootstrap, gamma=.995, lam=.95):
    """Each worker's GAE terminates at its own episode boundary."""
    result = torch.zeros_like(rewards)
    tail = torch.zeros_like(bootstrap)
    next_value = bootstrap
    for step in reversed(range(len(rewards))):
        active = 1 - dones[step].float()
        delta = rewards[step] + gamma * next_value * active - values[step]
        tail = delta + gamma * lam * active * tail
        result[step] = tail
        next_value = values[step]
    return result


def encode_batch(states, device):
    return (torch.as_tensor(np.asarray([s['obs'] for s in states]), device=device),
            torch.as_tensor(np.asarray([s['mask'] for s in states]), device=device),
            torch.tensor([s['label'] for s in states], device=device))


def widen_policy(source, hidden):
    """Duplicate neurons without forgetting the source policy's function.

    Divide outgoing weights by replica count. Zero-sum perturbations break
    symmetry in hidden connections while preserving initial outputs.
    """
    if hidden < source.hidden or hidden % source.hidden:
        raise ValueError('New hidden width must be a multiple of source width')
    result = Policy(source.obs_dim, hidden, source.depth)
    replicas = hidden // source.hidden
    indices = torch.arange(hidden) % source.hidden
    weights = source.state_dict()
    expanded = result.state_dict()
    for layer in range(source.depth):
        key = f'body.{layer * 2}'
        w = weights[key + '.weight'][indices]
        if layer:
            w = w[:, indices] / replicas
            noise = torch.randn(hidden, replicas, source.hidden) * 1e-4
            noise -= noise.mean(dim=1, keepdim=True)
            w = w + noise.flatten(1)
        expanded[key + '.weight'] = w
        expanded[key + '.bias'] = weights[key + '.bias'][indices]
    for head in ('actor', 'critic'):
        expanded[head + '.weight'] = weights[head + '.weight'][:, indices] / replicas
        expanded[head + '.bias'] = weights[head + '.bias']
    result.load_state_dict(expanded)
    return result


def action_weights(labels):
    counts = torch.bincount(labels, minlength=len(ACTIONS)).clamp(min=1)
    return (len(labels) / (len(ACTIONS) * counts.float())).sqrt().clamp(.5, 8.)


def run(args):
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable; use a CUDA-enabled PyTorch environment')
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    torch.cuda.set_per_process_memory_fraction(.8)
    torch.set_float32_matmul_precision('high')
    device = torch.device('cuda')
    source_policy, predictor, _ = load_checkpoint(args.source)
    if args.widen_source:
        if source_policy.obs_dim != TACTICAL_OBS_DIM or source_policy.depth != args.depth:
            raise ValueError('Widening requires a 110-input source with matching depth')
        policy = widen_policy(source_policy, args.hidden).to(device)
    else:
        policy = Policy(TACTICAL_OBS_DIM, args.hidden, args.depth).to(device)
    parameters = sum(p.numel() for p in policy.parameters())
    optimizer = torch.optim.AdamW(policy.parameters(), lr=2e-4, weight_decay=1e-4)
    metadata = {'device': torch.cuda.get_device_name(0), 'torch': torch.__version__,
                'seed': args.seed, 'parameters': parameters, 'workers': args.workers,
                'horizon': args.horizon, 'batch': args.batch, 'source': str(args.source),
                'widen_source': args.widen_source, 'balance_actions': args.balance_actions,
                'reward': 'score/400 + earned_coins*.08 + negative_hp/15 - .002 - death*2',
                'source_parameters': sum(p.numel() for p in source_policy.parameters())}
    print('GPU_SETUP', json.dumps(metadata), flush=True)
    started = time.monotonic()
    xs, masks, labels = [], [], []
    for _, direction, pair in tactical_cases(args.seed + 1000000, args.spatial_samples):
        observer = Observer(predictor, TACTICAL_OBS_DIM)
        observer.direction = direction
        for state in pair:
            obs, mask = observer.encode(state)
        xs.append(obs); masks.append(mask)
        labels.append(spatial_action(observer.tactical, obs[0], direction))
    replay_x = torch.as_tensor(np.asarray(xs), device=device)
    replay_m = torch.as_tensor(np.asarray(masks), device=device)
    replay_y = torch.tensor(labels, device=device)
    class_weights = action_weights(replay_y) if args.balance_actions else None
    del xs, masks, labels
    for epoch in range(args.warmup_epochs):
        total_loss = 0.
        for ix in torch.randperm(len(replay_x), device=device).split(args.batch):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = policy(replay_x[ix], replay_m[ix])[0]
                loss = nn.functional.cross_entropy(logits, replay_y[ix], weight=class_weights)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(policy.parameters(), .5, error_if_nonfinite=True)
            optimizer.step()
            total_loss += float(loss.detach())
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print('GPU_WARMUP', json.dumps({'epoch': epoch + 1, 'loss_sum': total_loss,
                                            'seconds': time.monotonic() - started}), flush=True)
    completed = deque(maxlen=100)
    total_steps = 0
    envs = Environments(args.workers, args.source, args.seed)
    try:
        for iteration in range(args.imitation_rounds + args.ppo_rounds):
            supervised = iteration < args.imitation_rounds
            phase = 'imitation' if supervised else 'ppo'
            for group in optimizer.param_groups:
                group['lr'] = (5e-5 if args.widen_source else 2e-4) if supervised else 3e-5
            collected = time.monotonic()
            rows = []
            for _ in range(args.horizon):
                obs, mask, label = encode_batch(envs.states, device)
                with torch.no_grad():
                    logits, value = policy(obs, mask)
                    distribution = Categorical(logits=logits)
                    action = distribution.sample()
                    if supervised:
                        # Demonstrations are NEVER mixed into PPO rollouts.
                        action = torch.where(torch.rand(args.workers, device=device) < .7, label, action)
                    log_prob = distribution.log_prob(action)
                states = envs.step(action.cpu().tolist())
                reward = torch.tensor([s['reward'] for s in states], device=device)
                done = torch.tensor([s['done'] for s in states], device=device)
                rows.append((obs, mask, label, action, log_prob, value, reward, done))
                completed.extend(s['completed'] for s in states if s['completed'] is not None)
            total_steps += args.workers * args.horizon
            rollout_seconds = time.monotonic() - collected
            bx, bm, by, ba, bp, bv, br, bd = [torch.stack([r[i] for r in rows]) for i in range(8)]
            with torch.no_grad():
                obs, mask, _ = encode_batch(envs.states, device)
                boot = policy(obs, mask)[1]
                adv = advantages(br, bv, bd, boot)
                returns = (adv + bv).flatten()
                adv = adv.flatten()
                adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            bx, bm = bx.flatten(0, 1), bm.flatten(0, 1)
            by, ba, bp = by.flatten(), ba.flatten(), bp.flatten()
            if supervised:
                replay_x = torch.cat((replay_x, bx))[-args.replay_size:]
                replay_m = torch.cat((replay_m, bm))[-args.replay_size:]
                replay_y = torch.cat((replay_y, by))[-args.replay_size:]
                class_weights = action_weights(replay_y) if args.balance_actions else None
                for _ in range(args.epochs):
                    for ix in torch.randperm(len(replay_x), device=device).split(args.batch):
                        with torch.autocast('cuda', dtype=torch.bfloat16):
                            loss = nn.functional.cross_entropy(policy(replay_x[ix], replay_m[ix])[0], replay_y[ix],
                                                               weight=class_weights)
                        optimizer.zero_grad(set_to_none=True)
                        loss.backward()
                        nn.utils.clip_grad_norm_(policy.parameters(), .5, error_if_nonfinite=True)
                        optimizer.step()
                kl = 0.
            else:
                # Pure on-policy clipped updates plus a small supervised anchor.
                for epoch in range(args.epochs):
                    divergences = []
                    for ix in torch.randperm(len(bx), device=device).split(min(args.batch, 2048)):
                        logits, value = policy(bx[ix], bm[ix])
                        distribution = Categorical(logits=logits)
                        log_ratio = distribution.log_prob(ba[ix]) - bp[ix]
                        ratio = log_ratio.exp()
                        actor = -torch.minimum(ratio * adv[ix], ratio.clamp(.85, 1.15) * adv[ix]).mean()
                        critic = nn.functional.smooth_l1_loss(value, returns[ix])
                        anchor_ix = torch.randint(len(replay_x), (min(2048, len(replay_x)),), device=device)
                        anchor = nn.functional.cross_entropy(policy(replay_x[anchor_ix], replay_m[anchor_ix])[0],
                                                            replay_y[anchor_ix], weight=class_weights)
                        loss = actor + .5 * critic - .005 * distribution.entropy().mean() + .03 * anchor
                        optimizer.zero_grad(set_to_none=True)
                        loss.backward()
                        nn.utils.clip_grad_norm_(policy.parameters(), .5, error_if_nonfinite=True)
                        optimizer.step()
                        divergences.append(float(((ratio - 1) - log_ratio).mean().detach()))
                    kl = float(np.mean(divergences))
                    if kl > .025:
                        break
            metadata.update(iteration=iteration + 1, phase=phase, total_decisions=total_steps,
                            spatial_samples=args.spatial_samples, completed_episodes=list(completed),
                            seconds=time.monotonic() - started,
                            peak_allocated_mb=torch.cuda.max_memory_allocated() / 2**20,
                            peak_reserved_mb=torch.cuda.max_memory_reserved() / 2**20)
            print('GPU_ROUND', json.dumps({**{k: metadata[k] for k in ('iteration', 'phase', 'total_decisions', 'seconds',
                                                                      'peak_allocated_mb', 'peak_reserved_mb')},
                                           'rollout_seconds': rollout_seconds, 'kl': kl,
                                           'recent_score': float(np.mean([x['score'] for x in completed])) if completed else None,
                                           'completed_count': len(completed)}), flush=True)
            if iteration + 1 == args.imitation_rounds or (iteration + 1 - args.imitation_rounds) % args.save_every == 0:
                checkpoint = args.output.with_name(args.output.stem + f'-{phase}-{iteration + 1}.dat')
                save_checkpoint(checkpoint, policy, predictor, metadata)
                print('GPU_CHECKPOINT', str(checkpoint), flush=True)
        save_checkpoint(args.output, policy, predictor, metadata)
        print('GPU_COMPLETE', json.dumps(metadata), flush=True)
    finally:
        envs.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('training_runs/champion.dat'))
    parser.add_argument('--output', type=Path, default=Path('training_runs/pilot-gpu.dat'))
    parser.add_argument('--seed', type=int, default=22000)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--hidden', type=int, default=1024)
    parser.add_argument('--depth', type=int, default=3)
    parser.add_argument('--horizon', type=int, default=256)
    parser.add_argument('--imitation-rounds', type=int, default=16)
    parser.add_argument('--ppo-rounds', type=int, default=64)
    parser.add_argument('--spatial-samples', type=int, default=60000)
    parser.add_argument('--warmup-epochs', type=int, default=40)
    parser.add_argument('--batch', type=int, default=8192)
    parser.add_argument('--epochs', type=int, default=6)
    parser.add_argument('--replay-size', type=int, default=262144)
    parser.add_argument('--save-every', type=int, default=16)
    parser.add_argument('--widen-source', action='store_true')
    parser.add_argument('--balance-actions', action='store_true')
    args = parser.parse_args()
    if any(getattr(args, key) < 1 for key in ('workers', 'horizon', 'imitation_rounds', 'ppo_rounds', 'spatial_samples',
                                             'batch', 'epochs', 'replay_size', 'save_every')) or args.warmup_epochs < 0:
        parser.error('Training counts must be positive; warmup epochs may be zero')
    if not 32 <= args.hidden <= 2048 or not 1 <= args.depth <= 6 or args.workers > 16:
        parser.error('hidden: 32..2048; depth: 1..6; workers: 1..16')
    if args.output.resolve() == args.source.resolve():
        parser.error('Output must not overwrite the source/champion checkpoint')
    run(args)


if __name__ == '__main__':
    mp.freeze_support()
    main()
