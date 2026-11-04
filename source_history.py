"""Bounded, payload-free local check journal shared by display processes."""
import datetime as dt
import fcntl
import hashlib
import json
import math
from pathlib import Path
import tempfile

LIMIT = 64
RETENTION = 7 * 86400
MAX_BYTES = 64 * 1024
SOURCES = ('gov', 'grid', 'weather', 'floods', 'threat', 'ncsc', 'news', 'php', 'kev', 'phpnews')
# Poll/cache bookkeeping and optional score enrichment are not source changes.
VOLATILE = {'fetched', 'attempted', 'checked', 'failed', 'source', 'raw',
            'score_checked', 'score_cached'}


def fingerprint(sample):
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in VOLATILE}
        if isinstance(value, list):
            return sorted((clean(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
        return value
    body = json.dumps(clean(sample), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(body.encode()).hexdigest()


class History:
    def __init__(self, directory):
        self.directory = Path(directory)

    def read(self, source, now):
        if source not in SOURCES:
            return {}
        try:
            path = self.directory / ('health-' + source + '.json')
            if path.stat().st_size > MAX_BYTES:
                return {}
            saved = json.loads(path.read_text())
            if saved.get('version') != 1 or saved.get('attempted') is None:
                return {}
            for field in ('attempted', 'successful'):
                value = saved.get(field)
                if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                    return {}
            if saved.get('failed') not in (True, False):
                return {}
            if not isinstance(saved.get('digest'), (str, type(None))):
                return {}
            events = saved['events']
            if not isinstance(events, list):
                return {}
            saved['events'] = [e for e in events if isinstance(e, dict)
                and isinstance(e.get('time'), (int, float)) and math.isfinite(e['time'])
                and 0 <= now-e['time'] <= RETENTION
                and e.get('kind') in ('checked', 'failed', 'recovered', 'baseline', 'changed')][-LIMIT:]
            return saved
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return {}

    def record(self, source, attempted, sample=None):
        """One completed attempt. None means failure, not an empty feed.

        Only a digest and fixed event codes are saved; no URLs, config, source
        text or exception messages. Lock/read/replace prevents lost updates.
        Disk failure must never turn a successful source into a failed source.
        """
        if source not in SOURCES:
            return
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / ('health-' + source + '.lock')).open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                old = self.read(source, attempted)
                if old.get('attempted', -1) >= attempted:
                    return
                digest = fingerprint(sample) if sample is not None else old.get('digest')
                kind = ('failed' if sample is None else 'baseline' if old.get('digest') is None
                        else 'changed' if digest != old['digest'] else 'recovered' if old.get('failed') else 'checked')
                events = old.get('events', []) + [dict(time=attempted, kind=kind)]
                result = dict(version=1, attempted=attempted,
                    successful=sample.get('fetched', attempted) if sample is not None else old.get('successful'),
                    failed=sample is None, digest=digest, events=events[-LIMIT:])
                with tempfile.NamedTemporaryFile(mode='w', dir=self.directory, prefix='health-', suffix='.tmp', delete=False) as out:
                    temporary = Path(out.name)
                    json.dump(result, out)
                temporary.replace(self.directory / ('health-' + source + '.json'))
        except (OSError, ValueError, TypeError):
            pass
        finally:
            if temporary:
                try: temporary.unlink(missing_ok=True)
                except OSError: pass


def detail(record, sample, now, max_age):
    """Legacy cache success is useful, but never invent an attempted check."""
    successful = record.get('successful', (sample or {}).get('fetched'))
    failed = record.get('failed', (sample or {}).get('failed', False))
    state = ('FAILED' if failed else 'NOT CHECKED' if successful is None else
             'STALE' if not 0 <= now-successful <= max_age else 'CHECKED')
    def stamp(value):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).strftime('%d %b %H:%M UTC') if value is not None else 'Not recorded'
    return state, 'Attempt: ' + stamp(record.get('attempted')), 'Success: ' + stamp(successful)
