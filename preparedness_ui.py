"""UK-first, source-labelled civil preparedness screens."""
import datetime as dt
import textwrap
import json
from pathlib import Path
import math
from cyber_graphics import draw_orb
from preparedness import LINKS, MAX_AGES, LEVELS, source_status

NAMES = ('UK status brief', 'Incident & cyber watch', 'Local readiness', 'Minutes to midnight')
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
    def __init__(self, ui, feeds):
        self.u = ui
        self.feeds = feeds
        self.links = []
        self.active_url = LINKS['prepare']
        self.doomsday = load_doomsday_setting()

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
        u.panel(846, 105, 406, 551, 'PUBLIC SOURCE STREAM', ' ')
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
                for row in textwrap.wrap(item['title'], 37):
                    rows.append((row, u.TEXT, item.get('url')))
                rows.append(('', u.DIM, None))
        rows.append(('PREPARE / HOUSEHOLD GUIDANCE', u.TEAL, LINKS['prepare']))
        for tip in PREPARE_TIPS:
            rows.extend((row, u.TEXT, LINKS['prepare']) for row in textwrap.wrap(tip, 37))
            rows.append(('', u.DIM, None))
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
        start = max(0, end-18)
        for n, (value, colour, url) in enumerate(rows[start:end]):
            if n == end-start-1 and not offset:
                value = value[:int((progress % 1)*max(1, len(value)))]+('_' if int(age*2)%2 else '')
            y = 154+n*25
            u.text(value, 860, y, 18, colour)
            if url:
                self.links.append(((856, y, 390, 24), url))
        u.line((860, 613), (1236, 613), u.DIM)
        u.text('HISTORY' if offset else 'AUTO REPLAY / SOURCE HEADLINES', 860, 624, 16, u.TEAL)
        u.text('PGUP / PGDN / END', 860, 645, 12, u.DIM)

    def draw(self, index, age, data, errors, now, stream_age=None):
        u = self.u
        self.links = []
        self.active_url = LINKS['prepare']
        u.panel(28, 105, 802, 551, f'0{index+1} / '+NAMES[index].upper(), 'UK / PUBLIC SOURCES')
        for i in range(18):
            height=3+int(7*(1+math.sin(age*1.6+i*.65)))
            u.line((775+i*8,94),(775+i*8,94-height),u.TEAL)
        u.text('DISPLAY SYNC',930,80,14,u.DIM)
        self.stream(age if stream_age is None else stream_age, data, errors, now)
        # Common secondary readouts keep the wider situation in every workspace.
        u.line((48, 502), (810, 502), u.DIM)
        u.text('WEATHER / '+getattr(self.feeds, 'weather_scope', 'UK').upper(), 48, 516, 17, u.TEAL)
        weather = data.get('weather', {})
        warnings = weather.get('items', [])
        title = warnings[int(age/12) % len(warnings)]['title'] if warnings else ('No bulletins returned' if weather else 'Source unavailable')
        self.paragraphs(title, 48, 542, width=36, size=19, limit=3)
        u.line((440, 516), (440, 624), u.DIM)
        u.text('LOCAL / '+getattr(self.feeds, 'flood_scope', 'ENGLAND').upper()[:32], 456, 516, 17, u.TEAL)
        flood = data.get('floods')
        count = len(flood.get('items', [])) if flood else None
        u.text(f'{count} FLOOD ALERTS / WARNINGS' if count is not None else 'FLOOD SOURCE UNAVAILABLE', 456, 542, 21, u.AMBER)
        self.paragraphs('England coverage. Check warning areas and validity at source.', 456, 575, width=35, size=18, limit=2, color=u.DIM)
        u.text('MET '+source_status('weather', data, errors, now), 48, 634, 13, u.DIM)
        u.text('EA '+source_status('floods', data, errors, now), 456, 634, 13, u.DIM)
        if index == 0:
            sample = data.get('threat')
            stale = sample and ('threat' in errors or now-sample['fetched'] > MAX_AGES['threat'])
            level = sample['level'].upper() if sample else 'UNAVAILABLE'
            u.text('UK TERRORISM / '+('LAST KNOWN ASSESSMENT' if stale else 'NATIONAL ASSESSMENT'), 48, 160, 20, u.DIM)
            # SUBSTANTIAL is the widest official level; keep its full word visible.
            u.text(level, 48, 198, 112, u.AMBER)
            meanings = {'LOW':'AN ATTACK IS HIGHLY UNLIKELY', 'MODERATE':'AN ATTACK IS POSSIBLE BUT NOT LIKELY',
                        'SUBSTANTIAL':'AN ATTACK IS LIKELY', 'SEVERE':'AN ATTACK IS HIGHLY LIKELY',
                        'CRITICAL':'AN ATTACK IS HIGHLY LIKELY IN THE NEAR FUTURE'}
            self.paragraphs(meanings.get(level, 'AWAITING AN OFFICIAL ASSESSMENT'),48,317,64,21,2,u.AMBER)
            for i, name in enumerate(LEVELS):
                selected = name == level.lower()
                x = 48+i*152
                u.text(('>> ' if selected else '   ')+name.upper(),x,365,15,u.AMBER if selected else u.DIM)
                u.line((x,389),(x+138,389),u.AMBER if selected else u.DIM,3 if selected else 1)
            self.status('threat',data,errors,now,411)
            self.source('GOV.UK / JTAC & MI5',LINKS['threat'],454)
            draw_orb(u, 742, 445, 30, age)
        elif index == 1:
            u.text('INCIDENT / CYBER / PUBLICATION DESK',48,160,22,u.TEAL)
            y = 202
            for name, label in [('ncsc','NCSC / OFFICIAL PUBLICATION'),('news','BBC / MEDIA REPORT')]:
                items = data.get(name, {}).get('items', [])
                item = items[int(age/16)%len(items)] if items else None
                u.text(label,48,y,18,u.AMBER)
                self.paragraphs(item['title'] if item else 'Source unavailable / no matching stories',48,y+28,63,23,3)
                if item:
                    self.links.append(((48,y+25,730,86),item['url']))
                    self.active_url=item['url']
                y += 134
            u.text('MEDIA REPORTS DO NOT CHANGE THE OFFICIAL THREAT LEVEL',48,479,16,u.DIM)
        elif index == 2:
            u.text('LOCAL READINESS / '+getattr(self.feeds,'flood_scope','ENGLAND').upper(),48,160,20,u.TEAL)
            u.text(str(count) if count is not None else '--',48,192,90,u.AMBER)
            u.text('FLOOD ALERTS / WARNINGS RETURNED',190,220,25,u.TEXT)
            items = flood.get('items',[]) if flood else []
            item = items[int(age/12)%len(items)] if items else None
            self.paragraphs(item['title'] if item else 'An empty feed is not an all-clear. Check your local flood risk.',48,296,65,22,2)
            if item:
                self.active_url=item['url']
                self.links.append(((48,290,750,60),item['url']))
            u.text('HOUSEHOLD ACTION / PREPARE',48,368,19,u.TEAL)
            self.paragraphs(PREPARE_TIPS[int(age/12)%len(PREPARE_TIPS)],48,398,60,22,3)
            self.links.append(((48,368,750,120),LINKS['prepare']))
        else:
            setting = self.doomsday
            u.text('DOOMSDAY CLOCK / PUBLISHED SETTING',48,160,22,u.DIM)
            u.text(str(setting['seconds_to_midnight']) if setting else '--',48,188,148,u.AMBER)
            u.text('SECONDS TO MIDNIGHT',48,340,31,u.TEXT)
            draw_orb(u, 650, 287, 82, age)
            u.text('VISUAL FX',610,407,14,u.DIM)
            self.paragraphs('Symbolic global risk assessment. Set by the Bulletin of the Atomic Scientists.',48,387,45,20,3)
            self.source('BULLETIN / '+(setting['announced'] if setting else 'UNAVAILABLE'),setting['url'] if setting else 'https://thebulletin.org/doomsday-clock/',466)
