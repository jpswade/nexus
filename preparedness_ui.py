"""UK-first, source-labelled civil preparedness screens."""
import datetime as dt
import textwrap
from zoneinfo import ZoneInfo
from preparedness import LINKS, MAX_AGES, source_status

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
        if index == 0:
            sample = data.get('threat')
            stale = sample and ('threat' in errors or now-sample['fetched'] > MAX_AGES['threat'])
            u.text('UK TERRORISM ASSESSMENT / '+('LAST KNOWN' if stale else 'NATIONAL'), 48, 157, 21, u.DIM)
            u.text(sample['level'] if sample else 'UNAVAILABLE', 48, 190, 44, u.AMBER if sample else u.DIM)
            self.status('threat', data, errors, now, 248)
            self.source('GOV.UK / JTAC & MI5', LINKS['threat'], 278, primary=False)
            u.line((48, 321), (1230, 321))
            u.text('MET OFFICE / '+self.feeds.weather_scope.upper(), 48, 344, 22, u.DIM)
            weather = data.get('weather')
            rows = weather.get('items', []) if weather else []
            if rows:
                row = rows[int(now/12) % len(rows)]
                colour = u.RED if row['colour'] == 'red' else u.AMBER
                self.wrap(row['title'], 387, color=colour, lines=3)
                self.active_url = row['url']
                if row.get('published'):
                    stamp = dt.datetime.fromtimestamp(row['published'], dt.timezone.utc).strftime('%d %b %H:%M UTC')
                    u.text('BULLETIN '+stamp, 48, 506, 18, u.DIM)
            else:
                self.wrap('No warning bulletins returned' if weather else 'Warning feed unavailable / awaiting verification', 388)
                self.active_url = LINKS['weather']
            u.text('Regional bulletins; check the source for locations and validity times.', 48, 538, 20, u.DIM)
            self.source('MET OFFICE / WARNING DETAILS', self.active_url)
            self.status('weather', data, errors, now)
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
            u.text('EUROPE/LONDON / '+local.strftime('%A %d %B %Y').upper(), 48, 365, 24, u.DIM)
            u.text('A CLOCK. NOT A THREAT SCORE OR A DISASTER FORECAST.', 48, 421, 23, u.AMBER)
            self.wrap('Be informed. Make a household plan. Keep useful supplies accessible. Follow official advice for your area.', 480, size=24, width=88, lines=2)
            self.source('PREPARE / UK GOVERNMENT CAMPAIGN', LINKS['prepare'])
            u.text('INDEPENDENT DISPLAY / NOT A GOVERNMENT EMERGENCY ALERT SERVICE', 48, 624, 18, u.DIM)
