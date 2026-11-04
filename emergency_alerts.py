"""Conservative GOV.UK Emergency Alerts HTML adapter (standard library only).

Broadcast end is not hazard expiry. Never geocode free-text areas or treat a
failed/unrecognised page as an empty list. Content: Crown copyright, OGL v3.
"""
import copy
import datetime as dt
import fcntl
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import tempfile
import threading
import time
from urllib.parse import urljoin, urlsplit
import urllib.request

CURRENT = 'https://www.gov.uk/alerts/current-alerts'
LICENCE = 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'
INTERVAL = 300
MAX_AGE = 900
MAX_BYTES = 1024 * 1024
MAX_ALERTS = 16


def official(url):
    p = urlsplit(url)
    return (p.scheme == 'https' and p.netloc == 'www.gov.uk' and
            re.fullmatch(r'/alerts/[a-z0-9-]+', p.path) and not p.query and not p.fragment)


class Page(HTMLParser):
    """Read semantic blocks only inside main; ignore menus/footer and scripts."""
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.main = False
        self.blocks = []
        self.links = []
        self.block = None
        self.anchor = None
        self.skip = 0
        self.feed(html)
        if self.main or not self.blocks:
            raise ValueError('Incomplete or unrecognised GOV.UK page')

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'main': self.main = True
        if not self.main: return
        if tag in ('script', 'style', 'svg'): self.skip += 1
        if self.skip: return
        if tag in ('h1', 'h2', 'h3', 'p'):
            self.finish()
            self.block = [tag, [], []]
        if tag == 'time' and self.block:
            self.block[2].append(attrs.get('datetime', ''))
        if tag == 'a': self.anchor = [attrs.get('href', ''), []]

    def finish(self):
        if self.block:
            tag, parts, times = self.block
            value = ' '.join(''.join(parts).split())
            if value: self.blocks.append((tag, value, times))
        self.block = None

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'svg') and self.skip:
            self.skip -= 1
            return
        if self.skip: return
        if tag == 'a' and self.anchor:
            self.links.append((self.anchor[0], ' '.join(''.join(self.anchor[1]).split())))
            self.anchor = None
        if tag in ('h1', 'h2', 'h3', 'p', 'main'): self.finish()
        if tag == 'main': self.main = False

    def handle_data(self, value):
        if not self.main or self.skip: return
        if self.block: self.block[1].append(value)
        if self.anchor: self.anchor[1].append(value)


def parse_index(html):
    page = Page(html)
    if not any(tag == 'h1' and value == 'Current alerts' for tag, value, _ in page.blocks):
        raise ValueError('Current alerts heading missing')
    empty = any(value == 'There are no current alerts.' for _, value, _ in page.blocks)
    links = []
    for href, title in page.links:
        if title.startswith('More information about this alert'):
            url = urljoin(CURRENT, href)
            if not official(url): raise ValueError('Unexpected alert link')
            if url not in links: links.append(url)
    headings = [v for t, v, _ in page.blocks if t == 'h3']
    if (empty and (links or headings)) or (not empty and (not links or len(headings) != len(links))):
        raise ValueError('Ambiguous current alerts listing')
    if len(links) > MAX_ALERTS: raise ValueError('Alert count exceeds fetch budget')
    return links


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise ValueError('Missing time zone')
    return parsed.timestamp()


def parse_detail(html, url):
    page = Page(html)
    if not any(t == 'h1' and v == 'Emergency Alert' for t, v, _ in page.blocks):
        raise ValueError('Emergency Alert heading missing')
    row = dict(url=url, area='Area not published', issued=None, stopped=None,
               expires=None, validity='Validity not published', status='current')
    instructions = []
    for tag, value, times in page.blocks:
        low = value.lower()
        if low.startswith('this alert was sent to ') or low.startswith('this alert is being sent to '):
            row['area'] = re.sub(r'^This alert (?:was|is being) sent to ', '', value).rstrip('.')
        elif low.startswith('sent by ') or low.startswith('issued at '):
            row['issued'] = timestamp(times[0]) if times else None
        elif tag == 'h2' and low.startswith('stopped sending'):
            row['status'] = 'past'
            row['stopped'] = timestamp(times[0]) if times else None
        elif tag == 'h2' and re.match(r'(?:alert )?(?:cancelled|withdrawn)', low):
            row['status'] = 'cancelled'
        elif low.startswith(('valid until ', 'expires at ')):
            row['validity'] = value
            row['expires'] = timestamp(times[0]) if times else None
        elif tag == 'p' and not low.startswith('surrounding areas might'):
            instructions.append(value)
    if not instructions: raise ValueError('Alert instructions missing')
    if sum(map(len, instructions)) > 32768: raise ValueError('Alert text exceeds budget')
    row['instructions'] = '\n'.join(instructions)
    row['test'] = bool(re.search(r'\b(this is a test|testing emergency alerts|test of emergency alerts|prawf yw hwn|dyma brawf)\b', row['instructions'], re.I))
    return row


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Unexpected redirect from official alert endpoint')


