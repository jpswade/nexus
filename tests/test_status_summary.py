import unittest
from types import SimpleNamespace
from status_summary import summary
from preparedness_ui import PreparednessDesktop


class StatusSummaryTests(unittest.TestCase):
    def test_weather_uses_highest_colour_and_preserves_stale(self):
        data = {'weather': {'fetched': 100, 'items': [{'colour':'yellow'}, {'colour':'red'}, {'colour':'amber'}]}}
        self.assertEqual(summary('weather', data, 100), 'RED / 3')
        self.assertEqual(summary('weather', data, 100, {'weather'}), 'RED / 3 [STALE]')
        self.assertEqual(summary('weather', {}, 100), 'UNAVAILABLE')
        self.assertEqual(summary('weather', {'weather':{'fetched':100,'items':[]}},100), 'NONE RETURNED')

    def test_every_uk_workspace_keeps_all_statuses(self):
        calls = []
        panels = []
        ui = SimpleNamespace(text=lambda *args: calls.append(args[0]), line=lambda *args: None,
                             panel=lambda *args: panels.append(args[4]), TEXT='green', DIM='grey',
                             TEAL='green', AMBER='orange', RED='red')
        view = PreparednessDesktop(ui, SimpleNamespace())
        for index in range(4):
            calls.clear()
            panels.clear()
            view.draw(index, 0, {}, {}, 100)
            self.assertEqual('UK / SITUATION MAP' in panels, index == 2)
            self.assertEqual('WEATHER WARNING / MET OFFICE' in panels, index != 2)
            for prefix in ('UK THREAT / ', 'WEATHER / ', 'FLOODS / ', 'DOOMSDAY / '):
                self.assertTrue(any(value.startswith(prefix) for value in calls), (index, prefix))

class LiveChecksTests(unittest.TestCase):
    def test_failed_or_stale_checks_never_report_empty_success(self):
        from status_summary import live_checks
        data={'grid':{'fetched':100,'failed':True,'items':[]},'weather':{'fetched':100,'items':[]}}
        checks=live_checks(data,{'fetched':100,'failed':True,'items':[]},100,{'weather'})
        self.assertEqual([r[1] for r in checks],['STALE','STALE','STALE','UNREADABLE'])

    def test_bulletins_are_not_emergencies_and_tests_are_explicit(self):
        from status_summary import live_checks
        data={'grid':{'fetched':100,'items':[{'published':90}]}}
        emergency={'fetched':100,'items':[{'status':'current','test':True}]}
        checks=live_checks(data,emergency,100)
        self.assertEqual(checks[0],('GOV.UK','1 TEST','ok'))
        self.assertEqual(checks[1],('GRID','1 BULLETINS','ok'))
