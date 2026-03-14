#!/usr/bin/env python3
"""
generate_sounds.py — Synthesise placeholder typewriter sound effects.

Run this script once during setup to populate assets/sounds/.  All sounds
are generated from mathematical primitives (filtered noise, tones, ADSR
envelopes) using numpy and the standard library's wave module — no external
audio assets are required.

The generated sounds are intentionally minimal but functional.  They can be
replaced at any time with higher-quality recordings simply by dropping .wav
files of the same name into assets/sounds/.

Sound inventory
---------------
  key_strike.wav      Short percussive click of a type bar striking paper
  space.wav           Slightly softer spacebar thud
  backspace.wav       Light mechanical retract click
  carriage_return.wav Mechanical sweep + return thunk
  line_feed.wav       Platen ratchet advance
  bell.wav            Ding near the right margin
  carriage_move.wav   Subtle tick used for incremental carriage sounds
"""

import os
import wave
import struct
import math
import array

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

SAMPLE_RATE = 44100
OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "sounds")


# ---------------------------------------------------------------------------
# WAV writing helpers
# ---------------------------------------------------------------------------

def _write_wav(path: str, samples):
    """Write a mono 16-bit PCM WAV from a sequence of float samples in [-1, 1]."""
    if HAS_NUMPY:
        data = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
        ints = (data * 32767.0).astype(np.int16)
        raw  = ints.tobytes()
    else:
        clipped = [max(-1.0, min(1.0, float(s))) for s in samples]
        ints    = [int(s * 32767) for s in clipped]
        raw     = struct.pack(f"<{len(ints)}h", *ints)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw)


def _linspace(start, stop, n):
    if HAS_NUMPY:
        return np.linspace(start, stop, n, dtype=np.float32)
    step = (stop - start) / max(1, n - 1)
    return [start + i * step for i in range(n)]


def _zeros(n):
    if HAS_NUMPY:
        return np.zeros(n, dtype=np.float32)
    return [0.0] * n


def _noise(n, rng=None):
    """Uniform white noise in [-1, 1]."""
    if HAS_NUMPY:
        rng = rng or np.random.default_rng(0)
        return rng.uniform(-1.0, 1.0, n).astype(np.float32)
    import random
    r = random.Random(0)
    return [r.uniform(-1.0, 1.0) for _ in range(n)]


def _exp_decay(n, rate):
    """Exponential decay envelope: e^(-rate * t/SR) over n samples."""
    t = _linspace(0.0, n / SAMPLE_RATE, n)
    if HAS_NUMPY:
        return np.exp(-rate * t).astype(np.float32)
    return [math.exp(-rate * ti) for ti in t]


def _sine(freq, n):
    t = _linspace(0.0, n / SAMPLE_RATE, n)
    if HAS_NUMPY:
        return np.sin(2.0 * math.pi * freq * t).astype(np.float32)
    return [math.sin(2.0 * math.pi * freq * ti) for ti in t]


def _mix(*args):
    """Element-wise mix of equal-length sequences."""
    if HAS_NUMPY:
        result = np.zeros(len(args[0]), dtype=np.float32)
        for a in args:
            result += np.asarray(a, dtype=np.float32)
        return result
    result = [0.0] * len(args[0])
    for a in args:
        for i, v in enumerate(a):
            result[i] += float(v)
    return result


def _scale(sig, gain):
    if HAS_NUMPY:
        return np.asarray(sig, dtype=np.float32) * gain
    return [v * gain for v in sig]


def _clip(sig):
    if HAS_NUMPY:
        return np.clip(np.asarray(sig, dtype=np.float32), -1.0, 1.0)
    return [max(-1.0, min(1.0, v)) for v in sig]


def _mul(a, b):
    """Pointwise multiply."""
    if HAS_NUMPY:
        return np.asarray(a, dtype=np.float32) * np.asarray(b, dtype=np.float32)
    return [float(x) * float(y) for x, y in zip(a, b)]


# ---------------------------------------------------------------------------
# Sound synthesisers
# ---------------------------------------------------------------------------

def make_key_strike() -> list:
    """
    Sharp type-bar impact: high-frequency noise burst with fast exponential
    decay, plus a small tonal transient for body.
    Duration ~40 ms.
    """
    n = int(0.040 * SAMPLE_RATE)
    env  = _exp_decay(n, 220)
    noise = _noise(n)
    tone  = _sine(1400, n)
    sig   = _mix(_scale(_mul(noise, env), 0.65),
                 _scale(_mul(tone,  env), 0.20))
    return _clip(sig)


