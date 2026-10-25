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
