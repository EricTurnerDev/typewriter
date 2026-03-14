"""
exporter.py — Export the document to image or document formats.

Supported formats
-----------------
  PNG    — always available (via pygame.image.save)
             All pages are composited into a single tall image with a
             PAGE_GAP-sized strip of background colour between them.
  PDF    — available when reportlab is installed  (pip install reportlab)
             Each Page object becomes one PDF page.

The export directory defaults to ./exports/ and is created automatically.
Filenames include a timestamp so exports never overwrite each other.
"""

from __future__ import annotations

import os
import datetime
import pygame
from config import (
    EXPORTS_DIR,
    PAPER_WIDTH, PAPER_HEIGHT, PAGE_GAP,
    BACKGROUND_COLOR,
)


class Exporter:
    """Exports the document (list of Page objects) to disk."""

    def __init__(self):
        os.makedirs(EXPORTS_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # PNG
    # ------------------------------------------------------------------

    def export_png(self, pages: list, path: str | None = None) -> str:
        """
        Composite all pages into a single tall PNG.

        Pages are arranged top-to-bottom with PAGE_GAP pixels of background
        colour between them, matching the on-screen document view.
        """
        if path is None:
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(EXPORTS_DIR, f"document_{ts}.png")

        n      = len(pages)
        total_h = n * PAPER_HEIGHT + max(0, n - 1) * PAGE_GAP
        canvas  = pygame.Surface((PAPER_WIDTH, total_h))
        canvas.fill(BACKGROUND_COLOR)

        for i, page in enumerate(pages):
            y = i * (PAPER_HEIGHT + PAGE_GAP)
            canvas.blit(page.get_surface(), (0, y))

        pygame.image.save(canvas, path)
        print(f"[export] PNG → {path}")
        return path

    # ------------------------------------------------------------------
    # PDF (optional)
    # ------------------------------------------------------------------

    def export_pdf(self, pages: list, path: str | None = None) -> str | None:
        """
        Save the document as a multi-page PDF using reportlab.

        Each Page object becomes one PDF page.
        Returns the path written, or None if reportlab is unavailable.
        """
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
        except ImportError:
            print("[export] PDF export requires reportlab: pip install reportlab")
            return None

        import tempfile

        if path is None:
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(EXPORTS_DIR, f"document_{ts}.pdf")

        tmp_paths = []
        try:
            # Write each page as a temporary PNG
            for page in pages:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_paths.append(tmp.name)
                pygame.image.save(page.get_surface_on_white(), tmp_paths[-1])

            c = rl_canvas.Canvas(path, pagesize=letter)
            for tmp_path in tmp_paths:
                c.drawImage(tmp_path, 0, 0, width=8.5 * inch, height=11.0 * inch)
                c.showPage()
            c.save()
            print(f"[export] PDF → {path}")
        finally:
            for tmp_path in tmp_paths:
                os.unlink(tmp_path)

        return path
