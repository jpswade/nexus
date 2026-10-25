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
        ui = SimpleNamespace(text=lambda *args: calls.append(args[0]), line=lambda *args: None,
                             panel=lambda *args: None, TEXT='green', DIM='grey',
                             TEAL='green', AMBER='orange', RED='red')
        view = PreparednessDesktop(ui, SimpleNamespace())
        for index in range(4):
            calls.clear()
            view.draw(index, 0, {}, {}, 100)
            for prefix in ('UK THREAT / ', 'WEATHER / ', 'FLOODS / ', 'DOOMSDAY / '):
                self.assertTrue(any(value.startswith(prefix) for value in calls), (index, prefix))
