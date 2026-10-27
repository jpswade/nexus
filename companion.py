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
from preparedness import display_items, article_date, PreparednessFeeds, MAX_AGES, INTERVALS
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
        target_x,target_y=x,y
        glyph=pygame.Surface((56,56),pygame.SRCALPHA)
        x,y=5,10
        colour=PALETTE.get(ink,ink)
        title=title.lower()
        if 'wind' in title:
            for i in range(3):
                dx=int(math.sin(age*3+i)*4)
                pygame.draw.line(glyph,colour,(x+dx,y+i*9),(x+40+dx,y+i*9),2)
                pygame.draw.arc(glyph,colour,(x+28+dx,y-9+i*9,16,12),-1.6,1.6,2)
        elif 'snow' in title or 'ice' in title:
            for angle in range(0,180,60):
                a=math.radians(angle)+age*.2
                dx,dy=int(math.cos(a)*19),int(math.sin(a)*19)
                pygame.draw.line(glyph,colour,(x+22-dx,y+12-dy),(x+22+dx,y+12+dy),2)
        elif 'rain' in title or 'thunder' in title:
            pygame.draw.ellipse(glyph,colour,(x,y-4,45,18),2)
            for i in range(4):
                dy=int(age*18+i*5)%17
                pygame.draw.line(glyph,colour,(x+7+i*9,y+16+dy),(x+3+i*9,y+23+dy),2)
        else:
            # A bulletin symbol, not an invented observation of current weather.
            pygame.draw.polygon(glyph,colour,[(x+22,y-5),(x+44,y+29),(x,y+29)],2)
            pygame.draw.line(glyph,colour,(x+22,y+4),(x+22,y+17),3)
            pygame.draw.circle(glyph,colour,(x+22,y+23),2)
        self.surface.blit(pygame.transform.smoothscale(glyph,(40,32)),(target_x,target_y-5))

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
        net=network or {}
        checked=net.get('checked')
        if checked is not None and now-checked<=35 and net.get('latency') is None:
            bright=int(age*2)%2 == 0
            colour='#ff6464' if bright else '#8b3038'
            pygame.draw.rect(self.surface,colour,(4,4,472,312),8)
            face=self.face(76)
            word=face.render('OFFLINE',True,colour)
            self.surface.blit(word,word.get_rect(center=(240,145)))
            self.text('CONNECTION PROBES FAILED',66,210,22,'muted',350)
            self.text('RETRYING',180,254,20,colour,160)
            return self.surface
        alerts=self.alerts.update(data,(),now)
        # The whole masthead is the assessment, with a single compact clock.
        threat=data.get('threat');level=threat['level'].upper() if threat else 'UNKNOWN'
        stale=not threat or now-threat['fetched']>MAX_AGES['threat']
        fill={'LOW':'#70b99c','MODERATE':'#a5cd65','SUBSTANTIAL':'#ead64c',
              'SEVERE':'#e6a23c','CRITICAL':'#ef6262'}.get(level,'#203640')
        ink='text' if level=='UNKNOWN' else '#081116'
        pygame.draw.rect(self.surface,fill,(0,0,480,66))
        self.text('NEXUS / UK TERRORISM'+(' / STALE' if stale else ''),16,3,14,ink,300)
        self.text(level,14,20,34,ink,320)
        self.text(dt.datetime.fromtimestamp(now).strftime('%H:%M'),371,4,27,ink,103)
        for i in range(5):
            active=i<({'LOW':1,'MODERATE':2,'SUBSTANTIAL':3,'SEVERE':4,'CRITICAL':5}.get(level,0))
            pygame.draw.rect(self.surface,ink if active else '#55605b',(374+i*19,43,14,10),0 if active else 1)
        weather=data.get('weather');wa=[a for a in alerts if a['source']=='weather']
        warning=max(wa,key=lambda a:a['rank'],default=None)
        weather_stale=not weather or now-weather['fetched']>MAX_AGES['weather']
        label=weather_label(warning,weather) if warning else None
        wf,wi=self.weather_style(label)
        pygame.draw.rect(self.surface,wf or PALETTE['panel'],(14,70,458,34))
        status=(label+' / '+('UPCOMING' if warning['detail'].startswith('UPCOMING') else 'WARNING')) if warning else 'NO ACTIVE WARNINGS'
        if weather_stale:
            status=(label+' / STALE') if warning else 'WARNINGS / STALE' if weather else 'WARNINGS / UNAVAILABLE'
        self.text(status,22,76,19,wi,373)
        if warning:
            self.weather_icon(warning['title'],418,77,age,wi)
        else:
            self.text('WX',427,77,18,'muted',40)
        # Independent channels: local conditions on the left, news on the right.
        for slot,x,sources,offset in (('local',14,('weather','floods'),0),
                                      ('news',247,('ncsc','news'),6)):
            phase=age+offset
            source=sources[int(phase/16)%len(sources)]
            sample=data.get(source)
            stale=not sample or now-sample['fetched']>MAX_AGES[source]
            items=display_items(source,sample,now)
            if source=='weather':
                items=wa
            item=items[int(phase/32)%len(items)] if items else None
            title=item['title'] if item else ('Source unavailable' if not sample else
                'Weather data stale' if source=='weather' and stale else
                {'weather':'No active weather warnings','floods':'No local flood alerts',
                 'ncsc':'No NCSC articles today','news':'No headlines listed'}[source])
            if source=='weather' and item:
                title=title.split(' affecting ')[0]
            heading={'weather':'WEATHER','floods':'LOCAL FLOODS','ncsc':'NCSC TODAY','news':'UK NEWS'}[source]
            rect=(x,110,225,148)
            self.box(rect,heading+(' / STALE' if stale else ''),ink='accent')
            self.lines(title,139,3,22,x=x+9,width=207)
            detail=article_date(item) if source=='ncsc' and item else scope if source=='floods' else 'MET OFFICE' if source=='weather' else 'NCSC' if source=='ncsc' else 'BBC NEWS'
            self.text(detail,x+9,226,12,'muted',207)
            # Thin moving channel marker, timed to the actual page rotation.
            pygame.draw.rect(self.surface,PALETTE['border'],(x+9,250,207,2))
            pygame.draw.rect(self.surface,PALETTE['accent'],(x+9,250,int(207*(phase%16)/16),2))
            self.shutter(slot,(source,(sample or {}).get('fetched')),age,rect,16,offset)
        # Current and session extrema share the animated ping bar.
        net=network or dict(colour='muted',checked=None,latency=None)
        latency=net.get('latency');checked=net.get('checked')
        old=checked is not None and now-checked>35
        good=checked is not None and not old and latency is not None
        tone='error' if old or checked is not None and not good else net['colour']
        pygame.draw.rect(self.surface,PALETTE['panel'],(14,266,458,54))
        current=str(round(latency)) if good else '--'
        maximum=net.get('maximum')
        suffix='/'+('--' if maximum is None else str(round(maximum)))
        # Fit the reading to its actual width, leaving the rest for the sweep.
        current_width=self.face(40).size(current)[0]
        suffix_width=self.face(24).size(suffix)[0]
        reading_x=466-current_width-suffix_width-2
        self.text(current,reading_x,268,40,tone,current_width)
        self.text(suffix,reading_x+current_width+2,284,24,'muted',suffix_width)
        track=pygame.Rect(14,266,reading_x-22,54)
        pygame.draw.rect(self.surface,PALETTE['border'],track)
        previous_clip=self.surface.get_clip()
        self.surface.set_clip(track)
        if good:
            # A measured latency trace, not a simulated progress indicator.
            history=net.get('history') or [latency]
            history=history[-22:]
            scale=max(50,max((v for v in history if v is not None),default=50))
            points=[]
            step=track.width/22
            for i,value in enumerate(history):
                x=int(track.right-(len(history)-i-.5)*step)
                if value is None:
                    pygame.draw.line(self.surface,PALETTE['error'],(x,track.bottom-10),(x,track.bottom-3),3)
                    points=[]
                    continue
                y=int(track.bottom-4-(track.height-9)*value/scale)
                pygame.draw.line(self.surface,PALETTE['muted'],(x,track.bottom-3),(x,y),2)
                if points:
                    pygame.draw.line(self.surface,PALETTE['accent'],points[-1],(x,y),2)
                points.append((x,y))
            if points:
                pygame.draw.circle(self.surface,PALETTE['accent'],points[-1],3+int((math.sin(age*5)+1)))
        else:
            self.text('CHECKING',track.left+12,track.top+15,20,'muted',track.width-24)
        self.surface.set_clip(previous_clip)
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
    frame_clock = pygame.time.Clock()
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
        frame_clock.tick(10)  # Match LCD driver cadence; include rendering time.


if __name__ == '__main__':
    main()
