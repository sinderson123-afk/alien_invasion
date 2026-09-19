"""Stdlib text client: python game_control.py state | act '{...}'"""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from file_crypto import decrypt_json


class GameClient:
    def __init__(self, session_file=None):
        path = Path(session_file) if session_file else Path(__file__).resolve().parent / 'saves/text-control.dat'
        session = decrypt_json(path)
        if not session:
            raise ValueError('Start the game with --text-control first (session file missing)')
        url = urlsplit(session['url'])
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
                or url.username or url.password or url.path or url.query or url.fragment):
            raise ValueError('Invalid local control endpoint')
        self.url, self.token = session['url'], session['token']
        self.opener = build_opener(ProxyHandler({}))  # Never send the token via an HTTP proxy.

    def request(self, path, data=None):
        body = None if data is None else json.dumps(data).encode('utf-8')
        request = Request(self.url + path, data=body,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=4) as response:
                return json.load(response)
        except HTTPError as exc:
            raise ValueError(f'HTTP {exc.code}: {exc.read().decode("utf-8")}') from exc

    def state(self):
        return self.request('/state')

    def act(self, **command):
        return self.request('/action', command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('state')
    act = commands.add_parser('act')
    act.add_argument('--action', choices=['start', 'pause', 'resume', 'menu', 'back',
                                          'missile', 'magnet', 'clover'])
    act.add_argument('--move', choices=['left', 'right', 'stop'])
    act.add_argument('--fire', choices=['on', 'off'])
    act.add_argument('--lease-ms', type=int)
    args = parser.parse_args()
    try:
        client = GameClient(args.session_file)
        if args.command == 'state':
            result = client.state()
        else:
            data = {k: v for k, v in vars(args).items()
                    if k in ('action', 'move', 'fire', 'lease_ms') and v is not None}
            if 'fire' in data:
                data['fire'] = data['fire'] == 'on'
            result = client.act(**data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, URLError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
