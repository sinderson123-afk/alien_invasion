"""Opt-in, loopback-only text controls. Game objects stay on the game thread."""

import hmac
import json
import queue
import secrets
import threading
import time
import weakref
from concurrent.futures import Future, TimeoutError
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pygame

from file_crypto import decrypt_json, encrypt_json
from game_stats import GameState


def validate_command(data):
    """Accept either one menu/item action or a complete held-input state."""
    if not isinstance(data, dict) or not data:
        raise ValueError('Expected a nonempty JSON object')
    if 'action' in data:
        if set(data) != {'action'} or data['action'] not in (
                'start', 'pause', 'resume', 'menu', 'back',
                'missile', 'magnet', 'clover'):
            raise ValueError('Unknown action or extra fields')
        return data
    if set(data) - {'move', 'fire', 'lease_ms'}:
        raise ValueError('Unknown control fields')
    move, fire, lease = data.get('move', 'stop'), data.get('fire', False), data.get('lease_ms', 1000)
    if move not in ('left', 'right', 'stop') or type(fire) is not bool:
        raise ValueError('move must be left/right/stop; fire must be boolean')
    if type(lease) is not int or not 100 <= lease <= 2000:
        raise ValueError('lease_ms must be an integer from 100 to 2000')
    return {'move': move, 'fire': fire, 'lease_ms': lease}


