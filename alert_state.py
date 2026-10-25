"""Persistent source-backed alerts; failed refreshes never imply an all-clear."""
import datetime as dt
import re
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from preparedness import MAX_AGES, LEVELS, LINKS


def weather_window(item):
    """Met Office RSS validity uses UK local time; unknown formats stay explicit."""
    match = re.search(r'valid from (\d{4}) \w{3} (\d{1,2} \w{3}) to (\d{4}) \w{3} (\d{1,2} \w{3})', item.get('description', ''))
    try:
        day = parse_qs(urlparse(item['url']).fragment.lstrip('?'))['date'][0]
        year = dt.date.fromisoformat(day).year
        if not match:
            return None, None
        start = dt.datetime.strptime(f'{year} {match[2]} {match[1]}', '%Y %d %b %H%M').replace(tzinfo=ZoneInfo('Europe/London'))
        end = dt.datetime.strptime(f'{year} {match[4]} {match[3]}', '%Y %d %b %H%M').replace(tzinfo=ZoneInfo('Europe/London'))
        if end < start:
            end = end.replace(year=year+1)
        return start.timestamp(), end.timestamp()
    except (KeyError, ValueError, TypeError):
        return None, None


class AlertState:
    def __init__(self):
        self.sources = {}
        self.seen = set()
        self.new_until = {}

    def update(self, data, errors, now):
        for source in ('weather', 'floods', 'threat'):
            sample = data.get(source)
            fresh = bool(sample) and source not in errors and now-sample['fetched'] <= MAX_AGES[source]
            if sample and (fresh or source not in self.sources):
                rows = []
                if source == 'threat':
                    level = sample['level'].lower()
                    if level in LEVELS and LEVELS.index(level) >= 3:
                        rows = [dict(key='threat', title='UK terrorism threat: '+level.upper(), rank=LEVELS.index(level), url=LINKS['threat'], detail='OFFICIAL NATIONAL ASSESSMENT')]
                else:
                    for item in sample.get('items', []):
                        if source == 'weather':
                            start, end = weather_window(item)
                            if end is not None and now >= end:
                                continue
                            detail = ('UPCOMING' if start and now < start else 'IN FORCE') if end else 'LISTED / CHECK VALIDITY AT SOURCE'
                            if end:
                                detail += ' / UNTIL '+dt.datetime.fromtimestamp(end, ZoneInfo('Europe/London')).strftime('%d %b %H:%M')
                            rank = {'red':5, 'amber':3, 'yellow':1}.get(item.get('colour'), 1)
                        else:
                            start = end = None
                            rank = {1:5, 2:3, 3:1}.get(item.get('severity'), 1)
                            detail = item.get('label', 'FLOOD ALERT').upper()
                        rows.append(dict(key=item.get('url', '')+'|'+item['title'], title=item['title'], rank=rank,
                                         url=item.get('url', LINKS[source]), detail=detail, start=start, end=end))
                previous = {(r['key'], r['rank']) for r in self.sources.get(source, [])}
                for row in rows:
                    signature = (source, row['key'], row['rank'])
                    if fresh and source in self.seen and (row['key'], row['rank']) not in previous:
                        self.new_until[signature] = now+60
                if fresh:
                    self.seen.add(source)
                self.sources[source] = rows
            for row in self.sources.get(source, []):
                row['stale'] = not fresh
        result = []
        for source, rows in self.sources.items():
            for row in rows:
                if row.get('end') and now >= row['end']:
                    continue
                entry = dict(row, source=source)
                entry['new'] = now < self.new_until.get((source, row['key'], row['rank']), 0)
                if row.get('start') and now >= row['start']:
                    entry['detail'] = entry['detail'].replace('UPCOMING', 'IN FORCE')
                result.append(entry)
        self.new_until = {k:v for k,v in self.new_until.items() if v>now}
        return sorted(result, key=lambda r:(r['new'], r['rank']), reverse=True)
