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


if __name__ == '__main__':
    unittest.main()
