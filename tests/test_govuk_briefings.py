"""Synthetic Search API fixtures: no real incident is asserted by these tests."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import parse_qs, urlsplit
from govuk_briefings import GovukBriefings, parse, card, stamp, MAX_BYTES, URL, FORMATS

NOW=stamp('2026-11-04T12:00:00Z')
FIXTURE=Path(__file__).parent/'fixtures/govuk-briefings.json'


def response(raw):
    result=MagicMock()
    result.__enter__.return_value.read.return_value=json.dumps(raw).encode()
    return result


class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads(FIXTURE.read_text())

    def test_filter_and_attribution(self):
        rows=parse(self.raw)
        self.assertEqual(len(rows),4)
        self.assertEqual({r['title'] for r in rows},{
            'Synthetic power outage: public advice', 'Synthetic water emergency: do not drink supply',
            'Synthetic rail disruption after storm', 'Synthetic major incident at hospital'})
        self.assertTrue(all(r['source'].startswith('GOV.UK / ') for r in rows))

    def test_duplicate_revisions_and_tracking_links(self):
        row=self.raw['results'][0]
        newer={**row,'public_timestamp':'2026-11-04T11:00:00Z','link':row['link']+'?utm_source=test'}
        copy={**newer,'link':row['link']+'-duplicate'}
        rows=parse({'results':[row,newer,copy], 'total':3})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['published'],stamp(newer['public_timestamp']))
        self.assertNotIn('?',rows[0]['url'])

    def test_recency_and_status(self):
        sample={'fetched':NOW,'items':parse(self.raw)}
        self.assertEqual(card(sample,NOW)['state'],'CHECKED')
        self.assertEqual(card(None,NOW)['state'],'UNAVAILABLE')
        self.assertEqual(card({**sample,'failed':True},NOW)['state'],'STALE')
        self.assertEqual(card(sample,NOW+3601)['state'],'STALE')
        self.assertEqual(card({**sample,'fetched':NOW+1},NOW)['state'],'STALE')
        self.assertEqual(card(sample,NOW+8*86400)['count'],0)
        self.assertEqual(card(sample,NOW-86400)['count'],0)
        self.assertNotEqual(card(sample,NOW,0)['title'],card(sample,NOW,48)['title'])

    def test_invalid_incomplete_and_untrusted_links_fail_closed(self):
        row=self.raw['results'][0]
        bad=[{}, {'results':[], 'total':1}, {'results':[{}],'total':1}]
        for change in ({'link':'https://evil.example/go'}, {'link':'//evil.example/go'},
                       {'public_timestamp':'2026-11-04'}, {'organisations':[None]}, {'title':None}):
            bad.append({'results':[{**row,**change}],'total':1})
        for payload in bad:
            with self.subTest(payload=payload),self.assertRaises((ValueError,KeyError,TypeError)):
                parse(payload)

    def test_failure_restart_recovery_empty_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            feed=GovukBriefings(d)
            with patch('govuk_briefings.urllib.request.urlopen',return_value=response(self.raw)) as opened:
                self.assertTrue(feed.refresh(NOW))
                self.assertFalse(feed.refresh(NOW+1))
                self.assertEqual(opened.call_count,1)
                query=parse_qs(urlsplit(opened.call_args.args[0].full_url).query)
                self.assertEqual(query['filter_format'],list(FORMATS))
                self.assertIn('from:2026-10-28',query['filter_public_timestamp'][0])
                self.assertEqual(opened.call_args.kwargs['timeout'],15)
                opened.return_value.__enter__.return_value.read.assert_called_once_with(MAX_BYTES+1)
            self.assertEqual(GovukBriefings(d).snapshot(),feed.snapshot())
            with patch('govuk_briefings.urllib.request.urlopen',side_effect=OSError()):
                self.assertFalse(feed.refresh(NOW+900))
            restored=GovukBriefings(d)
            self.assertEqual(restored.snapshot()['fetched'],NOW)
            self.assertEqual(card(restored.snapshot(),NOW+900)['state'],'STALE')
            self.assertFalse(restored.refresh(NOW+901))
            with patch('govuk_briefings.urllib.request.urlopen',return_value=response({'results':[],'total':0})):
                self.assertTrue(restored.refresh(NOW+1800))
            self.assertEqual(restored.snapshot()['items'],[])

    def test_bad_response_retains_last_good_and_first_failure_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            feed=GovukBriefings(d)
            with patch('govuk_briefings.urllib.request.urlopen',return_value=response({})):
                self.assertFalse(feed.refresh(NOW))
            self.assertEqual(card(feed.snapshot(),NOW)['state'],'UNAVAILABLE')
            with patch('govuk_briefings.urllib.request.urlopen',return_value=response(self.raw)):
                self.assertTrue(feed.refresh(NOW+900))
            broken=response({});broken.__enter__.return_value.read.return_value=b'x'*(MAX_BYTES+1)
            with patch('govuk_briefings.urllib.request.urlopen',return_value=broken):
                self.assertFalse(feed.refresh(NOW+1800))
            self.assertEqual(len(feed.snapshot()['items']),4)

    def test_corrupt_cache_and_unwritable_disk(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'govuk-briefings-v1.json'
            for body in ('bad',json.dumps({'source':'https://example.com','version':1})):
                path.write_text(body)
                self.assertIsNone(GovukBriefings(d).snapshot())
            feed=GovukBriefings(d)
            with patch('govuk_briefings.urllib.request.urlopen',return_value=response(self.raw)), patch('govuk_briefings.tempfile.NamedTemporaryFile',side_effect=OSError()):
                self.assertTrue(feed.refresh(NOW))
            self.assertEqual(len(feed.snapshot()['items']),4)

    def test_shared_cache_and_no_threat_changes(self):
        from preparedness import PreparednessFeeds
        from alert_state import AlertState
        with tempfile.TemporaryDirectory() as d:
            feeds=PreparednessFeeds(d,{})
            with patch('govuk_briefings.urllib.request.urlopen',return_value=response(self.raw)):
                self.assertTrue(feeds.refresh('govuk'))
            data,errors=PreparednessFeeds(d,{}).snapshot()
            self.assertIn('govuk',data);self.assertNotIn('govuk',errors)
            data['threat']={'level':'MODERATE','fetched':NOW}
            self.assertEqual(AlertState().update(data,set(),NOW),[])
            self.assertEqual(data['threat']['level'],'MODERATE')

    def test_companion_fallback_refreshes_briefings(self):
        from companion import refresh_overdue
        with tempfile.TemporaryDirectory() as d, patch('preparedness.PreparednessFeeds.refresh') as refresh:
            refresh_overdue(d,{}, {},NOW)
            self.assertIn(('govuk',),[c.args for c in refresh.call_args_list])


class DisplayTests(unittest.TestCase):
    def test_both_active_displays_and_offline(self):
        import pygame
        from companion import Companion
        from focused_ui import FocusedDesktop
        pygame.display.init();pygame.font.init()
        sample={'fetched':NOW,'items':parse(json.loads(FIXTURE.read_text()))}
        data={'govuk':sample,'threat':{'level':'SEVERE','fetched':NOW}}
        view=Companion()
        with patch.object(view,'text',wraps=view.text) as text:
            image=view.draw(data,NOW,43,'')
            words=[c.args[0] for c in text.call_args_list]
            self.assertIn('GOV.UK / CHECKED',words)
            self.assertIn('UK THREAT / SEVERE',words)
            self.assertIn('Wi-Fi --',words)
        self.assertEqual(image.get_size(),(480,320))
        with patch.object(view,'text',wraps=view.text) as text:
            view.draw(data,NOW,43,'',{'checked':NOW,'offline':True})
            self.assertNotIn('GOV.UK / CHECKED',[c.args[0] for c in text.call_args_list])
        ui=FocusedDesktop(pygame.display.set_mode((1280,720)),{'name':'Example'},preview=True)
        try:
            ui.draw(0,57,57,NOW,None,False,{},set(),data,set(),{},set(),terminal_hidden=True)
            self.assertEqual(ui.clicked_url((500,300)),card(sample,NOW)['url'])
        finally:pygame.quit()

if __name__=='__main__':unittest.main()
