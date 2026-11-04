import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from space_weather import (SpaceWeather, parse_alerts, parse_scales, parse_met,
                           alert_states, stamp, fetch, LIMIT)

FIXTURES = Path(__file__).parent/'fixtures'/'space_weather'
NOW = stamp('2026-11-04T12:00:00Z')


def fixture(name):
    text = (FIXTURES/(name+('.html' if name == 'met' else '.json'))).read_text()
    return text if name == 'met' else json.loads(text)


class Parsing(unittest.TestCase):
    def test_separate_scales_and_forecast_probabilities(self):
        rows = parse_scales(fixture('scales'))['rows']
        self.assertEqual(rows[0]['levels'], {'G': 2, 'R': 0, 'S': None})
        self.assertEqual(rows[1]['kind'], 'forecast')
        self.assertIsNone(rows[1]['levels']['R'])
        self.assertEqual(rows[1]['probabilities']['RMinorProb'], 25)
        self.assertEqual(rows[1]['end']-rows[1]['start'], 86400)

    def test_invalid_scales_fail_closed(self):
        raw = fixture('scales'); raw['0']['G']['Scale'] = '6'
        with self.assertRaises(ValueError): parse_scales(raw)
        with self.assertRaises(ValueError): parse_scales({})

    def test_bulletins_unordered_cancellation_test_observation(self):
        rows = parse_alerts(fixture('alerts'))['rows']
        expected = {'1':'superseded', '2':'cancelled', '3':'cancelled', '4':'test',
                    '5':'historical observation', '6':'validity unknown', '7':'expired', '8':'upcoming'}
        for order in (rows, list(reversed(rows))):
            self.assertEqual({r['serial']:r['state'] for r in alert_states(order, NOW)}, expected)

    def test_expiry_recomputed_without_fetch(self):
        rows = parse_alerts(fixture('alerts')[:1])['rows']
        self.assertEqual(alert_states(rows, NOW)[0]['state'], 'active')
        self.assertEqual(alert_states(rows, stamp('2026-11-04T13:00:00Z'))[0]['state'], 'expired')

    def test_future_cancellation_does_not_cancel_earlier(self):
        rows = parse_alerts(fixture('alerts')[:3])['rows']
        states = {r['serial']:r['state'] for r in alert_states(rows, stamp('2026-11-04T11:15:00Z'))}
        self.assertEqual(states['2'], 'active')

    def test_watch_year_rollover_and_cross_code_supersession(self):
        raw = fixture('alerts')[0]
        raw['issue_datetime'] = '2026-12-31 12:00:00'
        raw['message'] = 'Space Weather Message Code: WATA20\nSerial Number: 1\nWATCH: G1 predicted\nDec 31: G1 (Minor) Jan 01: G1 (Minor)\nTHIS SUPERSEDES ANY/ALL PRIOR WATCHES IN EFFECT'
        parsed = parse_alerts([raw])['rows'][0]
        self.assertEqual(parsed['end'], stamp('2027-01-02T00:00:00Z'))
        older = dict(parsed, code='WATA30', serial='9', issued=parsed['issued']-3600)
        states = {r['serial']:r['state'] for r in alert_states([parsed, older], parsed['issued']+1)}
        self.assertEqual(states, {'1':'active', '9':'superseded'})

    def test_empty_and_malformed_alerts(self):
        self.assertEqual(parse_alerts([]), {'rows': []})
        with self.assertRaises(ValueError): parse_alerts({})
        with self.assertRaises(KeyError): parse_alerts([{'message':'bogus'}])

    def test_met_uses_forecast_stamp_not_image_stamp(self):
        parsed = parse_met(fixture('met'))
        self.assertEqual(parsed['issued'], stamp('2026-11-04T09:00:00Z'))
        self.assertEqual(parsed['kind'], 'forecast')
        self.assertEqual(parsed['end']-parsed['issued'], 4*86400)

    def test_met_bst_and_changed_schema(self):
        parsed = parse_met(fixture('met').replace('(GMT)', '(BST)'))
        self.assertEqual(parsed['issued'], stamp('2026-11-04T08:00:00Z'))
        with self.assertRaises(ValueError): parse_met('<html>Maintenance</html>')


class Cache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = NOW
        self.calls = []
        self.fail = False

    def fetcher(self, name):
        self.calls.append(name)
        if self.fail: raise OSError('offline')
        return fixture(name)

    def service(self):
        return SpaceWeather(self.temp.name, self.fetcher, lambda:self.now)

    def test_initial_unavailable_no_network_on_snapshot(self):
        self.assertEqual(self.service().snapshot()['scales']['status'], 'unavailable')
        self.assertEqual(self.calls, [])

    def test_shared_cache_rate_limit_and_failure_survives_restart(self):
        service = self.service(); service.refresh()
        self.assertEqual(len(self.calls), 3)
        other = self.service(); other.refresh()
        self.assertEqual(len(self.calls), 3)
        self.fail = True; self.now += 3600; other.refresh()
        snap = self.service().snapshot()
        self.assertEqual(snap['scales']['status'], 'stale')
        self.assertEqual(snap['met']['status'], 'stale')
        self.assertEqual(snap['scales']['rows'][0]['levels']['G'], 2)
        self.assertEqual(snap['scales']['fetched'], NOW)
        self.assertTrue(snap['scales']['failed'])

    def test_old_source_stamp_is_stale_even_after_successful_fetch(self):
        self.now += 2*86400
        service = self.service(); service.refresh()
        self.assertEqual(service.snapshot()['scales']['status'], 'stale')
        self.assertEqual(service.snapshot()['met']['status'], 'stale')

    def test_empty_success_distinct_from_failure(self):
        service = SpaceWeather(self.temp.name, lambda name: [] if name == 'alerts' else fixture(name), lambda:self.now)
        service.refresh()
        self.assertEqual(service.snapshot()['alerts']['status'], 'empty')
        self.assertEqual(service.snapshot()['scales']['status'], 'checked')

    def test_malformed_replacement_retains_previous(self):
        service = self.service(); service.refresh(); self.now += 3600
        service.fetcher = lambda name: {}
        service.refresh()
        self.assertEqual(service.snapshot()['scales']['status'], 'stale')
        self.assertEqual(service.snapshot()['scales']['rows'][0]['levels']['G'], 2)

    def test_corrupt_cache_is_unavailable(self):
        Path(self.temp.name, 'scales.json').write_text('{bad')
        self.assertEqual(self.service().snapshot()['scales']['status'], 'unavailable')

    def test_process_lock_skips_duplicate_inflight_refresh(self):
        import fcntl
        service = self.service()
        with Path(self.temp.name, 'refresh.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            service.refresh()
        self.assertEqual(self.calls, [])
        service.refresh()
        self.assertEqual(len(self.calls), 3)

    def test_fetch_limits_size_and_timeout(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                self.size = size
                return b'x' * size
        response = Response()
        with patch('space_weather.urllib.request.urlopen', return_value=response) as opened:
            with self.assertRaises(ValueError): fetch('scales')
            self.assertEqual(response.size, LIMIT+1)
            self.assertEqual(opened.call_args.kwargs['timeout'], 8)


if __name__ == '__main__':
    unittest.main()
