"""Regression checks for persistent context, real changes, and cross-profile feeds."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
import pygame
from focused_state import ChangeLog, automatic_brief, php_summary
from focused_ui import FocusedDesktop

ROOT=Path(__file__).resolve().parents[1]


def advisory(now,ident='CVE-DEMO-001',severity='critical'):
    return {'id':ident,'severity':severity,'published':now-100,'summary':'Synthetic advisory for layout testing',
            'score':9.2,'cvss_version':'4.0','patches':['8.x.1'],'url':'https://example.com/advisory'}


class FocusedStateTests(unittest.TestCase):
    def test_initial_load_and_routine_refresh_do_not_replay_alerts(self):
        changes=ChangeLog()
        sample={'php':{'items':[advisory(1000)],'fetched':1000}}
        changes.update(sample,{},[],1000)
        sample['php']['fetched']=1100
        changes.update(sample,{},[],1100)
        self.assertEqual(list(changes.events),[])
        self.assertEqual(changes.brief_until,0)

    def test_new_critical_advisory_briefs_once_but_unavailable_source_does_not_clear_state(self):
        changes=ChangeLog()
        changes.update({'php':{'items':[advisory(1000)]}}, {},[],1000)
        changes.update({}, {},[],1010)
        rows=[advisory(1000),advisory(1020,'CVE-DEMO-002')]
        changes.update({'php':{'items':rows}}, {},[],1020)
        self.assertEqual(len(changes.events),1)
        self.assertIn('CVE-DEMO-002',changes.events[0]['title'])
        self.assertTrue(automatic_brief(0,4,changes,1021))
        changes.update({'php':{'items':rows}}, {},[],1025)
        self.assertEqual(len(changes.events),1)
        self.assertFalse(automatic_brief(0,15,changes,1030))

    def test_an_item_leaving_the_feed_is_a_change_not_a_safety_verdict(self):
        changes=ChangeLog()
        changes.update({'php':{'items':[advisory(1000)]}}, {},[],1000)
        changes.update({'php':{'items':[]}}, {},[],1010)
        self.assertEqual(len(changes.events),1)
        self.assertIn('Left the current feed',changes.events[0]['title'])
        self.assertEqual(changes.brief_until,0)

    def test_briefing_is_short_and_occurs_only_once_per_four_view_cycle(self):
        changes=ChangeLog()
        self.assertTrue(automatic_brief(0,44,changes,1000))
        self.assertFalse(automatic_brief(0,53,changes,1000))
        self.assertFalse(automatic_brief(1,44,changes,1000))
        self.assertFalse(automatic_brief(2,44,changes,1000))

    def test_unknown_php_is_not_zero_and_future_records_are_not_counted(self):
        self.assertFalse(php_summary({},1000)['available'])
        data={'php':{'items':[advisory(1101)]}}
        self.assertEqual(php_summary(data,1000)['critical'],0)

    def test_all_sources_start_in_both_profiles_without_a_live_display_or_network(self):
        class StartupComplete(Exception):pass
        for profile in ('uk','technical'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory:
                with patch.dict(os.environ,{'NEXUS_CONFIG':str(ROOT/'config.example.json'),'NEXUS_CACHE':directory}), \
                     patch.object(sys,'argv',['dashboard.py','--profile',profile]), \
                     patch('threading.Thread.start'), \
                     patch('security.SecurityFeeds.start') as security, \
                     patch('feeds.PlanetFeeds.start') as planet, \
                     patch('preparedness.PreparednessFeeds.start') as uk, \
                     patch('pygame.display.set_mode',side_effect=StartupComplete):
                    with self.assertRaises(StartupComplete):runpy.run_path(str(ROOT/'dashboard.py'),run_name='__main__')
                    security.assert_called_once();planet.assert_called_once();uk.assert_called_once()
        pygame.quit()


class PersistentLayoutTests(unittest.TestCase):
    def setUp(self):
        pygame.display.init();pygame.font.init()
        self.screen=pygame.display.set_mode((1280,720))
        self.ui=FocusedDesktop(self.screen,{'name':'Example area'},preview=True)

    def tearDown(self):pygame.quit()

    def test_php_link_and_retained_stale_warning_survive_every_workspace(self):
        now=1792940000
        php=advisory(now)
        security={'php':{'items':[php],'fetched':now}}
        item={'title':'Amber warning','colour':'amber','url':'https://www.metoffice.gov.uk/','description':''}
        uk={'weather':{'items':[item],'fetched':now},'threat':{'level':'MODERATE','fetched':now}}
        for workspace in range(5):
            self.ui.draw(workspace,3,3,now+10000+workspace,None,False,security,{'php'},uk,{'weather'},{},set(),automatic=False)
            primary=self.ui.renderer.selected[0]
            self.assertEqual(primary['url'],item['url'])
            self.assertEqual(primary['state'],'stale')
            self.assertTrue(primary['pinned'])
            for (x,y,w,h),url in self.ui.links:
                self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                self.assertLessEqual(x+w,1280);self.assertLessEqual(y+h,720)
        self.ui.draw(1,3,3,now+10010,None,False,security,{'php'},uk,{'weather'},{},set(),automatic=False)
        self.assertEqual(self.ui.renderer.selected[1]['url'],php['url'])

    def test_php_followup_notice_keeps_its_official_source_in_rotation(self):
        now=1792940000;url='https://www.php.net/archive/2026.php#demo'
        security={'php':{'items':[advisory(now)],'fetched':now},'phpnews':{'items':[{'title':'Demo follow-up','published':now,'url':url}],'fetched':now}}
        seen=set()
        for t in range(0,180,15):
            self.ui.draw(1,t,t,now+t,None,False,security,set(),{},set(),{},set(),automatic=False)
            if self.ui.renderer.selected[1]:seen.add(self.ui.renderer.selected[1]['url'])
        self.assertIn(url,seen)
        self.assertFalse(self.ui.terminal_visible)

    def test_terminal_never_covers_priority_or_weather_sidebars(self):
        now=1792940000;security={'php':{'items':[advisory(now)],'fetched':now}}
        self.ui.draw(1,48,48,now,None,False,security,set(),{},set(),{},set(),automatic=False)
        self.assertFalse(self.ui.terminal_visible)
        self.assertEqual(self.ui.clicked_url((950,300)),'https://example.com/advisory')
        self.assertIsNone(self.ui.renderer.selected[0])  # PHP no longer occupies permanent priority panel.


if __name__=='__main__':unittest.main()
