"""Bounded official space-weather checks. No local outage or threat inference."""
import datetime as dt
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import urllib.request

UTC = dt.timezone.utc
URLS = {
    'scales': 'https://services.swpc.noaa.gov/products/noaa-scales.json',
    'alerts': 'https://services.swpc.noaa.gov/products/alerts.json',
    'met': 'https://weather.metoffice.gov.uk/specialist-forecasts/space-weather',
}
LINKS = dict(URLS, scales='https://www.swpc.noaa.gov/noaa-scales-explanation',
             alerts='https://www.swpc.noaa.gov/products/alerts-watches-and-warnings')
INTERVALS = {'scales': 300, 'alerts': 300, 'met': 3600}
MAX_AGES = {'scales': 900, 'alerts': 900, 'met': 6*3600}
LIMIT = 1024*1024


def stamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    return result.replace(tzinfo=result.tzinfo or UTC).timestamp()


def utc(value):
    return dt.datetime.fromtimestamp(value, UTC).strftime('%d %b %H:%MZ') if value is not None else 'unknown'


def level(value):
    if value is None:
        return None
    if str(value) not in ('0', '1', '2', '3', '4', '5'):
        raise ValueError('Invalid scale')
    return int(value)


def parse_scales(raw):
    if not isinstance(raw, dict):
        raise ValueError("Invalid scales object")
    rows = []
    for key, kind in [('0', 'observation'), ('1', 'forecast'), ('2', 'forecast'), ('3', 'forecast')]:
        row = raw.get(key)
        if row is None:
            continue
        if not isinstance(row, dict) or any(not isinstance(row.get(axis, {}), dict) for axis in 'GRS'):
            raise ValueError('Invalid scale row')
        issued = stamp(row['DateStamp']+'T'+row['TimeStamp'])
        values = {axis: level(row.get(axis, {}).get('Scale')) for axis in 'GRS'}
        probs = {}
        for axis, fields in [('R', ('MinorProb', 'MajorProb')), ('S', ('Prob',))]:
            for field in fields:
                value = row.get(axis, {}).get(field)
                if value is not None:
                    value = int(value)
                    if not 0 <= value <= 100:
                        raise ValueError('Invalid probability')
                probs[axis+field] = value
        # Forecast date is the UTC day, not a fresh observation timestamp.
        start = stamp(row['DateStamp']+'T00:00:00Z') if kind == 'forecast' else issued
        rows.append(dict(kind=kind, issued=issued, start=start,
                         end=start+86400 if kind == 'forecast' else None,
                         levels=values, probabilities=probs))
    if not rows or not any(r['kind'] == 'observation' for r in rows):
        raise ValueError('Missing latest-observed scales')
    return {'rows': rows}


def field(message, name):
    match = re.search(r'^'+name+r':\s*([^\r\n]+)', message, re.M | re.I)
    return match.group(1).strip() if match else None


def message_time(message, name):
    value = field(message, name)
    if value is None:
        return None
    return dt.datetime.strptime(value, '%Y %b %d %H%M UTC').replace(tzinfo=UTC).timestamp()


