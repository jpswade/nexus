"""Recorded GOV.UK HTML structure plus clearly synthetic current-alert fixtures."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import pygame
from emergency_alerts import (CURRENT, EmergencyAlerts, MAX_ALERTS, MAX_AGE,
                              parse_index, parse_detail, presentation, timestamp, official, fetch)
from emergency_alerts_ui import panel

FIXTURES = Path(__file__).parent / 'fixtures/emergency'
NOW = timestamp('2026-11-04T11:00:00+00:00')
URL = 'https://www.gov.uk/alerts/example'


def fixture(name): return (FIXTURES / (name + '.html')).read_text()


class AdapterTests(unittest.TestCase):
    def test_live_empty_and_past_structure(self):
        self.assertEqual(parse_index(fixture('current-empty')), [])
        row = parse_detail(fixture('past-cornwall'), URL)
        self.assertEqual(row['status'], 'past')
        self.assertEqual(row['area'], 'Cornwall')
        self.assertFalse(row['test'])
        self.assertGreater(row['stopped'], row['issued'])
        self.assertIsNone(row['expires'])  # Broadcast end is not hazard expiry.
        self.assertEqual(row['validity'], 'Validity not published')
        self.assertTrue(parse_detail(fixture('past-test'), URL)['test'])

    def test_current_test_and_missing_fields(self):
        self.assertEqual(parse_index(fixture('current')), [URL])
        row = parse_detail(fixture('active'), URL)
        self.assertEqual(row['area'], 'Example region')
        self.assertEqual(row['status'], 'current')
        test = fixture('active').replace('Stay indoors.', 'This is a test of Emergency Alerts.')
        self.assertTrue(parse_detail(test, URL)['test'])
        row = parse_detail(fixture('expired'), URL)
        self.assertEqual(row['area'], 'Area not published')
        self.assertIsNone(row['issued'])
        status, rows, stale = presentation(dict(fetched=NOW, items=[row]), NOW)
        self.assertEqual(rows[0]['status'], 'expired')
        self.assertEqual(parse_detail(fixture('cancelled'), URL)['status'], 'cancelled')

    def test_unreadable_and_ambiguous_are_not_empty(self):
        for html in [fixture('blocked'), '<main><h1>Current alerts</h1></main>',
                     fixture('current').replace('/alerts/example', 'https://evil.example/alerts/example'),
                     fixture('current').replace('</main>', '<p>There are no current alerts.</p></main>'),
                     fixture('current')[:-8]]:
            with self.subTest(html=html[:30]), self.assertRaises(ValueError): parse_index(html)
        for url in ['http://www.gov.uk/alerts/x', 'https://www.gov.uk.evil/alerts/x',
                    'https://www.gov.uk/alerts/x?q=y', 'https://www.gov.uk:443/alerts/x']:
            self.assertFalse(official(url))
        with self.assertRaises(TimeoutError): fetch(CURRENT, 0)

    def test_failure_retains_last_known_across_restart_then_withdrawal(self):
        with tempfile.TemporaryDirectory() as directory:
            pages = {CURRENT: fixture('current'), URL: fixture('active')}
            source = EmergencyAlerts(directory, lambda url, _: pages[url])
            self.assertTrue(source.refresh(NOW))
            before = source.snapshot()['items']
            pages[URL] = fixture('blocked')
            self.assertFalse(source.refresh(NOW + 301))
            retained = EmergencyAlerts(directory).snapshot()
            self.assertEqual(retained['items'], before)
            self.assertIn('STALE', presentation(retained, NOW + 301)[0])
            self.assertEqual(retained['fetched'], NOW)
            pages[CURRENT] = fixture('current-empty')
            self.assertTrue(source.refresh(NOW + 602))
            self.assertEqual(source.snapshot()['items'][0]['status'], 'withdrawn')
            self.assertFalse(source.snapshot()['failed'])

    def test_first_failure_and_stale_empty_never_imply_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            source = EmergencyAlerts(directory, lambda *_: fixture('blocked'))
            source.refresh(NOW)
            self.assertIn('UNAVAILABLE', presentation(source.snapshot(), NOW)[0])
            source.fetcher = lambda *_: fixture('current-empty')
            source.refresh(NOW + 301)
            source.fetcher = lambda *_: fixture('blocked')
            source.refresh(NOW + 602)
            self.assertIn('STALE', presentation(source.snapshot(), NOW + 602)[0])
            self.assertNotIn('No current', presentation(source.snapshot(), NOW + 602)[0])

    def test_http_payload_type_size_and_redirect_are_bounded(self):
        import time
        from emergency_alerts import MAX_BYTES, NoRedirect
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_type.return_value = 'application/json'
        opener = MagicMock()
        opener.open.return_value = response
        with patch('emergency_alerts.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(ValueError): fetch(CURRENT, time.monotonic() + 45)
            response.headers.get_content_type.return_value = 'text/html'
            response.read1.side_effect = [b'x' * 65536] * (MAX_BYTES // 65536) + [b'x']
            with self.assertRaises(ValueError): fetch(CURRENT, time.monotonic() + 45)
            self.assertLessEqual(opener.open.call_args.kwargs['timeout'], 8)
        with self.assertRaises(ValueError): NoRedirect().redirect_request(None)

    def test_cache_and_request_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            source = EmergencyAlerts(directory, lambda url, _: calls.append(url) or fixture('current-empty'))
            source.refresh(NOW)
            source.refresh(NOW + 10)
            self.assertEqual(calls, [CURRENT])
            self.assertIn('STALE', presentation(source.snapshot(), NOW + MAX_AGE + 1)[0])
            source.path.write_text('{broken')
            self.assertEqual(EmergencyAlerts(directory).snapshot(), {})
            source.path.write_text('[]')
            self.assertEqual(EmergencyAlerts(directory).snapshot(), {})
        rows = ''.join('<h3>Alert</h3><a href="/alerts/x-%s">More information about this alert</a>' % i for i in range(MAX_ALERTS + 1))
        with self.assertRaises(ValueError): parse_index('<main><h1>Current alerts</h1>' + rows + '</main>')


class LayoutTests(unittest.TestCase):
    def setUp(self):
        pygame.display.init(); pygame.font.init()
        pygame.display.set_mode((1280, 720))
        self.row = parse_detail(fixture('active'), URL)
        self.data = dict(fetched=NOW, items=[self.row])

    def tearDown(self):
        pygame.quit()

    def test_panels_render_and_source_is_preserved(self):
        for size in ((458, 148), (580, 537)):
            image, url = panel(self.data, NOW, 0, size)
            self.assertEqual(image.get_size(), size)
            self.assertEqual(url, URL)

    def test_companion_keeps_threat_and_ping_pixels(self):
        from companion import Companion
        view = Companion()
        data = {'threat': {'level': 'MODERATE', 'fetched': NOW}}
        network = dict(checked=NOW, offline=False, colour='accent', latency=25)
        before = view.draw(data, NOW, 0, 'Example', network).copy()
        view.emergency_data = self.data
        after = view.draw(data, NOW, 0, 'Example', network).copy()
        for rect in ((0, 0, 480, 29), (0, 266, 480, 54)):
            self.assertEqual(pygame.image.tostring(before.subsurface(rect), 'RGB'),
                             pygame.image.tostring(after.subsurface(rect), 'RGB'))
        pygame.image.save(after, '/tmp/nexus-emergency-alerts/companion-emergency.png')

    def test_desktop_emergency_above_all_workspaces_and_terminal(self):
        from focused_ui import FocusedDesktop
        ui = FocusedDesktop(pygame.display.get_surface(), {'name': 'Example'}, preview=True)
        ui.emergency_data = self.data
        for profile in ('uk', 'technical'):
            for workspace in range(4):
                ui.draw(workspace,48,48,NOW,None,False,{},set(),{},set(),{},set(),profile=profile,manual_terminal=True)
                self.assertEqual(ui.clicked_url((500,300)), URL)
                self.assertLess(len(ui.links), 20)
        pygame.image.save(ui.screen, '/tmp/nexus-emergency-alerts/desktop-emergency.png')


if __name__ == '__main__': unittest.main()
