"""480x320 Pygame companion, written directly to the ILI9486 framebuffer."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import struct
import time
import threading
import math

import pygame
from preparedness import PreparednessFeeds, MAX_AGES, INTERVALS
from terminal_theme import PALETTE
from alert_state import AlertState
from companion_network import NetworkMonitor, sweep_duration

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
        self.tiles = {}

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

    def box(self, rect, title, fill=None, ink='muted'):
        pygame.draw.rect(self.surface, fill or PALETTE['panel'], rect)
        pygame.draw.rect(self.surface, PALETTE['border'], rect, 1)
        self.text(title, rect[0]+9, rect[1]+5, 16, ink, rect[2]-18)

    def weather_style(self, label):
        fill={'YELLOW':'#ead64c','AMBER':'#e6a23c','RED':'#ef6262'}.get(label)
        return fill, '#081116' if fill else 'text'

    def weather_icon(self, title, x, y, age, ink):
        colour=PALETTE.get(ink,ink)
        title=title.lower()
        if 'wind' in title:
            for i in range(3):
                dx=int(math.sin(age*3+i)*4)
                pygame.draw.line(self.surface,colour,(x+dx,y+i*9),(x+40+dx,y+i*9),2)
                pygame.draw.arc(self.surface,colour,(x+28+dx,y-9+i*9,16,12),-1.6,1.6,2)
        elif 'snow' in title or 'ice' in title:
            for angle in range(0,180,60):
                a=math.radians(angle)+age*.2
                dx,dy=int(math.cos(a)*19),int(math.sin(a)*19)
                pygame.draw.line(self.surface,colour,(x+22-dx,y+12-dy),(x+22+dx,y+12+dy),2)
        elif 'rain' in title or 'thunder' in title:
            pygame.draw.ellipse(self.surface,colour,(x,y-4,45,18),2)
            for i in range(4):
                dy=int(age*18+i*5)%17
                pygame.draw.line(self.surface,colour,(x+7+i*9,y+16+dy),(x+3+i*9,y+23+dy),2)
        else:
            # A bulletin symbol, not an invented observation of current weather.
            pygame.draw.polygon(self.surface,colour,[(x+22,y-5),(x+44,y+29),(x,y+29)],2)
            pygame.draw.line(self.surface,colour,(x+22,y+4),(x+22,y+17),3)
            pygame.draw.circle(self.surface,colour,(x+22,y+23),2)

    def shutter(self, slot, token, age, rect, period, offset=0):
        previous=self.tiles.get(slot)
        if previous is None:
            self.tiles[slot]=(token,age-1)
        elif previous[0]!=token:
            self.tiles[slot]=(token,age)
        opening=min(1,max(0,(age-self.tiles[slot][1])/.45))
        remaining=period-((age+offset)%period)
        visible=min(opening,min(1,remaining/.3))
        if visible<1:
            width=int(rect[2]*(1-visible))
            pygame.draw.rect(self.surface,PALETTE['background'],(rect[0]+rect[2]-width,rect[1],width,rect[3]))
            pygame.draw.line(self.surface,PALETTE['accent'],(rect[0]+rect[2]-width,rect[1]),(rect[0]+rect[2]-width,rect[1]+rect[3]-1),2)

    def draw(self, data, now, age, scope, network=None):
        self.surface.fill(PALETTE['background'])
        alerts=self.alerts.update(data,(),now)
        highest=max((a['rank'] for a in alerts),default=0)
        missing=any(not data.get(n) or now-data[n]['fetched']>MAX_AGES[n] for n in ('threat','weather','floods'))
        rail='#ff5555' if highest>=5 else '#ffbf66' if highest>=3 else '#e5d558' if highest else PALETTE['muted' if missing else 'accent']
        pygame.draw.rect(self.surface,rail,(0,0,6,320))
        self.text('NEXUS / '+('DATA STALE' if missing else 'SIGNAL OS'),16,3,19,'error' if missing else 'accent',300)
        self.text(dt.datetime.fromtimestamp(now).strftime('%H:%M:%S'),365,3,19,'text',110)
        # Permanent threat box. Only secondary content is ever shuttered.
        threat=data.get('threat');level=threat['level'].upper() if threat else 'UNKNOWN'
        fill={'SEVERE':'#e6a23c','CRITICAL':'#ef6262'}.get(level)
        ink='#081116' if fill else 'text'
        stale=not threat or now-threat['fetched']>MAX_AGES['threat']
        self.box((14,31,282,91),'UK THREAT / GOV.UK'+(' *' if stale else ''),fill,ink)
        self.text(level,24,53,38 if len(level)>6 else 48,ink,262)
        self.text('STALE / LAST KNOWN' if stale else 'NATIONAL ASSESSMENT',24,101,13,ink,262)
        net=network or dict(label='CHECKING',detail='Waiting for probe',colour='muted',checked=None,latency=None,history=[])
        old=net.get('checked') is not None and now-net['checked']>35
        tone='error' if old else net['colour']
        self.box((304,31,168,91),'NET / SESSION')
        self.text('PROBE STALE' if old else net['label'],314,56,20,tone,148)
        self.text(net['detail'],314,84,17,tone,148)
        low=net.get('minimum');high=net.get('maximum')
        low_text='--' if low is None else str(round(low))
        high_text='--' if high is None else str(round(high))
        self.text('MIN '+low_text+' / MAX '+high_text+' ms',314,105,12,'muted',148)
        weather=data.get('weather');wa=[a for a in alerts if a['source']=='weather']
        warning=max(wa,key=lambda a:a['rank'],default=None)
        label=weather_label(warning,weather) if warning else 'NONE LISTED' if weather else 'UNKNOWN'
        wf,wi=self.weather_style(label)
        self.box((304,130,168,70),'MET OFFICE'+(' *' if not weather or now-weather['fetched']>MAX_AGES['weather'] else ''),wf,wi)
        self.text(label if warning or not weather else 'NONE',314,156,18 if warning and len(label)>6 else 24,wi,104 if warning else 148)
        if warning:
            self.weather_icon(warning['title'],420,157,age,wi)
        # Independently timed content slots; refreshes also trigger a short reveal.
        index=int(age/13)%3
        source=('weather','floods','ncsc')[index]
        sample=data.get(source)
        stale=not sample or now-sample['fetched']>MAX_AGES[source]
        items=sample.get('items',[]) if sample else []
        title=warning['title'] if index==0 and warning else items[int(age/39)%len(items)]['title'] if items else 'No current bulletins returned' if sample else 'Waiting for source'
        fill,ink=(wf,wi) if index==0 else (None,'text')
        self.box((14,130,282,146),('WEATHER BULLETIN','LOCAL FLOOD WATCH','NCSC BRIEFING')[index]+(' *' if stale else ''),fill,ink)
        self.lines(title,160,3,23,ink,x=24,width=262)
        detail=('VALIDITY / CHECK SOURCE' if 'CHECK VALIDITY' in warning['detail'] else warning['detail']) if index==0 and warning else scope if index==1 else 'NCSC / SOURCE PUBLICATION' if index==2 else 'MET OFFICE / REGIONAL'
        self.text(detail,24,243,14,ink,262)
        stamp=dt.datetime.fromtimestamp(sample['fetched']).strftime('CHECKED %H:%M') if sample else 'NO SUCCESSFUL CHECK'
        self.text(('STALE / ' if stale else '')+stamp,24,259,12,ink,262)
        self.shutter('main',(index,(sample or {}).get('fetched')),age,(14,130,282,146),13)
        right=int((age+7)/19)%3
        source=('floods','news','weather')[right]
        sample=data.get(source);items=(sample or {}).get('items',[])
        side_stale=not sample or now-sample['fetched']>MAX_AGES[source]
        self.box((304,208,168,68),('LOCAL FLOODS','BBC BRIEF','SOURCE CHECK')[right]+(' *' if side_stale else ''))
        if right==0:
            self.text(str(len(items))+' ALERT'+('' if len(items)==1 else 'S') if sample else 'UNKNOWN',314,234,24,'error' if items else 'text',148)
        elif right==1:
            self.lines(items[int(age/57)%len(items)]['title'] if items else 'No publication',232,2,15,'text',314,148)
        else:
            fresh=sample and now-sample['fetched']<=MAX_AGES[source]
            self.text('FRESH' if fresh else 'STALE',314,234,24,'accent' if fresh else 'error',148)
        self.shutter('side',(right,(sample or {}).get('fetched')),age,(304,208,168,68),19,7)
        # Scanning corner accents give quiet motion without blinking the words.
        for x,y,w,h in ((14,31,282,91),(304,31,168,91)):
            phase=int(age*24)%(w-15)
            pygame.draw.line(self.surface,PALETTE['accent'],(x+phase,y),(x+phase+12,y),2)
        # One sweep per real probe cadence; the number counts completed probes.
        pygame.draw.rect(self.surface,PALETTE['panel'],(14,284,458,32))
        latency=net.get('latency');checked=net.get('checked')
        good=checked is not None and not old and latency is not None
        self.text('TCP #'+str(net.get('sequence',0)).zfill(5),24,287,15,tone,122)
        self.text(str(round(latency))+' ms' if good else 'NO REPLY' if checked else 'CHECKING',386,287,16,tone,80)
        pygame.draw.line(self.surface,PALETTE['border'],(151,301),(376,301),1)
        if good:
            phase=min(1,max(0,(now-checked)/sweep_duration(latency)))
            head=151+int(phase*225)
            for i in range(12):
                x=head-i*3
                if x>=151:
                    pygame.draw.line(self.surface,PALETTE['accent'],(x,296+i//4),(x,305-i//4),1)
        else:
            # No successful-looking sweep when offline or when measurements age out.
            for i in range(12):
                x=155+i*18
                if int(age*3+i)%3:
                    pygame.draw.line(self.surface,PALETTE[tone],(x,299),(x+7,303),2)
        return self.surface


def refresh_overdue(cache, config, attempted, now):
    """Refresh only overdue shared sources; main-view changes cannot strand LCD data."""
    feeds = PreparednessFeeds(cache, config)
    data, _ = feeds.snapshot()
    for name in ('threat', 'weather', 'floods', 'ncsc', 'news'):
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
        time.sleep(.125)


if __name__ == '__main__':
    main()
