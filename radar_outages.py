"""Optional Cloudflare Radar context; never an input to threat assessment.

Only normalized public annotations are cached. No credentials or HTTP errors
are logged. Two display processes share a nonblocking lock and retry timestamp.
"""
import copy
import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

URL = 'https://api.cloudflare.com/client/v4/radar/annotations/outages'
SOURCE = 'https://radar.cloudflare.com/outage-center'
INTERVAL = 900
MAX_AGE = 1800
RETENTION = 7 * 86400
LIMIT = 50
MAX_BYTES = 256 * 1024


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Missing timezone')
    return parsed.timestamp()


def clean(value, limit=120):
    return ' '.join(str(value or '').split())[:limit]


def parse(payload, asn=None):
    if payload.get('success') is not True:
        raise ValueError('Unsuccessful response')
    rows = payload['result']['annotations']
    if not isinstance(rows, list) or len(rows) > LIMIT:
        raise ValueError('Invalid annotations')
    items = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid annotation')
        if row.get('eventType') != 'OUTAGE':
            continue
        locations = row.get('locations', [])
        asns = [int(a) for a in row.get('asns', [])]
        if 'GB' not in locations and (asn is None or asn not in asns):
            continue
        start = stamp(row['startDate'])
        end = stamp(row['endDate']) if row.get('endDate') else None
        if end is not None and end < start:
            raise ValueError('Invalid interval')
        providers = [clean(a.get('name'), 60) + ' AS' + str(int(a['asn']))
                     for a in row.get('asnsDetails', [])[:4]]
        items.append(dict(start=start, end=end,
                          location=clean(', '.join(locations)) or 'Location unspecified',
                          provider=' / '.join(providers)[:160] or
                          (', '.join('AS'+str(a) for a in asns[:4]) or 'No provider specified'),
                          scope=clean(row.get('scope')) or 'Scope unspecified',
                          kind=clean((row.get('outage') or {}).get('outageType')) or 'Unspecified'))
    return sorted(items, key=lambda r: r['start'], reverse=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Never forward the Authorization header to a redirect destination.
        return None


def fetch(token, filters, cancelled):
    query = dict(dateRange='7d', limit=LIMIT, offset=0, format='JSON', **filters)
    request = urllib.request.Request(URL+'?'+urllib.parse.urlencode(query),
                                     headers={'Authorization': 'Bearer '+token})
    opener = urllib.request.build_opener(NoRedirect())
    deadline = time.monotonic()+15
    with opener.open(request, timeout=5) as response:
        body = bytearray()
        while True:
            if cancelled.is_set() or time.monotonic() > deadline:
                raise TimeoutError('Fetch cancelled or expired')
            chunk = response.read1(min(16384, MAX_BYTES+1-len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError('Response too large')
    return json.loads(body)


class RadarFeed:
    def __init__(self, cache=None, token=None, asn=None, transport=fetch):
        self._token = os.environ.get('CLOUDFLARE_RADAR_TOKEN', '').strip() if token is None else token
        raw_asn = os.environ.get('NEXUS_RADAR_ASN', '') if asn is None else asn
        self.invalid = False
        try:
            self.asn = int(raw_asn) if raw_asn else None
            if self.asn is not None and not 1 <= self.asn <= 4294967295:
                raise ValueError()
        except (ValueError, TypeError):
            self.asn = None
            self.invalid = True
        root = Path(os.environ.get('NEXUS_CACHE', Path(__file__).resolve().parent/'.cache'))
        self.path = Path(cache) if cache else root/'radar-outages.json'
        self.transport = transport
        self.cancelled = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.state = {}
        self.next_try = 0
        self.auth_failed = False
        self._load()

    def _load(self):
        try:
            with self.path.open('rb') as source:
                body = source.read(MAX_BYTES+1)
            if len(body) > MAX_BYTES:
                return
            data = json.loads(body)
            if not isinstance(data, dict):
                return
            if data.get('version') != 1 or data.get('asn') != self.asn:
                return
            now = time.time()
            for key in ('fetched', 'attempted'):
                value = data.get(key, 0)
                if not isinstance(value, (float, int)) or not math.isfinite(value) or value > now+60:
                    return
            items = data.get('items', [])
            if not isinstance(items, list) or len(items) > LIMIT*2:
                return
            for item in items:
                if not all(isinstance(item[k], str) for k in ('location','provider','scope','kind')):
                    return
                if not math.isfinite(item['start']) or (item['end'] is not None and not math.isfinite(item['end'])):
                    return
            with self.lock:
                self.state = data
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def _save(self, data):
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent, delete=False) as out:
                name = out.name
                json.dump(data, out, allow_nan=False)
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def refresh(self):
        if not self._token or self.invalid or self.auth_failed or self.cancelled.is_set():
            return
        now = time.time()
        if now < self.next_try:
            return
        self.next_try = now+INTERVAL  # Also bounds retries if disk access fails.
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.with_suffix('.lock').open('a') as lease:
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    self.next_try = now+10
                    return
                self._load()
                with self.lock:
                    data = copy.deepcopy(self.state)
                if 0 <= now-data.get('attempted', 0) < INTERVAL:
                    return
                data.update(version=1, asn=self.asn, attempted=now, failed=True)
                self._save(data)  # Crash/restart also respects the retry interval.
                try:
                    items = []
                    limited = False
                    queries = [{'location': 'GB'}]
                    if self.asn:
                        queries.append({'asn': self.asn})
                    for query in queries:
                        if self.cancelled.is_set():
                            return
                        payload = self.transport(self._token, query, self.cancelled)
                        items.extend(parse(payload, self.asn))
                        limited |= len(payload['result']['annotations']) >= LIMIT
                    unique = {json.dumps(item, sort_keys=True): item for item in items}
                    data.update(items=sorted(unique.values(), key=lambda r:r['start'], reverse=True),
                                fetched=time.time(), failed=False, limited=limited)
                except urllib.error.HTTPError as error:
                    if error.code in (401, 403):
                        self.auth_failed = True
                except Exception:
                    # Never stringify exceptions: transports may include credentials.
                    pass
                if self.cancelled.is_set():
                    return
                with self.lock:
                    self.state = data
                self._save(data)
        except OSError:
            with self.lock:
                self.state['failed'] = True

    def snapshot(self, now=None, offline=False):
        now = time.time() if now is None else now
        with self.lock:
            data = copy.deepcopy(self.state)
        fetched = data.get('fetched')
        age = max(0, now-fetched) if fetched is not None else None
        status = ('not configured' if not self._token else 'invalid ASN configuration' if self.invalid else
                  ('stale / credentials rejected' if fetched else 'credentials rejected') if self.auth_failed else
                  'unavailable' if fetched is None and data.get('failed') else
                  'waiting' if fetched is None else 'expired' if age > RETENTION else
                  'stale' if offline or data.get('failed') or age > MAX_AGE else 'checked')
        if status in ('not configured', 'invalid ASN configuration', 'expired'):
            data['items'] = []
        data.update(status=status, age=age, fetched=fetched)
        return data

    def start(self):
        if not self._token or self.invalid or self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run, daemon=True, name='radar-outages')
        self.thread.start()

    def _run(self):
        while not self.cancelled.is_set():
            self.refresh()
            self.cancelled.wait(10)

    def stop(self):
        self.cancelled.set()
        if self.thread:
            self.thread.join(timeout=.2)


def display_lines(sample, phase=0):
    """Shared presentation keeps missing/empty/error states consistent."""
    age = sample.get('age')
    status = sample.get('status', 'not configured').upper()
    freshness = status + (f' / {int(age//60)}m ago' if age is not None else '')
    items = sample.get('items', [])
    if not items:
        detail = ('No reports returned / 7d' if status == 'CHECKED' else
                  'Cached empty result / 7d' if status == 'STALE' else 'Reports unavailable')
        return [freshness, detail, 'Not an all-clear', 'UK + configured ASN', 'Context only; not Pi diagnosis']
    item = items[int(phase//8) % len(items)]
    def date(value):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).strftime('%d %b %H:%MZ')
    return [freshness+(' / LIMITED' if sample.get('limited') else ''),
            item['location']+' / '+item['provider'],
            item['kind']+' / '+item['scope'],
            'Start '+date(item['start']),
            'End '+(date(item['end']) if item['end'] is not None else 'not reported')]
