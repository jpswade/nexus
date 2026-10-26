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
from companion_network import NetworkMonitor

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


def weather_label(alert, sample):
    for item in (sample or {}).get('items', []):
        if item['title'] == alert['title'] and item.get('colour') in ('red','amber','yellow'):
            return item['colour'].upper()
    return 'BULLETIN'


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
        self.surface.blit(face.render(value, True, PALETTE.get(colour, colour)), (x, y))

    def lines(self, value, y, limit=3, size=28, colour='text', x=22, width=260):
        face = self.face(size)
        rows, row = [], ''
        for word in value.split():
            candidate = (row+' '+word).strip()
            if row and face.size(candidate)[0] > width:
                rows.append(row)
                row = word
            else:
                row = candidate
        rows.append(row)
        overflow = len(rows) > limit
        for i, row in enumerate(rows[:limit]):
            if overflow and i == limit-1:
                row += ' …'
            self.text(row, x, y+i*(size+5), size, colour, width)

    def box(self, rect, title):
        pygame.draw.rect(self.surface, PALETTE['panel'], rect)
        pygame.draw.rect(self.surface, PALETTE['border'], rect, 1)
        self.text(title, rect[0]+10, rect[1]+7, 17, 'muted', rect[2]-20)

    def draw(self, data, now, age, scope, network=None):
        self.surface.fill(PALETTE['background'])
        retained = self.alerts.update(data, (), now)
        # A persistent source-backed rail, independent of the rotating page.
        highest = max((a['rank'] for a in retained), default=0)
        missing = any(not data.get(n) or now-data[n]['fetched'] > MAX_AGES[n]
                      for n in ('threat', 'weather', 'floods'))
        rail = '#ff5555' if highest >= 5 else '#ffbf66' if highest >= 3 else '#e5d558' if highest else PALETTE['muted' if missing else 'accent']
        pygame.draw.rect(self.surface, rail, (0, 0, 6, 320))
        self.text('NEXUS / DATA STALE' if missing else 'NEXUS / LIVE', 16, 5, 21, 'error' if missing else 'accent', 280)
        self.text(dt.datetime.fromtimestamp(now).strftime('%H:%M:%S'), 355, 5, 21, 'text', 118)
        page = int(age/12) % 3
        name = ('threat', 'weather', 'floods')[page]
        sample = data.get(name)
        stale = not sample or now-sample['fetched'] > MAX_AGES[name]
        self.box((14, 38, 282, 274), ('UK ASSESSMENT', 'REGIONAL WEATHER', 'LOCAL FLOODS')[page])
        self.text('UNAVAILABLE' if not sample else 'STALE / LAST KNOWN' if stale else 'SOURCE FRESH', 24, 70, 19, 'error' if stale else 'accent', 262)
        if page == 0:
            level = sample['level'].upper() if sample else 'UNKNOWN'
            self.text(level, 24, 110, 38 if len(level)>8 else 54, 'error' if highest else 'text', 262)
            self.lines('UK terrorism assessment', 182, 2, 26)
            self.text('GOV.UK / NATIONAL',24,253,17,'muted',262)
        elif page == 1:
            alerts = [a for a in retained if a['source']=='weather']
            alert = max(alerts, key=lambda a:a['rank'], default=None)
            colour = weather_label(alert, sample) if alert else 'NONE LISTED' if sample else 'UNKNOWN'
            self.text(colour,24,101,35,'error' if alert else 'text',262)
            self.lines(alert['title'] if alert else 'No current bulletins returned' if sample else 'Waiting for Met Office',148,3,24)
            self.text(('VALIDITY / CHECK SOURCE' if 'CHECK VALIDITY' in alert['detail'] else alert['detail']) if alert else 'MET OFFICE / REGIONAL',24,253,16,'muted',262)
        else:
            items = sample.get('items',[]) if sample else []
            self.text(str(len(items))+' ALERTS' if sample else 'UNKNOWN',24,104,44,'error' if items else 'text',262)
            self.lines(items[int(age/12)%len(items)]['title'] if items else 'None returned / check source' if sample else 'Waiting for flood source',165,2,24)
            self.text(scope,24,253,16,'muted',262)
        stamp = dt.datetime.fromtimestamp(sample['fetched']).strftime('%H:%M / %d %b') if sample else 'No successful check'
        self.text(stamp,24,282,20,'error' if stale else 'muted',262)
        self.box((304,38,168,132),'CONNECTION')
        net = network or {'label':'CHECKING','detail':'Waiting for probe','colour':'muted','checked':None,'history':[]}
        old = net.get('checked') is not None and now-net['checked']>35
        label = 'PROBE STALE' if old else net['label']
        tone = 'error' if old else net['colour']
        pygame.draw.rect(self.surface, PALETTE[tone], (304,38,168,132), 2)
        self.text(label,314,67,20,tone,148)
        self.text(net['detail'],314,95,15,'muted',148)
        # Historical bars are measured TCP connection times, gaps are failures.
        for i, value in enumerate(net.get('history',[])):
            h = min(30,max(3,int(value/5))) if value is not None else 3
            pygame.draw.rect(self.surface, PALETTE['accent' if value is not None else 'error'],(314+i*6,149-h,4,h))
        if not old and net.get('checked') is not None:
            # Moving scan shows render liveness; the labelled result is probe-backed.
            x = 314+int(age*30)%145
            pygame.draw.line(self.surface,PALETTE[tone],(x,154),(x+3,154),2)
        for i, source in enumerate(('weather','floods')):
            y=178+i*70
            self.box((304,y,168,64),'WEATHER' if i==0 else 'FLOODS')
            sample=data.get(source)
            alerts=[a for a in retained if a['source']==source]
            stale = not sample or now-sample['fetched']>MAX_AGES[source]
            value = 'UNKNOWN' if not sample else str(len(alerts))+' LISTED'
            if source=='weather' and alerts:
                value=weather_label(max(alerts, key=lambda a:a['rank']), sample)
            self.text(value+(' *' if stale else ''),314,y+28,24,'error' if alerts or stale else 'text',148)
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
    network = NetworkMonitor()
    if not args.snapshot:
        network.start()
    start, refreshed = time.monotonic(), -100
    while True:
        age = time.monotonic()-start
        if age-refreshed >= 10:
            # Read the main dashboard's cache, without duplicate network requests.
            feeds = PreparednessFeeds(cache, config)
            data, _ = feeds.snapshot()
            refreshed = age
        surface = view.draw(data, time.time(), age, feeds.flood_scope, network.snapshot())
        if rotation == 180:
            surface = pygame.transform.rotate(surface, 180)
        if args.snapshot:
            pygame.image.save(surface, args.snapshot)
            return
        target.write(surface)
        time.sleep(.5)


if __name__ == '__main__':
    main()
