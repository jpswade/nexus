"""Presentation only: the shared policy owns card selection and dwell.

Pages retain their progress across policy visits so long evidence and complete URLs
remain accessible without a scrolling ticker. No I/O, source ranking or risk scoring.
"""
from collections import OrderedDict
import datetime as dt

from terminal_theme import PALETTE


def stamp(value):
    if value is None:
        return 'unknown'
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).strftime('%d %b %Y %H:%M UTC')


def wrap(value, face, width):
    """Wrap even unbroken URLs; never discard characters to fit the LCD."""
    rows = []
    for paragraph in str(value).splitlines() or ['']:
        row = ''
        for character in paragraph:
            if row and face.size(row + character)[0] > width:
                split = row.rfind(' ')
                if split > 0:
                    rows.append(row[:split])
                    row = row[split + 1:]
                else:
                    rows.append(row)
                    row = ''
            row += character
        rows.append(row)
    return rows


class CardRenderer:
    PAGE_SECONDS = 8

    def __init__(self):
        self.progress = OrderedDict()
        self.active = None
        self.last_age = None
        self.pages = []
        self.page = 0
        self.layout_token = None

    def draw(self, view, card, age, policy_available=True):
        view.box((14, 110, 458, 148), '', ink='accent')
        if card is None:
            self.active = None
            self.last_age = age
            self.pages = []
            self.layout_token = None
            view.text('BRIEFING', 23, 115, 14, 'accent', 438)
            view.lines('No priority item' if policy_available else 'Briefing policy unavailable',
                       143, 2, 26, x=23, width=438)
            view.text('Checks remain visible above', 23, 231, 14, 'muted', 438)
            return
        # Text changes reset the presentation, not policy timing. Retain at most 64
        # cursors; no image or camera data are retained.
        content = [card['title'], *card['body'], 'Source: ' + card['source'],
                   'Published: ' + stamp(card['published']),
                   'Checked: ' + stamp(card['checked']),
                   'Valid until: ' + stamp(card['valid_until']),
                   'Link: ' + (card['url'] or 'unavailable')]
        token = (card['id'], tuple(content), card['state'], card['severity'])
        elapsed = self.progress.pop(token, 0)
        if self.active == token and self.last_age is not None:
            elapsed += max(0, age - self.last_age)
        self.progress[token] = elapsed
        while len(self.progress) > 64:
            self.progress.popitem(last=False)
        self.active, self.last_age = token, age
        if self.layout_token != token:
            rows = [row for value in content for row in wrap(value, view.face(22), 438)]
            self.pages = [rows[i:i+4] for i in range(0, len(rows), 4)]
            self.layout_token = token
        self.page = int(elapsed / self.PAGE_SECONDS) % len(self.pages)
        colour = {'critical': 'error', 'warning': 'warning', 'advisory': 'accent'}.get(card['severity'], 'text')
        if colour not in PALETTE:
            colour = '#e6a23c'
        label = card['group'].upper() + ' / ' + card['state'].upper() + ' / ' + card['severity'].upper()
        view.text(label, 23, 114, 13, colour, 438)
        for i, row in enumerate(self.pages[self.page]):
            view.text(row, 23, 134 + i*24, 22, 'text', 438)
        view.text(f"{self.page+1}/{len(self.pages)} · {card['source']}", 23, 236, 13, 'muted', 438)
