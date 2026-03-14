#!/usr/bin/env python3
"""
main.py — Entry point for the Typewriter application.

Usage
-----
  python main.py                        # full-screen, blank document
  python main.py --windowed             # resizable window (useful for testing)
  python main.py --no-sound             # disable audio
  python main.py FILE.typewriter        # open a specific document
"""

import argparse
import sys


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="typewriter",
        description="A distraction-free mechanical typewriter simulator for Linux.",
    )
    parser.add_argument(
        "document",
        nargs="?",
        metavar="FILE",
        help="Path to a .typewriter document to open.",
    )
    parser.add_argument(
        "--windowed", "-w",
        action="store_true",
        help="Run in a resizable window instead of full-screen.",
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable all audio.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    args.document_path = args.document

    try:
        from app import TypewriterApp
        app = TypewriterApp(args)
        app.initialize()
        app.run()
    except KeyboardInterrupt:
        # Clean Ctrl-C from the terminal — pygame.quit() is called inside run()
        pass
    except Exception as exc:
        # Print the error before pygame tears down the display
        import traceback
        print("\n[typewriter] Unhandled exception:", file=sys.stderr)
        traceback.print_exc()
        try:
            import pygame
            pygame.quit()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
