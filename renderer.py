"""
renderer.py — Everything drawn to the screen.

Scale model
-----------
The paper is scaled so it fits entirely on screen (PAPER_ZOOM = 1.0):

    scale = min(
                (screen_w - 2*PAD) / PAPER_WIDTH,
                (screen_h - 2*PAD) / PAPER_HEIGHT * PAPER_ZOOM,
            )

Document layout
---------------
All pages are stacked vertically in document space with PAGE_GAP pixels
between them.  Page i occupies document rows:

    [i * (PAPER_HEIGHT + PAGE_GAP),  i * (PAPER_HEIGHT + PAGE_GAP) + PAPER_HEIGHT)

Carriage-tracking viewport
---------------------------
The page pans so the carriage cursor stays at a fixed screen anchor:

    anchor_x = screen_w * CURSOR_TARGET_X_FRAC   (horizontal centre)
    anchor_y = screen_h * CURSOR_TARGET_Y_FRAC   (70 % down — "near bottom")

    doc_carriage_y = page_idx * (PAPER_HEIGHT + PAGE_GAP) + carriage_y

    paper_x  = anchor_x - display_x      * scale   (display_x animates → carriage_x)
    doc_top_y = anchor_y - doc_carriage_y * scale   (top of page 0 in screen coords)

    screen_y of page i = doc_top_y + i * (PAPER_HEIGHT + PAGE_GAP) * scale

    update_carriage_view(carriage_x, carriage_y, page_idx)
                Called after every carriage move.
"""

from __future__ import annotations

import time
import pygame
from config import (
    PAPER_WIDTH, PAPER_HEIGHT, PAGE_GAP,
    PAPER_SHADOW_COLOR, PAPER_SHADOW_OFFSET,
    BACKGROUND_COLOR,
    CARRIAGE_INDICATOR_COLOR, CARRIAGE_INDICATOR_WIDTH,
    PAPER_ZOOM,
    CURSOR_TARGET_X_FRAC, CURSOR_TARGET_Y_FRAC,
    MARGIN_LEFT, MARGIN_TOP,
    OVERLAY_FONT_SIZE, OVERLAY_LINE_H, OVERLAY_PADDING,
    OVERLAY_BG_ALPHA, OVERLAY_TEXT_COLOR,
)

_PAPER_MARGIN  = 24     # min gap between paper edge and screen edge (px)
_CR_ANIM_SPEED = 2800   # page-pixels per second for the carriage-return slide

_PAGE_STRIDE = PAPER_HEIGHT + PAGE_GAP   # doc-space rows per page