def make_space() -> list:
    """
    Spacebar: heavier, slightly longer than a letter key.
    Duration ~55 ms.
    """
    n = int(0.055 * SAMPLE_RATE)
    env   = _exp_decay(n, 150)
    noise = _noise(n)
    tone  = _sine(700, n)
    sig   = _mix(_scale(_mul(noise, env), 0.70),
                 _scale(_mul(tone,  env), 0.15))
    return _clip(sig)


def make_backspace() -> list:
    """
    Light retract click — softer than a key strike.
    Duration ~30 ms.
    """
    n = int(0.030 * SAMPLE_RATE)
    env   = _exp_decay(n, 320)
    noise = _noise(n)
    sig   = _scale(_mul(noise, env), 0.40)
    return _clip(sig)


def make_carriage_return() -> list:
    """
    Mechanical sweep then a solid thunk as the carriage hits the stop.
    Duration ~280 ms.
    """
    if HAS_NUMPY:
        n      = int(0.280 * SAMPLE_RATE)
        t      = np.linspace(0.0, 0.280, n, dtype=np.float32)
        rng    = np.random.default_rng(1)
        noise  = rng.uniform(-1.0, 1.0, n).astype(np.float32)

        # Sliding frequency sweep for the "whoosh" feel
        freq   = 500.0 - 300.0 * (t / 0.280)
        phase  = np.cumsum(freq / SAMPLE_RATE) * 2.0 * math.pi
        sweep  = np.sin(phase) * np.exp(-t * 12.0)

        # Background mechanical rattle
        rattle = noise * np.exp(-t * 18.0)

        # Thunk at ~240 ms
        thunk_start = int(0.240 * SAMPLE_RATE)
        thunk = np.zeros(n, dtype=np.float32)
        tt    = t[thunk_start:] - 0.240
        thunk_n = rng.uniform(-1.0, 1.0, n - thunk_start).astype(np.float32)
        thunk[thunk_start:] = thunk_n * np.exp(-tt * 90.0) * 0.9

        sig = sweep * 0.35 + rattle * 0.25 + thunk * 0.55
        return _clip(sig)

    # Fallback without numpy: simplified version
    n     = int(0.280 * SAMPLE_RATE)
    noise = _noise(n)
    env   = _exp_decay(n, 15)
    return _clip(_scale(_mul(noise, env), 0.70))


def make_line_feed() -> list:
    """
    Platen ratchet: short, mid-frequency click with a bit of resonance.
    Duration ~65 ms.
    """
    n = int(0.065 * SAMPLE_RATE)
    env   = _exp_decay(n, 95)
    noise = _noise(n)
    tone  = _sine(550, n)
    sig   = _mix(_scale(_mul(noise, env), 0.55),
                 _scale(_mul(tone,  env), 0.30))
    return _clip(sig)


def make_bell() -> list:
    """
    Classic typewriter bell: decaying harmonic tone at ~880 Hz.
    Duration ~900 ms.
    """
    n = int(0.900 * SAMPLE_RATE)
    env = _exp_decay(n, 4.5)
    f1  = _sine(880,  n)
    f2  = _sine(1760, n)
    f3  = _sine(2640, n)
    sig = _mix(_scale(f1, 0.50),
               _scale(f2, 0.25),
               _scale(f3, 0.10))
    return _clip(_scale(_mul(sig, env), 0.70))


def make_carriage_move() -> list:
    """
    Very short tick for incremental carriage position sounds.
    Duration ~18 ms.
    """
    n = int(0.018 * SAMPLE_RATE)
    env   = _exp_decay(n, 500)
    noise = _noise(n)
    sig   = _scale(_mul(noise, env), 0.28)
    return _clip(sig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SOUNDS = {
    "key_strike":      make_key_strike,
    "space":           make_space,
    "backspace":       make_backspace,
    "carriage_return": make_carriage_return,
    "line_feed":       make_line_feed,
    "bell":            make_bell,
    "carriage_move":   make_carriage_move,
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if not HAS_NUMPY:
        print("Warning: numpy not found — generating sounds with pure Python (slower).")

    for name, generator in SOUNDS.items():
        out_path = os.path.join(OUT_DIR, f"{name}.wav")
        print(f"  Generating {name}.wav …", end=" ", flush=True)
        samples = generator()
        _write_wav(out_path, samples)
        print("done")

    print(f"\nAll sounds written to: {OUT_DIR}")
    print("Replace any .wav file with a recording to use custom sounds.")


if __name__ == "__main__":
    main()
