"""Conservative, informational UK service-disruption briefings from GOV.UK."""
import datetime as dt
import json
import math
from pathlib import Path
import re
import tempfile
import threading
import time
import urllib.parse
import urllib.request

URL = 'https://www.gov.uk/api/search.json'
SOURCE = 'GOV.UK'
INTERVAL = 900
MAX_AGE = 3600
WINDOW = 7 * 86400
MAX_BYTES = 8 * 1048576
MAX_ROWS = 1000
FORMATS = ('news_story', 'press_release', 'guidance')
# Domestic service publishers only; exclude foreign aid/travel/political coverage.
ORGANISATIONS = {'cabinet-office', 'department-for-energy-security-and-net-zero',
    'department-for-transport', 'department-for-environment-food-rural-affairs',
    'environment-agency', 'uk-health-security-agency', 'department-of-health-and-social-care',
    'national-highways', 'maritime-and-coastguard-agency', 'home-office',
    'ministry-of-housing-communities-and-local-government', 'ofgem', 'ofwat'}
SERVICE = re.compile(r'\b(power|electricity|energy|gas|water|rail|railway|train|transport|roads?|motorways?|hospitals?|nhs|ambulance|public services?|schools?)\b', re.I)
INCIDENT = re.compile(r'\b(disruption|outages?|blackouts?|power cuts?|supply interruptions?|shortages?|emergency|major incident|closures?|closed|suspended|do not drink|boil water|storm|flooding|floods?)\b', re.I)
ROUTINE = re.compile(r'\b(funding|investment|invests?|million|billion|budget|appoints?|appointed|consultation|speech|reform|legislation|bill|strategy|policy|summit|conference|visits?|meets?|meetings?|talks|pledges?|overseas|abroad|plans?|exercise|drill|anniversary|awards?)\b', re.I)


def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Publication must include timezone')
    return parsed.timestamp()


def utc(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).strftime('%d %b %H:%M UTC')


def parse(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('results'), list):
        raise ValueError('Expected Search API results')
    records = raw['results']
    if (len(records) > MAX_ROWS or not isinstance(raw.get('total'), int)
            or raw['total'] != len(records)):
        raise ValueError('Incomplete or oversized Search API result')
    rows = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('Invalid search record')
        title, description = record.get('title'), record.get('description', '')
        link = record.get('link')
        if (not isinstance(title, str) or not title.strip() or len(title) > 1000
                or not isinstance(description, str) or len(description) > 20000
                or not isinstance(link, str)):
            raise ValueError('Invalid briefing text/link')
        published = stamp(record['public_timestamp'])
        parts = urllib.parse.urlsplit(link)
        if parts.scheme or parts.netloc or not parts.path.startswith('/government/') or '\\' in link:
            raise ValueError('Expected relative GOV.UK government link')
        organisations = record.get('organisations', [])
        if not isinstance(organisations, list) or any(not isinstance(o, dict) for o in organisations):
            raise ValueError('Invalid organisations')
        publishers = [o for o in organisations if o.get('slug') in ORGANISATIONS]
        # Incident must appear in the headline, not just boilerplate in the body.
        if (record.get('format') not in FORMATS or not publishers or ROUTINE.search(title)
                or not INCIDENT.search(title) or not SERVICE.search(title+' '+description)):
            continue
        url = 'https://www.gov.uk'+parts.path.rstrip('/')
        row = dict(id=url, url=url, title=' '.join(title.split()),
                   text=' '.join(description.split()), published=published,
                   source='GOV.UK / '+str(publishers[0].get('title') or publishers[0]['slug']))
        if url not in rows or published > rows[url]['published']:
            rows[url] = row
    # A repeated headline at the same publication time is also a duplicate.
    unique = {}
    for row in sorted(rows.values(), key=lambda r: (r['published'], r['url']), reverse=True):
        unique.setdefault((row['title'].casefold(), row['published']), row)
    return list(unique.values())


def card(sample, now, phase=0):
    state = 'UNAVAILABLE'
    if sample and sample.get('fetched') is not None:
        age = now-sample['fetched']
        state = 'STALE' if sample.get('failed') or not 0 <= age <= MAX_AGE else 'CHECKED'
    rows = [r for r in (sample or {}).get('items', []) if 0 <= now-r['published'] <= WINDOW]
    row = rows[int(phase//48) % len(rows)] if rows else None
    return dict(state=state,
        title=row['title'] if row else ('No matching briefings in 7 days' if state == 'CHECKED' else 'Briefings '+state.lower()),
        text=row['text'] if row else 'Limited to selected official service-disruption briefings. Not an all-clear.',
        issued='Published/updated '+utc(row['published']) if row else 'No current dated briefing',
        checked='Last check '+utc(sample['fetched']) if sample and sample.get('fetched') is not None else 'No successful check',
        source=row['source'] if row else SOURCE,
        url=row['url'] if row else 'https://www.gov.uk/search/news-and-communications',
        count=len(rows))


class GovukBriefings:
    """Shared, atomic disk cache; no requests on the render thread.

    One bounded seven-day query every fifteen minutes, including after failures.
    Failure status is persisted so the companion cannot mistake cached data for
    a successful refresh. GOV.UK Search is public; no credentials are required.
    """
    def __init__(self, directory):
        self.path = Path(directory)/'govuk-briefings-v1.json'
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
            query = urllib.parse.urlencode(dict(count=MAX_ROWS,
                order='-public_timestamp',
                fields='title,description,link,public_timestamp,organisations,format',
                filter_format=FORMATS,
                filter_public_timestamp='from:'+(end-dt.timedelta(days=7)).strftime('%Y-%m-%d %H:%M')+',to:'+end.strftime('%Y-%m-%d %H:%M')), doseq=True)
            request = urllib.request.Request(URL+'?'+query, headers={
                'User-Agent': 'NexusGovukBriefings/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = response.read(MAX_BYTES+1)
            if len(payload) > MAX_BYTES:
                raise ValueError('Oversized GOV.UK response')
            raw = json.loads(payload)
            items = parse(raw)
            result = dict(version=1, source=URL, fetched=now, attempted=now,
                          failed=False, raw=raw, items=items)
            ok = True
        except Exception:
            result = dict(self.snapshot() or dict(version=1, source=URL,
                          fetched=None, raw={'results': [], 'total': 0}, items=[]),
                          failed=True, attempted=now)
            ok = False
        with self.lock:
            self.sample = result
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent,
                                             prefix='govuk-', delete=False) as handle:
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
