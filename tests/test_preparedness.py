import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from preparedness import PreparednessFeeds, build_sources, parse_feed, source_status
from preparedness_ui import midnight_remaining

ROOT = Path(__file__).resolve().parents[1]


def national_body(level='substantial'):
    return {'details': {'parts': [{'slug': 'terrorism-threat-levels', 'body':
        f'<p>The threat to the UK (England, Wales, Scotland and Northern Ireland) from terrorism is <strong>{level}</strong>.</p>'
        '<p>The threat to Northern Ireland from Northern Ireland-related terrorism is severe.</p>'}]}}


class PreparednessTests(unittest.TestCase):
    def test_uk_level_is_not_northern_ireland_level(self):
        self.assertEqual(parse_feed('threat', national_body())['level'], 'SUBSTANTIAL')
        with self.assertRaises(ValueError):
            parse_feed('threat', national_body('unknown'))
        body = national_body()
        body['details']['parts'][0]['body'] = '<p>National threat level definitions: low moderate severe critical</p>'
        with self.assertRaises(ValueError):
            parse_feed('threat', body)

    def test_floods_exclude_ended_warnings_and_reject_missing_data(self):
        row = {'severityLevel': 2, 'description': 'Test river', 'severity': 'Flood warning',
               'floodAreaID': 'ABC123', 'timeMessageChanged': '2026-10-25T10:00:00'}
        result = parse_feed('floods', {'items': [row, {**row, 'severityLevel': 4}]})
        self.assertEqual(len(result['items']), 1)
        self.assertTrue(result['items'][0]['url'].endswith('/ABC123'))
        self.assertIn('/target-area/', result['items'][0]['url'])
        with self.assertRaises(ValueError):
            parse_feed('floods', {})
        self.assertEqual(parse_feed('floods', {'items': []})['items'], [])

    def test_rss_reports_and_warning_bulletins_keep_source_links(self):
        rss = '''<rss><channel><pubDate>Sun, 25 Oct 2026 10:00:00 GMT</pubDate>
        <item><title>Amber warning of wind affecting North West England</title><link>https://www.metoffice.gov.uk/warning</link></item>
        </channel></rss>'''
        item = parse_feed('weather', rss)['items'][0]
        self.assertEqual(item['colour'], 'amber')
        self.assertIsNotNone(item['published'])
        self.assertEqual(item['url'], 'https://www.metoffice.gov.uk/warning')
        with self.assertRaises(ValueError):
            parse_feed('weather', '<html><body>Unavailable</body></html>')
        with self.assertRaises(ValueError):
            parse_feed('weather', rss.replace('Amber warning', 'Changed structure'))
        self.assertEqual(parse_feed('weather', '<rss><channel/></rss>')['items'], [])
        news = '<rss><channel><item><title>Cyber attack reported by company</title><link>javascript:bad()</link></item><item><title>Football result</title></item></channel></rss>'
        items = parse_feed('news', news)['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['url'], 'https://www.bbc.co.uk/news/uk')

    def test_local_scope_and_cache_identity_change_with_coordinates(self):
        config = {'latitude': 52, 'longitude': -2, 'preparedness': {
            'weather_region': 'nw', 'nation': 'england', 'local_alerts': True, 'flood_radius_km': 25}}
        urls, scope, flood_scope = build_sources(config)
        self.assertEqual(scope, 'North West England')
        self.assertIn('lat=52.0', urls['floods'])
        self.assertIn('approx 25 km', flood_scope)
        with tempfile.TemporaryDirectory() as directory:
            first = PreparednessFeeds(directory, config)
            second = PreparednessFeeds(directory, {**config, 'latitude': 53})
            self.assertNotEqual(first.directory, second.directory)
        config['preparedness']['nation'] = 'scotland'
        self.assertNotIn('floods', build_sources(config)[0])
        config['preparedness']['weather_region'] = 'invalid'
        with self.assertRaises(ValueError):
            build_sources(config)

    def test_failed_refresh_preserves_data_and_marks_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = PreparednessFeeds(directory, {})
            sample = {'level': 'MODERATE', 'fetched': time.time()}
            feed.data['threat'] = sample
            with patch('urllib.request.urlopen', side_effect=OSError('offline')):
                self.assertFalse(feed.refresh('threat'))
            data, errors = feed.snapshot()
            self.assertEqual(data['threat'], sample)
            self.assertTrue(source_status('threat', data, errors, time.time()).startswith('STALE'))
            self.assertEqual(source_status('news', {}, {'news'}, time.time()), 'UNAVAILABLE')

    def test_midnight_uses_real_elapsed_time_across_dst(self):
        tz = ZoneInfo('Europe/London')
        self.assertEqual(midnight_remaining(dt.datetime(2026, 10, 25, 0, 0, tzinfo=tz)), '25:00:00')
        self.assertEqual(midnight_remaining(dt.datetime(2026, 3, 29, 0, 0, tzinfo=tz)), '23:00:00')
        self.assertEqual(midnight_remaining(dt.datetime(2026, 10, 26, 23, 59, 30, tzinfo=tz)), '00:00:30')

    def test_all_uk_screens_render_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, 'NEXUS_CONFIG': str(ROOT/'config.example.json'), 'NEXUS_CACHE': directory}
            feed = PreparednessFeeds(Path(directory)/'preparedness', {})
            for populated in (False, True):
                if populated:
                    now = time.time()
                    samples = {'threat': {'level': 'MODERATE', 'updated': '2026-10-01T00:00:00Z'},
                               'weather': {'items': [{'title': 'Amber warning of wind affecting a demo region', 'url': 'https://www.metoffice.gov.uk/', 'colour': 'amber', 'published': now}]},
                               'floods': {'items': [{'title': 'Demo flood area', 'label': 'Severe flood warning', 'severity': 1, 'url': 'https://www.gov.uk/', 'updated': '2026-10-25T10:00:00'}]},
                               'news': {'items': [{'title': 'Demo reported incident', 'url': 'https://www.bbc.co.uk/', 'published': now}]},
                               'ncsc': {'items': [{'title': 'Demo official publication', 'url': 'https://www.ncsc.gov.uk/', 'published': now}]}}
                    for name, sample in samples.items():
                        (feed.directory/f'{name}.json').write_text(json.dumps({**sample, 'source': feed.urls[name], 'fetched': now}))
                for workspace, age in [(1, 3), (2, 3), (2, 16), (3, 3), (4, 3)]:
                    result = subprocess.run([sys.executable, 'dashboard.py', '--profile', 'uk', '--snapshot',
                                             str(Path(directory)/'frame.png'), '--workspace', str(workspace), '--age', str(age)],
                                            cwd=ROOT, env=env, capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
