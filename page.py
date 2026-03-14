"""
page.py — The virtual sheet of paper.

The Page owns a pygame.Surface that acts as the permanent canvas.  Every
keystroke calls stamp(), which blits a rendered glyph at the given pixel
position with optional ink-alpha variation and sub-pixel jitter.

Because we paint directly onto a surface (not into a text model), all
typewriter effects come for free:
  - overtyping / overstrike  → just blit again at the same position
  - backspace-and-retype     → blit on top of the old glyph
  - ink variation            → randomised alpha per stamp
  - positional jitter        → sub-pixel random offset per stamp

Session replay is supported by recording every stamp call as a dict so
we can re-execute the sequence losslessly from a saved session.
"""

from __future__ import annotations

import pygame
import random
from config import (
    PAPER_WIDTH, PAPER_HEIGHT, PAPER_COLOR,
    PAPER_TEXTURE_NOISE,
    INK_COLOR_BASE, INK_ALPHA_MIN, INK_ALPHA_MAX,
    INK_JITTER_X, INK_JITTER_Y,
)


# Number of discrete alpha buckets used for the glyph cache.
# 8 buckets covers the INK_ALPHA_MIN–INK_ALPHA_MAX range with fine
# enough granularity to look varied while keeping memory bounded.
_ALPHA_BUCKETS = 8


def _quantise_alpha(alpha: int) -> int:
    """Round alpha to the nearest cache bucket boundary."""
    span = INK_ALPHA_MAX - INK_ALPHA_MIN
    step = span / _ALPHA_BUCKETS
    bucket = round((alpha - INK_ALPHA_MIN) / step)
    bucket = max(0, min(_ALPHA_BUCKETS - 1, bucket))
    return INK_ALPHA_MIN + int(bucket * step)


class Page:
    """
    A pygame.Surface representing one sheet of paper in the typewriter.

    Public API
    ----------
    stamp(char, x, y, alpha=None, jitter=True)
        Paint a glyph at pixel position (x, y).
    clear()
        Reset to a blank sheet.
    get_surface() -> pygame.Surface
        The renderable surface (do not modify externally).
    get_strikes() -> list[dict]
        All recorded stamp calls for session serialisation.
    restore_from_strikes(strikes)
        Replay a saved strike list to reconstruct the page.
    """

    def __init__(self, font: pygame.font.Font):
        self._font = font
        # The permanent canvas — regular surface so blitted SRCALPHA
        # character surfaces alpha-blend correctly into the paper colour.
        self._surface = pygame.Surface((PAPER_WIDTH, PAPER_HEIGHT))
        self._surface.fill(PAPER_COLOR)
        self._apply_paper_texture()

        # Cache: (char, alpha_bucket) → SRCALPHA Surface
        self._glyph_cache: dict = {}

        # Ordered list of every stamp() call — used for session save/restore
        self._strikes: list = []

    # ------------------------------------------------------------------
    # Texture
    # ------------------------------------------------------------------

    def _apply_paper_texture(self):
        """Add subtle per-pixel luminance noise to simulate paper grain."""
        if PAPER_TEXTURE_NOISE <= 0:
            return
        try:
            import numpy as np
            arr = pygame.surfarray.pixels3d(self._surface)
            rng = np.random.default_rng(seed=42)
            noise = rng.integers(
                -PAPER_TEXTURE_NOISE, PAPER_TEXTURE_NOISE + 1,
                arr.shape, dtype=np.int16,
            )
            np.clip(arr.astype(np.int16) + noise, 0, 255, out=noise)
            arr[:] = noise.astype(np.uint8)
            del arr  # release the pixel-array lock
        except Exception:
            pass  # numpy absent or surfarray unavailable — skip texture

    # ------------------------------------------------------------------
    # Glyph cache
    # ------------------------------------------------------------------

    def _get_glyph(self, char: str, alpha: int) -> pygame.Surface:
        """
        Return a cached SRCALPHA Surface for (char, alpha).

        pygame 2.x supports RGBA tuples as the colour argument to
        font.render(), so we bake the ink colour + alpha directly into the
        rendered surface rather than calling set_alpha() afterwards (which
        behaves differently on SRCALPHA surfaces).
        """
        bucket = _quantise_alpha(alpha)
        key = (char, bucket)
        if key not in self._glyph_cache:
            color = (*INK_COLOR_BASE, bucket)
            surf = self._font.render(char, True, color)
            self._glyph_cache[key] = surf.convert_alpha()
        return self._glyph_cache[key]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stamp(
        self,
        char: str,
        x: int,
        y: int,
        alpha: int | None = None,
        jitter: bool = True,
    ):
        """
        Stamp a single glyph onto the page surface.

        Parameters
        ----------
        char   : The character to render (should be a single glyph).
        x, y   : Top-left pixel of the character cell on the page.
        alpha  : Ink opacity (INK_ALPHA_MIN–INK_ALPHA_MAX).  Random if None.
        jitter : Whether to apply sub-pixel positional randomness.
        """
        if alpha is None:
            alpha = random.randint(INK_ALPHA_MIN, INK_ALPHA_MAX)

        jx = random.uniform(-INK_JITTER_X, INK_JITTER_X) if jitter else 0.0
        jy = random.uniform(-INK_JITTER_Y, INK_JITTER_Y) if jitter else 0.0

        px = int(x + jx)
        py = int(y + jy)

        glyph = self._get_glyph(char, alpha)
        self._surface.blit(glyph, (px, py))

        self._strikes.append({
            "char":  char,
            "x":     x,
            "y":     y,
            "alpha": alpha,
            "jx":    jx,
            "jy":    jy,
        })

    def clear(self):
        """Reset the page to a blank sheet of paper."""
        self._strikes.clear()
        self._glyph_cache.clear()
        self._surface.fill(PAPER_COLOR)
        self._apply_paper_texture()

    def get_surface(self) -> pygame.Surface:
        return self._surface

    def get_surface_on_white(self) -> pygame.Surface:
        """Return a copy of the page with a pure white background (for export)."""
        surf = pygame.Surface((PAPER_WIDTH, PAPER_HEIGHT))
        surf.fill((255, 255, 255))
        for s in self._strikes:
            px = int(s["x"] + s["jx"])
            py = int(s["y"] + s["jy"])
            glyph = self._get_glyph(s["char"], s["alpha"])
            surf.blit(glyph, (px, py))
        return surf

    def get_strikes(self) -> list:
        return list(self._strikes)

    def restore_from_strikes(self, strikes: list):
        """
        Reconstruct the page by replaying a saved strike list.

        The jitter values stored in each strike record are reused verbatim
        so the restored page is pixel-identical to the original.
        """
        self._surface.fill(PAPER_COLOR)
        self._apply_paper_texture()
        self._strikes = []

        for s in strikes:
            px = int(s["x"] + s["jx"])
            py = int(s["y"] + s["jy"])
            glyph = self._get_glyph(s["char"], s["alpha"])
            self._surface.blit(glyph, (px, py))
            self._strikes.append(dict(s))
