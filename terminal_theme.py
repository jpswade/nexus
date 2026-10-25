"""Shared terminal identity for the Nexus and configurable home views."""
from pathlib import Path

FONT = Path(__file__).resolve().parent / "assets/fonts/ShareTechMono-Regular.ttf"
PALETTE = {
    "background": "#000600", "panel": "#000600", "text": "#80ff70",
    "muted": "#59bb51", "accent": "#a4ff88", "border": "#438c3e",
    "error": "#ffbf66",
}


def font(size):
    from bitmap_font import BitmapFont
    return BitmapFont(size)


def switch_view(view):
    """Replace the current process, preserving systemd ownership and signals."""
    import os
    import sys
    os.execv(sys.executable, [sys.executable, str(FONT.parents[2] / "launch.py"), view])
