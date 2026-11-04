"""Elexon SYSWARN bulletins, deliberately separate from local outage telemetry.

The official schema has no event ID, revision, scope, validity or active flag.
Never infer an active incident (or match a cancellation) from arbitrary prose.
"""
from source_history import History
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import threading
import time
import urllib.parse
import urllib.request

URL = 'https://data.elexon.co.uk/bmrs/api/v1/system/warnings'
SOURCE = 'Elexon Insights / BMRS'
CREDIT = 'contains BMRS data © Elexon Limited copyright and database right'
INTERVAL = 300
MAX_AGE = 900
WINDOW = 7 * 86400
MAX_BYTES = 1048576
MAX_ROWS = 2000


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('SYSWARN publication must include timezone')
    return parsed.timestamp()


def utc(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).strftime('%d %b %H:%M UTC')


def parse(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('data'), list):
        raise ValueError('Expected SYSWARN data array')
    if len(raw['data']) > MAX_ROWS:
        raise ValueError('Too many SYSWARN records')
    rows = {}
    for record in raw['data']:
        if not isinstance(record, dict):
            raise ValueError('Invalid SYSWARN record')
        kind, body = record.get('warningType'), record.get('warningText')
        if not isinstance(kind, str) or not kind.strip() or len(kind) > 200:
            raise ValueError('Missing or oversized warning type')
        if not isinstance(body, str) or not body.strip() or len(body) > 32000:
            raise ValueError('Missing or oversized warning text')
        issued = stamp(record['publishTime'])
        body = ' '.join(body.replace('\\r', ' ').replace('\\n', ' ').split())
        key = hashlib.sha256(json.dumps([issued, kind, body]).encode()).hexdigest()
        rows[key] = dict(id=key, title=kind.strip(), text=body, published=issued,
                         url=URL)
    return sorted(rows.values(), key=lambda row: (row['published'], row['id']), reverse=True)


# Topic labels only, never severity or lifecycle state. Exact source type names;
# see docs/grid-notices.md for the official evidence and deliberately narrow map.
NOTICE_TOPICS = {
    'SO-SO TRADES': ('Market bulletin', 'Operator trading / settlement prices'),
    'IT SYSTEMS OUTAGE': ('IT service bulletin', 'Industry IT services; not a power-cut notice'),
    'ELECTRICITY MARGIN NOTICE': ('Margin notice', 'Market request for additional spare capacity'),
    'HIGH RISK OF DEMAND REDUCTION': ('Demand-control notice', 'Operational warning; check source instructions'),
    'DEMAND CONTROL IMMINENT': ('Demand-control notice', 'Operational warning; check source instructions'),
}


def classify(kind):
    """Describe the topic of a known type without interpreting arbitrary prose."""
    return NOTICE_TOPICS.get(' '.join(kind.upper().split()),
                             ('Unclassified bulletin', 'Unknown type; check source'))


def persistent_alerts(sample, now):
    """No current SYSWARN row can prove active + relevant + uncancelled.

    Keep this gate explicit. Adding prose guesses or invented JSON fields here
    would turn historical market messages into unsupported persistent alerts.
    """
    return []


def card(sample, now, phase=0):
    state = 'UNAVAILABLE'
    if sample and sample.get('fetched') is not None:
        age = now-sample['fetched']
        state = 'STALE' if sample.get('failed') or not 0 <= age <= MAX_AGE else 'CHECKED'
    rows = [r for r in (sample or {}).get('items', [])
            if 0 <= now-r['published'] <= WINDOW]
    # Show the newest bulletin for each type; retain older revisions in cache.
    # Types are NOT incident IDs; this is a display choice, not supersession.
    latest = {}
    for row in sorted(rows, key=lambda r: (r['published'], r['id']), reverse=True):
        latest.setdefault(row['title'], row)
    rows = list(latest.values())
    row = rows[int(phase // 64) % len(rows)] if rows else None
    title = row['title'] if row else ('No notices returned in 7-day window' if state == 'CHECKED'
                                     else 'Grid notices '+state.lower())
    detail = 'Source text mentions cancellation; check source' if row and re.search(
        r'\b(cancelled|canceled|cancellation|withdrawn)\b', row['title']+' '+row['text'], re.I) else 'Bulletin / active status unconfirmed'
    category, meaning = classify(row['title']) if row else ('No bulletin', 'No bulletin to classify')
    return dict(state=state, title=title, detail=detail, category=category, meaning=meaning,
                scope='GB system / affected scope unspecified',
                issued='Issued '+utc(row['published']) if row else 'Issue time unavailable',
                validity='Validity not structured / check source',
                text=row['text'] if row else 'Coverage is limited to published system notices; this is not an all-clear.',
                checked='Last check '+utc(sample['fetched']) if sample and sample.get('fetched') else 'No successful check',
                source=SOURCE, url=URL)


class GridNotices:
    """Shared, atomic disk cache; no requests on the render thread.

    One bounded seven-day query every five minutes, including after failures.
    Failure status is persisted so the companion cannot mistake cached data for
    a successful refresh. Elexon is public: no Cloudflare/API token is required.
    """
    def __init__(self, directory):
        self.path = Path(directory)/'grid-notices-v1.json'
        self.lock = threading.Lock()
        self.sample = None
        self.attempted = None
        try:
            if self.path.stat().st_size > 2*MAX_BYTES:
                raise ValueError('Oversized cache')
            saved = json.loads(self.path.read_text())
            if saved['source'] != URL or saved['version'] != 1:
                raise ValueError('Wrong cache provenance')
            if not all(isinstance(saved[k], (int, float)) and math.isfinite(saved[k])
                       for k in ('attempted',)):
                raise ValueError('Invalid cache timestamp')
            fetched = saved['fetched']
            if fetched is not None and (not isinstance(fetched, (int, float)) or not math.isfinite(fetched)):
                raise ValueError('Invalid fetch time')
            items = parse(saved['raw']) if fetched is not None else []
            self.sample = dict(saved, items=items)
            self.attempted = saved['attempted']
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def snapshot(self):
        with self.lock:
            return dict(self.sample) if self.sample else None

    def refresh(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            if self.attempted is not None and 0 <= now-self.attempted < INTERVAL:
                return False
            self.attempted = now
        try:
            end = dt.datetime.fromtimestamp(now, dt.timezone.utc)
            query = urllib.parse.urlencode(dict(format='json',
                publishDateTimeFrom=(end-dt.timedelta(days=7)).isoformat(),
                publishDateTimeTo=end.isoformat()))
            request = urllib.request.Request(URL+'?'+query, headers={
                'User-Agent': 'NexusGridNotices/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = response.read(MAX_BYTES+1)
            if len(payload) > MAX_BYTES:
                raise ValueError('Oversized SYSWARN response')
            raw = json.loads(payload)
            items = parse(raw)
            result = dict(version=1, source=URL, fetched=now, attempted=now,
                          failed=False, raw=raw, items=items)
            ok = True
        except Exception:
            result = dict(self.snapshot() or dict(version=1, source=URL,
                          fetched=None, raw={'data': []}, items=[]),
                          failed=True, attempted=now)
            ok = False
        History(self.path.parent).record('grid', now, result if ok else None)
        with self.lock:
            self.sample = result
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent,
                                             prefix='grid-', delete=False) as handle:
                temporary = Path(handle.name)
                json.dump({k: v for k, v in result.items() if k != 'items'}, handle)
            temporary.replace(self.path)
        except OSError:
            pass
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return ok

    def start(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            self.refresh()
            time.sleep(INTERVAL)