class Renderer:
    """Scales and tracks the carriage position to pan the document, draws every frame."""

    def __init__(self, screen: pygame.Surface):
        self._screen = screen

        # Logical carriage state (set instantly on every carriage move).
        self._carriage_x: int = MARGIN_LEFT
        self._carriage_y: int = MARGIN_TOP
        self._page_idx:   int = 0

        # Animated horizontal position — chases _carriage_x at _anim_speed.
        self._display_x:  float = float(MARGIN_LEFT)
        self._anim_speed: float = _CR_ANIM_SPEED   # page-px/sec; set per CR
        self._last_time:  float = time.monotonic()


        # Cached layout — rebuilt when screen size changes.
        self._layout_size: tuple[int, int] = (0, 0)
        self._scale:   float = 1.0
        self._disp_w:  int   = PAPER_WIDTH
        self._disp_h:  int   = PAPER_HEIGHT

        self._bg:     pygame.Surface | None = None
        self._shadow: pygame.Surface | None = None
        self._overlay_font: pygame.font.Font | None = None

        self._recompute_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _recompute_layout(self):
        sw, sh = self._screen.get_size()
        if (sw, sh) == self._layout_size:
            return

        self._layout_size = (sw, sh)

        avail_w = max(1, sw - _PAPER_MARGIN * 2)
        avail_h = max(1, sh - _PAPER_MARGIN * 2)

        fit_h        = avail_h / PAPER_HEIGHT
        self._scale  = min(avail_w / PAPER_WIDTH, fit_h * PAPER_ZOOM)
        self._disp_w = int(PAPER_WIDTH  * self._scale)
        self._disp_h = int(PAPER_HEIGHT * self._scale)

        self._bg = pygame.Surface((sw, sh))
        self._bg.fill(BACKGROUND_COLOR)

        shadow = pygame.Surface((self._disp_w, self._disp_h))
        shadow.fill(PAPER_SHADOW_COLOR)
        shadow.set_alpha(110)
        self._shadow = shadow

    def _compute_doc_top_y(self) -> tuple[int, int]:
        """
        Return (paper_x, doc_top_y):
          paper_x    — screen x of the left edge of every page (pages share x)
          doc_top_y  — screen y of the top edge of document page 0
        """
        sw, sh = self._screen.get_size()
        anchor_x    = sw * CURSOR_TARGET_X_FRAC
        anchor_y    = sh * CURSOR_TARGET_Y_FRAC
        doc_caret_y = self._page_idx * _PAGE_STRIDE + self._carriage_y

        paper_x   = int(anchor_x - self._display_x * self._scale)
        doc_top_y = int(anchor_y - doc_caret_y    * self._scale)
        return paper_x, doc_top_y

    def _page_screen_y(self, doc_top_y: int, idx: int) -> int:
        """Screen y of the top edge of page idx."""
        return doc_top_y + int(idx * _PAGE_STRIDE * self._scale)

    # ------------------------------------------------------------------
    # Carriage-view API
    # ------------------------------------------------------------------

    def update_carriage_view(self, carriage_x: int, carriage_y: int, page_idx: int = 0):
        """Store carriage position; next draw() will pan to keep it at the anchor."""
        self._carriage_x = carriage_x
        self._carriage_y = carriage_y
        self._page_idx   = page_idx

    def scroll_by(self, delta: float):
        pass   # view tracks carriage; manual scroll not needed

    def start_carriage_return(self, sound_duration: float):
        """
        Set the horizontal animation speed so _display_x reaches MARGIN_LEFT
        exactly when the carriage-return sound ends.

        Call this before update_carriage_view() so _display_x still holds the
        pre-return position.
        """
        distance = self._display_x - MARGIN_LEFT
        if sound_duration > 0 and distance > 1:
            self._anim_speed = distance / sound_duration
        else:
            self._anim_speed = _CR_ANIM_SPEED

    def scroll_to_top(self):
        self._carriage_x = MARGIN_LEFT
        self._carriage_y = MARGIN_TOP
        self._page_idx   = 0
        self._display_x  = float(MARGIN_LEFT)   # snap, no animation

    def reset_scroll(self):
        self.scroll_to_top()

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def _advance_animation(self):
        """Step _display_x toward _carriage_x at a fixed page-pixel rate."""
        now = time.monotonic()
        dt  = min(now - self._last_time, 0.1)
        self._last_time = now

        target = float(self._carriage_x)
        diff   = target - self._display_x
        step   = self._anim_speed * dt

        if abs(diff) <= step:
            self._display_x  = target
            self._anim_speed = _CR_ANIM_SPEED   # reset to default after arrival
        elif diff > 0:
            self._display_x += step
        else:
            self._display_x -= step


    # ------------------------------------------------------------------
    # Main draw
    # ------------------------------------------------------------------

    def draw(
        self,
        pages: list,
        page_idx: int,
        carriage,
        show_overlay: bool = False,
        overlay_lines: list[str] | None = None,
    ):
        self._recompute_layout()
        self._advance_animation()

        paper_x, doc_top_y = self._compute_doc_top_y()
        sw, sh = self._screen.get_size()

        # Background
        self._screen.blit(self._bg, (0, 0))

        # Draw each page
        for i, page in enumerate(pages):
            page_y = self._page_screen_y(doc_top_y, i)

            # Skip pages entirely outside the viewport
            if page_y + self._disp_h < 0 or page_y > sh:
                continue

            # Drop shadow
            sx = paper_x + int(PAPER_SHADOW_OFFSET[0] * self._scale)
            sy = page_y  + int(PAPER_SHADOW_OFFSET[1] * self._scale)
            self._screen.blit(self._shadow, (sx, sy))

            # Paper (scaled)
            scaled_page = pygame.transform.smoothscale(
                page.get_surface(), (self._disp_w, self._disp_h)
            )
            self._screen.blit(scaled_page, (paper_x, page_y))

        # Carriage indicator on the active page only
        active_page_y = self._page_screen_y(doc_top_y, page_idx)
        self._draw_carriage_indicator(carriage, paper_x, active_page_y)

        if show_overlay and overlay_lines:
            self._draw_overlay(overlay_lines)

    # ------------------------------------------------------------------
    # Carriage indicator
    # ------------------------------------------------------------------

    def _draw_carriage_indicator(self, carriage, paper_x: int, paper_y: int):
        s  = self._scale
        # Use _display_x (the animated position) rather than carriage.x so the
        # cursor stays fixed on screen while the paper slides underneath it —
        # matching real typewriter behaviour where the typing point is stationary.
        cx = paper_x + int(self._display_x * s)
        cy = paper_y + int(carriage.y * s)
        cw = max(1, int(carriage.char_width  * s))
        ch = max(1, int(carriage.line_height * s))

        sw, sh = self._screen.get_size()
        if cx < 0 or cx + cw > sw or cy + ch < 0 or cy > sh:
            return

        indicator = pygame.Surface((cw, ch), pygame.SRCALPHA)
        indicator.fill(CARRIAGE_INDICATOR_COLOR)
        self._screen.blit(indicator, (cx, cy))

        underline_h = max(1, int(CARRIAGE_INDICATOR_WIDTH * s))
        line_y = cy + ch
        if 0 <= line_y < sh:
            underline = pygame.Surface((cw, underline_h), pygame.SRCALPHA)
            underline.fill((200, 80, 50, 200))
            self._screen.blit(underline, (cx, line_y))


    # ------------------------------------------------------------------
    # Overlay
    # ------------------------------------------------------------------

    def _get_overlay_font(self) -> pygame.font.Font:
        if self._overlay_font is None:
            self._overlay_font = pygame.font.SysFont("monospace", OVERLAY_FONT_SIZE)
        return self._overlay_font

    def _draw_overlay(self, lines: list[str]):
        font    = self._get_overlay_font()
        max_w   = max((font.size(ln)[0] for ln in lines), default=200)
        panel_w = max_w + OVERLAY_PADDING * 2
        panel_h = len(lines) * OVERLAY_LINE_H + OVERLAY_PADDING * 2

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 9, 8, OVERLAY_BG_ALPHA))

        for i, line in enumerate(lines):
            surf = font.render(line, True, OVERLAY_TEXT_COLOR)
            panel.blit(surf, (OVERLAY_PADDING, OVERLAY_PADDING + i * OVERLAY_LINE_H))

        sw, sh = self._screen.get_size()
        self._screen.blit(panel, ((sw - panel_w) // 2, (sh - panel_h) // 2))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def paper_to_screen(self, px: int, py: int) -> tuple[int, int]:
        paper_x, doc_top_y = self._compute_doc_top_y()
        page_y = self._page_screen_y(doc_top_y, self._page_idx)
        return (
            paper_x + int(px * self._scale),
            page_y  + int(py * self._scale),
        )
