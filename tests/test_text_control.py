"""Offline control-contract tests; all saves and sessions live in a temp folder."""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from concurrent.futures import Future
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame

from alien_invasion import AlienInvasion
from game_control import GameClient
from text_control import validate_command


class ValidationTests(unittest.TestCase):
    def test_fresh_profiles_do_not_share_skills_or_items(self):
        from player_data import PlayerData
        with tempfile.TemporaryDirectory() as folder:
            first = PlayerData(Path(folder) / 'first.dat').load()
            first['skills']['speed'] = 5
            first['items']['shield'] = 5
            second = PlayerData(Path(folder) / 'second.dat').load()
            self.assertEqual(second['skills']['speed'], 0)
            self.assertEqual(second['items']['shield'], 0)

    def test_mutations_and_malformed_controls_rejected(self):
        for payload in ({'score': 9999}, {'hp': 999}, {'x': 0}, {'action': 'eval'},
                        {'move': 'up'}, {'fire': 1}, {'lease_ms': True},
                        {'lease_ms': 2001}, {'lease_ms': 0}, [], {},
                        {'action': 'start', 'fire': True}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_command(payload)


class LoopTests(unittest.TestCase):
    def test_shop_uses_visible_prices_and_does_not_stack_speed(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch('sys.argv', [str(Path(folder) / 'game.py')]), \
                patch.object(AlienInvasion, '_start_update_check'), \
                patch('player_data.PlayerData.is_authenticated', return_value=True):
            game = AlienInvasion(0, Path(folder) / 'control.dat')
            try:
                # Isolated economy fixture; no real account or score upload.
                game.stats.coins = 20
                control = game.text_control
                control.apply({'action': 'shop'})
                game._update_screen()
                control.apply({'action': 'purchase', 'offer': 'upgrade_skill:speed'})
                self.assertEqual(game.stats.coins, 17)
                speed = game.settings.ship_speed
                self.assertAlmostEqual(speed, 1.65)
                control.apply({'action': 'purchase', 'offer': 'buy_item:shield'})
                self.assertEqual(game.stats.coins, 7)
                self.assertEqual(game.stats.items['shield'], 1)
                self.assertEqual(game.settings.ship_speed, speed)
                with self.assertRaises(ValueError):
                    control.apply({'action': 'purchase', 'offer': 'buy_item:shield'})
                with self.assertRaises(ValueError):
                    control.apply({'action': 'purchase', 'offer': 'buy_armor:tilkal'})
                self.assertEqual(game.stats.coins, 7)
                control.publish(force=True)
                exported = json.loads(control._snapshot)
                self.assertIn('shop', exported)
                self.assertNotIn('objects', exported)
            finally:
                game.text_control.close()
                pygame.quit()

    def test_real_game_loop_over_http(self):
        # Use the real update/render loop and original speed/cooldown/cap. No
        # real account is loaded, and update checks/stat uploads are disabled.
        with tempfile.TemporaryDirectory() as folder:
            session = Path(folder) / 'control.dat'
            with patch('sys.argv', [str(Path(folder) / 'game.py')]), \
                    patch.object(AlienInvasion, '_start_update_check'), \
                    patch.object(AlienInvasion, '_upload_current_stats'), \
                    patch('player_data.PlayerData.is_authenticated', return_value=True):
                game = AlienInvasion(0, session)
                self.assertTrue(str(game.stats.player_data.file_path).startswith(folder))
                control = game.text_control
                client = GameClient(session)
                done = threading.Event()
                errors = []
                shots = []
                original_fire = game._fire_bullet

                def counted_fire():
                    shots.append(control.frame)
                    return original_fire()

                game._fire_bullet = counted_fire

                def wait_for(predicate):
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        state = client.state()
                        if predicate(state):
                            return state
                        time.sleep(0.02)
                    raise AssertionError('Timed out waiting for observed state')

                def drive():
                    try:
                        self.assertEqual(client.state()['state'], 'menu')
                        opener = build_opener(ProxyHandler({}))
                        for headers in ({}, {'Authorization': 'Bearer ' + control.token,
                                              'Origin': 'https://example.org'}):
                            with self.assertRaises(HTTPError) as denied:
                                opener.open(Request(control.url + '/state', headers=headers), timeout=2)
                            self.assertEqual(denied.exception.code, 403)
                        with self.assertRaisesRegex(ValueError, 'HTTP 400'):
                            client.act(score=100000)
                        with self.assertRaisesRegex(ValueError, 'HTTP 409'):
                            client.act(move='left')
                        client.act(action='start')
                        first = wait_for(lambda s: s['state'] == 'playing')
                        with self.assertRaisesRegex(ValueError, 'HTTP 409'):
                            client.act(action='missile')
                        client.act(move='right', fire=True, lease_ms=500)
                        moved = wait_for(lambda s: s.get('ship', {}).get('x', 0) > first['ship']['x'] + 5)
                        delta = moved['ship']['x'] - first['ship']['x']
                        self.assertLessEqual(delta, (moved['frame'] - first['frame']) * game.settings.ship_speed + 1)
                        for _ in range(12):
                            client.act(move='right', fire=True, lease_ms=200)
                        expired = wait_for(lambda s: s['control']['lease_remaining_ms'] == 0
                                          and not s['control']['fire'])
                        self.assertEqual(expired['control']['move'], 'stop')
                        self.assertGreater(len(shots), 0)
                        for before, after in zip(shots, shots[1:]):
                            self.assertGreaterEqual(after - before, game.settings.bullet_fire_cooldown + 1)
                        self.assertLessEqual(len(game.bullets), game.settings.bullet_allowed)
                        time.sleep(0.1)
                        self.assertEqual(client.state()['ship']['x'], expired['ship']['x'])
                        client.act(action='pause')
                        paused = wait_for(lambda s: s['state'] == 'paused')
                        with self.assertRaisesRegex(ValueError, 'HTTP 409'):
                            client.act(move='left', fire=True)
                        time.sleep(0.1)
                        self.assertEqual(client.state()['objects'], paused['objects'])
                        client.act(action='resume')
                        client.act(move='left', fire=True)
                        wait_for(lambda s: s['control']['fire'])
                        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
                        wait_for(lambda s: not s['control']['fire'])
                        self.assertEqual(game.ship.moving_left, False)
                        self.assertEqual(game.stats.score, 0)
                        self.assertFalse(any(key in json.dumps(client.state())
                                             for key in ('token', 'dive_velocity', 'windup', 'spawn_timer')))
                        client.act(action='pause')
                    except BaseException as exc:
                        errors.append(exc)
                    finally:
                        done.set()

                class EndTest(Exception):
                    pass

                clock = game.clock
                deadline = time.monotonic() + 10

                class TestClock:
                    def tick(self, fps):
                        if done.is_set() or time.monotonic() > deadline:
                            raise EndTest()
                        return clock.tick(fps)

                game.clock = TestClock()
                driver = threading.Thread(target=drive, daemon=True)
                driver.start()
                try:
                    with self.assertRaises(EndTest):
                        game.run_game()
                    driver.join(timeout=4)
                    self.assertFalse(driver.is_alive())
                    if errors:
                        raise errors[0]
                finally:
                    control.close()
                    pygame.quit()
                self.assertFalse(session.exists())

    def test_offscreen_objects_and_transition_are_not_exported(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch('sys.argv', [str(Path(folder) / 'game.py')]), \
                patch.object(AlienInvasion, '_start_update_check'), \
                patch('player_data.PlayerData.is_authenticated', return_value=True):
            game = AlienInvasion(0, Path(folder) / 'control.dat')
            try:
                game._start_new_game()
                # Test fixtures only, in this isolated, unranked test process.
                alien = next(iter(game.aliens))
                alien.rect.x = -10000
                control = game.text_control
                stale = Future()
                control.pending.put(({'action': 'pause'}, stale, time.monotonic() - 1))
                control.pump()
                self.assertEqual(stale.result()[0], 408)
                cancelled = Future()
                cancelled.cancel()
                control.pending.put(({'action': 'pause'}, cancelled, time.monotonic() + 1))
                control.pump()
                self.assertEqual(game.state.name, 'PLAYING')
                control.publish(force=True)
                state = json.loads(control._snapshot)
                aliens = [obj for obj in state['objects'] if obj['kind'] == 'alien']
                self.assertEqual(len(aliens), len(game.aliens) - 1)
                game.in_transition = True
                control.publish(force=True)
                state = json.loads(control._snapshot)
                self.assertFalse(state['accepts_controls'])
                self.assertEqual(state['objects'], [])
                self.assertNotIn('ship', state)
            finally:
                game.text_control.close()
                pygame.quit()


if __name__ == '__main__':
    unittest.main()
