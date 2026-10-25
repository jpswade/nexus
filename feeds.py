"""Public planetary data feeds. Fetching and parsing stay outside the render loop."""
import datetime
import json
import math
import pathlib
import threading
import time
import urllib.request

URLS = {
    'iss': 'https://api.wheretheiss.at/v1/satellites/25544',
    'quakes': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson',
    'kp': 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
    'wind': 'https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json',
}
INTERVALS = {'iss': 20, 'quakes': 300, 'kp': 600, 'wind': 300}
MAX_AGES = {'iss': 120, 'quakes': 1200, 'kp': 5*3600, 'wind': 1800}


def timestamp(value):
    if isinstance(value, (int, float)):
        return float(value)
    result = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        result = result.replace(tzinfo=datetime.timezone.utc)
    return result.timestamp()


def finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite observation')
    return result


def parse(name, raw):
    if name == 'iss':
        result = {key: finite(raw[key]) for key in ('latitude', 'longitude', 'altitude', 'velocity')}
        if not (-90 <= result['latitude'] <= 90 and -180 <= result['longitude'] <= 180):
            raise ValueError('Invalid satellite coordinates')
        return dict(result, observed=timestamp(raw['timestamp']), visibility=raw.get('visibility', 'unknown'))
    if name == 'quakes':
        events = []
        for feature in raw['features']:
            props = feature['properties']
            if props.get('type', 'earthquake') != 'earthquake' or props.get('mag') is None:
                continue
            lon, lat, depth = feature['geometry']['coordinates']
            events.append({'mag': finite(props['mag']), 'place': props.get('place') or 'Location pending',
                           'time': finite(props['time'])/1000, 'lat': finite(lat), 'lon': finite(lon),
                           'depth': finite(depth)})
        events.sort(key=lambda event: event['time'], reverse=True)
        return {'events': events, 'observed': finite(raw['metadata']['generated'])/1000}
    # NOAA has used both header/row tables and lists of objects.
    if raw and isinstance(raw[0], list):
        raw = [dict(zip(raw[0], row)) for row in raw[1:]]
    valid = []
    for row in raw:
        try:
            key = 'Kp' if name == 'kp' else 'proton_speed'
            if name == 'wind' and row.get('active') is not True:
                continue
            value = finite(row[key])
            if value < 0 or (name == 'kp' and value > 9):
                continue
            valid.append((timestamp(row['time_tag']), value))
        except (KeyError, TypeError, ValueError):
            continue
    if not valid:
        raise ValueError('No valid observations')
    valid.sort()
    return {'value': valid[-1][1], 'observed': valid[-1][0], 'history': valid[-24:]}


def age_label(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60: return f'{seconds}s ago'
    if seconds < 3600: return f'{seconds//60}m ago'
    return f'{seconds//3600}h ago'


class PlanetFeeds:
    def __init__(self, directory, urls=None, intervals=None, parser=parse, decoder=None):
        self.urls = URLS if urls is None else urls
        self.intervals = INTERVALS if intervals is None else intervals
        self.parser = parser
        self.decoder = decoder or (lambda name, response: json.load(response))
        self.directory = pathlib.Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.data, self.errors = {}, set()
        for name in self.urls:
            try:
                self.data[name] = json.loads((self.directory / f'{name}.json').read_text())
            except (OSError, ValueError):
                pass

    def start(self):
        for name in self.urls:
            threading.Thread(target=self._worker, args=(name,), daemon=True).start()

    def snapshot(self):
        with self.lock:
            return self.data.copy(), self.errors.copy()

    def _worker(self, name):
        while True:
            try:
                request = urllib.request.Request(self.urls[name], headers={'User-Agent': 'NexusDashboard/1.0', 'Accept': 'application/json'})
                with urllib.request.urlopen(request, timeout=20) as response:
                    result = self.parser(name, self.decoder(name, response))
                result['fetched'] = time.time()
                with self.lock:
                    self.data[name] = result
                    self.errors.discard(name)
                try:
                    temporary = self.directory / f'{name}.tmp'
                    temporary.write_text(json.dumps(result))
                    temporary.replace(self.directory / f'{name}.json')
                except OSError:
                    pass
                print(f'{name}: feed updated', flush=True)
                delay = self.intervals[name]
            except Exception as error:
                with self.lock:
                    self.errors.add(name)
                print(f'{name}: feed unavailable ({error})', flush=True)
                delay = max(60, self.intervals[name])
            time.sleep(delay)
