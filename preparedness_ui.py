"""UK-first, source-labelled civil preparedness screens."""
import datetime as dt
import textwrap
import json
from pathlib import Path
import math
from cyber_graphics import draw_orb
from status_summary import summary
from preparedness import LINKS, MAX_AGES, LEVELS, source_status

NAMES = ('Planetary observatory', 'Incident & cyber watch', 'UK situation map', 'Minutes to midnight')
PREPARE_TIPS = (
    'Keep important contact numbers on paper and agree a household emergency plan.',
    'Check your smoke alarms monthly. Review the support needs of people you care for.',
    'Check your flood risk and sign up for official warnings that cover your area.',
    'Ask your utility suppliers about Priority Services Registers if you need extra support.',
)


def load_doomsday_setting(path=None):
    """Load an explicitly dated, source-verified editorial record, not a timer."""
    try:
        record = json.loads((Path(path) if path else Path(__file__).parent/'data/doomsday-clock.json').read_text())
        seconds = record['seconds_to_midnight']
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 0 <= seconds <= 3600:
            raise ValueError('Invalid setting')
        for key in ('announced', 'verified'):
            dt.date.fromisoformat(record[key])
        if not record['url'].startswith('https://thebulletin.org/doomsday-clock/'):
            raise ValueError('Expected original publisher')
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None


