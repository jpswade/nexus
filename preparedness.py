"""UK public-source preparedness feeds; never synthesises a threat score."""
import datetime as dt
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

URLS = {
    'threat': 'https://www.gov.uk/api/content/terrorism-national-emergency',
    'weather': 'https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/UK',
    'floods': 'https://environment.data.gov.uk/flood-monitoring/id/floods?min-severity=3',
    'ncsc': 'https://www.ncsc.gov.uk/api/1/services/v1/news-rss-feed.xml',
    'news': 'https://feeds.bbci.co.uk/news/uk/rss.xml',
}
LINKS = {
    'threat': 'https://www.gov.uk/terrorism-national-emergency',
    'weather': 'https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings',
    'floods': 'https://check-for-flooding.service.gov.uk/alerts-and-warnings',
    'ncsc': 'https://www.ncsc.gov.uk/section/keep-up-to-date/news',
    'news': 'https://www.bbc.co.uk/news/uk',
    'prepare': 'https://prepare.campaign.gov.uk/',
}
INTERVALS = {'threat': 3600, 'weather': 300, 'floods': 900, 'ncsc': 900, 'news': 900}
MAX_AGES = {'threat': 7200, 'weather': 900, 'floods': 1800, 'ncsc': 3600, 'news': 3600}
REGIONS = {'UK': 'UK', 'nw': 'North West England', 'ne': 'North East England',
           'yh': 'Yorkshire & Humber', 'wm': 'West Midlands', 'em': 'East Midlands',
           'ee': 'East of England', 'sw': 'South West England', 'se': 'London & South East',
           'wl': 'Wales', 'ni': 'Northern Ireland', 'os': 'Orkney & Shetland',
           'he': 'Highlands & Eilean Siar', 'gr': 'Grampian', 'st': 'Strathclyde',
           'ta': 'Central, Tayside & Fife', 'dg': 'SW Scotland & Borders'}
TOPICS = re.compile(r'\b(cyber\w*|attack\w*|flood\w*|storm\w*|outage\w*|emergency|terror\w*|evacuat\w*|power cut\w*|ransomware|wildfire\w*)\b', re.I)
LEVELS = ('low', 'moderate', 'substantial', 'severe', 'critical')


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(value or '')
    return ' '.join(' '.join(parser.parts).split())


def safe_link(value, fallback):
    parsed = urllib.parse.urlparse(value or '')
    if parsed.scheme != 'https' or not parsed.hostname:
        return fallback
    return value


