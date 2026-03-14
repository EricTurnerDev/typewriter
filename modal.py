"""
modal.py — Modal overlay widgets for the typewriter application.

Two classes:

  TextInputModal
      A single-line text prompt drawn over the main view.  The caller checks
      modal.done / modal.confirmed / modal.text after processing events.

  DocumentBrowserModal
      A navigable list of .typewriter files found in given search directories.
      The caller checks modal.done / modal.create_new / modal.selected_path.

Both classes follow the same contract:
  handle_event(event)   — process one pygame event
  render(screen, font)  — draw the modal onto *screen*
  done                  — True once the user confirms or cancels
"""

from __future__ import annotations

import os
import glob

import pygame

from config import (
    OVERLAY_TEXT_COLOR,
    OVERLAY_BG_ALPHA,
    OVERLAY_LINE_H,
    OVERLAY_PADDING,
)

# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

_PANEL_BG_COLOR   = (10, 9, 8)
_HIGHLIGHT_COLOR  = (60, 55, 45)
_DIM_COLOR        = (140, 132, 115)
_BORDER_COLOR     = (80, 74, 62)


def _draw_panel(
    screen: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    highlight_idx: int | None = None,
    subtitle: str | None = None,
) -> None:
    """
    Render a dark semi-transparent panel centred on *screen*.

    *lines*         — text rows to display
    *highlight_idx* — if set, that row is drawn with a highlight background
    *subtitle*      — dim line appended below the list (e.g. a file path)
    """
    line_h   = OVERLAY_LINE_H
    padding  = OVERLAY_PADDING

    total_lines = len(lines) + (1 if subtitle is not None else 0)
    max_text_w  = max(
        (font.size(ln)[0] for ln in lines),
        default=200,
    )
    if subtitle:
        max_text_w = max(max_text_w, font.size(subtitle)[0])

    panel_w = max_text_w + padding * 2
    panel_h = total_lines * line_h + padding * 2 + (line_h if subtitle else 0)

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((*_PANEL_BG_COLOR, OVERLAY_BG_ALPHA))

    # Optional border
    pygame.draw.rect(panel, (*_BORDER_COLOR, 200), panel.get_rect(), 1)

    sw, sh = screen.get_size()
    panel_x = (sw - panel_w) // 2
    panel_y = (sh - panel_h) // 2

    for i, line in enumerate(lines):
        row_y = padding + i * line_h

        # Highlight background for the selected row
        if highlight_idx is not None and i == highlight_idx:
            hl = pygame.Surface((panel_w - 2, line_h), pygame.SRCALPHA)
            hl.fill((*_HIGHLIGHT_COLOR, 220))
            panel.blit(hl, (1, row_y))

        color = OVERLAY_TEXT_COLOR
        surf  = font.render(line, True, color)
        panel.blit(surf, (padding, row_y))

    # Subtitle (dim) below the list
    if subtitle:
        sub_y = padding + len(lines) * line_h + line_h // 2
        sub_surf = font.render(subtitle, True, _DIM_COLOR)
        panel.blit(sub_surf, (padding, sub_y))

    screen.blit(panel, (panel_x, panel_y))


# ---------------------------------------------------------------------------
# ConfirmModal
# ---------------------------------------------------------------------------

