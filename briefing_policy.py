"""Pure cached-data card policy shared by HDMI and LCD (see docs/briefing-policy.md)."""
import datetime as dt
import hashlib
import math

from alert_state import weather_window
from preparedness import LINKS, MAX_AGES, display_items


def _stamp(value):
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
            value = parsed.replace(tzinfo=parsed.tzinfo or dt.timezone.utc).timestamp()
        return float(value) if value is not None and math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _snapshot(value):
    """Accept feed snapshot dictionaries or their (data, errors) pair."""
    if isinstance(value, tuple) and len(value) == 2:
        data, errors = value
        return {k: dict(v, failed=True) if k in errors else v for k, v in data.items()}
    return value if isinstance(value, dict) else {}


def _health(sample, record, now, age):
    success = _stamp(sample.get('fetched', sample.get('checked')))
    checked = _stamp(record.get('attempted', sample.get('attempted', sample.get('checked', success))))
    status = str(sample.get('status', '')).lower()
    if success is None or status in ('unavailable', 'waiting', 'not configured', 'credentials rejected', 'invalid asn configuration'):
        return 'unavailable', checked
    stale = (sample.get('failed') or record.get('failed') or
             not 0 <= now-success <= age or 'stale' in status or status == 'expired')
    return ('stale' if stale else 'current'), checked