def parse_alerts(raw):
    if not isinstance(raw, list) or len(raw) > 2000:
        raise ValueError('Invalid alert list')
    rows = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get('message'), str):
            raise ValueError('Invalid bulletin')
        message = item['message']
        issued = stamp(item['issue_datetime'])
        code = field(message, 'Space Weather Message Code')
        serial = field(message, 'Serial Number')
        if not code or not serial:
            raise ValueError('Missing bulletin identity')
        title = re.search(r'^(?:(?:EXTENDED|CONTINUED|CANCEL(?:LED)?)\s+)?(?:WARNING|WATCH|ALERT|SUMMARY|TEST):?[^\r\n]*', message, re.M | re.I)
        title = title.group(0) if title else 'Unrecognised bulletin'
        test = bool(re.search(r'\bTEST\b', message, re.I))
        cancelled = bool(re.match(r'CANCEL', title, re.I))
        kind = ('test' if test else 'cancellation' if cancelled else
                'warning' if 'WARNING' in title.upper() else 'watch' if 'WATCH' in title.upper() else
                'observation' if re.search(r'ALERT|SUMMARY', title, re.I) else 'unknown')
        start = message_time(message, 'Valid From')
        end = message_time(message, '(?:Now Valid Until|Valid To|Valid Until|End Time)')
        days = []
        if kind == 'watch':
            # Watch day tables omit the year; select the closest date to issuance,
            # including Dec/Jan rollover. A watch is a forecast, not an observation.
            year = dt.datetime.fromtimestamp(issued, UTC).year
            for month, day in re.findall(r'\b([A-Z][a-z]{2})\s+(\d{2})\s*:', message):
                candidates = []
                for y in (year-1, year, year+1):
                    try:
                        candidates.append(dt.datetime.strptime(f'{y} {month} {day}', '%Y %b %d').replace(tzinfo=UTC).timestamp())
                    except ValueError:
                        pass
                if candidates:
                    days.append(min(candidates, key=lambda value: abs(value-issued)))
            if days:
                start, end = min(days), max(days)+86400
        scales = {axis: None for axis in 'GRS'}
        # Only explicit scale fields, never mentions in boilerplate/impact text.
        for axis, value in re.findall(r'NOAA Scale:\s*([GRS])([1-5])\b', message, re.I):
            scales[axis.upper()] = int(value)
        rows.append(dict(code=code, serial=serial, issued=issued, kind=kind,
                         title=title[:240], start=start, end=end, levels=scales,
                         geography=field(message, 'Potential Impacts') or 'Geography unspecified; global bulletin',
                         cancel=field(message, 'Cancel Serial Number'),
                         extends=field(message, 'Extension to Serial Number'),
                         supersedes='THIS SUPERSEDES ANY/ALL PRIOR WATCHES' in message.upper()))
    return {'rows': rows}


def alert_states(rows, now):
    """Resolve explicit relationships and time windows, never feed position."""
    result = [dict(row) for row in rows]
    cancellations = {(r['code'], r['cancel']) for r in rows
                     if r['kind'] == 'cancellation' and r['issued'] <= now and r['cancel']}
    extensions = {(r['code'], r['extends']) for r in rows
                  if r['kind'] == 'warning' and r['issued'] <= now and r['extends']}
    watches = [r['issued'] for r in rows if r['kind'] == 'watch' and r['supersedes'] and r['issued'] <= now]
    for row in result:
        identity = (row['code'], row['serial'])
        kind = row['kind']
        if kind in ('test', 'cancellation'):
            state = 'test' if kind == 'test' else 'upcoming cancellation' if row['issued'] > now else 'cancelled'
        elif identity in cancellations:
            state = 'cancelled'
        elif identity in extensions or (kind == 'watch' and watches and row['issued'] < max(watches)):
            state = 'superseded'
        elif kind == 'observation':
            state = 'historical observation'
        elif kind not in ('watch', 'warning') or row['start'] is None or row['end'] is None or row['end'] <= row['start']:
            state = 'validity unknown'
        elif now >= row['end']:
            state = 'expired'
        elif now < max(row['start'], row['issued']):
            state = 'upcoming'
        else:
            state = 'active'
        row['state'] = state
    return sorted(result, key=lambda r: (r['state'] == 'active', r['issued']), reverse=True)


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def plain(html):
    parser = Text()
    parser.feed(html)
    return ' '.join(' '.join(parser.parts).split())


def parse_met(raw):
    if not isinstance(raw, str):
        raise ValueError('Invalid Met Office document')
    # Deliberately scoped to the forecast overview. Image/aurora timestamps and
    # navigation text must not make an old forecast appear newly issued.
    block = re.search(r'<div class="overview-content">(.*?)</div>\s*</div>\s*<p class="issued-at-time">(.*?)</p>', raw, re.S)
    if not block:
        raise ValueError('Met Office overview schema changed')
    headline = re.search(r'<h3>Space Weather Forecast Headline:\s*(.*?)</h3>', block[1], re.S)
    issued = re.search(r'Issued at:\s*(\d\d:\d\d) \((GMT|BST|UTC)\) on \w+ (\d{1,2} \w+ \d{4})', plain(block[2]))
    if not headline or not issued or 'Four-Day Space Weather Forecast Summary' not in plain(block[1]):
        raise ValueError('Missing forecast headline, issuance or period')
    zone = dt.timezone(dt.timedelta(hours=1 if issued[2] == 'BST' else 0))
    when = dt.datetime.strptime(issued[3]+' '+issued[1], '%d %b %Y %H:%M').replace(tzinfo=zone).timestamp()
    return {'headline': plain(headline[1]), 'issued': when, 'end': when+4*86400,
            'geography': 'UK context / global space weather', 'kind': 'forecast',
            'period': 'Four-day outlook; see source for daily detail'}


