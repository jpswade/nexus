"""480x320 Pygame companion, written directly to the ILI9486 framebuffer."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import struct
import time
import threading

import pygame
from preparedness import PreparednessFeeds, MAX_AGES, INTERVALS
from terminal_theme import PALETTE
from alert_state import AlertState

ROOT = Path(__file__).resolve().parent


def find_lcd(sysfs=Path('/sys/class/graphics')):
    for entry in sorted(sysfs.glob('fb[0-9]*')):
        try:
            if (entry/'name').read_text().strip() == 'fb_ili9486':
                return '/dev/'+entry.name
        except OSError:
            continue
    raise RuntimeError('ILI9486 display unavailable; load the piscreen overlay')


class Framebuffer:
    """Reject unexpected devices/formats rather than touching the HDMI console."""
    def __init__(self, path):
        import fcntl
        device = Path(path)
        info = Path('/sys/class/graphics')/device.name
        if info.joinpath('name').read_text().strip() != 'fb_ili9486':
            raise ValueError('Expected the ILI9486 framebuffer')
        self.file = device.open('r+b', buffering=0)
        try:
            var = bytearray(160)
            fcntl.ioctl(self.file, 0x4600, var)  # FBIOGET_VSCREENINFO
            values = struct.unpack_from('24I', var)
            if values[:2] != (480, 320) or values[4:8] != (0, 0, 16, 0):
                raise ValueError('Expected 480x320, zero offsets, 16-bit colour')
            if values[8:17] != (11, 5, 0, 5, 6, 0, 0, 5, 0):
                raise ValueError('Expected RGB565 framebuffer')
            if int(info.joinpath('stride').read_text()) != 960:
                raise ValueError('Unexpected framebuffer stride')
        except Exception:
            self.file.close()
            raise

    def write(self, surface):
        self.file.seek(0)
        payload = bytes(surface.get_buffer())
        if len(payload) != 480*320*2:
            raise ValueError('Unexpected frame size')
        self.file.write(payload)


class Companion:
    def __init__(self):
        pygame.font.init()
        self.surface = pygame.Surface((480, 320), depth=16, masks=(0xf800, 0x07e0, 0x001f, 0))
        self.fonts = {}
        self.alerts = AlertState()

    def face(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.SysFont('DejaVu Sans', size)
        return self.fonts[size]

    def text(self, value, x, y, size=24, colour='text', width=456):
        # Never shrink status text to fit: wrap elsewhere, truncate metadata.
        face = self.face(size)
        if face.size(value)[0] > width:
            while value and face.size(value+'…')[0] > width:
                value = value[:-1]
            value += '…'
        self.surface.blit(face.render(value, True, PALETTE[colour]), (x, y))

    def lines(self, value, y, limit=3, size=28, colour='text'):
        face = self.face(size)
        rows, row = [], ''
        for word in value.split():
            candidate = (row+' '+word).strip()
            if row and face.size(candidate)[0] > 456:
                rows.append(row)
                row = word
            else:
                row = candidate
        rows.append(row)
        overflow = len(rows) > limit
        for i, row in enumerate(rows[:limit]):
            if overflow and i == limit-1:
                row += ' …'
            self.text(row, 12, y+i*(size+5), size, colour)

    def draw(self, data, now, age, scope):
        self.surface.fill(PALETTE['background'])
        page = int(age/12) % 3
        name = ('threat', 'weather', 'floods')[page]
        sample = data.get(name)
        stale = not sample or now-sample['fetched'] > MAX_AGES[name]
        self.text(('NATIONAL ASSESSMENT', 'REGIONAL WEATHER', 'LOCAL FLOOD ALERTS')[page], 12, 8, 23, 'accent', 350)
        self.text(dt.datetime.fromtimestamp(now).strftime('%H:%M'), 382, 8, 23, 'accent', 86)
        self.text('SOURCE UNAVAILABLE' if not sample else ('STALE · LAST KNOWN' if stale else 'LATEST SOURCE CHECK'),
                  12, 42, 23, 'error' if stale else 'text')
        retained = self.alerts.update(data, (), now)
        if page == 0:
            self.text('UK terrorism assessment', 12, 82, 26)
            level = sample['level'].upper() if sample else 'UNAVAILABLE'
            self.text(level, 12, 120, 56 if len(level) > 9 else 64, 'error')
            self.text('GOV.UK · national context', 12, 207, 24, 'muted')
        elif page == 1:
            # Use the same validity and stale-retention model as the HDMI view.
            alerts = [a for a in retained if a['source'] == 'weather']
            alert = max(alerts, key=lambda a: a['rank'], default=None)
            items = sample.get('items', []) if sample else []
            highest = next((item for item in items if alert and item['title'] == alert['title']), {})
            self.text((str(highest.get('colour', 'BULLETINS')).upper() if alert else 'CHECK SOURCE' if items else 'NO BULLETINS' if sample else 'UNAVAILABLE'),
                      12, 78, 42, 'error' if alert else 'text')
            self.lines(alert['title'] if alert else ('Listed bulletin validity: check source' if items else 'None returned · not an all-clear' if sample else 'Waiting for Met Office'), 136, 3, 28)
            if alert:
                self.text(alert['detail'], 12, 234, 18, 'muted')
        else:
            items = sample.get('items', []) if sample else []
            self.text(str(len(items))+' ALERT'+('' if len(items) == 1 else 'S') if sample else 'UNAVAILABLE', 12, 78, 56, 'error' if items else 'text')
            self.lines(items[int(age/12)%len(items)]['title'] if items else ('None returned · not an all-clear' if sample else 'Waiting for Environment Agency'), 149, 2, 28)
            self.text(scope, 12, 223, 21, 'muted')
        stamp = dt.datetime.fromtimestamp(sample['fetched']).strftime('%d %b %H:%M') if sample else 'No successful check'
        self.text(('Last checked ' if sample else '')+stamp, 12, 257, 22, 'error' if stale else 'muted')
        pygame.draw.line(self.surface, PALETTE['border'], (12, 288), (468, 288))
        self.text(('GOV.UK', 'MET OFFICE', 'ENVIRONMENT AGENCY')[page], 12, 293, 18, 'muted', 360)
        self.text(str(page+1)+' / 3', 398, 293, 18, 'accent', 70)
        return self.surface


def refresh_overdue(cache, config, attempted, now):
    """Refresh only overdue shared sources; main-view changes cannot strand LCD data."""
    feeds = PreparednessFeeds(cache, config)
    data, _ = feeds.snapshot()
    for name in ('threat', 'weather', 'floods'):
        sample = data.get(name)
        due = not sample or now-sample['fetched'] >= INTERVALS[name]
        if due and now-attempted.get(name, float('-inf')) >= 300:
            attempted[name] = now
            feeds.refresh(name)


def fallback_worker(cache, config):
    attempted = {}
    while True:
        refresh_overdue(cache, config, attempted, time.time())
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', help='Override automatic ILI9486 discovery')
    parser.add_argument('--snapshot')
    args = parser.parse_args()
    config = json.loads(Path(os.environ.get('NEXUS_CONFIG', ROOT/'config.json')).read_text())
    rotation = config.get('companion_rotation', 0)
    if rotation not in (0, 180):
        raise ValueError('companion_rotation must be 0 or 180 degrees')
    cache = Path(os.environ.get('NEXUS_CACHE', ROOT/'.cache'))/'preparedness'
    view = Companion()
    target = None if args.snapshot else Framebuffer(args.device or find_lcd())
    if not args.snapshot:
        threading.Thread(target=fallback_worker, args=(cache, config), daemon=True).start()
    start, refreshed = time.monotonic(), -100
    while True:
        age = time.monotonic()-start
        if age-refreshed >= 10:
            # Read the main dashboard's cache, without duplicate network requests.
            feeds = PreparednessFeeds(cache, config)
            data, _ = feeds.snapshot()
            refreshed = age
        surface = view.draw(data, time.time(), age, feeds.flood_scope)
        if rotation == 180:
            surface = pygame.transform.rotate(surface, 180)
        if args.snapshot:
            pygame.image.save(surface, args.snapshot)
            return
        target.write(surface)
        time.sleep(.5)


if __name__ == '__main__':
    main()
