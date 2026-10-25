"""UK-first, source-labelled civil preparedness screens."""
import datetime as dt
import textwrap
from zoneinfo import ZoneInfo
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


def midnight_remaining(now):
    tomorrow = now.date()+dt.timedelta(days=1)
    midnight = dt.datetime.combine(tomorrow, dt.time(), tzinfo=now.tzinfo)
    seconds = max(0, int(midnight.timestamp()-now.timestamp()))
    return f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'


class PreparednessDesktop:
    def __init__(self, ui, feeds):
        self.u = ui
        self.feeds = feeds
        self.links = []
        self.active_url = LINKS['prepare']

    def wrap(self, value, y, size=26, width=82, lines=3, color=None):
        rows = textwrap.wrap(str(value), width)
        if len(rows) > lines:
            rows = rows[:lines]
            rows[-1] = rows[-1].rstrip(' .')+'...'
        for i, row in enumerate(rows):
            self.u.text(row, 48, y+i*(size+9), size, color or self.u.TEXT)

    def source(self, label, url, y=588, primary=True):
        self.u.text(label+' / OPEN SOURCE >', 48, y, 19, self.u.TEAL)
        self.links.append(((42, y-4, 1190, 30), url))
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

    def draw(self, index, age, data, errors, now):
        u = self.u
        self.links = []
        self.active_url = LINKS['prepare']
        u.panel(28, 105, 1224, 551, f'0{index+1} / '+NAMES[index].upper(), 'INDEPENDENT / PUBLIC SOURCES')
        # Animation belongs to the terminal chrome, never to the assessment.
        for i in range(18):
            height=3+int(7*(1+math.sin(age*1.6+i*.65)))
            u.line((775+i*8,94),(775+i*8,94-height),u.TEAL)
        u.text('DISPLAY SYNC',930,80,14,u.DIM)
        if index == 0:
            sample = data.get('threat')
            stale = sample and ('threat' in errors or now-sample['fetched'] > MAX_AGES['threat'])
            level = sample['level'].upper() if sample else 'UNAVAILABLE'
            position = LEVELS.index(level.lower())+1 if level.lower() in LEVELS else None
            colour = u.AMBER if sample else u.DIM
            u.text('UK TERRORISM THREAT / '+('LAST KNOWN ASSESSMENT' if stale else 'NATIONAL ASSESSMENT'), 48, 162, 23, u.DIM)
            # A stable hero word, almost three times the former size.
            u.text(level, 64, 210, 112, colour)
            meanings = {
                'LOW': 'AN ATTACK IS HIGHLY UNLIKELY',
                'MODERATE': 'AN ATTACK IS POSSIBLE BUT NOT LIKELY',
                'SUBSTANTIAL': 'AN ATTACK IS LIKELY',
                'SEVERE': 'AN ATTACK IS HIGHLY LIKELY',
                'CRITICAL': 'AN ATTACK IS HIGHLY LIKELY IN THE NEAR FUTURE',
            }
            u.text(meanings.get(level, 'AWAITING AN OFFICIAL ASSESSMENT'), 64, 328, 23, colour)
            # Brackets unfold on entry. The selected level never cycles or flashes.
            extent = min(1., max(0., age)/1.2)
            trace = 64+int((age % 8)/8*710)
            u.line((trace,194),(trace+48,194),colour,2)
            for x, direction in ((48, 1), (850, -1)):
                for y, dy in ((200, 1), (320, -1)):
                    u.line((x,y),(x+direction*28*extent,y),colour,2)
                    u.line((x,y),(x,y+dy*24*extent),colour,2)
            draw_orb(u, 1060, 296, 104, age)
            u.text('TOPOLOGY / VISUAL FX', 945, 451, 16, u.DIM)
            for i, name in enumerate(LEVELS, 1):
                x = 48+(i-1)*163
                selected = i == position
                u.text(('>> ' if selected else '   ')+name.upper(), x, 375, 18, colour if selected else u.DIM)
                u.line((x,405),(x+140,405),colour if selected else u.DIM,4 if selected else 1)
            self.status('threat', data, errors, now, 431)
            self.source('GOV.UK / JTAC & MI5', LINKS['threat'], 456)
            u.line((48,490),(1230,490))
            u.text('MET OFFICE / '+self.feeds.weather_scope.upper(),48,506,18,u.DIM)
            weather = data.get('weather')
            rows = weather.get('items', []) if weather else []
            weather_url = LINKS['weather']
            if rows:
                row = rows[int(now/12) % len(rows)]
                self.wrap(row['title'], 535, size=22, width=100, lines=2,
                          color=u.RED if row['colour']=='red' else u.AMBER)
                weather_url = row['url']
            else:
                self.wrap('No warning bulletins returned' if weather else 'Weather warnings unavailable',535,size=22,lines=2)
            self.source('WEATHER / CHECK AREA & VALIDITY',weather_url,598,primary=False)
            self.status('weather',data,errors,now)
        elif index == 1:
            name = 'ncsc' if int(age/12) % 2 == 0 else 'news'
            label = 'NCSC / OFFICIAL PUBLICATION' if name == 'ncsc' else 'BBC NEWS / MEDIA REPORT'
            u.text(label, 48, 164, 25, u.DIM)
            rows = data.get(name, {}).get('items', [])
            if rows:
                row = rows[int(now/24) % len(rows)]
                self.wrap(row['title'], 222, size=32, width=66, lines=4)
                if row.get('published'):
                    published = dt.datetime.fromtimestamp(row['published'], dt.timezone.utc).strftime('%d %b %Y %H:%M UTC')
                    u.text('PUBLISHED '+published, 48, 405, 21, u.DIM)
                self.active_url = row['url']
            else:
                self.wrap('No matching stories in this feed' if name in data else 'Source unavailable / retrying in background', 240, size=30)
                self.active_url = LINKS[name]
            self.wrap('Publication is not proof of an ongoing attack or a change to the national threat level.', 475, size=22, width=94, lines=2, color=u.DIM)
            self.source(label, self.active_url)
            self.status(name, data, errors, now)
        elif index == 2:
            u.text('ENVIRONMENT AGENCY / '+self.feeds.flood_scope.upper(), 48, 159, 22, u.DIM)
            sample = data.get('floods')
            rows = sample.get('items', []) if sample else []
            if rows:
                row = rows[int(now/12) % len(rows)]
                u.text(f'{len(rows)} ALERTS / WARNINGS RETURNED', 48, 201, 34, u.AMBER)
                u.text(row['label'].upper(), 48, 260, 28, u.RED if row['severity'] == 1 else u.AMBER)
                self.wrap(row['title'], 304, lines=2)
                u.text('SOURCE UPDATE '+row['updated'], 48, 390, 20, u.DIM)
                self.active_url = row['url']
            else:
                message = 'No alerts returned by this feed' if sample else 'Local flood status unavailable'
                self.wrap(message, 211, size=32, lines=2)
                self.wrap('Flood coverage is England only. An empty feed is not an all-clear.', 320, size=23, width=91, lines=2, color=u.DIM)
                self.active_url = 'https://www.gov.uk/check-flooding'
            u.line((48, 442), (1230, 442))
            self.wrap(PREPARE_TIPS[int(now/30) % len(PREPARE_TIPS)], 465, size=24, width=88, lines=2)
            self.source('PREPARE / HOUSEHOLD GUIDANCE', LINKS['prepare'], 545, primary=False)
            self.source('FLOOD DETAILS', self.active_url, 583)
            if 'floods' in self.feeds.urls:
                self.status('floods', data, errors, now)
            else:
                u.text('USE YOUR NATIONAL FLOOD WARNING SERVICE', 48, 624, 18, u.AMBER)
        else:
            local = dt.datetime.fromtimestamp(now, ZoneInfo('Europe/London'))
            u.text('TIME UNTIL LOCAL MIDNIGHT', 48, 162, 24, u.DIM)
            u.text(midnight_remaining(local), 48, 206, 132, u.TEXT)
            draw_orb(u, 1070, 283, 100, age)
            u.text('VISUAL FX', 1020, 437, 16, u.DIM)
            u.text('EUROPE/LONDON / '+local.strftime('%A %d %B %Y').upper(), 48, 365, 24, u.DIM)
            u.text('A CLOCK. NOT A THREAT SCORE OR A DISASTER FORECAST.', 48, 421, 23, u.AMBER)
            self.wrap('Be informed. Make a household plan. Keep useful supplies accessible. Follow official advice for your area.', 480, size=24, width=88, lines=2)
            self.source('PREPARE / UK GOVERNMENT CAMPAIGN', LINKS['prepare'])
            u.text('INDEPENDENT DISPLAY / NOT A GOVERNMENT EMERGENCY ALERT SERVICE', 48, 624, 18, u.DIM)