def build_cards(context, now):
    """Return the fixed #46 plain-dictionary contract; no I/O or mutation.

    Retention belongs to feed caches: supply the last successful payload with
    failed=True (or a failed source record), never replace it with an empty feed.
    """
    context = dict(context or {})
    if not isinstance(context.get('location'), dict):
        context['location'] = {'floods_scope': str(context.get('location') or '')}
    uk, security = (_snapshot(context.get(k)) for k in ('uk', 'security'))
    records = dict(context.get('source_records') or {})
    for key in ('uk_errors', 'sec_errors', 'planet_errors'):
        for name in context.get(key, ()):
            records[name] = dict(records.get(name, {}), failed=True)
    cards = {}

    def add(key, group, title, body, source, url='', sample=None, row=None,
            severity='info', age=3600, record=None, summary=False, expired=False):
        sample, row = sample or {}, row or {}
        state, checked = _health(sample, records.get(record or key, {}), now, age)
        end = _stamp(row.get('valid_until', row.get('expires', row.get('end'))))
        ended = expired or end is not None and now >= end
        body = list(dict.fromkeys(str(line) for line in body if line is not None and str(line) and str(line) != str(title)))
        if ended:
            state, severity = 'info', 'info'
            body.append('Ended / historical evidence; not an active warning.')
        elif state == 'stale':
            body.append('STALE / last-known evidence; refresh failed or overdue.')
        elif state == 'unavailable':
            body.append('Unknown / no successful check available.')
        if severity in ('warning', 'critical', 'advisory') and end is None:
            body.append('Validity end not established; check source.')
        words = len((' '.join([title] + body)).split())
        duration = 0 if summary or ended and group == 'situation' else max(12, math.ceil(words / 2.5) + 4)
        cards[key] = dict(id=key, group=group, title=str(title), body=body,
            source=source, url=url or '', published=_stamp(row.get('published', row.get('issued', row.get('updated')))),
            checked=checked, valid_until=end, state=state, severity=severity,
            pinned=not ended and group in ('situation','infrastructure') and severity in ('warning', 'critical'), duration=duration)

    def feed(name, sample, group, source, url, rows, age=3600):
        state, _ = _health(sample or {}, records.get(name, {}), now, age)
        if not rows:
            add(name + ':check', group, source, ['None returned in display window; not an all-clear.'] if state == 'current' else ['Source check unavailable or stale.'],
                source, url, sample, age=age, record=name, summary=True)

    threat = uk.get('threat') or {}
    body = ['Official national assessment: ' + str(threat.get('level', 'unknown'))]
    for name, observation in (threat.get('observations') or {}).items():
        body.append(name + ': ' + str(observation.get('level', 'unknown')))
    if threat.get('disagreement'):
        body.append('Official sources disagree; no combined assessment.')
    if threat.get('source_name') == 'MI5':
        body.append('MI5 fallback / GOV.UK assessment unavailable.')
    add('threat', 'situation', 'UK terrorism assessment', body,
        threat.get('source_name', 'GOV.UK / MI5'), threat.get('url', LINKS['threat']), threat,
        threat, severity={'severe': 'warning', 'critical': 'critical'}.get(str(threat.get('level')).lower(), 'info'), age=7200, summary=True)

    for name, source in [('weather', 'Met Office'), ('floods', 'Environment Agency')]:
        sample = uk.get(name) or {}
        rows = sample.get('items', [])
        feed(name, sample, 'situation', source, LINKS[name], rows, MAX_AGES[name])
        for row in rows:
            start, end = weather_window(row) if name == 'weather' else (None, None)
            end = row.get('valid_until', end)
            severity = ({'red': 'critical', 'amber': 'warning', 'yellow': 'advisory'}.get(str(row.get('colour')).lower(), 'info') if name == 'weather'
                        else {1: 'critical', 2: 'warning', 3: 'advisory'}.get(row.get('severity'), 'info'))
            body = [row.get('description') or row.get('label'), 'Scope: ' + str((context.get('location') or {}).get(name + '_scope', 'as returned by source; local applicability unconfirmed'))]
            if start and now < start:
                body.append('Upcoming / not yet in force.')
            identity = row.get('url') or row.get('title', '')
            key = name + ':' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            add(key, 'situation', row.get('title', source), body, source, row.get('url', LINKS[name]), sample,
                dict(row, valid_until=end), severity, MAX_AGES[name], name)

    emergency = context.get('emergency') or {}
    rows = emergency.get('items', [])
    feed('gov', emergency, 'situation', 'GOV.UK Emergency Alerts', 'https://www.gov.uk/alerts', rows, 900)
    for row in rows:
        ended = row.get('status') != 'current'
        add('gov:' + row['url'], 'situation', ('TEST / ' if row.get('test') else '') + row.get('area', 'Emergency alert'),
            [row.get('instructions'), row.get('validity'), 'Source status: ' + row.get('status', 'unknown')],
            'GOV.UK Emergency Alerts', row['url'], emergency, row,
            'warning' if not ended and not row.get('test') else 'info', 900, 'gov', expired=ended)

    # One CISA model: the legacy UK "news" slot is KEV, never BBC news.
    kev = security.get('kev') or uk.get('news') or {}
    enriched = {r.get('id'): r for r in (uk.get('news') or {}).get('items', [])}
    if security.get('kev'):
        kev = dict(kev, items=[dict(r, **{k:v for k,v in enriched.get(r.get('id'),{}).items() if k in ('score','severity','cvss_version','score_source','score_cached')}) for r in kev.get('items',[])])
    if not security.get('kev') and records.get('news', {}).get('failed'):
        kev = dict(kev, failed=True)
    for name, sample, source, group, url, window in [
        ('ncsc', uk.get('ncsc') or {}, 'NCSC today', 'cyber', LINKS['ncsc'], None),
        ('kev', kev, 'CISA KEV', 'cyber', LINKS['news'], 30*86400),
        ('php', security.get('php') or {}, 'PHP security advisories', 'cyber', 'https://github.com/php/php-src/security/advisories', 90*86400),
        ('phpnews', security.get('phpnews') or {}, 'PHP releases', 'cyber', 'https://www.php.net/releases/', 90*86400),
        ('grid', uk.get('grid') or {}, 'Elexon', 'infrastructure', 'https://data.elexon.co.uk/bmrs/api/v1/system/warnings', 7*86400),
        ('govuk', uk.get('govuk') or {}, 'GOV.UK briefings', 'situation', 'https://www.gov.uk/search/all', 7*86400)]:
        rows = display_items('ncsc', sample, now) if name == 'ncsc' else [r for r in sample.get('items', [])
            if (published := _stamp(r.get('published', r.get('added')))) is not None and 0 <= now-published <= window]
        age = {'grid': 900, 'kev': 7200}.get(name, 3600)
        feed(name, sample, group, source, url, rows, age)
        for row in rows:
            title = row.get('title') or row.get('summary') or row.get('name') or row.get('id', source)
            body = [row.get('text'), row.get('description'), row.get('summary')]
            if name == 'php': body += ['Fixed versions: '+', '.join(row.get('patches') or ['See vendor advisory'])]
            if name == 'kev':
                body += [row.get('id'), 'Known exploited vulnerability / asset exposure not assessed.', row.get('action')]
            if name in ('php', 'kev'):
                body += ['CVSS: ' + str(row.get('score', 'unavailable')) + ' / assessor: ' + str(row.get('score_source', 'source advisory')),
                         'Source severity: ' + str(row.get('severity', 'unknown'))]
            if name == 'grid':
                from grid_notices import classify
                body.insert(0, classify(row.get('title',''))[0])
                body.append('Bulletin only; validity/cancellation unstructured. No local outage inferred.')
            identity = str(row.get('id') or row.get('url') or title)
            severity = {'critical': 'critical', 'high': 'warning', 'medium': 'advisory'}.get(str(row.get('severity')).lower(), 'info') if name == 'php' else 'info'
            add(name + ':' + identity, group, title, body, source, row.get('url', url), sample,
                dict(row, published=row.get('published', row.get('added'))), severity, age, 'news' if name == 'kev' and not security.get('kev') else name)

    radar = context.get('radar') or {}
    rows = radar.get('items', [])
    feed('radar', radar, 'infrastructure', 'Cloudflare Radar', 'https://radar.cloudflare.com/outage-center', rows, 1800)
    for row in rows:
        identity = '|'.join(str(row.get(k)) for k in ('start', 'provider', 'location', 'scope'))
        add('radar:' + hashlib.sha256(identity.encode()).hexdigest()[:16], 'infrastructure', 'Reported internet outage',
            [row.get('provider'), row.get('location'), row.get('kind'), row.get('scope'), 'Context only; not Pi diagnosis.'],
            'Cloudflare Radar', 'https://radar.cloudflare.com/outage-center', radar, dict(row, published=row.get('start')), age=1800)

    for name in ('scales', 'alerts', 'met'):
        sample = (context.get('space') or {}).get(name) or {}
        source = 'Met Office' if name == 'met' else 'NOAA SWPC'
        rows = [sample] if name == 'met' and sample.get('headline') else sample.get('rows', [])
        feed('space:' + name, sample, 'infrastructure', source, sample.get('url', ''), rows, 21600 if name == 'met' else 900)
        for row in rows:
            body = [row.get('geography'), 'Global context; local grid/GPS impacts not assessed.']
            if name == 'scales':
                body += [axis + ': ' + str(row.get('levels', {}).get(axis, 'unknown')) for axis in 'GRS']
                body.append('Probabilities: ' + str(row.get('probabilities', {})))
            else:
                body.append('Source state: ' + str(row.get('state', 'forecast')))
            identity = str(row.get('id') or (str(row.get('code')) + ':' + str(row.get('serial')) if row.get('code') else row.get('issued'))) + ':' + str(row.get('kind', name))
            if name == 'scales':
                identity += ':' + str(row.get('start'))
            add('space:' + name + ':' + identity, 'infrastructure', row.get('title') or row.get('headline') or 'NOAA ' + row.get('kind', 'scales'), body,
                source, sample.get('url', ''), sample, row,
                ({'warning': 'warning', 'watch': 'advisory'}.get(row.get('kind', '').lower(), 'info') if name == 'alerts' and row.get('state') == 'active' else 'info'),
                21600 if name == 'met' else 900, expired=row.get('state') in ('expired', 'cancelled'))

    weather = context.get('weather') or {}
    if context.get('weather_failed'): weather = dict(weather, failed=True)
    add('conditions', 'situation', 'Local weather conditions',
        ['Temperature: '+str(weather.get('temp','unknown'))+' C', 'High / low: '+str(weather.get('high','unknown'))+' / '+str(weather.get('low','unknown'))+' C'],
        'Open-Meteo', 'https://open-meteo.com/', weather, age=1800, summary=not weather)
    network = context.get('network') or {}
    network = network.get('connection',network)
    add('network', 'node', 'Network checks',
        [network.get('label', 'Unknown'), 'Confirmed offline' if network.get('offline') is True else 'Offline not confirmed',
         'Latency ms: ' + str(network.get('latency', 'unknown'))], 'Local probes', sample=network, age=60, summary=not network)
    motion = context.get('motion') or {}
    add('motion', 'node', 'Camera movement experiment',
        ['Camera: ' + ('available' if motion.get('online') else 'unavailable'), 'Movement state: ' + str(motion.get('state', 'unknown')),
         'Movement is not occupancy; no emergency inference.'], 'Local camera', sample=motion, age=60, summary=not motion)
    telemetry = context.get('telemetry') or {}
    add('telemetry', 'node', 'Local node measurements',
        [key + ': ' + str(telemetry.get(key, 'unknown')) for key in ('cpu', 'memory', 'temperature', 'uptime', 'signal', 'traffic')],
        'Local telemetry', sample=telemetry, age=60, summary=not telemetry)
    if records:
        body=[]
        for name, record in sorted(records.items()):
            body.append(name.upper()+': '+('failed / retained cache' if record.get('failed') else 'last check recorded'))
        add('source-health','node','Source check history',body,'Local check journal',sample={'checked':now})
    planet = _snapshot(context.get('planet'))
    for name, keys, age in [('iss', ('altitude', 'velocity'), 120), ('quakes', ('events',), 1200),
                             ('kp', ('value',), 18000), ('wind', ('value',), 1800), ('doomsday', ('label',), 86400)]:
        sample = planet.get(name) or {}
        add('planet:' + name, 'observatory', name.upper(), [key + ': ' + str(sample.get(key, 'unknown')) for key in keys] +
            (['Symbolic context; not a forecast or local risk level.'] if name == 'doomsday' else ['Background context only.']),
            {'iss': 'Where the ISS at', 'quakes': 'USGS', 'kp': 'NOAA', 'wind': 'NOAA', 'doomsday': 'Bulletin of the Atomic Scientists'}[name],
            sample=sample, row=dict(published=sample.get('observed')), age=age)
    return list(cards.values())


