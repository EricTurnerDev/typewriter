"""
document.py — Document persistence using the .typewriter ZIP archive format.

Archive layout
--------------
  document.typewriter  (ZIP file)
  ├── meta.json          {"version": 1, "saved_at": "…", "current_page": 0,
  │                       "pages": [{"carriage": {…}}, …]}
  ├── strikes_000.json   strike log for page 0
  ├── strikes_001.json   strike log for page 1
  ├── page_000.png       rendered PNG snapshot of page 0
  └── page_001.png       rendered PNG snapshot of page 1

Legacy format (directory with state.json) is handled by load_legacy().
"""

from __future__ import annotations

import datetime
import io
import json
import os
import zipfile

import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_FORMAT_VERSION = 1


class Document:
    """
    Represents a typewriter document backed by a .typewriter ZIP archive.

    Attributes
    ----------
    path : str | None
        Filesystem path to the .typewriter file, or None for an untitled doc.
    dirty : bool
        True when there are unsaved changes since the last explicit save.
    """

    def __init__(self, path: str | None = None):
        self.path  = path
        self.dirty = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def display_name(self) -> str:
        """Basename without the .typewriter extension, or 'Untitled'."""
        if self.path is None:
            return "Untitled"
        base = os.path.basename(self.path)
        if base.endswith(".typewriter"):
            base = base[: -len(".typewriter")]
        return base or "Untitled"

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    def mark_dirty(self):
        self.dirty = True

    def mark_clean(self):
        self.dirty = False

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(
        self,
        pages: list,
        page_states: list[dict],
        current_idx: int,
        path: str | None = None,
    ) -> str:
        """
        Write the document to a .typewriter ZIP archive.

        If *path* is provided it overrides (and updates) self.path.
        Raises ValueError if neither argument nor self.path is set.
        Updates self.path and marks the document clean on success.

        Returns the path written to.
        """
        if path is not None:
            self.path = path
        if self.path is None:
            raise ValueError("Document has no path — provide one to save()")
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._write_zip(self.path, pages, page_states, current_idx)
        self.mark_clean()
        return self.path

    def _write_zip(
        self,
        path: str,
        pages: list,
        page_states: list[dict],
        current_idx: int,
    ) -> None:
        """Shared implementation: write all data into a ZIP at *path*."""
        now_str = datetime.datetime.now().isoformat()

        # Build the meta structure (no strikes — those go in separate members)
        pages_meta = []
        for i in range(len(pages)):
            pages_meta.append({"carriage": page_states[i]})

        meta = {
            "version":      _FORMAT_VERSION,
            "saved_at":     now_str,
            "current_page": current_idx,
            "pages":        pages_meta,
        }

        # Write to a temporary in-memory buffer then rename for atomicity
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", json.dumps(meta, indent=2))

            for i, page in enumerate(pages):
                # Strike log
                strikes_name = f"strikes_{i:03d}.json"
                zf.writestr(
                    strikes_name,
                    json.dumps(page.get_strikes(), indent=2),
                )

                # PNG snapshot
                png_name = f"page_{i:03d}.png"
                png_buf  = io.BytesIO()
                pygame.image.save(page.get_surface(), png_buf)
                png_buf.seek(0)
                zf.writestr(png_name, png_buf.read())

        # Atomic write: write to .tmp then replace
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as fh:
            fh.write(buf.getvalue())
        os.replace(tmp_path, path)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls, path: str
    ) -> tuple[Document, list[dict], int] | None:
        """
        Load a .typewriter ZIP archive.

        Returns (document, pages_data, current_idx) on success, or None
        if the file is missing, invalid, or not a recognised archive.

        pages_data items have keys "strikes" and "carriage".
        """
        if not os.path.isfile(path):
            return None
        try:
            return cls._read_zip(path)
        except Exception as exc:
            print(f"[document] Failed to load '{path}': {exc}")
            return None

    @classmethod
    def _read_zip(
        cls, path: str
    ) -> tuple[Document, list[dict], int]:
        """Internal: parse a ZIP and return (doc, pages_data, current_idx)."""
        with zipfile.ZipFile(path, "r") as zf:
            meta_bytes = zf.read("meta.json")
            meta       = json.loads(meta_bytes)

            pages_meta  = meta.get("pages", [])
            current_idx = meta.get("current_page", 0)
            current_idx = max(0, min(current_idx, max(0, len(pages_meta) - 1)))

            pages_data: list[dict] = []
            for i, pm in enumerate(pages_meta):
                strikes_name = f"strikes_{i:03d}.json"
                try:
                    strikes = json.loads(zf.read(strikes_name))
                except KeyError:
                    strikes = []
                pages_data.append({
                    "strikes":  strikes,
                    "carriage": pm.get("carriage", {}),
                })

        doc = cls(path=path)
        doc.mark_clean()
        return (doc, pages_data, current_idx)

    @classmethod
    def load_legacy(
        cls, session_dir: str
    ) -> tuple[Document, list[dict], int] | None:
        """
        Load an old-style session directory containing state.json.

        Returns (document, pages_data, current_idx) on success, or None
        if the directory is not a valid legacy session.

        The returned Document has path=None and dirty=True (it has never
        been saved in the new format).
        """
        state_path = os.path.join(session_dir, "state.json")
        if not os.path.exists(state_path):
            return None

        try:
            with open(state_path) as fh:
                state = json.load(fh)
        except Exception as exc:
            print(f"[document] Failed to read legacy state '{state_path}': {exc}")
            return None

        version = state.get("version", 1)

        if version == 1:
            # Single-page legacy format
            pages_data = [
                {
                    "strikes":  state.get("strikes",  []),
                    "carriage": state.get("carriage", {}),
                }
            ]
            current_idx = 0
        else:
            # Multi-page legacy format (version 2)
            pages_data  = state.get("pages", [])
            current_idx = state.get("current_page", 0)
            current_idx = max(0, min(current_idx, max(0, len(pages_data) - 1)))
            # Normalise each page entry to ensure both keys exist
            for pd in pages_data:
                pd.setdefault("strikes",  [])
                pd.setdefault("carriage", {})

        doc = cls(path=None)
        doc.dirty = True   # encourage user to save in the new format
        return (doc, pages_data, current_idx)
