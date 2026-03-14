"""
sound_manager.py — All audio playback for the typewriter.

Design principles:
  - Missing sound files degrade gracefully to silence (no crash).
  - Sound files live in SOUNDS_DIR so they are trivially replaceable.
  - Each logical sound type has a dedicated play_*() method so call sites
    read clearly and channel assignments stay centralised here.
  - Volume is adjustable at runtime without reloading assets.
  - Sound file paths are configurable via sounds.toml; the user can override
    individual sounds by placing a sounds.toml in ~/.config/typewriter/.
"""

from __future__ import annotations

import os
import pygame
from config import (
    BASE_DIR,
    SOUNDS_DIR,
    SOUND_VOLUME, SOUND_FREQUENCY, SOUND_BUFFER, SOUND_CHANNELS,
    CH_KEY, CH_CARRIAGE, CH_LINEFEED, CH_BELL,
)

try:
    import tomllib                          # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli as tomllib             # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None                      # type: ignore[assignment]

# Default sound → filename mapping (bare filenames resolve to SOUNDS_DIR)
_DEFAULTS: dict[str, str] = {
    "key_strike":       "key_strike.wav",
    "space":            "space.wav",
    "backspace":        "backspace.wav",
    "carriage_return":  "carriage_return.wav",
    "line_feed":        "line_feed.wav",
    "bell":             "bell.wav",
    "carriage_move":    "carriage_move.wav",
}

_USER_CONFIG_PATH = os.path.expanduser("~/.config/typewriter/sounds.toml")
_APP_CONFIG_PATH  = os.path.join(BASE_DIR, "sounds.toml")


def _load_toml(path: str) -> dict:
    if tomllib is None:
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"[sound] Could not parse '{path}': {exc}")
        return {}


def _resolve_path(value: str, config_dir: str) -> str:
    """
    Turn a config value into an absolute file path.

    Rules (in order):
      1. Empty string        → "" (silence this sound)
      2. Absolute path       → used as-is
      3. Bare filename       → looked up in SOUNDS_DIR
      4. Relative path       → relative to the config file's directory
    """
    if not value:
        return ""
    if os.path.isabs(value):
        return value
    if os.sep not in value:
        return os.path.join(SOUNDS_DIR, value)
    return os.path.abspath(os.path.join(config_dir, value))


def _build_sound_map() -> dict[str, str]:
    """
    Return a dict of sound_name → absolute_path by merging:
      1. Built-in defaults
      2. App-level sounds.toml  (next to main.py)
      3. User sounds.toml       (~/.config/typewriter/sounds.toml)

    Later layers override earlier ones.  Unknown keys are ignored.
    """
    result = dict(_DEFAULTS)

    for config_path in (_APP_CONFIG_PATH, _USER_CONFIG_PATH):
        data = _load_toml(config_path)
        overrides = data.get("sounds", {})
        config_dir = os.path.dirname(os.path.abspath(config_path))
        for name, value in overrides.items():
            if name in result and isinstance(value, str):
                result[name] = _resolve_path(value, config_dir)

    # Resolve any remaining bare filenames from the defaults layer
    for name, value in result.items():
        if value and not os.path.isabs(value):
            result[name] = _resolve_path(value, SOUNDS_DIR)

    return result


class SoundManager:
    """
    Loads and plays typewriter sound effects.

    Instantiate with enabled=False (or --no-sound flag) to silence everything
    without changing any call sites.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._volume = SOUND_VOLUME
        self._sounds: dict[str, pygame.mixer.Sound] = {}

        if self.enabled:
            self._init_mixer()
            self._load_sounds()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_mixer(self):
        try:
            pygame.mixer.pre_init(
                frequency=SOUND_FREQUENCY,
                size=-16,           # signed 16-bit samples
                channels=1,         # mono
                buffer=SOUND_BUFFER,
            )
            pygame.mixer.init()
            pygame.mixer.set_num_channels(SOUND_CHANNELS)
        except pygame.error as exc:
            print(f"[sound] Mixer init failed ({exc}); audio disabled.")
            self.enabled = False

    def _load_sounds(self):
        sound_map = _build_sound_map()
        for name, path in sound_map.items():
            if not path:
                continue    # explicitly silenced in config
            if not os.path.exists(path):
                continue    # missing file — degrade gracefully
            try:
                snd = pygame.mixer.Sound(path)
                snd.set_volume(self._volume)
                self._sounds[name] = snd
            except pygame.error as exc:
                print(f"[sound] Could not load '{path}': {exc}")

    # ------------------------------------------------------------------
    # Low-level play
    # ------------------------------------------------------------------

    def _play(self, name: str, channel: int | None = None):
        if not self.enabled:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        if channel is not None:
            pygame.mixer.Channel(channel).play(snd)
        else:
            snd.play()

    # ------------------------------------------------------------------
    # High-level typed API
    # ------------------------------------------------------------------

    def play_key_strike(self):
        self._play("key_strike", CH_KEY)

    def play_space(self):
        self._play("space", CH_KEY)

    def play_backspace(self):
        self._play("backspace", CH_KEY)

    def play_carriage_return(self):
        self._play("carriage_return", CH_CARRIAGE)

    def carriage_return_duration(self) -> float:
        """Return the length of the carriage-return sound in seconds, or 0."""
        snd = self._sounds.get("carriage_return")
        return snd.get_length() if snd is not None else 0.0

    def play_line_feed(self):
        self._play("line_feed", CH_LINEFEED)

    def play_bell(self):
        self._play("bell", CH_BELL)

    def play_carriage_move(self):
        self._play("carriage_move", CH_CARRIAGE)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, value: float):
        self._volume = max(0.0, min(1.0, value))
        for snd in self._sounds.values():
            snd.set_volume(self._volume)
