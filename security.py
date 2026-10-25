"""Read-only vulnerability intelligence; no scanning or asset exposure claims."""
import datetime
import re
from html.parser import HTMLParser
from feeds import PlanetFeeds, timestamp

URLS = {
    'php': 'https://api.github.com/repos/php/php-src/security-advisories?state=published&per_page=100',
    'kev': 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json',
    'phpnews': f'https://www.php.net/archive/{datetime.datetime.now(datetime.timezone.utc).year}.php',
}
INTERVALS = {'php': 900, 'kev': 1800, 'phpnews': 900}
MAX_AGES = {'php': 3600, 'kev': 7200, 'phpnews': 3600}


class PHPNewsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.current = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article' and 'newsItem' in attrs.get('class', '').split():
            self.current = {'title': '', 'body': '', 'published': 0, 'url': 'https://www.php.net/'}
        if self.current is None:
            return
        if tag == 'h2':
            self.in_title = True
        if tag == 'time' and attrs.get('datetime'):
            self.current['published'] = timestamp(attrs['datetime'])
        if tag == 'a' and self.in_title and attrs.get('href', '').startswith('https://www.php.net/'):
            self.current['url'] = attrs['href']

    def handle_endtag(self, tag):
        if tag == 'h2':
            self.in_title = False
        if tag == 'article' and self.current is not None:
            item = self.current
            item['title'] = ' '.join(item['title'].split())
            body = ' '.join(item.pop('body').split())
            item['cves'] = sorted(set(re.findall(r'CVE-\d{4}-\d{4,}', body)))
            # Keep only short source titles and identifiers, never exploit writeups.
            if re.search(r'security|advisory', item['title'], re.I):
                self.items.append(item)
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current['body'] += ' ' + data
            if self.in_title:
                self.current['title'] += data


def parse_security(name, raw):
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if name == 'phpnews':
        parser = PHPNewsParser()
        parser.feed(raw)
        if not parser.items:
            raise ValueError('No PHP security announcements found')
        return {'items': sorted(parser.items, key=lambda r: r['published'], reverse=True)[:8], 'observed': now}
    if name == 'php':
        if not isinstance(raw, list):
            raise ValueError('Invalid PHP advisory response')
        items = []
        for row in raw:
            if row.get('withdrawn_at') or row.get('state', 'published') != 'published':
                continue
            versions = row.get('cvss_severities') or {}
            score, cvss_version = None, None
            for key, label in [('cvss_v4', '4.0'), ('cvss_v3', '3.x')]:
                value = versions.get(key) or {}
                if value.get('score') is not None:
                    score, cvss_version = float(value['score']), label
                    break
            if score is None and (row.get('cvss') or {}).get('score') is not None:
                score, cvss_version = float(row['cvss']['score']), '3.x'
            patches = sorted({v['patched_versions'].strip() for v in row.get('vulnerabilities', []) if v.get('patched_versions')})
            items.append({'id': row.get('cve_id') or row['ghsa_id'], 'ghsa': row['ghsa_id'],
                          'summary': row.get('summary') or 'Security advisory',
                          'severity': row.get('severity') or 'unknown', 'score': score, 'cvss_version': cvss_version,
                          'published': timestamp(row['published_at']),
                          'updated': timestamp(row.get('updated_at') or row['published_at']),
                          'patches': patches, 'url': row['html_url']})
        items.sort(key=lambda item: item['published'], reverse=True)
        return {'items': items, 'observed': now, 'limit': 100}
    if name == 'kev':
        items = []
        for row in raw['vulnerabilities']:
            items.append({'id': row['cveID'], 'vendor': row['vendorProject'], 'product': row['product'],
                          'name': row['vulnerabilityName'], 'added': row['dateAdded'],
                          'due': row.get('dueDate', ''), 'action': row.get('requiredAction', ''),
                          'ransomware': row.get('knownRansomwareCampaignUse', 'Unknown'),
                          'url': 'https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search='+row['cveID']})
        items.sort(key=lambda item: (item['added'], item['id']), reverse=True)
        return {'items': items, 'observed': now, 'catalog_updated': timestamp(raw['dateReleased']), 'count': len(items)}
    raise ValueError('Unknown security feed')


def decode(name, response):
    if name == 'phpnews':
        return response.read().decode('utf-8')
    import json
    return json.load(response)


class SecurityFeeds(PlanetFeeds):
    def __init__(self, directory):
        super().__init__(directory, URLS, INTERVALS, parse_security, decode)


def php_priority(items, kev_ids, now):
    """Prioritise recent critical items and known exploitation without hiding new advisories."""
    recent = [item for item in items if now-item['published'] <= 90*86400]
    pool = recent or items
    return sorted(pool, key=lambda item: (item['id'] in kev_ids,
                  item['severity'] == 'critical', item['published']), reverse=True)
