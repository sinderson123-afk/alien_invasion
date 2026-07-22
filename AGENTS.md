# AGENTS.md — Alien Invasion

## Quick start

```bash
pip install pygame
python alien_invasion.py
```

There is no root `requirements.txt` — only `web/requirements.txt` for the server.

## Architecture

- **Single-file entrypoint**: `alien_invasion.py` (~2000 lines). All game logic lives in this file.
- **Flat module layout**: every `.py` is a top-level module. No packages, no `setup.py`.
- **State machine**: `GameState` enum in `game_stats.py` drives all event routing (7 states: `LOGIN → MENU → PLAYING ⇄ PAUSED ⇄ SHOP`, + `TUTORIAL`, `LEADERBOARD`).
- **`web/` is a separate app**: Flask + Firestore backend, deployed on Cloud Run. Not part of the desktop game.
- **`resource/`**: images (sprites), sounds (audio), videos (menu background — gitignored).

## Build & release

- **PyInstaller**: use `AlienInvasion.spec` (not CLI flags). The spec collects pygame binaries and embeds `resource/`.
  ```bash
  pip install pygame pyinstaller pillow
  python -c "from PIL import Image; img=Image.open('resource/images/cover.png'); img.save('icon.ico',format='ICO',sizes=[(256,256)])"
  python -m PyInstaller AlienInvasion.spec --clean --noconfirm
  ```
- **CI** (`.github/workflows/release.yml`): push to `main` → dev prerelease; tag `v*` → stable release. `_build_info.py` is CI-generated and gitignored (`settings.py` imports `IS_DEV_BUILD` from it, defaults to `False`).
- The CI uses `--onefile --windowed` + `--hidden-import cv2` (for optional video background). Locally the spec file is authoritative.

## File system

- **`resource_path()`** in `settings.py`: must wrap every file path to work under PyInstaller `--onefile` (`sys._MEIPASS`). Never use bare `Path(...)` for bundled resources.
- **`saves/`** directory: gitignored. Created automatically by `player_data.py` and `settings.py`. Contains encrypted `.dat` files (savegame, high score, player data, upload cache).
- **Encrypted files**: `file_crypto.py` uses XOR+SHA256 key derivation + CRC32 integrity check + atomic write (`.tmp → rename`, with `.bak` fallback). All persistence goes through `encrypt_json`/`decrypt_json`.

## Quirks & conventions

- **No tests, no linter, no type checker config** in this repo. Manual verification only.
- **`pygame.key.stop_text_input()`** is called at startup to prevent Chinese IME from intercepting keyboard input.
- **`cv2` (OpenCV)** is an optional dependency for `video_background.py` menu video — falls back to static blur. Not listed in pip install.
- **Networking**: `web_client.py` uses stdlib only (`urllib`). Handles offline caching of uploads.
- **Boss** is a singleton tracked as `self.boss` (not in a sprite group). All boss interactions check `self.boss is not None`.
- **Meteors** have their own collision system with fragment spawning on destruction.
- **Save/resume** serializes nearly full game state including alien AI state (dive velocity, cruise position, etc.). The save format has a `version` field with migration logic in `_migrate_save()`.
