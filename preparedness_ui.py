"""UK-first, source-labelled civil preparedness screens."""
import datetime as dt
import textwrap
import json
from pathlib import Path
import math
from cyber_graphics import draw_orb
from status_summary import summary
from alert_state import AlertState
from preparedness import display_items, article_date, LINKS, MAX_AGES, LEVELS, source_status

NAMES = ('UK situation console', 'Incident & cyber watch', 'UK situation map', 'Minutes to midnight')
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
        self.alerts = AlertState()
        self.links = []
        self.active_url = LINKS['prepare']
        self.doomsday = load_doomsday_setting()
        self.visuals = None
        self.map = None
        self.globe = None
        self.local_weather = None
        self.weather_failed = False
        if hasattr(ui, 'blit'):
            from animated_visuals import Visuals
            self.visuals = Visuals()
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
        u.panel(840,105,412,551,'PUBLIC SOURCE BRIEFING','')
        rows = []
        for name, label in [('weather', 'MET OFFICE'), ('floods', 'ENV. AGENCY'),
                            ('ncsc', 'NCSC / PUBLICATION'), ('news', 'CISA / EXPLOITED CVEs / GLOBAL')]:
            sample = data.get(name, {})
            items = display_items(name, sample, now)[:6]
            state = source_status(name, data, errors, now)
            rows.append((label, u.TEAL, LINKS.get(name, LINKS['prepare'])))
            rows.append((state, u.DIM, None))
            if not items:
                rows.append(('No NCSC articles published today' if name == 'ncsc' and sample else 'No items returned' if sample else 'Waiting for source...', u.DIM, None))
            for item in items:
                rows.append((label, u.TEAL, item.get('url')))
                published = item.get('published')
                if published:
                    stamp = article_date(item) if name == 'ncsc' else dt.datetime.fromtimestamp(published, dt.timezone.utc).strftime('%d %b %H:%M UTC')
                    rows.append((('ADDED TO KEV '+item['added']) if name=='news' else stamp, u.DIM, None))
                for row in textwrap.wrap(item['title'], 38):
                    rows.append((row, u.TEXT, item.get('url')))
                rows.append(('', u.DIM, None))
        rows.append(('PREPARE / HOUSEHOLD GUIDANCE', u.TEAL, LINKS['prepare']))
        for tip in PREPARE_TIPS:
            rows.extend((row, u.TEXT, LINKS['prepare']) for row in textwrap.wrap(tip, 38))
            rows.append(('', u.DIM, None))
        rows = [row for row in rows if row[0]]
        self.stream_length = len(rows)
        # Show complete lines; each remains visible for roughly a minute.
        progress = max(0., age)/4.0
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
            y = 154+n*25
            u.text(value,854,y,18,colour)
            if url:
                self.links.append(((850, y, 396, 24), url))
        u.line((854,613),(1238,613),u.DIM)
        u.text('HISTORY' if offset else 'AUTO REPLAY / 4 SECONDS PER LINE',854,624,15,u.TEAL)
        u.text('SPACE PAUSE / PGUP / PGDN / END',854,645,12,u.DIM)

    def briefing_cards(self, age, data, errors, now):
        u=self.u
        rows=data.get('weather',{}).get('items',[])
        rank={'red':3,'amber':2,'yellow':1}
        item=max(rows,key=lambda row:rank.get(row.get('colour'),0),default=None)
        u.panel(324,105,500,160,'WEATHER WARNING / MET OFFICE','')
        self.paragraphs(item['title'] if item else ('No weather bulletins returned' if 'weather' in data else 'Weather source unavailable'),340,154,33,19,3,u.AMBER)
        if self.visuals:
            u.blit(self.visuals.frame('wind' if item and 'wind' in item['title'].lower() else 'weather',age),702,151)
        u.text('VISUAL FX',718,239,11,u.DIM)
        issued=dt.datetime.fromtimestamp(item['published'],dt.timezone.utc).strftime('%d %b %H:%M UTC') if item and item.get('published') else 'NOT PROVIDED'
        u.text('ISSUED '+issued+' / CHECK VALIDITY AT SOURCE',340,215,12,u.DIM)
        u.text(source_status('weather',data,errors,now),340,242,13,u.DIM)
        self.links.append(((324,145,500,120),item['url'] if item else LINKS['weather']))
        u.panel(324,277,500,125,'LOCAL FLOOD DETAILS / ENVIRONMENT AGENCY','')
        sample=data.get('floods')
        items=sample.get('items',[]) if sample else []
        flood=items[int(age/20)%len(items)] if items else None
        title=(flood['label']+' / '+flood['title']) if flood else ('No alerts returned / not an all-clear' if sample else 'Flood source unavailable')
        self.paragraphs(title,340,325,36,18,2)
        if self.visuals:
            u.blit(self.visuals.frame('water',age),702,315)
        u.text('VISUAL FX',718,385,10,u.DIM)
        u.text(source_status('floods',data,errors,now),340,382,12,u.DIM)
        self.links.append(((324,317,500,85),flood['url'] if flood else LINKS['floods']))
        name='ncsc' if int(age/20)%2==0 else 'news'
        if name=='ncsc' and not display_items('ncsc',data.get('ncsc'),now):
            name='news'
        label='NCSC / OFFICIAL PUBLICATION' if name=='ncsc' else 'CISA / EXPLOITED CVEs / GLOBAL'
        items=display_items(name,data.get(name),now)
        item=items[int(age/40)%len(items)] if items else None
        u.panel(324,414,500,138,label,'')
        self.paragraphs(item['title'] if item else ('No NCSC articles published today' if name=='ncsc' and name in data else 'No matching publications' if name in data else 'Source unavailable'),340,460,33,19,3)
        if self.visuals:
            u.blit(self.visuals.frame('orb',age),702,457)
        u.text('VISUAL FX',718,539,10,u.DIM)
        published=dt.datetime.fromtimestamp(item['published'],dt.timezone.utc).strftime('%d %b %Y %H:%M UTC') if item and item.get('published') else 'DATE NOT PROVIDED'
        if name=='news' and item:
            published='ADDED TO KEV '+item['added']
        stale=not data.get(name) or name in errors or now-data[name]['fetched']>MAX_AGES[name]
        u.text(published+(' / STALE' if stale else ''),340,530,13,u.DIM)
        self.active_url=item['url'] if item else LINKS[name]
        self.links.append(((324,454,500,98),self.active_url))

    def draw(self, index, age, data, errors, now, stream_age=None):
        u = self.u
        self.links = []
        self.active_url = LINKS['prepare']
        u.text('UK THREAT / '+summary('threat',data,now,errors),28,72,18,u.AMBER)
        u.text('WEATHER / '+summary('weather',data,now,errors),410,72,17,u.TEAL)
        u.text('FLOODS / '+summary('floods',data,now,errors),780,72,17,u.TEAL)
        setting=self.doomsday
        u.text('DOOMSDAY / '+(str(setting['seconds_to_midnight'])+'s' if setting else '--'),1080,72,17,u.AMBER)
        warnings = [row for row in self.alerts.update(data,errors,now)
                    if row['source'] in ('weather','floods')]
        stale = sum(row['stale'] for row in warnings)
        upcoming = sum(not row['stale'] and row['detail'].startswith('UPCOMING') for row in warnings)
        current = sum(not row['stale'] and (row['source']=='floods' or row['detail'].startswith('IN FORCE')) for row in warnings)
        unknown = len(warnings)-stale-upcoming-current
        unavailable = sum(name not in data or name in errors or now-data[name]['fetched']>MAX_AGES[name]
                          for name in ('weather','floods'))
        u.panel(28,105,280,167,'WARNING OVERVIEW','')
        u.text(str(len(warnings)) if warnings or not unavailable else '--',44,145,60,u.AMBER if warnings else u.TEXT)
        u.text('LISTED',151,160,23,u.AMBER if warnings else u.DIM)
        u.text('WEATHER + FLOOD',151,190,13,u.DIM)
        counts = 'VALIDITY AWAITING FRESH DATA' if unavailable else f'IN FORCE {current} / UPCOMING {upcoming}'
        u.text(counts,44,218,15,u.DIM if unavailable else u.TEAL)
        note = f'STALE {stale} / VALIDITY UNKNOWN {unknown}'
        if unavailable:
            note = f'{unavailable}/2 SOURCES STALE OR UNAVAILABLE'
        elif not warnings:
            note = 'NONE LISTED / NOT AN ALL-CLEAR'
        u.text(note,44,247,12,u.AMBER if unavailable or unknown else u.DIM)
        u.panel(28,286,280,266,'UK THREAT / GOV.UK','')
        sample=data.get('threat')
        level=sample['level'].upper() if sample else 'UNAVAILABLE'
        u.text(level,42,338,44,getattr(u,'LIME',u.TEAL))
        meanings={'LOW':'Attack highly unlikely','MODERATE':'Attack possible, not likely',
                  'SUBSTANTIAL':'An attack is likely','SEVERE':'An attack is highly likely',
                  'CRITICAL':'Attack highly likely in the near future'}
        self.paragraphs(meanings.get(level,'Awaiting official source'),44,395,27,18,2,u.DIM)
        for i,name in enumerate(LEVELS):
            selected=name==level.lower()
            u.line((44+i*50,459),(84+i*50,459),getattr(u,'LIME',u.TEAL) if selected else u.DIM,4 if selected else 1)
            if selected:u.text('>> '+name.upper(),44,475,15,getattr(u,'LIME',u.TEAL))
        self.paragraphs(source_status('threat',data,errors,now),44,509,30,14,2,u.DIM)
        self.links.append(((28,286,280,266),LINKS['threat']))
        self.active_url=LINKS['threat']
        if index==2:
            u.panel(324,105,500,447,'UK / SITUATION MAP','')
            if self.map:
                import pygame
                u.blit(pygame.transform.smoothscale(self.map.draw(age),(350,350)),399,150)
            u.text('CONFIGURED AREA / GEOGRAPHIC CONTEXT',340,510,17,u.DIM)
        else:
            self.briefing_cards(age,data,errors,now)
        u.panel(324,565,244,91,'WEATHER / MET OFFICE','')
        weather=self.local_weather
        stale=weather and (self.weather_failed or now-weather['fetched']>1800)
        temp=f"{weather['temp']:.0f} C" if weather else '-- C'
        u.text(temp,340,605,28,u.TEXT)
        self.paragraphs(summary('weather',data,now,errors),417,607,19,14,2,u.AMBER)
        u.text('OPEN-METEO'+(' / STALE' if stale else ''),340,639,10,u.DIM)
        self.links.append(((324,565,244,91),LINKS['weather']))
        u.panel(580,565,244,91,'LOCAL FLOODS / EA','')
        u.text(summary('floods',data,now,errors),596,606,20,u.AMBER)
        self.paragraphs(getattr(self.feeds,'flood_scope','ENGLAND'),596,634,33,11,1,u.DIM)
        self.links.append(((580,565,244,91),LINKS['floods']))
        u.panel(28,565,280,91,'DOOMSDAY / BULLETIN','')
        u.text(str(setting['seconds_to_midnight']) if setting else '--',44,601,36,getattr(u,'LIME',u.TEAL))
        u.text('SECONDS TO MIDNIGHT',112,607,16,u.TEXT)
        u.text(setting['announced'] if setting else 'UNAVAILABLE',112,631,13,u.DIM)
        self.links.append(((28,565,280,91),setting['url'] if setting else 'https://thebulletin.org/doomsday-clock/'))
        if index==3:self.active_url=setting['url'] if setting else 'https://thebulletin.org/doomsday-clock/'
        self.stream(age if stream_age is None else stream_age,data,errors,now)

    def alert_rail(self, age, data, errors, now):
        alerts = self.alerts.update(data, errors, now)
        if not alerts:
            return False
        u = self.u
        item = alerts[int(age/8) % len(alerts)]
        colour = u.RED if item['rank'] >= 5 else u.AMBER
        # Only the border pulses; the words never blink off.
        pulse = colour if int(age) % 2 else u.DIM
        u.line((28,663),(1252,663),pulse,3)
        u.line((28,718),(1252,718),pulse,3)
        prefix = 'LAST KNOWN / STALE' if item['stale'] else ('NEW WARNING' if item['new'] else 'WARNING WATCH')
        u.text(f"! {prefix} / {len(alerts)} LISTED",40,668,19,colour)
        u.text(textwrap.shorten(item['title'],width=83,placeholder='...'),450,668,19,u.TEXT)
        u.text(item['source'].upper()+' / '+item['detail'],40,696,14,colour)
        u.text('O OPEN WARNING / '+str(int(age/8)%len(alerts)+1)+' OF '+str(len(alerts)),1236,696,14,u.DIM,True)
        self.active_url = item['url']
        self.links.append(((28,663,1224,57),item['url']))
        return True
