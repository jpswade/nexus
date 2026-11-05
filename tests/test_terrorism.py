import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from preparedness import PreparednessFeeds, URLS, parse_feed
from terrorism import MI5_URL, parse_assessment, threat_details

FIXTURE = (Path(__file__).parent/'fixtures/terrorism/mi5.html').read_text()


def gov(level='moderate'):
    return {'details': {'parts': [{'slug': 'terrorism-threat-levels', 'body':
        '<p>The threat to the UK (England, Wales, Scotland and Northern Ireland) '
        f'from terrorism is <strong>{level}</strong>.</p>'}]}}


class ParsingTests(unittest.TestCase):
    def test_current_national_only(self):
        self.assertEqual(parse_assessment(FIXTURE, mi5=True), 'SUBSTANTIAL')
        self.assertEqual(parse_feed('threat', gov())['level'], 'MODERATE')

    def test_rejects_missing_ambiguous_or_changed_structure(self):
        for body in (FIXTURE.replace('Current national threat level', 'National history'),
                     FIXTURE.replace('SUBSTANTIAL</strong>', 'UNKNOWN</strong>'),
                     FIXTURE.replace('SUBSTANTIAL</strong>', 'LOW or SEVERE</strong>'),
                     FIXTURE+FIXTURE,
                     '<p>Current Threat Level: CRITICAL</p>',
                     '<h3>Current national threat level</h3><p>LOW MODERATE SEVERE</p>',
                     '<html><title>Just a moment...</title></html>',
                     FIXTURE.replace('from all forms of terrorism', 'from some terrorism')):
            with self.subTest(body=body[:60]), self.assertRaises(ValueError):
                parse_assessment(body, mi5=True)

    def test_hidden_sentence_and_duplicate_paragraph_rejected(self):
        sentence = FIXTURE.split('<h3>Current national threat level</h3>')[1].split('<h3>')[0]
        for body in ('<h3>Current national threat level</h3><script>'+sentence+'</script>',
                     FIXTURE.replace(sentence, sentence+sentence)):
            with self.assertRaises(ValueError): parse_assessment(body, mi5=True)
        duplicate = gov()
        duplicate['details']['parts'] *= 2
        with self.assertRaises(ValueError): parse_feed('threat', duplicate)
        raw = gov()
        raw['details']['parts'][0]['body'] *= 2
        with self.assertRaises(ValueError): parse_feed('threat', raw)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.feeds = PreparednessFeeds(self.directory.name, {})

    def refresh(self, primary=gov(), secondary=FIXTURE):
        def read(request, **kwargs):
            value = primary if request.full_url == URLS['threat'] else secondary
            if isinstance(value, Exception): raise value
            return io.BytesIO(json.dumps(value).encode() if isinstance(value, dict) else value.encode())
        with patch('urllib.request.urlopen', side_effect=read), patch('time.time', return_value=10000):
            return self.feeds.refresh('threat')

    def test_fallback_on_network_json_and_schema_failure(self):
        for failure in (OSError('offline'), '<html>blocked</html>', {}, gov('unknown')):
            with self.subTest(failure=failure):
                self.assertTrue(self.refresh(primary=failure))
                sample = self.feeds.data['threat']
                self.assertEqual(sample['source'], MI5_URL)
                self.assertEqual(sample['source_name'], 'MI5')
                self.assertEqual(sample['level'], 'SUBSTANTIAL')
                self.assertEqual(sample['fetched'], 10000)
                reloaded = PreparednessFeeds(self.directory.name, {})
                self.assertEqual(reloaded.data['threat'], sample)

    def test_disagreement_never_selects_by_severity(self):
        for level in ('low', 'critical'):
            self.assertTrue(self.refresh(primary=gov(level)))
            sample = self.feeds.data['threat']
            self.assertTrue(sample['disagreement'])
            self.assertEqual(sample['level'], level.upper())
            self.assertEqual(sample['source_name'], 'GOV.UK')
            self.assertIn('MI5 SUBSTANTIAL', threat_details(sample,10000)[0])
            self.assertEqual(sample['observations']['MI5']['fetched'], 10000)

    def test_agreement_and_primary_only(self):
        self.assertTrue(self.refresh(primary=gov('substantial')))
        self.assertFalse(self.feeds.data['threat']['disagreement'])
        self.assertTrue(self.refresh(secondary=OSError('timeout')))
        self.assertFalse(self.feeds.data['threat']['disagreement'])
        self.assertEqual(self.feeds.data['threat']['source_name'], 'GOV.UK')

    def test_total_failure_retains_cache_and_checked_time_across_restart(self):
        self.refresh(primary=OSError())
        previous = self.feeds.data['threat'].copy()
        self.assertFalse(self.refresh(OSError(), OSError()))
        self.assertEqual(self.feeds.data['threat'], previous)
        reloaded = PreparednessFeeds(self.directory.name, {})
        self.assertEqual(reloaded.data['threat'], previous)
        self.assertIn('threat', reloaded.errors)
        self.assertTrue(threat_details(previous,10001,True)[1].startswith('STALE / last OK'))
        self.assertTrue(self.refresh())
        self.assertNotIn('threat', PreparednessFeeds(self.directory.name, {}).errors)

    def test_cold_start_and_oversize_fail_closed(self):
        self.assertFalse(self.refresh(OSError(), OSError()))
        self.assertNotIn('threat', self.feeds.data)
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'x'*4_194_305)):
            with self.assertRaises(ValueError): self.feeds._read(MI5_URL)


class DisplayTests(unittest.TestCase):
    def test_both_displays_show_disagreement_sources_and_success_time(self):
        import os
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        import pygame
        from companion import Companion
        from focused_ui import FocusedDesktop
        pygame.display.init()
        pygame.font.init()
        self.addCleanup(pygame.quit)
        sample = {'level': 'LOW', 'source_name': 'GOV.UK', 'fetched': 10000,
                  'disagreement': True, 'observations': {'GOV.UK': {'level': 'LOW'},
                                                       'MI5': {'level': 'CRITICAL'}}}
        lcd = Companion()
        desktop = FocusedDesktop(pygame.display.set_mode((1280,720)), {}, preview=True)
        for ui in (lcd, desktop):
            with patch.object(ui, 'text', wraps=ui.text) as text:
                if ui is lcd:
                    ui.draw({'threat': sample},10001,3,'',errors={'threat'})
                else:
                    ui.draw(0,3,3,10001,None,False,{},set(),{'threat':sample},{'threat'},{},set())
                labels = [str(call.args[0]) for call in text.call_args_list]
                self.assertTrue(any('SOURCES DIFFER' in label for label in labels))
                self.assertFalse(any('GOV.UK LOW / MI5 CRITICAL' in label for label in labels))
                self.assertTrue(any('STALE' in label for label in labels))

    def test_lcd_offline_takeover_precedes_assessment(self):
        import os
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        import pygame
        from companion import Companion
        lcd = Companion()
        with patch('companion.threat_details') as details:
            lcd.draw({},10000,3,'',network={'checked':10000,'offline':True})
            details.assert_not_called()
        pygame.quit()

    def test_longest_disagreement_metadata_fits(self):
        import pygame
        from companion import Companion
        lcd = Companion()
        source, checked = threat_details({'level':'SUBSTANTIAL','fetched':10000,
            'disagreement':True,'observations':{'GOV.UK':{'level':'SUBSTANTIAL'},
                                               'MI5':{'level':'SUBSTANTIAL'}}},10000,True)
        self.assertLessEqual(lcd.face(13).size(source)[0],458)
        self.assertLessEqual(lcd.face(12).size(checked)[0],458)
        pygame.quit()
