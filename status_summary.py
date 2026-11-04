"""Compact cached-source summaries shared by both physical displays."""
from preparedness import MAX_AGES


def summary(name, data, now, errors=()):
    sample = data.get(name)
    if not sample:
        return 'UNAVAILABLE'
    stale = name in errors or now-sample['fetched'] > MAX_AGES[name]
    if name == 'threat':
        value = sample['level'].upper()
    elif name == 'weather':
        items = sample.get('items', [])
        rank = {'red': 3, 'amber': 2, 'yellow': 1}
        highest = max((str(item.get('colour', '')).lower() for item in items),
                      key=lambda colour: rank.get(colour, 0), default='')
        value = f'{len(items)} BULLETINS' if items else 'NONE RETURNED'
        if highest in rank:
            value = highest.upper()+f' / {len(items)}'
    else:
        value = f"{len(sample.get('items', []))} ALERTS"
    return value+(' [STALE]' if stale else '')


def live_checks(data, emergency, now, errors=(), alerts=()):
    """Check health and source results, never a combined emergency severity."""
    from emergency_alerts import presentation
    from grid_notices import MAX_AGE as GRID_AGE, WINDOW
    _, rows, stale = presentation(emergency, now)
    current = [r for r in rows if r['status'] == 'current']
    real = sum(not r.get('test', False) for r in current)
    tests = len(current)-real
    value = f'{real} LISTED' if real else f'{tests} TEST' if tests else 'NONE LISTED'
    gov = ('GOV.UK', 'UNREADABLE' if emergency.get('failed') else 'NOT CHECKED', 'unknown') if emergency.get('fetched') is None else ('GOV.UK', 'STALE' if stale else value, 'stale' if stale else 'alert' if real else 'ok')
    grid = data.get('grid') or {}
    fetched = grid.get('fetched')
    if fetched is None:
        grid_check = ('GRID', 'UNREADABLE', 'unknown')
    elif grid.get('failed') or not 0 <= now-fetched <= GRID_AGE:
        grid_check = ('GRID', 'STALE', 'stale')
    else:
        count = sum(0 <= now-r['published'] <= WINDOW for r in grid.get('items', []))
        grid_check = ('GRID', f'{count} BULLETINS', 'ok')
    result = [gov, grid_check]
    for source, label in [('weather', 'WEATHER'), ('floods', 'FLOODS')]:
        sample = data.get(source)
        if not sample:
            result.append((label, 'UNREADABLE', 'unknown'))
        elif source in errors or sample.get('failed') or not 0 <= now-sample['fetched'] <= MAX_AGES[source]:
            result.append((label, 'STALE', 'stale'))
        else:
            count = sum(a['source'] == source for a in alerts)
            result.append((label, f'{count} LISTED' if count else 'NONE LISTED', 'alert' if count else 'ok'))
    return result