class TextControl:
    def __init__(self, game, port, session_file):
        self.game = game
        self.session_file = Path(session_file)
        self.token = secrets.token_urlsafe(32)
        self.pending = queue.Queue(maxsize=16)
        self.firing = False
        self.moving = False
        self.direction = 'stop'
        self.expires = 0
        self.frame = 0
        self._ids = weakref.WeakKeyDictionary()
        self._next_id = 0
        self._snapshot = b'{}'
        self._next_snapshot = 0
        control = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(2)

            def log_message(self, *_args):
                pass  # Never log the local bearer token or request bodies.

            def reply(self, status, data):
                body = data if isinstance(data, bytes) else json.dumps(data).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def authorized(self):
                expected_host = f'127.0.0.1:{control.server.server_port}'
                auth = self.headers.get('Authorization', '')
                if (self.headers.get('Host') != expected_host
                        or self.headers.get('Origin') is not None
                        or not hmac.compare_digest(auth.encode(), ('Bearer ' + control.token).encode())):
                    self.reply(403, {'error': 'Local bearer authentication required'})
                    return False
                return True

            def do_GET(self):
                if not self.authorized():
                    return
                if self.path != '/state':
                    self.reply(404, {'error': 'Unknown endpoint'})
                    return
                self.reply(200, control._snapshot)

            def do_POST(self):
                if not self.authorized():
                    return
                if self.path != '/action':
                    self.reply(404, {'error': 'Unknown endpoint'})
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 2048 or self.headers.get_content_type() != 'application/json':
                        raise ValueError('Expected application/json, maximum 2048 bytes')
                    command = validate_command(json.loads(self.rfile.read(length)))
                except (ValueError, TypeError, OSError, RecursionError) as exc:
                    self.reply(400, {'error': str(exc)})
                    return
                result = Future()
                try:
                    control.pending.put_nowait((command, result, time.monotonic() + 1))
                except queue.Full:
                    self.reply(429, {'error': 'Input queue full'})
                    return
                try:
                    status, body = result.result(timeout=2)
                    self.reply(status, body)
                except TimeoutError:
                    cancelled = result.cancel()
                    self.reply(504, {'error': 'Game loop did not respond',
                                     'cancelled': cancelled})

        self.server = HTTPServer(('127.0.0.1', port), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            if not encrypt_json({'url': self.url, 'token': self.token}, self.session_file):
                raise OSError('Could not write text-control session file')
            self.publish(force=True)
        except BaseException:
            self.server.server_close()
            raise
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.1}, daemon=True)
        self.thread.start()

    def release(self):
        if self.moving:
            self.game.ship.moving_left = self.game.ship.moving_right = False
        self.moving = self.firing = False
        self.direction = 'stop'
        self.expires = 0

    def ready(self):
        g = self.game
        return (g.state == GameState.PLAYING and not g.in_transition
                and not g.ship_death_frames and not g.game_over_frames)

    def actions(self):
        g = self.game
        if g.show_notifications or g._account_confirm:
            return []
        if self.ready():
            result = ['pause']
            if g.stats.missiles > 0:
                result.append('missile')
            if g.stats.items.get('magnet', 0) > 0 and not g.magnet_active:
                result.append('magnet')
            if g.stats.items.get('clover', 0) > 0:
                result.append('clover')
            return result
        return {GameState.MENU: ['start'], GameState.PAUSED: ['resume', 'menu'],
                GameState.TUTORIAL: ['back'], GameState.LEADERBOARD: ['back'],
                GameState.SHOP: ['back']}.get(g.state, [])

    def apply(self, command):
        g = self.game
        if 'action' not in command:
            if not self.ready():
                raise ValueError('Held controls require active gameplay')
            g.ship.target_x = None
            g.firing = g.mouse_firing = False
            g.ship.moving_left = command['move'] == 'left'
            g.ship.moving_right = command['move'] == 'right'
            self.moving = True
            self.direction = command['move']
            # Use the existing per-frame fire cadence, never synthesize repeated
            # SPACE keydowns (which would fire immediately and bypass cooldown).
            self.firing = command['fire']
            self.expires = time.monotonic() + command['lease_ms'] / 1000
            return
        action = command['action']
        if action not in self.actions():
            raise ValueError('Action unavailable in this state or item stock is empty')
        if action == 'start':
            g._start_new_game()
        elif action == 'menu':
            g._return_to_menu()
        else:
            key = {'pause': pygame.K_ESCAPE, 'resume': pygame.K_ESCAPE,
                   'back': pygame.K_ESCAPE, 'missile': pygame.K_e,
                   'magnet': pygame.K_n, 'clover': pygame.K_c}[action]
            g._check_keydown_events(pygame.event.Event(pygame.KEYDOWN, key=key))

    def pump(self):
        """Called once per normal 60 Hz frame; HTTP threads never mutate a game."""
        if time.monotonic() >= self.expires or not self.ready():
            self.release()
        try:
            command, future, deadline = self.pending.get_nowait()
        except queue.Empty:
            return
        if not future.set_running_or_notify_cancel():
            return
        if time.monotonic() > deadline:
            future.set_result((408, {'error': 'Input expired before game processed it'}))
            return
        try:
            self.apply(command)
        except ValueError as exc:
            future.set_result((409, {'error': str(exc)}))
        except Exception:
            future.set_result((500, {'error': 'Game action failed'}))
            raise
        else:
            future.set_result((200, {'ok': True, 'frame': self.frame,
                                     'state': self.game.state.name.lower()}))

    def actor(self, sprite, kind):
        rect = sprite.rect.clip(self.game.screen_rect)
        if rect.width <= 0 or rect.height <= 0:
            return None
        if sprite not in self._ids:
            self._next_id += 1
            self._ids[sprite] = self._next_id
        return {'id': self._ids[sprite], 'kind': kind,
                'x': rect.x, 'y': rect.y, 'width': rect.width, 'height': rect.height}

    def publish(self, force=False):
        self.frame += 1
        now = time.monotonic()
        if not force and now < self._next_snapshot:
            return
        self._next_snapshot = now + 0.05  # At most 20 observations per second.
        g = self.game
        state = {'version': 1, 'frame': self.frame, 'observed_at': time.time(),
                 'state': g.state.name.lower(),
                 'screen': {'width': g.screen_rect.width, 'height': g.screen_rect.height},
                 'accepts_controls': self.ready(), 'actions': self.actions(),
                 'control': {'move': self.direction, 'fire': self.firing,
                             'lease_remaining_ms': max(0, round((self.expires - now) * 1000))}}
        if g.state == GameState.MENU:
            state['hud'] = {'coins': g.stats.coins, 'best': g.stats.high_score}
        if g.state in (GameState.PLAYING, GameState.PAUSED):
            state['hud'] = {'hp': g.stats.ship_hp, 'max_hp': g.stats.max_hp,
                            'score': g.stats.score, 'best': g.stats.high_score,
                            'level': g.stats.level, 'coins': g.stats.coins,
                            'missiles': g.stats.missiles, 'critical_hits': g.stats.crit_count}
            state['phase'] = ('transition' if g.in_transition else
                              'game_over' if g.game_over_frames else
                              'dying' if g.ship_death_frames else 'active')
            state['objects'] = []
            # Omit the scene during cinematics and opaque overlays. Export only
            # on-screen rectangles, never AI state, targets, RNG, or spawn timers.
            if not g.in_transition and not g.show_notifications:
                if not g.ship_death_frames and not g.game_over_frames:
                    state['ship'] = self.actor(g.ship, 'ship')
                for name, kind in (('aliens', 'alien'), ('bullets', 'bullet'),
                                   ('missiles', 'missile'), ('boss_bullets', 'hostile_bullet'),
                                   ('boss_missiles', 'hostile_missile'), ('meteors', 'meteor'),
                                   ('meteor_fragments', 'meteor_fragment'),
                                   ('coins', 'coin'), ('gems', 'gem')):
                    for sprite in getattr(g, name):
                        actor = self.actor(sprite, kind)
                        if actor:
                            state['objects'].append(actor)
                if g.boss is not None:
                    actor = self.actor(g.boss, 'boss')
                    if actor:
                        state['objects'].append(actor)
        self._snapshot = json.dumps(state, separators=(',', ':')).encode('utf-8')

    def close(self):
        self.release()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        data = decrypt_json(self.session_file)
        if data and data.get('token') == self.token:
            self.session_file.unlink(missing_ok=True)
            self.session_file.with_suffix(self.session_file.suffix + '.bak').unlink(missing_ok=True)
