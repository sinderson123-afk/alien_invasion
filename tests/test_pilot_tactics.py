"""Spatial regression fixtures contain observations only, never live accounts."""

import tempfile
from pathlib import Path
import unittest

try:
    import numpy as np
    import torch
    from neural_pilot import Observer, Policy, Predictor, load_checkpoint, save_checkpoint
    from pilot_tactics import spatial_action, spatial_features
    TRAINING_AVAILABLE = True
except ImportError:
    TRAINING_AVAILABLE = False


def scene(*objects):
    return {'frame': 10, 'screen': {'width': 1200, 'height': 800},
            'ship': {'x': 552, 'y': 704, 'width': 96, 'height': 96},
            'state': 'playing', 'accepts_controls': True, 'actions': [],
            'hud': {'hp': 30, 'max_hp': 30}, 'objects': list(objects)}


def actor(identity, kind, x, y, width=40, height=32):
    return {'id': identity, 'kind': kind, 'x': x - width / 2,
            'y': y - height / 2, 'width': width, 'height': height}


@unittest.skipUnless(TRAINING_AVAILABLE, 'optional training dependencies not installed')
class SpatialTests(unittest.TestCase):
    def features(self, state, velocities=None):
        return spatial_features(state, velocities or {}, 1.5 / 1200, 2.5 / 800)

    def test_single_enemy_requires_tracking_in_both_directions(self):
        for x, expected in ((300, 0), (900, 1), (600, 2)):
            features = self.features(scene(actor('a', 'alien', x, 300)))
            self.assertEqual(spatial_action(features, .5, -1), expected)

    def test_moving_enemy_requires_lead_even_when_currently_aligned(self):
        state = scene(actor('a', 'alien', 600, 300))
        for vx, expected in ((-.001, 0), (.001, 1)):
            f = self.features(state, {'a': (vx, 0)})
            self.assertAlmostEqual(f[1], 0)
            self.assertGreater(abs(f[2]), .05)
            self.assertEqual(spatial_action(f, .5, -1), expected)

    def test_opposite_targets_in_same_coarse_column_remain_distinguishable(self):
        for x, expected in ((630, 0), (690, 1)):
            state = scene(actor('a', 'alien', x, 300))
            state['ship']['x'] = 612  # Center 660: both targets fall in column 6.
            f = self.features(state)
            self.assertEqual(int(x / 100), 6)
            self.assertEqual(spatial_action(f, .55, -1), expected)

    def test_safe_low_drop_takes_priority_over_opposite_enemy(self):
        for drop_x, expected in ((360, 0), (840, 1)):
            f = self.features(scene(actor('a', 'alien', 1200 - drop_x, 200),
                                    actor('c', 'coin', drop_x, 740, 16, 16)))
            self.assertEqual(spatial_action(f, .5, -1), expected)

    def test_dodge_has_priority_over_pickup(self):
        f = self.features(scene(actor('c', 'gem', 820, 740, 16, 16),
                                actor('b', 'hostile_bullet', 642, 725, 12, 20)))
        self.assertGreater(f[18], 0)
        self.assertEqual(spatial_action(f, .5, 1), 0)

    def test_blank_overlay_does_not_retain_targets(self):
        observer = Observer(obs_dim=110)
        observer.encode(scene(actor('a', 'alien', 300, 300)))
        state = scene()
        state.update(frame=16, accepts_controls=False)
        state.pop('ship')
        obs, _ = observer.encode(state)
        np.testing.assert_array_equal(obs[90:], np.zeros(20))

    def test_both_checkpoint_dimensions_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            for dimension in (90, 110):
                policy, predictor = Policy(dimension), Predictor()
                path = Path(folder) / f'{dimension}.dat'
                save_checkpoint(path, policy, predictor, {})
                restored, _, _ = load_checkpoint(path)
                obs = torch.zeros(dimension)
                mask = torch.ones(23, dtype=torch.bool)
                torch.testing.assert_close(policy(obs, mask)[0], restored(obs, mask)[0])

    def test_original_version_one_checkpoint_still_loads(self):
        from file_crypto import decrypt_json, encrypt_json
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.dat'
            policy = Policy(90)
            save_checkpoint(path, policy, Predictor(), {})
            data = decrypt_json(path)
            data['version'] = 1
            del data['obs_dim']
            encrypt_json(data, path)
            restored, _, _ = load_checkpoint(path)
            obs = torch.zeros(90)
            mask = torch.ones(23, dtype=torch.bool)
            torch.testing.assert_close(policy(obs, mask)[0], restored(obs, mask)[0])

    def test_large_policy_checkpoint_preserves_architecture(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'large.dat'
            policy = Policy(110, hidden=256, depth=3)
            save_checkpoint(path, policy, Predictor(), {})
            restored, _, _ = load_checkpoint(path)
            self.assertEqual((restored.hidden, restored.depth), (256, 3))
            obs = torch.randn(4, 110)
            mask = torch.ones(4, 23, dtype=torch.bool)
            mask[:, 12:] = False
            torch.testing.assert_close(policy(obs, mask)[0], restored(obs, mask)[0])

    def test_parallel_advantages_do_not_cross_episode_boundaries(self):
        from neural_gpu import advantages
        rewards = torch.tensor([[1., 10.], [2., 20.]])
        dones = torch.tensor([[True, False], [False, True]])
        result = advantages(rewards, torch.zeros_like(rewards), dones,
                            torch.tensor([3., 99.]), gamma=1., lam=1.)
        torch.testing.assert_close(result, torch.tensor([[1., 30.], [5., 20.]]))

    def test_parallel_workers_have_independent_normal_movement(self):
        from neural_gpu import Environments
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.dat'
            save_checkpoint(path, Policy(110), Predictor(), {})
            envs = Environments(2, path, 990000)
            try:
                before = [s['obs'][0] for s in envs.states]
                states = envs.step([0, 1])
                self.assertLess(states[0]['obs'][0], before[0])
                self.assertGreater(states[1]['obs'][0], before[1])
                for state in states:
                    self.assertEqual(state['obs'].shape, (110,))
                    self.assertTrue(np.isfinite(state['obs']).all())
                    self.assertTrue(state['mask'][state['label']])
                    self.assertFalse(state['done'])
            finally:
                envs.close()
            self.assertTrue(all(not p.is_alive() for p in envs.processes))

    def test_widening_preserves_policy_value_and_action_mask(self):
        from neural_gpu import widen_policy
        source = Policy(110, hidden=128, depth=2)
        enlarged = widen_policy(source, 512)
        obs = torch.randn(17, 110)
        mask = torch.rand(17, 23) > .3
        original_logits, original_value = source(obs, mask)
        logits, value = enlarged(obs, mask)
        torch.testing.assert_close(logits, original_logits, atol=2e-6, rtol=2e-5)
        torch.testing.assert_close(value, original_value, atol=2e-6, rtol=2e-5)
        self.assertGreater(sum(p.numel() for p in enlarged.parameters()),
                           sum(p.numel() for p in source.parameters()))


if __name__ == '__main__':
    unittest.main()
