"""480x320 Pygame companion, written directly to the ILI9486 framebuffer."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import struct
import time

import pygame
from preparedness import PreparednessFeeds, MAX_AGES
from preparedness_ui import load_doomsday_setting
from terminal_theme import font, PALETTE
from status_summary import summary
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
        self.setting = load_doomsday_setting()
        self.alerts = AlertState()

    def text(self, value, x, y, size=18, colour='text', width=456):
        size = int(size)
        while True:
            if size not in self.fonts:
                self.fonts[size] = font(size)
            face = self.fonts[size]
            if face.size(value)[0] <= width or size <= 12:
                break
            size -= 1
        if face.size(value)[0] > width:
            while value and face.size(value+'...')[0] > width:
                value = value[:-1]
            value += '...'
        self.surface.blit(face.render(value, True, PALETTE[colour]), (x, y))

    def lines(self, value, y, limit=3):
        if 20 not in self.fonts:
            self.fonts[20] = font(20)
        face = self.fonts[20]
        words = value.split()
        rows, row = [], ''
        for word in words:
            candidate = (row+' '+word).strip()
            if row and face.size(candidate)[0] > 450:
                rows.append(row)
                row = word
            else:
                row = candidate
        rows.append(row)
        if len(rows) > limit:
            rows = rows[:limit]
            rows[-1] = rows[-1][:-3]+'...'
        for i, row in enumerate(rows):
            self.text(row, 12, y+i*23, 20)

    def draw(self, data, now, age, scope):
        self.surface.fill(PALETTE['background'])
        self.text('NEXUS / AUX 01', 12, 8, 19, 'accent')
        self.text(dt.datetime.fromtimestamp(now).strftime('%H:%M:%S'), 370, 8, 19, 'accent', 100)
        threat = data.get('threat')
        self.text('UK TERRORISM / GOV.UK', 12, 37, 16, 'muted')
        self.text(threat['level'].upper() if threat else 'UNAVAILABLE', 12, 55, 48, 'error')
        stamp = dt.datetime.fromtimestamp(threat['fetched'], dt.timezone.utc).strftime('%d %b %H:%M UTC') if threat else '--'
        stale = not threat or now-threat['fetched'] > MAX_AGES['threat']
        self.text(('STALE / CHECK ' if stale else 'CACHED / CHECK ')+stamp, 12, 106, 14, 'error' if stale else 'muted')
        pygame.draw.line(self.surface, PALETTE['border'], (12, 127), (468, 127))
        setting = self.setting
        seconds = str(setting['seconds_to_midnight']) if setting else '--'
        self.text('DOOMSDAY / '+seconds+'s',12,134,20,'error',240)
        self.text('BULLETIN / '+(setting['announced'] if setting else '--'),250,137,14,'muted',218)
        self.text('MET OFFICE / '+summary('weather',data,now),12,163,19,'accent')
        weather = data.get('weather', {})
        warnings = weather.get('items', [])
        rank = {'red':3, 'amber':2, 'yellow':1}
        highest = max(warnings, key=lambda item: rank.get(item.get('colour'),0), default=None)
        self.lines(highest['title'] if highest else ('No bulletins returned' if weather else 'Weather source unavailable'),186,limit=2)
        self.text('EA FLOODS / '+summary('floods',data,now),12,237,19,'accent')
        name = ('ncsc', 'news')[int(age/15)%2]
        label = 'NCSC' if name == 'ncsc' else 'BBC'
        sample = data.get(name)
        stale = not sample or now-sample['fetched'] > MAX_AGES[name]
        items = sample.get('items', []) if sample else []
        item = items[int(age/30)%len(items)] if items else None
        alerts = self.alerts.update(data, (), now)
        if alerts:
            alert = alerts[int(age/8)%len(alerts)]
            self.text(('STALE / ' if alert['stale'] else 'WARNING / ')+alert['title'],12,270,18,'error')
            self.text(str(len(alerts))+' LISTED / '+alert['detail'],12,292,12,'error')
            pygame.draw.rect(self.surface, PALETTE['error' if int(age)%2 else 'muted'], (2,260,476,58),2)
        else:
            self.text(label+(' [STALE]' if stale else '')+' / '+(item['title'] if item else 'No publication available'),12,272,17,'muted')
        return self.surface


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
