"""Readable terminal briefings, with one primary subject per screen."""
import datetime
import textwrap
from feeds import age_label
from security import MAX_AGES, php_priority


class SecurityDesktop:
    def __init__(self, ui):
        self.u = ui

    def wrap(self, value, x, y, width=82, size=24, color=None, lines=3):
        for i, row in enumerate(textwrap.wrap(str(value), width)[:lines]):
            self.u.text(row, x, y+i*(size+8), size, color or self.u.TEXT)

    def freshness(self, name, data, errors, now):
        sample = data.get(name)
        if not sample:
            return 'UNAVAILABLE / RETRYING' if name in errors else 'CONNECTING'
        age = now-sample['fetched']
        return ('STALE / ' if name in errors or age > MAX_AGES[name] else 'CHECKED / ')+age_label(age).upper()

    def source_status(self, data, errors, now):
        for x, name, label in [(48, 'php', 'PHP'), (450, 'kev', 'CISA'), (850, 'phpnews', 'PHP.NET')]:
            status = self.freshness(name, data, errors, now)
            self.u.text(label+' / '+status, x, 624, 18,
                        self.u.AMBER if status.startswith(('STALE', 'UNAVAILABLE')) else self.u.DIM)

    def draw(self, index, age, data, errors, now):
        u = self.u
        php = data.get('php', {}).get('items', [])
        kev = data.get('kev', {}).get('items', [])
        ids = {r['id'] for r in kev}
        priority = php_priority(php, ids, now)
        notices = data.get('phpnews', {}).get('items', [])
        fresh = [r for r in php if 0 <= now-r['published'] < 30*86400]
        critical = [r for r in fresh if r['severity'] == 'critical']
        u.panel(28, 105, 1224, 551,
                ['01 / SECURITY BRIEF', '02 / PHP ADVISORY', '03 / EXPLOITED IN THE WILD'][index],
                'PUBLIC SOURCES / READ ONLY')
        if index == 0:
            u.text('PHP / LAST 30 DAYS', 48, 160, 20, u.DIM)
            u.text(f'{len(critical):02d} CRITICAL' if 'php' in data else '-- CRITICAL', 48, 190, 42, u.AMBER)
            u.text(f'{len(fresh)} ADVISORIES' if 'php' in data else 'AWAITING PHP', 500, 202, 26, u.TEXT)
            u.text(f'{len(kev)} IN KEV' if 'kev' in data else 'AWAITING CISA', 1230, 202, 26, u.TEXT, True)
            u.line((48, 252), (1230, 252))
            u.text('PRIORITY ADVISORY', 48, 275, 20, u.DIM)
            if priority:
                row = priority[0]
                u.text(row['id'], 48, 309, 38, u.TEXT)
                u.text(row['severity'].upper(), 1230, 319, 26, u.AMBER, True)
                self.wrap(row['summary'], 48, 365, width=83, size=26, lines=3)
                self.wrap('FIXED: '+(' / '.join(row['patches']) or 'See vendor advisory'), 48, 478, size=22, lines=2)
            else:
                u.text(self.freshness('php', data, errors, now), 48, 324, 30, u.DIM)
            u.text('ADVISORY WATCH / NO FLEET OR PACKAGE INVENTORY', 48, 580, 20, u.DIM)
        elif index == 1:
            # Alternate a full advisory with a full announcement; never stack windows.
            count = len(priority)+len(notices)
            selected = int(age/12) % count if count else 0
            if selected < len(priority):
                row = priority[selected]
                u.text(row['id'], 48, 163, 40, u.TEXT)
                u.text(f'{selected+1}/{count}', 1230, 177, 24, u.DIM, True)
                score = f'CVSS {row["cvss_version"]}: {row["score"]:.1f}' if row['score'] is not None else 'CVSS NOT SUPPLIED'
                u.text(row['severity'].upper()+' / '+score, 48, 224, 26, u.AMBER)
                self.wrap(row['summary'], 48, 279, width=83, size=26, lines=3)
                self.wrap('FIXED: '+(' / '.join(row['patches']) or 'See vendor advisory'), 48, 399, size=24, lines=2)
                status = 'CISA KEV / KNOWN EXPLOITED' if row['id'] in ids else 'CISA CATALOG / NO MATCH' if 'kev' in data else 'CISA KEV / UNAVAILABLE'
                u.text(status, 48, 490, 24, u.AMBER if row['id'] in ids else u.DIM)
                u.text(row['ghsa']+' / PHP-SRC', 48, 548, 20, u.DIM)
            elif notices:
                item = notices[selected-len(priority)]
                u.text('PHP.NET / FOLLOW-UP GUIDANCE', 48, 166, 30, u.TEXT)
                self.wrap(item['title'], 48, 233, width=78, size=28, lines=4)
                self.wrap(' / '.join(item['cves']), 48, 420, size=24, lines=2)
                u.text(datetime.datetime.fromtimestamp(item['published']).strftime('%d %b %Y'), 48, 532, 24, u.DIM)
            else:
                u.text('AWAITING PHP ADVISORIES', 48, 200, 32, u.DIM)
        else:
            # Cycle catalog pages, four readable entries per page.
            pages = max(1, (len(kev)+3)//4)
            page = int(age/12) % pages
            u.text(f'RECENT CATALOG ADDITIONS / PAGE {page+1}', 48, 158, 22, u.DIM)
            for i, row in enumerate(kev[page*4:page*4+4]):
                y = 205+i*87
                u.text(row['id'], 48, y, 28, u.AMBER)
                u.text('ADDED '+row['added'], 1230, y, 22, u.DIM, True)
                self.wrap(row['vendor']+' / '+row['product'], 48, y+37, width=95, size=22, lines=1)
            if not kev:
                u.text(self.freshness('kev', data, errors, now), 48, 225, 30, u.DIM)
            u.text('CATALOG RECORDS / NOT LIVE ATTACK VOLUME / FOLLOW VENDOR GUIDANCE', 48, 580, 18, u.DIM)
        self.source_status(data, errors, now)

    def terminal(self, index, age, data, errors, now, key, forced=False):
        u = self.u
        u.panel(28, 105, 1224, 551, 'NEXUS / SYSTEM BRIEFING', 'T TO RETURN')
        php = data.get('php', {}).get('items', [])
        kev = data.get('kev', {}).get('items', [])
        rows = [
            '> NEXUS BRIEF --PUBLIC-ADVISORIES',
            '',
            f'PHP ADVISORIES LOADED : {len(php) if "php" in data else "UNAVAILABLE"}',
            f'CISA EXPLOITED CATALOG: {len(kev) if "kev" in data else "UNAVAILABLE"}',
            '',
            'SCOPE: ADVISORY WATCH. NO FLEET OR PACKAGE INVENTORY.',
            'FOLLOW VENDOR GUIDANCE FOR YOUR INSTALLED VERSIONS.',
            '',
            '> BACKGROUND REFRESH ACTIVE',
        ]
        # Brief reveal on entry; no continuously scrolling text or flicker.
        visible = '\n'.join(rows)[:int(max(0, age-7.65)*400)]
        for i, row in enumerate(visible.split('\n')):
            u.text(row, 48, 166+i*40, 25, u.TEXT)
        if int(age*2) % 2:
            u.text('█', 48, 552, 26, u.TEXT)
        self.source_status(data, errors, now)