class PreparednessDesktop:
    def __init__(self, ui, feeds, location=None):
        self.u = ui
        self.feeds = feeds
        self.links = []
        self.active_url = LINKS['prepare']
        self.doomsday = load_doomsday_setting()
        self.map = None
        self.globe = None
        self.local_weather = None
        self.weather_failed = False
        if hasattr(ui, 'blit'):
            from uk_map import UKMap
            self.map = UKMap(location)
            from observatory_globe import ObservatoryGlobe
            self.globe = ObservatoryGlobe(location)

    def wrap(self, value, y, size=26, width=82, lines=3, color=None):
        rows = textwrap.wrap(str(value), width)
        if len(rows) > lines:
            rows = rows[:lines]
            rows[-1] = rows[-1].rstrip(' .')+'...'
        for i, row in enumerate(rows):
            self.u.text(row, 48, y+i*(size+9), size, color or self.u.TEXT)

    def source(self, label, url, y=588, primary=True):
        self.u.text(label+' / OPEN SOURCE >', 48, y, 19, self.u.TEAL)
        self.links.append(((42, y-4, 770, 30), url))
        if primary:
            self.active_url = url

    def status(self, name, data, errors, now, y=624):
        value = source_status(name, data, errors, now)
        self.u.text(value, 48, y, 18, self.u.AMBER if value.startswith(('STALE', 'UNAVAILABLE')) else self.u.DIM)

    def clicked_url(self, point):
        x, y = point
        for (rx, ry, w, h), url in self.links:
            if rx <= x <= rx+w and ry <= y <= ry+h:
                return url
        return None

    def scroll(self, lines):
        if not getattr(self, 'scroll_offset', 0):
            self.history_cursor = getattr(self, 'stream_cursor', 16)
        self.scroll_offset = max(0, min(getattr(self, 'stream_length', 0)-1,
                                        getattr(self, 'scroll_offset', 0)+lines))

    def paragraphs(self, value, x, y, width=65, size=22, limit=3, color=None):
        rows = textwrap.wrap(str(value), width) or ['']
        if len(rows) > limit:
            rows = rows[:limit]
            rows[-1] = rows[-1].rstrip(' .')+'...'
        for n, row in enumerate(rows):
            self.u.text(row, x, y+n*(size+5), size, color or self.u.TEXT)

    def stream(self, age, data, errors, now):
        """Replay source headlines; motion changes presentation, never source facts."""
        u = self.u
        u.panel(324,565,928,91,'SOURCE BRIEFING / AUTO REPLAY','PGUP / PGDN / END')
        rows = []
        for name, label in [('weather', 'MET OFFICE'), ('floods', 'ENV. AGENCY'),
                            ('ncsc', 'NCSC / PUBLICATION'), ('news', 'BBC / MEDIA REPORT')]:
            sample = data.get(name, {})
            items = sample.get('items', [])[:6]
            state = source_status(name, data, errors, now)
            rows.append((label, u.TEAL, LINKS.get(name, LINKS['prepare'])))
            rows.append((state, u.DIM, None))
            if not items:
                rows.append(('No items returned' if sample else 'Waiting for source...', u.DIM, None))
            for item in items:
                rows.append((label, u.TEAL, item.get('url')))
                published = item.get('published')
                if published:
                    stamp = dt.datetime.fromtimestamp(published, dt.timezone.utc).strftime('%d %b %H:%M UTC')
                    rows.append((stamp, u.DIM, None))
                for row in textwrap.wrap(label+' / '+item['title'], 95):
                    rows.append((row, u.TEXT, item.get('url')))
                rows.append(('', u.DIM, None))
        rows.append(('PREPARE / HOUSEHOLD GUIDANCE', u.TEAL, LINKS['prepare']))
        for tip in PREPARE_TIPS:
            rows.extend((row, u.TEXT, LINKS['prepare']) for row in textwrap.wrap(tip, 95))
            rows.append(('', u.DIM, None))
        rows = [row for row in rows if row[0]]
        self.stream_length = len(rows)
        # Begin with a populated transcript, then reveal a line every 0.8 s.
        progress = max(0., age)*1.25
        cursor = min(len(rows), 16+int(progress))
        if cursor == len(rows):
            cursor = 16+int(progress) % max(1, len(rows)-15)
        self.stream_cursor = cursor
        if getattr(self, 'scroll_offset', 0):
            cursor = min(len(rows), getattr(self, 'history_cursor', cursor))
        offset = min(getattr(self, 'scroll_offset', 0), max(0, cursor-1))
        end = cursor-offset
        start = max(0, end-2)
        for n, (value, colour, url) in enumerate(rows[start:end]):
            if n == end-start-1 and not offset:
                value = value[:int((progress % 1)*max(1, len(value)))]+('_' if int(age*2)%2 else '')
            y = 609+n*23
            u.text(value, 340, y, 17, colour)
            if url:
                self.links.append(((336, y, 900, 22), url))
        if offset:u.text('HISTORY',1125,581,14,u.AMBER)

    def draw(self, index, age, data, errors, now, stream_age=None):
        u = self.u
        self.links = []
        self.active_url = LINKS['prepare']
        u.text('UK THREAT / '+summary('threat',data,now,errors),28,72,18,u.AMBER)
        u.text('WEATHER / '+summary('weather',data,now,errors),410,72,17,u.TEAL)
        u.text('FLOODS / '+summary('floods',data,now,errors),780,72,17,u.TEAL)
        setting=self.doomsday
        u.text('DOOMSDAY / '+(str(setting['seconds_to_midnight'])+'s' if setting else '--'),1080,72,17,u.AMBER)
        u.panel(28,105,280,167,'LOCAL TIME','')
        moment=dt.datetime.fromtimestamp(now)
        u.text(moment.strftime('%H:%M'),44,153,60,u.TEXT)
        u.text(moment.strftime('%S'),251,169,24,u.DIM)
        u.text(moment.strftime('%a %d %b %Y').upper(),44,224,18,u.DIM)
        u.panel(28,286,280,266,'UK THREAT / GOV.UK','')
        sample=data.get('threat')
        level=sample['level'].upper() if sample else 'UNAVAILABLE'
        u.text(level,42,338,44,u.AMBER)
        meanings={'LOW':'Attack highly unlikely','MODERATE':'Attack possible, not likely',
                  'SUBSTANTIAL':'An attack is likely','SEVERE':'An attack is highly likely',
                  'CRITICAL':'Attack highly likely in the near future'}
        self.paragraphs(meanings.get(level,'Awaiting official source'),44,395,27,18,2,u.DIM)
        for i,name in enumerate(LEVELS):
            selected=name==level.lower()
            u.line((44+i*50,459),(84+i*50,459),u.AMBER if selected else u.DIM,4 if selected else 1)
            if selected:u.text('>> '+name.upper(),44,475,15,u.AMBER)
        self.paragraphs(source_status('threat',data,errors,now),44,509,30,14,2,u.DIM)
        self.links.append(((28,286,280,266),LINKS['threat']))
        self.active_url=LINKS['threat']
        u.panel(324,105,600,447,'UK / SITUATION MAP' if index==2 else 'EARTH / GEOGRAPHIC OBSERVATORY','')
        if self.globe and index!=2:
            u.blit(self.globe.draw(age if stream_age is None else stream_age),340,151)
        elif self.map:
            # The same map, scaled to fit the central instrument bay.
            import pygame
            u.blit(pygame.transform.smoothscale(self.map.draw(age),(390,390)),429,150)
        if index!=2:
            u.text('ROTATING VIEW / CONFIGURED AREA MARKER',342,529,15,u.DIM)
        u.panel(940,105,312,270,'LOCAL WEATHER / MET OFFICE','')
        weather=self.local_weather
        if weather:
            stale=self.weather_failed or now-weather['fetched']>1800
            u.text(f"{weather['temp']:.0f} C",956,153,46,u.TEXT)
            u.text('OPEN-METEO / '+('STALE' if stale else 'LATEST'),1076,177,13,u.DIM)
        else:u.text('TEMPERATURE UNAVAILABLE',956,163,18,u.DIM)
        u.text(summary('weather',data,now,errors),956,213,20,u.AMBER)
        rows=data.get('weather',{}).get('items',[])
        rank={'red':3,'amber':2,'yellow':1}
        item=max(rows,key=lambda item:rank.get(item.get('colour'),0),default=None)
        self.paragraphs(item['title'] if item else ('No bulletins returned' if 'weather' in data else 'Weather source unavailable'),956,246,28,18,4)
        self.paragraphs(source_status('weather',data,errors,now),956,344,34,12,2,u.DIM)
        self.links.append(((940,105,312,270),item['url'] if item else LINKS['weather']))
        u.panel(940,389,312,163,'LOCAL / FLOOD WATCH','')
        u.text(summary('floods',data,now,errors),956,439,23,u.AMBER)
        self.paragraphs(getattr(self.feeds,'flood_scope','ENGLAND'),956,474,33,15,2,u.DIM)
        u.text('EA / ENGLAND / CHECK AREA',956,522,14,u.DIM)
        self.links.append(((940,389,312,163),LINKS['floods']))
        u.panel(28,565,280,91,'DOOMSDAY / BULLETIN','')
        u.text(str(setting['seconds_to_midnight']) if setting else '--',44,601,36,u.AMBER)
        u.text('SECONDS TO MIDNIGHT',112,607,16,u.TEXT)
        u.text(setting['announced'] if setting else 'UNAVAILABLE',112,631,13,u.DIM)
        self.links.append(((28,565,280,91),setting['url'] if setting else 'https://thebulletin.org/doomsday-clock/'))
        if index==3:self.active_url=setting['url'] if setting else 'https://thebulletin.org/doomsday-clock/'
        self.stream(age if stream_age is None else stream_age,data,errors,now)
