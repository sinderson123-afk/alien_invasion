"""Desktop game HTTP client - zero external deps (stdlib only)

API:
  - send_code(email, purpose)    Send email verification code
  - register(email, code, username, password)  Register
  - login(identifier, password)              Login (username or email)
  - reset_password(email, code, new_password)  Reset password
  - upload_stats(token, ...)     Upload stats
  - get_leaderboard()            Get leaderboard
  - check_update(current_version) Check GitHub for newer release
"""

import json
import sys
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin
from file_crypto import encrypt_json, decrypt_json


_saves = Path(os.path.dirname(sys.argv[0])) / "saves"
_saves.mkdir(exist_ok=True)
_CACHE_FILE = _saves / "upload_cache.dat"
_TIMEOUT = 8

_REPO_OWNER = "sinderson123-afk"
_REPO_NAME = "alien_invasion"
_PAGES_ORIGIN = "https://logan-ai.org"

_GITHUB_RELEASE_BASE = f"https://github.com/{_REPO_OWNER}/{_REPO_NAME}/releases/download"

_MIRROR_POOL = [
    "https://gh.llkk.cc/",
    "https://github.akams.cn/",
    "https://gh-proxy.com/",
]


def _compare_versions(current: str, latest: str) -> bool:
    """Return True if latest is strictly newer than current (both like 'v1.2.3' or '1.2.3')."""
    def parse(v):
        return tuple(int(p) for p in v.lstrip('v').split('.'))
    try:
        return parse(latest) > parse(current)
    except (ValueError, IndexError):
        return latest != current


class WebClient:
    """Game API client"""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self._pending_uploads = self._load_cache()

    # ------------------------------------------------------------------
    # Local cache
    # ------------------------------------------------------------------
    def _load_cache(self) -> list:
        data = decrypt_json(_CACHE_FILE)
        return data.get('uploads', []) if data else []

    def _save_cache(self):
        encrypt_json({'uploads': self._pending_uploads}, _CACHE_FILE)

    # ------------------------------------------------------------------
    # HTTP wrapper
    # ------------------------------------------------------------------
    def _post(self, endpoint: str, data: dict, token: str | None = None):
        url = urljoin(self.server_url, endpoint)
        body = json.dumps(data).encode()
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        req = Request(url, data=body, headers=headers, method='POST')
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    def _get(self, endpoint: str):
        url = urljoin(self.server_url, endpoint)
        with urlopen(url, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    # ------------------------------------------------------------------
    # Auth: send verification code
    # ------------------------------------------------------------------
    def send_code(self, email: str, purpose: str = 'register') -> dict:
        """Send email verification code, returns {success, message} or {error}"""
        return self._post('/api/auth/send-code', {
            'email': email.strip().lower(),
            'purpose': purpose,
        })

    # ------------------------------------------------------------------
    # Auth: register
    # ------------------------------------------------------------------
    def register(self, email: str, code: str, username: str,
                 password: str) -> dict:
        """Register new account, returns {token, username, email} or {error}"""
        return self._post('/api/auth/register', {
            'email': email.strip().lower(),
            'code': code.strip(),
            'username': username.strip(),
            'password': password,
        })

    # ------------------------------------------------------------------
    # Auth: login
    # ------------------------------------------------------------------
    def login(self, identifier: str, password: str) -> dict:
        """Login (username or email), returns {token, username, email} or {error}"""
        return self._post('/api/auth/login', {
            'identifier': identifier.strip(),
            'password': password,
        })

    # ------------------------------------------------------------------
    # Auth: reset password
    # ------------------------------------------------------------------
    def reset_password(self, email: str, code: str,
                       new_password: str) -> dict:
        """Reset password, returns {success, message} or {error}"""
        return self._post('/api/auth/reset-password', {
            'email': email.strip().lower(),
            'code': code.strip(),
            'new_password': new_password,
        })

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def upload_stats(self, token: str, score: int, level: int,
                     kills: int = 0, coins: int = 0) -> dict:
        data = {'score': score, 'level': level, 'kills': kills, 'coins': coins}
        try:
            result = self._post('/api/stats', data, token=token)
        except (URLError, HTTPError, OSError, json.JSONDecodeError):
            self._pending_uploads.append({
                'score': score, 'level': level, 'kills': kills, 'coins': coins,
                'time': int(time.time()),
            })
            self._save_cache()
            return {'status': 'error', 'message': 'Upload failed, cached locally'}
        self._retry_cache(token)
        return result

    def _retry_cache(self, token: str):
        if not self._pending_uploads:
            return
        remaining = []
        for entry in self._pending_uploads:
            try:
                self._post('/api/stats', {
                    'score': entry['score'], 'level': entry['level'],
                    'kills': entry['kills'], 'coins': entry['coins'],
                }, token=token)
            except (URLError, HTTPError, OSError, json.JSONDecodeError):
                remaining.append(entry)
        self._pending_uploads = remaining
        self._save_cache()

    # ------------------------------------------------------------------
    # Leaderboard
    # ------------------------------------------------------------------
    def get_leaderboard(self, limit: int = 20) -> dict:
        return self._get(f'/api/leaderboard?limit={limit}')

    # ------------------------------------------------------------------
    # Update check (version.json on Cloudflare Pages → GitHub API fallback)
    # ------------------------------------------------------------------
    def check_update(self, current_version: str):
        """Check for newer version. Returns (new_version, release_url) or (None, None).
        Primary: Cloudflare Pages version.json (fast, works in China).
        Fallback: GitHub API /releases/latest."""
        tag, url = self._check_from_pages(current_version)
        if tag:
            return tag, url

        tag, url = self._check_from_github(current_version)
        if tag:
            return tag, url
        return None, None

    def _check_from_pages(self, current_version: str):
        url = f"{_PAGES_ORIGIN}/version.json"
        try:
            req = Request(url)
            with urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get('latest', '')
            if tag and _compare_versions(current_version, tag):
                release_url = (f"https://github.com/{_REPO_OWNER}/{_REPO_NAME}"
                               f"/releases/tag/{tag}")
                return tag, release_url
        except (URLError, HTTPError, OSError, json.JSONDecodeError, ValueError):
            pass
        return None, None

    def _check_from_github(self, current_version: str):
        url = (f"https://api.github.com/repos/{_REPO_OWNER}/{_REPO_NAME}"
               "/releases/latest")
        try:
            req = Request(url, headers={'Accept': 'application/json'})
            with urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get('tag_name', '')
            if tag and _compare_versions(current_version, tag):
                return tag, data.get('html_url', '')
        except (URLError, HTTPError, OSError, json.JSONDecodeError, ValueError):
            pass
        return None, None

    @staticmethod
    def get_download_urls(tag: str):
        """Return (direct_url, mirror_urls) for a release tag.
        Mirrors are for users behind China's GFW."""
        direct = f"{_GITHUB_RELEASE_BASE}/{tag}/AlienInvasion.exe"
        mirrors = [f"{m}{direct}" for m in _MIRROR_POOL]
        return direct, mirrors

    @staticmethod
    def open_release_page(url: str):
        """Open the release page in the default browser."""
        import webbrowser
        webbrowser.open(url)