def rss_date(value):
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    return parsed.replace(tzinfo=dt.timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()


def parse_feed(name, raw):
    if name == 'threat':
        parts = raw['details']['parts']
        body = next(p['body'] for p in parts if p['slug'] == 'terrorism-threat-levels')
        content = plain(body)
        # Match the UK sentence only, never the NI-specific level or definitions.
        match = re.search(r'The threat to the UK\s*\(England, Wales, Scotland and Northern Ireland\)\s*from terrorism is\s+(low|moderate|substantial|severe|critical)\b', content, re.I)
        if not match:
            raise ValueError('National threat sentence changed; do not guess')
        return {'level': match.group(1).upper(), 'updated': raw.get('public_updated_at'),
                'url': LINKS[name]}
    if name == 'floods':
        if not isinstance(raw.get('items'), list):
            raise ValueError('Missing flood items')
        items = []
        for row in raw['items']:
            severity = int(row['severityLevel'])
            if severity == 4:
                continue
            if severity not in (1, 2, 3):
                raise ValueError('Unknown flood severity')
            area = str(row['floodAreaID'])
            items.append({'title': row['description'], 'severity': severity,
                          'label': row['severity'], 'updated': row['timeMessageChanged'],
                          'url': 'https://check-for-flooding.service.gov.uk/target-area/'+urllib.parse.quote(area, safe='')})
        return {'items': sorted(items, key=lambda row: row['severity'])}
    root = ET.fromstring(raw)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('Expected RSS channel, not an error page')
    channel_date = rss_date(channel.findtext('pubDate') or channel.findtext('lastBuildDate'))
    items, seen = [], set()
    for item in channel.findall('item'):
        title = plain(item.findtext('title'))
        if not title:
            raise ValueError('Missing headline')
        if name == 'weather' and not re.match(r'^(Yellow|Amber|Red) warning\b', title, re.I):
            if 'no warnings' in title.lower():
                continue
            raise ValueError('Unrecognised warning bulletin')
        if name == 'news' and not TOPICS.search(title):
            continue
        url = safe_link(item.findtext('link'), LINKS[name])
        if (title, url) in seen:
            continue
        seen.add((title, url))
        items.append({'title': title, 'url': url,
                      'published': rss_date(item.findtext('pubDate')) or channel_date,
                      'description': plain(item.findtext('description')) if name == 'weather' else '',
                      'colour': title.split()[0].lower() if name == 'weather' else None})
    return {'items': items[:100], 'published': channel_date}


def build_sources(config):
    options = config.get('preparedness', {})
    region = options.get('weather_region', 'UK')
    if region not in REGIONS:
        raise ValueError('Unknown preparedness.weather_region')
    urls = {**URLS, 'weather': URLS['weather'].rsplit('/', 1)[0]+'/'+region}
    scope = 'England / national'
    if options.get('local_alerts', False):
        if options.get('nation') != 'england':
            # Never imply the EA feed covers a Scottish, Welsh or NI postcode.
            urls.pop('floods')
            scope = 'Local flood feed not configured for this nation'
        else:
            lat, lon = float(config['latitude']), float(config['longitude'])
            radius = float(options.get('flood_radius_km', 25))
            if not all(math.isfinite(v) for v in (lat, lon, radius)) or not (-90 <= lat <= 90 and -180 <= lon <= 180 and 1 <= radius <= 100):
                raise ValueError('Invalid local flood coordinates or radius')
            urls['floods'] += '&'+urllib.parse.urlencode({'lat': lat, 'long': lon, 'dist': radius})
            scope = f'{options.get("local_label", "Configured location")} / within approx {radius:g} km'
    return urls, REGIONS[region], scope


class PreparednessFeeds:
    def __init__(self, directory, config):
        self.urls, self.weather_scope, self.flood_scope = build_sources(config)
        # A changed location/region must not reuse the old location's cache.
        identity = hashlib.sha256(json.dumps(self.urls, sort_keys=True).encode()).hexdigest()[:16]
        self.directory = Path(directory)/identity
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.data, self.errors = {}, set()
        for name, url in self.urls.items():
            try:
                sample = json.loads((self.directory/f'{name}.json').read_text())
                if sample['source'] != url or not math.isfinite(float(sample['fetched'])):
                    continue
                if name == 'threat' and sample['level'].lower() not in LEVELS:
                    continue
                if name != 'threat' and not isinstance(sample['items'], list):
                    continue
                self.data[name] = sample
            except (OSError, ValueError, KeyError, TypeError):
                pass

    def snapshot(self):
        with self.lock:
            return self.data.copy(), self.errors.copy()

    def start(self):
        for name in self.urls:
            threading.Thread(target=self._worker, args=(name,), daemon=True).start()

    def refresh(self, name):
        try:
            request = urllib.request.Request(self.urls[name], headers={'User-Agent': 'NexusPreparedness/1.0', 'Accept': '*/*'})
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = response.read(4_194_305)
            if len(payload) > 4_194_304:
                raise ValueError('Oversized feed')
            raw = json.loads(payload) if name in ('threat', 'floods') else payload
            result = {**parse_feed(name, raw), 'fetched': time.time(), 'source': self.urls[name]}
            with self.lock:
                self.data[name] = result
                self.errors.discard(name)
            try:
                temporary = self.directory/f'{name}.tmp'
                temporary.write_text(json.dumps(result))
                temporary.replace(self.directory/f'{name}.json')
            except OSError:
                pass
            return True
        except Exception:
            with self.lock:
                self.errors.add(name)
            print(f'{name}: UK feed unavailable; retaining last verified data', flush=True)
            return False

    def _worker(self, name):
        while True:
            self.refresh(name)
            time.sleep(INTERVALS[name])


def source_status(name, data, errors, now):
    sample = data.get(name)
    if sample is None:
        return 'UNAVAILABLE' if name in errors else 'CONNECTING'
    stale = name in errors or now-sample['fetched'] > MAX_AGES[name]
    stamp = dt.datetime.fromtimestamp(sample['fetched'], dt.timezone.utc).strftime('%d %b %H:%M UTC')
    return ('STALE / LAST CHECK ' if stale else 'CHECKED ')+stamp
