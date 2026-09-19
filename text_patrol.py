"""Play an already-started game using only the public text-control interface."""

import argparse
import time

from game_control import GameClient


def patrol(client, seconds):
    state = client.state()
    if not state.get('accepts_controls'):
        raise ValueError('Start or resume a game first')
    direction = 'left'
    deadline = time.monotonic() + seconds
    next_report = 0
    last_score = 0
    try:
        while time.monotonic() < deadline:
            state = client.state()
            if time.time() - state['observed_at'] > 1:
                raise ValueError('Observation is stale; stopping input')
            if state['state'] != 'playing':
                break
            hud = state.get('hud', {})
            last_score = hud.get('score', last_score)
            if time.monotonic() >= next_report:
                print(f"level={hud.get('level')} hp={hud.get('hp')}/{hud.get('max_hp')} "
                      f"score={last_score} move={direction}", flush=True)
                next_report = time.monotonic() + 1
            if state.get('phase') in ('dying', 'game_over'):
                break
            ship = state.get('ship')
            if state.get('accepts_controls') and ship:
                width = state['screen']['width']
                center = ship['x'] + ship['width'] / 2
                if center <= width * 0.2:
                    direction = 'right'
                elif center >= width * 0.8:
                    direction = 'left'
                # Refresh ordinary held controls, with a short disconnect lease.
                client.act(move=direction, fire=True, lease_ms=400)
            time.sleep(0.1)
    finally:
        # Best effort. If disconnected, the lease releases inputs automatically.
        try:
            state = client.state()
            if state.get('accepts_controls'):
                client.act(move='stop', fire=False)
                client.act(action='pause')
        except (ValueError, OSError):
            pass
    print(f'Patrol finished. Last observed score: {last_score}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--session-file')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error('--seconds must be between 1 and 600')
    try:
        patrol(GameClient(args.session_file), args.seconds)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Patrol interrupted\n')


if __name__ == '__main__':
    main()