PARSERS = {'scales': parse_scales, 'alerts': parse_alerts, 'met': parse_met}


def fetch(name):
    request = urllib.request.Request(URLS[name], headers={'User-Agent': 'NEXUS-space-weather/1.0', 'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError('Unexpected response status')
        payload = response.read(LIMIT+1)
    if len(payload) > LIMIT:
        raise ValueError('Response too large')
    text = payload.decode('utf-8')
    return text if name == 'met' else json.loads(text)


class SpaceWeather:
    """One low-rate worker; atomic disk cache and process lock share LCD/desktop checks."""
    def __init__(self, directory=None, fetcher=fetch, clock=time.time):
        self.directory = Path(directory) if directory is not None else Path(os.environ.get('NEXUS_CACHE', Path(__file__).resolve().parent/'.cache'))/'space-weather'
        self.fetcher, self.clock = fetcher, clock
        self.data = {}
        self.lock = threading.Lock()
        self.started = False
        self._load()

    def _load(self):
        for name in URLS:
            try:
                path = self.directory/(name+'.json')
                if path.stat().st_size > LIMIT*2:
                    continue
                row = json.loads(path.read_text())
                if not isinstance(row, dict) or any(not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key]) for key in ('checked',)):
                    continue
                if 'raw' in row and (not isinstance(row.get('fetched'), (int, float)) or not math.isfinite(row['fetched'])):
                    continue
                if 'raw' in row:
                    PARSERS[name](row['raw'])
                self.data[name] = row
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue

    def refresh(self):
        # flock is available on the target Pi and macOS. Lock covers check/fetch/
        # rename so two displays never duplicate a due request.
        import fcntl
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory/'refresh.lock').open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            with self.lock:
                self._load()
            for name in URLS:
                now = self.clock()
                old = self.data.get(name, {})
                if 0 <= now-old.get('checked', float('-inf')) < INTERVALS[name]:
                    continue
                row = dict(old, checked=now)
                try:
                    raw = self.fetcher(name)
                    PARSERS[name](raw)
                    row = dict(raw=raw, fetched=now, checked=now, failed=False)
                except Exception:
                    # Never erase last known good data; errors contain no URL,
                    # request headers or credentials and survive process restart.
                    row['failed'] = True
                with self.lock:
                    self.data[name] = row
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(mode='w', dir=self.directory, delete=False) as output:
                        temp = output.name
                        json.dump(row, output)
                    os.replace(temp, self.directory/(name+'.json'))
                finally:
                    if temp and os.path.exists(temp):
                        os.unlink(temp)

    def snapshot(self, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            cached = dict(self.data)
        result = {}
        for name in URLS:
            row = cached.get(name, {})
            content = PARSERS[name](row['raw']) if 'raw' in row else {}
            stale = row.get('failed', False) or not 0 <= now-row.get('fetched', 0) <= MAX_AGES[name]
            if name == 'scales' and content:
                observed = next(r for r in content['rows'] if r['kind'] == 'observation')
                stale |= not 0 <= now-observed['issued'] <= MAX_AGES[name]
            if name == 'met' and content:
                stale |= not 0 <= now-content['issued'] <= 24*3600
            if name == 'alerts' and content:
                content['rows'] = alert_states(content['rows'], now)
            status = 'unavailable' if not content else 'stale' if stale else 'empty' if name == 'alerts' and not content['rows'] else 'checked'
            result[name] = dict(content, status=status, fetched=row.get('fetched'), checked=row.get('checked'),
                                failed=row.get('failed', False), url=LINKS[name])
        return result

    def start(self):
        if not self.started:
            self.started = True
            threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            try:
                self.refresh()
            except OSError:
                with self.lock:
                    for row in self.data.values():
                        row['failed'] = True
            time.sleep(30)
