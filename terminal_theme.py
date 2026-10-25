"""Shared terminal identity for the Nexus and configurable home views."""
from pathlib import Path

FONT = Path(__file__).resolve().parent / "assets/fonts/ShareTechMono-Regular.ttf"
PALETTE = {
    "background": "#050b17", "panel": "#091321", "text": "#c2f3fa",
    "muted": "#689cae", "accent": "#55e6ed", "border": "#224759",
    "error": "#ffbf66",
}


def font(size):
    import pygame
    return pygame.font.Font(str(FONT), max(10, round(size)))


def switch_view(view):
    """Replace the current process, preserving systemd ownership and signals."""
    import os
    import sys
    os.execv(sys.executable, [sys.executable, str(FONT.parents[2] / "launch.py"), view])
