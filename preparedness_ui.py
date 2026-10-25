"""UK-first, source-labelled civil preparedness screens."""
import datetime as dt
import textwrap
import json
from pathlib import Path
import math
from cyber_graphics import draw_orb
from status_summary import summary
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
    def __init__(self, ui, feeds, location=None):
        self.u = ui
        self.feeds = feeds
        self.links = []
        self.active_url = LINKS['prepare']
        self.doomsday = load_doomsday_setting()
        self.map = None
        if hasattr(ui, 'blit'):
            from uk_map import UKMap
            self.map = UKMap(location)

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
        u.panel(28,105,507,551,'UK / SITUATION MAP','')
        u.text('UK THREAT / '+summary('threat',data,now,errors),28,72,18,u.AMBER)
        u.text('WEATHER / '+summary('weather',data,now,errors),410,72,17,u.TEAL)
        u.text('FLOODS / '+summary('floods',data,now,errors),780,72,17,u.TEAL)
        setting=self.doomsday
        u.text('DOOMSDAY / '+(str(setting['seconds_to_midnight'])+'s' if setting else '--'),1080,72,17,u.AMBER)
        if self.map:
            u.blit(self.map.draw(age),42,153)
        self.stream(age if stream_age is None else stream_age,data,errors,now)
        u.panel(550,105,280,230,'NATIONAL ASSESSMENT','')
        sample=data.get('threat')
        level=sample['level'].upper() if sample else 'UNAVAILABLE'
        u.text(level,563,160,44,u.AMBER)
        meanings={'LOW':'Attack highly unlikely','MODERATE':'Attack possible, not likely',
                  'SUBSTANTIAL':'An attack is likely','SEVERE':'An attack is highly likely',
                  'CRITICAL':'Attack highly likely in the near future'}
        self.paragraphs(meanings.get(level,'Awaiting official source'),563,213,28,17,2,u.DIM)
        for i,name in enumerate(LEVELS):
            selected=name==level.lower()
            u.line((565+i*50,257),(605+i*50,257),u.AMBER if selected else u.DIM,4 if selected else 1)
            if selected:u.text('>> '+name.upper(),565,270,15,u.AMBER)
        state=source_status('threat',data,errors,now)
        self.paragraphs(state,563,293,32,13,2,u.DIM)
        u.text('GOV.UK / JTAC & MI5',563,318,12,u.TEAL)
        self.links.append(((550,105,280,230),LINKS['threat']))
        self.active_url=LINKS['threat']
        u.panel(550,349,280,307,NAMES[index].upper()[:24],'')
        if index==0:
            u.text('MET OFFICE',565,402,20,u.TEAL)
            self.paragraphs(getattr(self.feeds,'weather_scope','UK'),565,432,28,16,2,u.DIM)
            rows=data.get('weather',{}).get('items',[])
            item=rows[int(age/12)%len(rows)] if rows else None
            self.paragraphs(item['title'] if item else ('No bulletins returned / check source' if 'weather' in data else 'Weather source unavailable'),565,480,24,19,5)
            self.paragraphs(source_status('weather',data,errors,now),565,610,30,13,2,u.DIM)
            self.links.append(((550,390,280,260),item['url'] if item else LINKS['weather']))
        elif index==1:
            name='ncsc' if int(age/16)%2==0 else 'news'
            u.text('NCSC / PUBLICATION' if name=='ncsc' else 'BBC / MEDIA REPORT',565,402,18,u.TEAL)
            rows=data.get(name,{}).get('items',[])
            item=rows[int(now/60)%len(rows)] if rows else None
            self.paragraphs(item['title'] if item else 'Source unavailable / no stories',565,446,24,19,6)
            self.paragraphs('Reports do not change the UK threat assessment.',565,602,30,14,3,u.DIM)
            self.active_url=item['url'] if item else LINKS[name]
            self.links.append(((550,390,280,260),self.active_url))
        elif index==2:
            sample=data.get('floods')
            rows=sample.get('items',[]) if sample else []
            u.text(str(len(rows)) if sample else '--',565,396,70,u.AMBER)
            u.text('FLOOD ALERTS / WARNINGS',565,470,17,u.TEAL)
            item=rows[int(age/12)%len(rows)] if rows else None
            self.paragraphs(item['title'] if item else 'No items returned is not an all-clear.',565,504,26,18,4)
            self.paragraphs(getattr(self.feeds,'flood_scope','ENGLAND'),565,607,32,13,2,u.DIM)
            self.active_url=item['url'] if item else LINKS['floods']
            self.links.append(((550,390,280,260),self.active_url))
        else:
            u.text(str(setting['seconds_to_midnight']) if setting else '--',565,395,72,u.AMBER)
            u.text('SECONDS TO MIDNIGHT',565,477,20,u.TEXT)
            self.paragraphs('Published symbolic global risk assessment. Bulletin of the Atomic Scientists.',565,519,28,16,5)
            u.text(setting['announced'] if setting else 'UNAVAILABLE',565,618,16,u.DIM)
            self.active_url=setting['url'] if setting else 'https://thebulletin.org/doomsday-clock/'
            self.links.append(((550,390,280,260),self.active_url))
