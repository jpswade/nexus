"""Synthetic official-schema fixtures; no token or live requests required."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import pygame
from radar_outages import RadarFeed, parse, display_lines, MAX_AGE, RETENTION, LIMIT, NoRedirect, fetch

FIXTURE=json.loads((Path(__file__).parent/'fixtures/radar-outages.json').read_text())

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/'radar.json'
        self.transport=Mock(return_value=copy.deepcopy(FIXTURE))
        self.feed=RadarFeed(self.path,token='synthetic-secret',transport=self.transport)
    def tearDown(self):
        self.feed.stop()
        self.directory.cleanup()
    def test_official_schema_uk_and_provider(self):
        rows=parse(FIXTURE)
        self.assertEqual(len(rows),2)
        self.assertIsNone(rows[0]['end'])
        self.assertIn('Example network AS64500',rows[0]['provider'])
        self.assertEqual(len(parse(FIXTURE,64501)),3)
    def test_no_token_no_calls_or_cache_writes(self):
        feed=RadarFeed(self.path,token='',transport=self.transport)
        for _ in range(3):feed.start();feed.refresh()
        self.assertEqual(feed.snapshot()['status'],'not configured')
        self.transport.assert_not_called()
        self.assertFalse(self.path.exists())
    def test_bad_asn_no_calls(self):
        feed=RadarFeed(self.path,token='x',asn='bad',transport=self.transport)
        feed.refresh()
        self.assertEqual(feed.snapshot()['status'],'invalid ASN configuration')
        self.transport.assert_not_called()
    def test_cooldown_shared_and_credentials_not_cached(self):
        self.feed.refresh();self.feed.refresh()
        other=RadarFeed(self.path,token='synthetic-secret',transport=self.transport)
        other.refresh()
        self.transport.assert_called_once()
        self.assertNotIn('synthetic-secret',self.path.read_text())
    def test_two_queries_and_deduplication(self):
        feed=RadarFeed(self.path,token='x',asn=64501,transport=self.transport)
        feed.refresh()
        self.assertEqual(self.transport.call_count,2)
        self.assertEqual(len(feed.snapshot()['items']),3)
        self.assertEqual(self.transport.call_args_list[0].args[1],{'location':'GB'})
        self.assertEqual(self.transport.call_args_list[1].args[1],{'asn':64501})
    def test_expiry_offline_and_retention(self):
        self.feed.refresh();now=self.feed.snapshot()['fetched']
        self.assertEqual(self.feed.snapshot(now)['status'],'checked')
        self.assertEqual(self.feed.snapshot(now,offline=True)['status'],'stale')
        self.assertEqual(self.feed.snapshot(now+MAX_AGE+1)['status'],'stale')
        expired=self.feed.snapshot(now+RETENTION+1)
        self.assertEqual(expired['status'],'expired');self.assertEqual(expired['items'],[])
    def test_empty_not_all_clear(self):
        self.transport.return_value={'success':True,'result':{'annotations':[]}}
        self.feed.refresh()
        self.assertIn('No reports returned / 7d',display_lines(self.feed.snapshot()))
        self.assertIn('Not an all-clear',display_lines(self.feed.snapshot()))
    def test_failure_preserves_previous_timestamp(self):
        self.feed.refresh();before=self.feed.snapshot()
        self.transport.side_effect=RuntimeError('synthetic-secret')
        with patch('radar_outages.time.time',return_value=before['fetched']+901):
            self.feed.refresh()
        after=self.feed.snapshot()
        self.assertEqual(after['status'],'stale')
        self.assertEqual(after['fetched'],before['fetched'])
        self.assertEqual(after['items'],before['items'])
        self.assertNotIn('synthetic-secret',self.path.read_text())
    def test_initial_failure(self):
        self.transport.side_effect=TimeoutError()
        self.feed.refresh()
        self.assertEqual(self.feed.snapshot()['status'],'unavailable')
    def test_auth_failure_suspends_until_restart(self):
        self.transport.side_effect=urllib.error.HTTPError('url',403,'denied',{},None)
        self.feed.refresh();self.feed.next_try=0;self.feed.refresh()
        self.transport.assert_called_once()
        self.assertEqual(self.feed.snapshot()['status'],'credentials rejected')
    def test_cancel_late_result_not_published(self):
        def transport(*args):
            self.feed.stop()
            return FIXTURE
        self.feed.transport=transport
        self.feed.refresh()
        self.assertIsNone(self.feed.snapshot()['fetched'])
        self.assertNotIn('fetched',json.loads(self.path.read_text()))
    def test_corrupt_future_and_oversized_cache(self):
        for body in ('no json','x'*300000,json.dumps({'version':1,'asn':None,'fetched':1e20})):
            self.path.write_text(body)
            feed=RadarFeed(self.path,token='x')
            self.assertIsNone(feed.snapshot()['fetched'])
    def test_invalid_payload_never_empty_success(self):
        for payload in ({'success':False}, {'success':True,'result':{}},
                        {'success':True,'result':{'annotations':[None]}},
                        {'success':True,'result':{'annotations':[{}]*(LIMIT+1)}}):
            with self.assertRaises((ValueError,KeyError)):parse(payload)
    def test_limit_label(self):
        self.transport.return_value={'success':True,'result':{'annotations':[FIXTURE['result']['annotations'][0]]*LIMIT}}
        self.feed.refresh()
        self.assertIn('LIMITED',display_lines(self.feed.snapshot())[0])
    def test_no_redirect(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_response_size_bound(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read1.return_value=b'x'*16384
        opener=Mock();opener.open.return_value=response
        with patch('radar_outages.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(ValueError):fetch('x',{'location':'GB'},threading.Event())
        self.assertLessEqual(response.read1.call_count,17)
    def test_lock_excludes_second_process_reader(self):
        import fcntl
        with self.path.with_suffix('.lock').open('a') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.feed.refresh()
        self.transport.assert_not_called()
    def test_worker_stop_discards_delayed_response(self):
        entered=threading.Event();release=threading.Event()
        def transport(*args):
            entered.set();release.wait(2)
            return FIXTURE
        self.feed.transport=transport
        self.feed.start()
        self.assertTrue(entered.wait(1))
        self.feed.stop();release.set();self.feed.thread.join(1)
        self.assertFalse(self.feed.thread.is_alive())
        self.assertIsNone(self.feed.snapshot()['fetched'])
    def test_partial_provider_failure_does_not_publish_partial_success(self):
        feed=RadarFeed(self.path,token='x',asn=64500,
                       transport=Mock(side_effect=[FIXTURE,TimeoutError()]))
        feed.refresh()
        self.assertEqual(feed.snapshot()['status'],'unavailable')
        self.assertIsNone(feed.snapshot()['fetched'])
    def test_snapshot_copy(self):
        self.feed.refresh();sample=self.feed.snapshot();sample['items'].clear()
        self.assertTrue(self.feed.snapshot()['items'])

class RenderTests(unittest.TestCase):
    def setUp(self):
        pygame.display.init();pygame.font.init();pygame.display.set_mode((1280,720))
    def tearDown(self):pygame.quit()
    def test_both_displays_and_persistent_context(self):
        from focused_ui import FocusedDesktop
        from companion import Companion
        with tempfile.TemporaryDirectory() as directory:
            feed=RadarFeed(Path(directory)/'cache',token='x',transport=lambda *args:FIXTURE)
            feed.refresh();now=feed.snapshot()['fetched']
            view=FocusedDesktop(pygame.display.get_surface(),{'name':'Example'},preview=True)
            view.radar=feed
            with patch.object(view,'text',wraps=view.text) as text:
                view.draw(2,33,33,now,None,False,{},set(),{'threat':{'level':'MODERATE','fetched':now}},set(),{},set(),automatic=False)
                words=[str(c.args[0]) for c in text.call_args_list]
                self.assertIn('UK TERRORISM / MODERATE',words)
                self.assertIn('Cloudflare Radar / CC BY-NC 4.0',words)
            if os.environ.get('NEXUS_RADAR_RENDER_DIR'):
                pygame.image.save(view.screen,str(Path(os.environ['NEXUS_RADAR_RENDER_DIR'])/'desktop.png'))
            small=Companion();small.radar=feed
            with patch.object(small,'text',wraps=small.text) as text:
                small.draw({'threat':{'level':'MODERATE','fetched':now}},now,65,'',
                           dict(checked=now,offline=False,latency=25,colour='accent'))
                words=[str(c.args[0]) for c in text.call_args_list]
                self.assertIn('UK THREAT / MODERATE',words)
                small.draw({'threat':{'level':'MODERATE','fetched':now}},now+100,165,'',dict(checked=now+100,offline=False,latency=25,colour='accent'))
                self.assertIn('Cloudflare Radar / CC BY-NC 4.0',' '.join(sum(small.card_renderer.pages,[])))
                self.assertTrue(small.card_renderer.active[0].startswith('radar:'))
                self.assertIn('Wi-Fi --',words)
            if os.environ.get('NEXUS_RADAR_RENDER_DIR'):
                pygame.image.save(small.surface,str(Path(os.environ['NEXUS_RADAR_RENDER_DIR'])/'companion.png'))

if __name__=='__main__':unittest.main()
