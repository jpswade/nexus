import json
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from source_history import History, LIMIT, RETENTION, MAX_BYTES, detail


class HistoryTests(unittest.TestCase):
    def test_failure_recovery_empty_change_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            h=History(root)
            h.record('weather',100,{'items':[{'id':'a','title':'PRIVATE TEXT'}], 'fetched':100})
            h.record('weather',101)
            h=History(root)
            self.assertEqual(h.read('weather',101)['successful'],100)
            h.record('weather',102,{'items':[{'id':'a','title':'PRIVATE TEXT'}], 'fetched':102})
            h.record('weather',103,{'items':[], 'fetched':103})
            record=h.read('weather',103)
            self.assertEqual([e['kind'] for e in record['events']],['baseline','failed','recovered','changed'])
            self.assertNotIn('PRIVATE', (Path(root)/'health-weather.json').read_text())
            self.assertEqual(detail(record,None,2000,900)[0],'STALE')
            self.assertEqual(detail({},None,2000,900)[0],'NOT CHECKED')

    def test_reordering_and_routine_poll_are_not_changes(self):
        with tempfile.TemporaryDirectory() as root:
            h=History(root)
            h.record('weather',100,{'items':[{'id':'a'},{'id':'b'}], 'fetched':100})
            h.record('weather',101,{'items':[{'id':'b'},{'id':'a'}], 'fetched':101})
            self.assertEqual(h.read('weather',101)['events'][-1]['kind'],'checked')
            h.record('weather',100,{'items':[]})
            self.assertEqual(h.read('weather',101)['attempted'],101)

    def test_bounded_retention_and_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as root:
            h=History(root)
            for i in range(100): h.record('grid',i,{'items':[]})
            self.assertEqual(len(h.read('grid',100)['events']),LIMIT)
            h.record('grid',RETENTION+200,{'items':[]})
            self.assertEqual(len(h.read('grid',RETENTION+200)['events']),1)
            path=Path(root)/'health-grid.json'
            self.assertLess(path.stat().st_size,MAX_BYTES)
            for body in ('null','{"version":1,"events":null}', 'x'*(MAX_BYTES+1)):
                path.write_text(body)
                self.assertEqual(h.read('grid',100),{})
            h.record('grid',RETENTION+201)
            self.assertTrue(h.read('grid',RETENTION+201)['failed'])

    def test_disk_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('source_history.tempfile.NamedTemporaryFile',side_effect=OSError('private error')):
                History(root).record('weather',100,{'items':[]})

    def test_adapter_records_failed_attempt_without_clearing_success(self):
        from preparedness import PreparednessFeeds
        with tempfile.TemporaryDirectory() as root:
            feed=PreparednessFeeds(root,{})
            with patch('preparedness.urllib.request.urlopen',side_effect=OSError('SECRET')):
                self.assertFalse(feed.refresh('weather'))
            record=feed.history.read('weather',__import__('time').time())
            self.assertTrue(record['failed'])
            self.assertIsNone(record['successful'])
            self.assertNotIn('SECRET',(feed.directory/'health-weather.json').read_text())


class DetailsTests(unittest.TestCase):
    def test_each_header_opens_and_closes_and_renders(self):
        import pygame
        from focused_ui import FocusedDesktop
        pygame.init()
        screen=pygame.display.set_mode((1280,720))
        ui=FocusedDesktop(screen,{},preview=True)
        for i,source in enumerate(('gov','grid','weather','floods')):
            self.assertTrue(ui.click_detail((245+i*251,40)))
            self.assertEqual(ui.source_detail,source)
            ui.draw(0,0,0,10000,None,False,{},set(),{},set(),{},set())
            self.assertTrue(ui.clicked_url((370,615)).startswith('https://'))
            self.assertTrue(ui.click_detail((850,125)))
            self.assertIsNone(ui.source_detail)
        pygame.quit()

    def test_companion_health_does_not_hide_ping_or_offline(self):
        from companion import Companion
        view=Companion()
        view.motion.snapshot=lambda now: {}
        with patch.object(view,'text',wraps=view.text) as text:
            view.draw({},10000,35,'')
            values=[c.args[0] for c in text.call_args_list]
            self.assertIn('GOV.UK NOT CHECKED',values)
            self.assertIn('No priority item',values)
            self.assertIn('Wi-Fi --',values)
        with patch.object(view,'text',wraps=view.text) as text:
            view.draw({},10000,35,'',{'checked':10000,'offline':True})
            self.assertNotIn('GOV.UK ALERTS',[c.args[0] for c in text.call_args_list])

class SharedJournalTests(unittest.TestCase):
    def test_two_process_writers_merge_without_losing_sources(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as root:
            script = ('from source_history import History; import sys; '
                      'h=History(sys.argv[1]); '
                      '[h.record(sys.argv[2], i, {"items":[]}) for i in range(1,30)]')
            jobs=[subprocess.Popen([sys.executable,'-c',script,root,source]) for source in ('weather','grid')]
            for job in jobs:self.assertEqual(job.wait(timeout=10),0)
            for source in ('weather','grid'):
                self.assertEqual(len(History(root).read(source,30)['events']),29)

    def test_second_instance_preserves_previous_checks(self):
        with tempfile.TemporaryDirectory() as root:
            first,second=History(root),History(root)
            first.record('weather',1,{'items':[]})
            second.record('weather',2)
            first.record('weather',3,{'items':[]})
            self.assertEqual([e['kind'] for e in second.read('weather',3)['events']],
                             ['baseline','failed','recovered'])