class Rotation:
    """Non-preemptive readable dwell; priority order within fair rounds.

    Every eligible ID is served once per round. Newly arrived cards join the next
    round, bounding starvation even under continuous arrivals. One instance per
    display stream; group changes begin a new round.
    """
    def __init__(self):
        self._group = None
        self._active = None
        self._until = 0
        self._last_now = None
        self._queue = []

    def select(self, cards, now, group=None):
        eligible = {c['id']: c for c in cards if c['duration'] > 0
                    and (c['group'] == group if group is not None else c['group'] != 'observatory')
                    and (c['state']=='info' or c['valid_until'] is None or now < c['valid_until'])}
        if group != self._group or self._last_now is not None and now < self._last_now:
            self._active, self._queue = None, []
        self._group, self._last_now = group, now
        if self._active in eligible and now < self._until:
            return eligible[self._active]
        self._queue = [key for key in self._queue if key in eligible]
        if not self._queue:
            ranks = {'critical': 3, 'warning': 2, 'advisory': 1, 'info': 0}
            self._queue = sorted(eligible, key=lambda key: (-int(eligible[key]['pinned']), -ranks[eligible[key]['severity']], -(eligible[key]['published'] or 0), key))
        if not self._queue:
            self._active = None
            return None
        self._active = self._queue.pop(0)
        card = eligible[self._active]
        self._until = now + card['duration']
        return card
