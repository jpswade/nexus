"""Presentation state for the focused desktop; source facts stay with feed parsers."""
from collections import deque
from security import php_priority

UK_NAMES = ('Local situation', 'PHP watch', 'Public briefing', 'World view')


def php_summary(data, now):
    rows = data.get('php', {}).get('items', [])
    ids = {row['id'] for row in data.get('kev', {}).get('items', [])}
    priority = php_priority(rows, ids, now)
    recent = [row for row in rows if 0 <= now-row['published'] < 30*86400]
    return {'available': 'php' in data, 'priority': priority,
            'critical': sum(row.get('severity') == 'critical' for row in recent),
            'kev_ids': ids}


class ChangeLog:
    """Only source changes generate entries; routine polls never replay a feed."""
    def __init__(self):
        self.baselines = {}
        self.events = deque(maxlen=12)
        self.brief_until = 0

    def observe(self, source, records, now):
        if source in self.baselines:
            previous = self.baselines[source]
            for key, (fingerprint, title, urgent, url) in records.items():
                if key not in previous or fingerprint != previous[key][0]:
                    self.events.append({'time': now, 'title': title, 'url': url})
                    if urgent:
                        self.brief_until = now+9
            for key in previous.keys()-records.keys():
                old=previous[key]
                self.events.append({'time':now, 'title':'Left the current feed / '+old[1], 'url':old[3]})
        self.baselines[source] = records

    def update(self, security, uk, alerts, now):
        for source in ('php', 'kev', 'phpnews'):
            if source not in security:
                continue  # A failed/missing source is not an empty successful result.
            rows = security[source].get('items', [])
            records = {}
            for row in rows:
                key = row.get('id') or row.get('url') or row.get('title')
                if source == 'php':
                    fingerprint = (row.get('severity'), row.get('score'), tuple(row.get('patches', [])), row.get('updated'))
                    title = 'PHP / '+row['id']+' / '+row.get('summary', '')
                    urgent = row.get('severity') == 'critical'
                elif source == 'kev':
                    fingerprint = (row.get('added'), row.get('action'))
                    title, urgent = 'CISA KEV / '+row['id']+' added to catalog', True
                else:
                    fingerprint = (row.get('published'), tuple(row.get('cves', [])))
                    title, urgent = 'PHP.net / '+row.get('title', ''), False
                records[key] = (fingerprint, title, urgent, row.get('url'))
            self.observe(source, records, now)
        # Retained stale warnings are not treated as fresh changes.
        for source in ('weather', 'floods'):
            if source not in uk or any(row['stale'] for row in alerts if row['source'] == source):
                continue
            records = {row['key']: ((row['rank'], row['detail']), row['title'], row['rank'] >= 3, row['url'])
                       for row in alerts if row['source'] == source}
            self.observe('alert-'+source, records, now)


def automatic_brief(workspace, age, changes, now):
    """One short scheduled briefing per four-minute cycle, or a material change."""
    return (workspace == 0 and 44 <= age < 53) or changes.brief_until > now
