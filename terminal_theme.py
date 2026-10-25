"""Shared terminal identity for the Nexus and configurable home views."""
from pathlib import Path

FONT = Path(__file__).resolve().parent / "assets/fonts/ShareTechMono-Regular.ttf"
PALETTE = {
    "background": "#050d11", "panel": "#08141a", "text": "#d8ecee",
    "muted": "#70949f", "accent": "#35dccc", "border": "#203640",
    "error": "#ffbf66", "lime": "#b9f45b", "blue": "#509ac5",
}


def font(size):
    import pygame
    return pygame.font.Font(str(FONT), max(10, round(size)))


def switch_view(view):
    """Replace the current process, preserving systemd ownership and signals."""
    import os
    import sys
    os.execv(sys.executable, [sys.executable, str(FONT.parents[2] / "launch.py"), view])
