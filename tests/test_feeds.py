import unittest
from feeds import parse, age_label, timestamp


class FeedParsingTests(unittest.TestCase):
    def test_iss_rejects_invalid_coordinates(self):
        raw = dict(latitude=95, longitude=10, altitude=400, velocity=27000, timestamp=100)
        with self.assertRaises(ValueError):
            parse('iss', raw)

    def test_wind_uses_latest_active_valid_sample(self):
        raw = [
            dict(time_tag='2026-10-25T10:00:00Z', active=True, proton_speed=390),
            dict(time_tag='2026-10-25T10:02:00Z', active=False, proton_speed=999),
            dict(time_tag='2026-10-25T10:03:00Z', active=True, proton_speed=None),
            dict(time_tag='2026-10-25T09:00:00Z', active=True, proton_speed=400),
        ]
        result = parse('wind', raw)
        self.assertEqual(result['value'], 390)
        self.assertEqual(result['observed'], timestamp('2026-10-25T10:00:00Z'))

    def test_kp_accepts_table_and_object_formats(self):
        row = {'time_tag': '2026-10-25T09:00:00', 'Kp': '2.33'}
        self.assertEqual(parse('kp', [row]), parse('kp', [list(row), list(row.values())]))

    def test_bad_solar_data_is_not_displayed_as_zero(self):
        with self.assertRaises(ValueError):
            parse('kp', [{'time_tag': '2026-10-25T09:00:00', 'Kp': 'NaN'}])
        with self.assertRaises(ValueError):
            parse('wind', [])

    def test_quakes_filter_null_magnitudes_and_non_earthquakes(self):
        def feature(mag, when, kind='earthquake'):
            return {'properties': {'mag': mag, 'time': when, 'type': kind, 'place': 'Test region'},
                    'geometry': {'coordinates': [20, 30, 10]}}
        result = parse('quakes', {'metadata': {'generated': 10000}, 'features': [
            feature(None, 9000), feature(4, 7000), feature(5, 8000), feature(3, 9000, 'explosion')]})
        self.assertEqual([e['mag'] for e in result['events']], [5, 4])
        self.assertEqual(result['observed'], 10)

    def test_age_is_based_on_observation_not_fetch_time(self):
        self.assertEqual(age_label(86400), '24h ago')
        self.assertEqual(age_label(-5), '0s ago')
        self.assertEqual(age_label(125), '2m ago')

    def test_explicit_timestamp_offset_is_preserved(self):
        self.assertEqual(timestamp('2026-10-25T10:00:00+01:00'), timestamp('2026-10-25T09:00:00Z'))


if __name__ == '__main__':
    unittest.main()
