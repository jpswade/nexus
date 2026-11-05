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

class StatusBoardTests(unittest.TestCase):
    def test_every_check_is_present_and_missing_is_not_clear(self):
        from status_summary import status_board
        rows={r['id']:r for r in status_board({},10000)}
        self.assertEqual(set(rows),{'gov','grid','weather','floods','internet','G','R','S','ncsc','govuk','camera','health'})
        self.assertTrue(all(r['state']!='ok' for r in rows.values()))
        self.assertEqual(rows['health']['value'],'0/11 CURRENT')

    def test_space_axes_are_separate_and_stale_values_are_retained(self):
        from status_summary import status_board
        context={'space':{'scales':{'status':'checked','rows':[{'kind':'forecast','levels':{'G':'5'}},{'kind':'observation','levels':{'G':'2','R':'0','S':None}}]}},'radar':{'status':'checked','items':[]}}
        rows={r['id']:r for r in status_board(context,10000)}
        self.assertEqual((rows['G']['value'],rows['G']['state']),('G2','alert'))
        self.assertEqual((rows['R']['value'],rows['R']['state']),('R0','ok'))
        self.assertEqual(rows['S']['state'],'unknown')
        self.assertEqual(rows['internet']['value'],'0 REPORTS / 7D')
        self.assertEqual(rows['internet']['state'],'info')
        context['space']['scales']['status']='stale'
        rows={r['id']:r for r in status_board(context,10000)}
        self.assertEqual((rows['G']['value'],rows['G']['state']),('G2 / STALE','stale'))

    def test_empty_weather_and_failed_check_remain_distinct(self):
        from status_summary import status_board
        context={'uk':{'weather':{'fetched':10000,'items':[]},'grid':{'fetched':10000,'items':[]}}}
        rows={r['id']:r for r in status_board(context,10000)}
        self.assertEqual(rows['weather']['value'],'NONE ACTIVE')
        context['source_records']={'weather':{'failed':True},'grid':{'failed':True}}
        rows={r['id']:r for r in status_board(context,10000)}
        self.assertEqual(rows['weather']['state'],'stale')
        self.assertEqual(rows['grid']['state'],'stale')