def fetch(url, deadline):
    if not official(url): raise ValueError('Untrusted alert endpoint')
    request = urllib.request.Request(url, headers={'User-Agent': 'Nexus-EmergencyAlerts/1.0', 'Accept': 'text/html'})
    remaining = deadline - time.monotonic()
    if remaining <= 0: raise TimeoutError('Fetch budget exhausted')
    with urllib.request.build_opener(NoRedirect).open(request, timeout=min(8, remaining)) as response:
        if response.headers.get_content_type() != 'text/html': raise ValueError('Expected HTML')
        chunks = []; size = 0
        while True:
            if time.monotonic() >= deadline: raise TimeoutError('Fetch budget exhausted')
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            if size > MAX_BYTES: raise ValueError('Oversized alert page')
        return b''.join(chunks).decode('utf-8')


def load_cache(path):
    try:
        if path.stat().st_size > 2 * MAX_BYTES: return {}
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or data.get('version') != 1: return {}
        if not isinstance(data.get('items'), list) or len(data['items']) > MAX_ALERTS * 2: return {}
        for row in data['items']:
            if not isinstance(row, dict) or not isinstance(row.get('url'), str): return {}
            if not official(row['url']): return {}
            if not isinstance(row.get('test'), bool): return {}
            if row['status'] not in ('current', 'past', 'cancelled', 'withdrawn'): return {}
            if not all(isinstance(row[k], str) for k in ('area', 'instructions', 'validity')): return {}
            for key in ('issued', 'stopped', 'expires'):
                if row.get(key) is not None and (not isinstance(row[key], (int, float)) or not math.isfinite(row[key])): return {}
        if not isinstance(data['checked'], (int, float)) or not math.isfinite(data['checked']): return {}
        if data.get('fetched') is not None and (not isinstance(data['fetched'], (int, float)) or not math.isfinite(data['fetched'])): return {}
        return data
    except (OSError, ValueError, TypeError, KeyError):
        return {}


class EmergencyAlerts:
    def __init__(self, directory, fetcher=fetch):
        self.directory = Path(directory)
        self.path = self.directory / 'emergency-alerts.json'
        self.fetcher = fetcher
        self.data = load_cache(self.path)

    def snapshot(self):
        return copy.deepcopy(self.data)

    def refresh(self, now=None, force=False):
        now = time.time() if now is None else now
        # Separate processes share one request/cache writer. No private config used.
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / 'emergency-alerts.lock').open('a') as lock:
                try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: return False
                cached = load_cache(self.path)
                if cached: self.data = cached
                if not force and 0 <= now - self.data.get('checked', 0) < INTERVAL: return False
                old = self.data
                try:
                    deadline = time.monotonic() + 45
                    urls = parse_index(self.fetcher(CURRENT, deadline))
                    items = [parse_detail(self.fetcher(url, deadline), url) for url in urls]
                    removed = [dict(row, status='withdrawn' if row['status'] == 'current' else row['status']) for row in old.get('items', [])
                               if row['url'] not in urls]
                    result = dict(version=1, checked=now, fetched=now, failed=False,
                                  items=items + removed[:MAX_ALERTS])
                except Exception:
                    # Do not leak request URLs/headers/errors into logs or cache.
                    result = dict(old, version=1, checked=now, failed=True,
                                  items=old.get('items', []))
                self.data = result
                with tempfile.NamedTemporaryFile(mode='w', dir=self.directory, delete=False) as out:
                    temporary = Path(out.name)
                    json.dump(result, out)
                try: temporary.replace(self.path)
                finally: temporary.unlink(missing_ok=True)
                return not result['failed']
        except OSError:
            self.data = dict(self.data, failed=True)
            return False

    def start(self):
        def work():
            while True:
                self.refresh()
                time.sleep(30)
        threading.Thread(target=work, daemon=True).start()


def presentation(data, now):
    fetched = data.get('fetched')
    stale = fetched is None or data.get('failed', False) or now - fetched > MAX_AGE or now < fetched
    rows = []
    for item in data.get('items', []):
        row = dict(item)
        if row.get('expires') is not None and now >= row['expires'] and row['status'] == 'current':
            row['status'] = 'expired'
        rows.append(row)
    current = [r for r in rows if r['status'] == 'current']
    if fetched is None: status = 'UNAVAILABLE / check unreadable' if data.get('failed') else 'NOT CHECKED'
    elif stale: status = 'STALE / last-known data'
    elif current: status = '%s current / %s test' % (sum(not r['test'] for r in current), sum(r['test'] for r in current))
    else: status = 'None listed / not an all-clear'
    # Retain ended/removed records for review, with their explicit status.
    return status, current or rows, stale
