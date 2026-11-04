import copy
import datetime as dt
import json
from pathlib import Path
import unittest

from briefing_policy import Rotation, build_cards

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/briefing_policy/scenarios.json').read_text())
NOW = FIXTURES['now']
SCENARIOS = FIXTURES['scenarios']


def indexed(context, now=NOW):
    return {c['id']: c for c in build_cards(context, now)}


def warning(context, now=NOW):
    return next(c for c in build_cards(context, now) if c['id'].startswith('weather:') and c['id'] != 'weather:check')


class PolicyTests(unittest.TestCase):
    def test_contract_all_synthetic_states_and_no_mutation(self):
        for name, context in SCENARIOS.items():
            with self.subTest(name=name):
                before = copy.deepcopy(context)
                cards = build_cards(context, NOW)
                self.assertEqual(context, before)
                self.assertEqual(cards, build_cards(context, NOW))
                self.assertEqual(len(cards), len({c['id'] for c in cards}))
                json.dumps(cards, allow_nan=False)
                for c in cards:
                    self.assertEqual(set(c), set('id group title body source url published checked valid_until state severity pinned duration'.split()))
                    self.assertIn(c['group'], ('situation', 'cyber', 'infrastructure', 'node', 'observatory'))
                    self.assertIn(c['state'], ('current', 'stale', 'unavailable', 'info'))
                    self.assertIn(c['severity'], ('info', 'advisory', 'warning', 'critical'))
                    self.assertIsInstance(c['pinned'], bool)
                    self.assertTrue(all(isinstance(line, str) for line in c['body']))

    def test_quiet_unknown_failed_are_distinct(self):
        self.assertEqual(indexed({})['weather:check']['state'], 'unavailable')
        quiet = indexed(SCENARIOS['quiet'])['weather:check']
        self.assertEqual((quiet['state'], quiet['duration']), ('current', 0))
        failed = indexed(SCENARIOS['failed_feed'])['ncsc:check']
        self.assertEqual((failed['state'], failed['checked'], failed['severity']), ('unavailable', NOW, 'info'))
        self.assertEqual(failed['duration'], 0)  # Failure stays in checks/details, not empty rotation.

    def test_retained_warning_and_expiry(self):
        fresh = warning(SCENARIOS['new_warning'])
        stale = warning(SCENARIOS['stale_warning'])
        self.assertEqual(fresh['id'], stale['id'])
        self.assertEqual((stale['state'], stale['severity'], stale['pinned']), ('stale', 'warning', True))
        self.assertIsNone(stale['valid_until'])
        expired = warning(SCENARIOS['expiry'])
        self.assertEqual((expired['state'], expired['severity'], expired['pinned']), ('info', 'info', False))
        self.assertIsNone(Rotation().select([expired], NOW))

    def test_threat_provenance_no_synthesized_level(self):
        card = indexed(SCENARIOS['conflicting_threat'])['threat']
        self.assertIn('GOV.UK: SUBSTANTIAL', card['body'])
        self.assertIn('MI5: SEVERE', card['body'])
        self.assertEqual(card['severity'], 'info')
        sample = {'fetched': NOW, 'level': 'SEVERE', 'source_name': 'MI5'}
        card = indexed({'uk': ({'threat': sample}, {'threat'})})['threat']
        self.assertEqual(card['state'], 'stale')
        self.assertIn('fallback', ' '.join(card['body']))

    def test_ncsc_uk_day_dates_and_cisa_dedup(self):
        now = dt.datetime(2026, 7, 2, 0, 30, tzinfo=dt.timezone.utc).timestamp()
        items = [{'title': str(i), 'url': 'https://example.org/' + str(i), 'published': stamp}
                 for i, stamp in enumerate((now-3600, now-7200, None, now+60))]
        sample = {'items': items, 'fetched': now, 'item_dates': True}
        cards = build_cards({'uk': {'ncsc': sample}}, now)
        articles = [c for c in cards if c['source'] == 'NCSC today']
        self.assertEqual([c['title'] for c in articles], ['0'])
        self.assertIsNone(articles[0]['valid_until'])
        kev = {'fetched': NOW, 'items': [{'id': 'CVE-2026-0001', 'name': 'Synthetic', 'added': '2026-11-04'}]}
        cards = build_cards({'security': {'kev': kev}, 'uk': {'news': kev}}, NOW)
        self.assertEqual(len([c for c in cards if c['source'] == 'CISA KEV']), 1)
        self.assertNotIn('BBC', str(cards))

    def test_camera_and_network_never_escalate_or_expose_configuration(self):
        for name in ('offline', 'recovery', 'camera_loss', 'camera_movement'):
            context = copy.deepcopy(SCENARIOS[name])
            context.setdefault('motion', {})['capture_url'] = 'PRIVATE_SENTINEL'
            context['motion']['error'] = 'PRIVATE_SENTINEL'
            cards = indexed(context)
            self.assertNotIn('PRIVATE_SENTINEL', str(cards))
            for key in ('motion', 'network'):
                self.assertEqual(cards[key]['severity'], 'info')
                self.assertFalse(cards[key]['pinned'])
            self.assertGreater(cards['motion']['duration'], 0)
        self.assertIn('Confirmed offline', indexed(SCENARIOS['offline'])['network']['body'])
        self.assertNotIn('Confirmed offline', indexed(SCENARIOS['recovery'])['network']['body'])

    def test_source_records_and_future_checks(self):
        context = copy.deepcopy(SCENARIOS['new_warning'])
        context['source_records'] = {'weather': {'failed': True, 'attempted': NOW+1}}
        self.assertEqual(warning(context)['state'], 'stale')
        context.pop('source_records')
        context['uk']['weather']['fetched'] = NOW+1
        self.assertEqual(warning(context)['state'], 'stale')

    def test_long_body_readable_and_unstructured_grid_not_warning(self):
        card = indexed(SCENARIOS['long_text'])['grid:synthetic-grid']
        self.assertGreater(card['duration'], 25)
        self.assertEqual(card['severity'], 'info')
        self.assertIsNone(card['valid_until'])
        self.assertIn('validity/cancellation unstructured', ' '.join(card['body']))

    def test_emergency_test_withdrawal_expiry(self):
        for status, test, expires, severity in [('current', False, NOW+10, 'warning'),
                ('current', True, NOW+10, 'info'), ('withdrawn', False, None, 'info'),
                ('current', False, NOW, 'info')]:
            row = dict(url='https://www.gov.uk/alerts/example', status=status, test=test, expires=expires)
            card = indexed({'emergency': {'fetched': NOW, 'items': [row]}})['gov:' + row['url']]
            self.assertEqual(card['severity'], severity)

    def test_distinct_space_forecasts_and_failed_legacy_kev(self):
        rows = [dict(kind='forecast', issued=NOW, start=NOW+i*86400,
                     end=NOW+(i+1)*86400, levels={'G': i}) for i in range(3)]
        cards = build_cards({'space': {'scales': {'fetched': NOW, 'rows': rows}}}, NOW)
        self.assertEqual(len([c for c in cards if c['id'].startswith('space:scales:')]), 3)
        cards = indexed({'uk': {'news': {'fetched': NOW, 'items': []}},
                         'source_records': {'news': {'failed': True}}})
        self.assertEqual(cards['kev:check']['state'], 'stale')
        cards = indexed({'space': {'met': {'fetched': NOW, 'status': 'unavailable'}}})
        self.assertEqual(cards['space:met:check']['state'], 'unavailable')

    def test_space_warning_and_background_not_local_risk(self):
        sample = {'fetched': NOW, 'rows': [dict(id='one', kind='warning', state='active', issued=NOW, end=NOW+100)]}
        cards = build_cards({'space': {'alerts': sample}}, NOW)
        card = next(c for c in cards if c['id'] == 'space:alerts:one:warning')
        self.assertTrue(card['pinned'])
        self.assertIn('local grid/GPS impacts not assessed', ' '.join(card['body']))


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.warning = warning(SCENARIOS['new_warning'])
        self.quiet = indexed(SCENARIOS['recovery'])['network']

    def test_dwell_survives_reordering_refresh_and_new_arrival(self):
        rotation = Rotation()
        self.assertEqual(rotation.select([self.quiet], NOW)['id'], 'network')
        refreshed = dict(self.quiet, checked=NOW+1, duration=200)
        self.assertEqual(rotation.select([self.warning, refreshed], NOW+1)['id'], 'network')
        self.assertEqual(rotation.select([self.warning, refreshed], NOW+self.quiet['duration'])['id'], self.warning['id'])

    def test_priority_and_no_starvation_with_continuous_arrivals(self):
        rotation = Rotation()
        cards = [self.quiet, self.warning]
        self.assertEqual(rotation.select(cards, NOW)['id'], self.warning['id'])
        cards.append(dict(self.warning, id='new-warning'))
        self.assertEqual(rotation.select(cards, NOW+self.warning['duration'])['id'], 'network')

    def test_group_switch_removal_backwards_clock_and_observatory(self):
        obs = indexed({})['planet:iss']
        rotation = Rotation()
        self.assertIsNone(rotation.select([obs], NOW))
        self.assertEqual(rotation.select([obs], NOW, 'observatory')['id'], obs['id'])
        self.assertEqual(rotation.select([self.quiet], NOW, 'node')['id'], 'network')
        self.assertIsNone(rotation.select([], NOW+1, 'node'))
        self.assertEqual(rotation.select([self.warning, self.quiet], NOW-10)['id'], self.warning['id'])

    def test_expiry_interrupts_dwell_and_summary_excluded(self):
        rotation = Rotation()
        card = dict(self.warning, valid_until=NOW+1)
        self.assertEqual(rotation.select([card, self.quiet], NOW)['id'], card['id'])
        self.assertEqual(rotation.select([card, self.quiet], NOW+1)['id'], 'network')
        self.assertIsNone(Rotation().select([dict(self.quiet, duration=0)], NOW))


if __name__ == '__main__':
    unittest.main()
