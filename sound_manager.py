"""
sound_manager.py — All audio playback for the typewriter.

Design principles:
  - Missing sound files degrade gracefully to silence (no crash).
  - Sound files live in SOUNDS_DIR so they are trivially replaceable.
  - Each logical sound type has a dedicated play_*() method so call sites
    read clearly and channel assignments stay centralised here.
  - Volume is adjustable at runtime without reloading assets.
"""

from __future__ import annotations

import os
import pygame
from config import (
    SOUNDS_DIR,
    SOUND_VOLUME, SOUND_FREQUENCY, SOUND_BUFFER, SOUND_CHANNELS,
    CH_KEY, CH_CARRIAGE, CH_LINEFEED, CH_BELL,
)


# Map of logical sound name → WAV filename in SOUNDS_DIR
_SOUND_FILES: dict[str, str] = {
    "key_strike":       "key_strike.wav",
    "space":            "space.wav",
    "backspace":        "backspace.wav",
    "carriage_return":  "carriage_return.wav",
    "line_feed":        "line_feed.wav",
    "bell":             "bell.wav",
    "carriage_move":    "carriage_move.wav",
}


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
        for name, filename in _SOUND_FILES.items():
            path = os.path.join(SOUNDS_DIR, filename)
            if not os.path.exists(path):
                # Not fatal — the app runs silently for missing assets
                continue
            try:
                snd = pygame.mixer.Sound(path)
                snd.set_volume(self._volume)
                self._sounds[name] = snd
            except pygame.error as exc:
                print(f"[sound] Could not load '{filename}': {exc}")

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