class ConfirmModal:
    """
    A yes/no confirmation prompt.

    Press Y or Enter to confirm; N or Escape to cancel.

    Attributes
    ----------
    done      : bool — True once the user responds
    confirmed : bool — True if the user pressed Y or Enter
    """

    def __init__(self, message: str, confirm_hint: str = "Y / Enter — yes",
                 cancel_hint: str = "N / Esc  — go back"):
        self.message      = message
        self._confirm_hint = confirm_hint
        self._cancel_hint  = cancel_hint
        self.done      = False
        self.confirmed = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE,) or (
            event.unicode and event.unicode.lower() == "n"
        ):
            self.done      = True
            self.confirmed = False
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) or (
            event.unicode and event.unicode.lower() == "y"
        ):
            self.done      = True
            self.confirmed = True

    def render(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        lines = [
            self.message,
            "",
            f"  {self._confirm_hint}",
            f"  {self._cancel_hint}",
        ]
        _draw_panel(screen, font, lines)


# ---------------------------------------------------------------------------
# TextInputModal
# ---------------------------------------------------------------------------

class TextInputModal:
    """
    Single-line text prompt modal.

    Attributes
    ----------
    done      : bool  — True once user presses Enter or Escape
    confirmed : bool  — True if user pressed Enter (False if Escape)
    text      : str   — current contents of the input field
    """

    def __init__(self, prompt: str, initial: str = ""):
        self.prompt    = prompt
        self.text      = initial
        self.done      = False
        self.confirmed = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_ESCAPE:
            self.done      = True
            self.confirmed = False

        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.done      = True
            self.confirmed = True

        elif event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]

        else:
            char = event.unicode
            if char and char.isprintable():
                self.text += char

    def render(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        input_display = f"> {self.text}_"
        lines = [
            "─" * max(len(self.prompt), len(input_display)),
            self.prompt,
            input_display,
            "─" * max(len(self.prompt), len(input_display)),
        ]
        _draw_panel(screen, font, lines)


# ---------------------------------------------------------------------------
# DocumentBrowserModal
# ---------------------------------------------------------------------------

class DocumentBrowserModal:
    """
    Navigable list of .typewriter files.

    The first entry is always "[ New document ]".  Files are found by
    scanning *search_dirs* for *.typewriter files; duplicates and
    *current_path* are excluded.

    Attributes
    ----------
    done          : bool       — True once user presses Enter or Escape
    selected_path : str | None — path of chosen file, or None
    create_new    : bool       — True if user chose "[ New document ]"
    """

    _NEW_LABEL = "[ New document ]"

    def __init__(
        self,
        search_dirs: list[str],
        current_path: str | None = None,
    ):
        self._entries: list[str | None] = [None]   # None → "[ New document ]"
        self._selected  = 0
        self.done          = False
        self.selected_path = None
        self.create_new    = False

        # Scan for .typewriter files, deduplicate, exclude current
        seen: set[str] = set()
        if current_path:
            seen.add(os.path.abspath(current_path))

        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue
            pattern = os.path.join(directory, "*.typewriter")
            for filepath in sorted(glob.glob(pattern)):
                abs_path = os.path.abspath(filepath)
                if abs_path not in seen:
                    seen.add(abs_path)
                    self._entries.append(abs_path)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_ESCAPE:
            self.done = True
            return

        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.done = True
            entry = self._entries[self._selected]
            if entry is None:
                self.create_new    = True
                self.selected_path = None
            else:
                self.create_new    = False
                self.selected_path = entry
            return

        if event.key in (pygame.K_UP, pygame.K_LEFT):
            self._selected = max(0, self._selected - 1)

        elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            self._selected = min(len(self._entries) - 1, self._selected + 1)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _entry_label(self, entry: str | None) -> str:
        if entry is None:
            return self._NEW_LABEL
        base = os.path.basename(entry)
        if base.endswith(".typewriter"):
            base = base[: -len(".typewriter")]
        return base

    def render(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        title = "─── OPEN DOCUMENT ───"

        lines: list[str] = [title, ""]
        entry_start = len(lines)

        for entry in self._entries:
            lines.append(f"  {self._entry_label(entry)}")

        # Adjust highlight index to account for header rows
        highlight_idx = entry_start + self._selected

        # Subtitle: full path of selected entry (or blank for New)
        selected_entry = self._entries[self._selected]
        if selected_entry is not None:
            subtitle = selected_entry
        else:
            subtitle = "Start a fresh document"

        _draw_panel(screen, font, lines, highlight_idx=highlight_idx, subtitle=subtitle)
