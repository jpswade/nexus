"""Public-domain 8x8 glyphs in tall terminal cells; no antialiasing."""
import json
from pathlib import Path
import unicodedata
import pygame

GLYPHS = json.loads((Path(__file__).parent/'assets/fonts/font8x8.json').read_text())


def ascii_text(value):
    value = str(value).upper()
    for original, replacement in [('…', '...'), ('°', ' DEG'), ('·', '/'), ('—', '-'), ('–', '-'), ('’', "'"), ('█', '\x7f')]:
        value = value.replace(original, replacement)
    return unicodedata.normalize('NFKD', value).encode('ascii', 'replace').decode('ascii')


class BitmapFont:
    def __init__(self, size):
        self.height = max(8, round(size))
        self.width = max(8, round(self.height/2))
        self.cache = {}

    def size(self, value):
        return len(ascii_text(value))*self.width, self.height

    def get_linesize(self):
        return self.height+4

    def render(self, value, antialias, color, background=None):
        value = ascii_text(value)
        color = tuple(pygame.Color(color))
        result = pygame.Surface((max(1, len(value)*self.width), self.height), pygame.SRCALPHA)
        if background is not None:
            result.fill(background)
        for i, char in enumerate(value):
            key = (char, color)
            if key not in self.cache:
                glyph = pygame.Surface((8, 8), pygame.SRCALPHA)
                rows = [255]*8 if char == '\x7f' else GLYPHS[ord(char)]
                for y, row in enumerate(rows):
                    for x in range(8):
                        if row & (1 << x):
                            glyph.set_at((x, y), color)
                self.cache[key] = pygame.transform.scale(glyph, (self.width, self.height))
            result.blit(self.cache[key], (i*self.width, 0))
        return result


def ascii_box(surface, rectangle, color):
    """Draw literal + - | characters around a rectangle, on a cell grid."""
    rectangle = pygame.Rect(rectangle)
    font = BitmapFont(16)
    columns = max(2, rectangle.width//font.width)
    edge = font.render('+'+'-'*(columns-2)+'+', False, color)
    surface.blit(edge, rectangle.topleft)
    surface.blit(edge, (rectangle.x, rectangle.bottom-font.height))
    side = font.render('|', False, color)
    for y in range(rectangle.y+font.height, rectangle.bottom-font.height, font.height):
        surface.blit(side, (rectangle.x, y))
        surface.blit(side, (rectangle.x+(columns-1)*font.width, y))
