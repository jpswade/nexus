import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from grid_notices import GridNotices, parse, card, stamp, persistent_alerts, MAX_BYTES, URL, classify

FIXTURE = Path(__file__).parent/'fixtures/grid-notices.json'
NOW = stamp('2026-11-04T00:00:00Z')


class GridTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text())

    def test_official_shape_and_duplicate_updates(self):
        rows = parse(self.raw)
        self.assertEqual(len(parse({'data': self.raw['data']*2})),len(rows))
        self.assertEqual(rows, sorted(rows,key=lambda r:(r['published'],r['id']),reverse=True))
        self.assertEqual(card({'fetched':NOW,'items':rows},NOW)['state'],'CHECKED')
        self.assertEqual(persistent_alerts({'items': rows},NOW),[])

    def test_missing_stale_empty_historical_future_are_distinct(self):
        self.assertEqual(card(None,NOW)['state'],'UNAVAILABLE')
        self.assertIn('No notices',card({'fetched':NOW,'items':[]},NOW)['title'])
        sample={'fetched':NOW,'items':parse(self.raw)}
        self.assertEqual(card(sample,NOW+901)['state'],'STALE')
        self.assertEqual(card({**sample,'failed':True},NOW)['state'],'STALE')
        self.assertEqual(card({**sample,'fetched':NOW+1},NOW)['state'],'STALE')
        self.assertIn('No notices',card({**sample,'fetched':NOW+8*86400},NOW+8*86400)['title'])
        self.assertIn('No notices',card({**sample,'fetched':0},0)['title'])

    def test_updates_cancellation_and_unknown_fields_never_claim_active(self):
        # Synthetic lifecycle: the API has no ID or structured cancellation link.
        original={'publishTime':'2026-11-03T10:00:00Z','warningType':'DEMAND CONTROL',
                  'warningText':'Synthetic notice; check official instructions'}
        update={**original,'publishTime':'2026-11-03T11:00:00Z','warningText':'Synthetic update'}
        cancel={**original,'publishTime':'2026-11-03T12:00:00Z','warningText':'Synthetic notice cancelled',
                'active':True,'validTo':'2099-01-01T00:00:00Z'}
        sample={'fetched':NOW,'items':parse({'data':[original,cancel,update]})}
        c=card(sample,NOW)
        self.assertIn('cancellation',c['detail'])
        self.assertIn('12:00',c['issued'])
        self.assertIn('not structured',c['validity'])
        self.assertEqual(persistent_alerts(sample,NOW),[])
        self.assertEqual(persistent_alerts(sample,NOW+100000),[])

    def test_topics_are_exact_type_matches_not_body_keywords(self):
        expected = {
            'SO-SO TRADES': 'Market bulletin',
            'IT SYSTEMS OUTAGE': 'IT service bulletin',
            'ELECTRICITY MARGIN NOTICE': 'Margin notice',
            'HIGH RISK OF DEMAND REDUCTION': 'Demand-control notice',
            'DEMAND CONTROL IMMINENT': 'Demand-control notice',
            'UNKNOWN EMERGENCY': 'Unclassified bulletin',
            'CANCELLED DEMAND CONTROL IMMINENT': 'Unclassified bulletin',
            'TEST ELECTRICITY MARGIN NOTICE': 'Unclassified bulletin',
        }
        for kind, category in expected.items():
            with self.subTest(kind=kind):
                rows = parse({'data': [dict(publishTime='2026-11-03T12:00:00Z',
                    warningType=kind, warningText='Demand control imminent; cancelled; active') ]})
                sample = {'fetched': NOW, 'items': rows}
                self.assertEqual(card(sample, NOW)['category'], category)
                self.assertEqual(persistent_alerts(sample, NOW), [])
                self.assertEqual(persistent_alerts({**sample, 'failed': True}, NOW), [])
        self.assertEqual(classify('  electricity   margin notice ')[0], 'Margin notice')

    def test_topic_survives_lifecycle_without_becoming_active(self):
        # Synthetic lifecycle reflects the July 8–9 official EMN sequence:
        # issue, two updates, cancellation, all with the same warningType.
        records = [dict(publishTime='2026-07-09T%02d:00:00Z' % hour,
                        warningType='ELECTRICITY MARGIN NOTICE', warningText=body)
                   for hour, body in [(8, 'Synthetic issue'), (12, 'Synthetic update'),
                                      (16, 'Synthetic update'), (18, 'Synthetic cancellation')]]
        now = stamp('2026-07-09T19:00:00Z')
        for count in range(1, 5):
            sample = {'fetched': now, 'items': parse({'data': records[:count]})}
            self.assertEqual(card(sample, now)['category'], 'Margin notice')
            self.assertEqual(persistent_alerts(sample, now), [])
        self.assertIn('cancellation', card(sample, now)['detail'])
        self.assertEqual(card(sample, NOW)['category'], 'No bulletin')
        sample['items'][0]['title'] = 'CANCELLATION'
        sample['items'][0]['text'] = 'See previous notification'
        self.assertIn('cancellation', card(sample, now)['detail'])

    def test_malformed_fails_closed(self):
        for payload in ({},{'data':None},{'data':[{}]}, {'data':[{'warningType':'X','warningText':'text','publishTime':'2026-11-03'}]}):
            with self.subTest(payload=payload),self.assertRaises((ValueError,KeyError,TypeError)):
                parse(payload)

    def test_card_types_advance_and_never_mutate_threat(self):
        from alert_state import AlertState
        sample={'fetched':NOW,'items':parse(self.raw)}
        self.assertNotEqual(card(sample,NOW,0)['title'],card(sample,NOW,64)['title'])
        data={'grid':sample,'threat':{'fetched':NOW,'level':'MODERATE'}}
        self.assertEqual(AlertState().update(data,set(),NOW),[])
        self.assertEqual(data['threat']['level'],'MODERATE')

    def test_preparedness_merges_separate_grid_cache(self):
        from preparedness import PreparednessFeeds
        with tempfile.TemporaryDirectory() as directory:
            feeds=PreparednessFeeds(directory,{})
            with patch('grid_notices.urllib.request.urlopen',return_value=self.response(self.raw)):
                self.assertTrue(feeds.refresh('grid'))
            data,errors=feeds.snapshot()
            self.assertIn('grid',data)
            self.assertNotIn('grid',errors)
            cached=PreparednessFeeds(directory,{})
            self.assertEqual(cached.snapshot()[0]['grid']['items'],data['grid']['items'])

    def response(self,raw):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(raw).encode()
        return response

    def test_bounded_cache_failure_restart_recovery_and_empty_replaces(self):
        with tempfile.TemporaryDirectory() as directory:
            feed=GridNotices(directory)
            with patch('grid_notices.urllib.request.urlopen',return_value=self.response(self.raw)) as opened:
                self.assertTrue(feed.refresh(NOW))
                self.assertFalse(feed.refresh(NOW+1))
                self.assertEqual(opened.call_count,1)
                self.assertEqual(opened.call_args.kwargs['timeout'],15)
                url=opened.call_args.args[0].full_url
                self.assertTrue(url.startswith(URL))
                self.assertIn('publishDateTimeFrom=',url)
                opened.return_value.__enter__.return_value.read.assert_called_once_with(MAX_BYTES+1)
            restored=GridNotices(directory)
            self.assertEqual(feed.snapshot(),restored.snapshot())
            with patch('grid_notices.urllib.request.urlopen',side_effect=OSError('offline')):
                self.assertFalse(restored.refresh(NOW+300))
            failed=GridNotices(directory)
            self.assertEqual(card(failed.snapshot(),NOW+300)['state'],'STALE')
            self.assertEqual(failed.snapshot()['fetched'],NOW)
            self.assertFalse(failed.refresh(NOW+301))
            with patch('grid_notices.urllib.request.urlopen',return_value=self.response({'data':[]})):
                self.assertTrue(failed.refresh(NOW+600))
            self.assertEqual(failed.snapshot()['items'],[])
            self.assertFalse(failed.snapshot()['failed'])

    def test_first_failure_oversize_bad_json_and_unwritable_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            feed=GridNotices(directory)
            response=self.response({})
            for offset,payload in enumerate((b'x'*(MAX_BYTES+1),b'<html>blocked</html>',b'{"data":null}')):
                response.__enter__.return_value.read.return_value=payload
                with patch('grid_notices.urllib.request.urlopen',return_value=response):
                    self.assertFalse(feed.refresh(NOW+300*offset))
                self.assertEqual(card(feed.snapshot(),NOW)['state'],'UNAVAILABLE')
            with patch('grid_notices.urllib.request.urlopen',return_value=self.response(self.raw)), \
                 patch('grid_notices.tempfile.NamedTemporaryFile',side_effect=OSError()):
                self.assertTrue(feed.refresh(NOW+900))

    def test_corrupt_or_wrong_source_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'grid-notices-v1.json'
            for body in ('bad',json.dumps({'source':'https://example.com/','version':1})):
                path.write_text(body)
                self.assertIsNone(GridNotices(directory).snapshot())


class GridDisplayTests(unittest.TestCase):
    def test_companion_grid_rotation_preserves_header_and_strip(self):
        from companion import Companion
        view=Companion()
        data={'threat':{'level':'SEVERE','fetched':NOW},
              'grid':{'fetched':NOW,'items':parse(json.loads(FIXTURE.read_text()))}}
        with patch.object(view,'text',wraps=view.text) as text:
            image=view.draw(data,NOW,49,'')
            words=[c.args[0] for c in text.call_args_list]
            self.assertIn('GRID / CHECKED',words)
            self.assertIn('UK THREAT / SEVERE',words)
            self.assertIn('Wi-Fi --',words)
            self.assertIn('Validity / active unknown',words)
            self.assertIn('Market bulletin',words)
        self.assertEqual(image.get_size(),(480,320))

    def test_companion_cancellation_and_scope_stay_above_alert_strip(self):
        from companion import Companion
        view = Companion()
        records = {'data': [dict(publishTime='2026-11-03T12:00:00Z',
            warningType='ELECTRICITY MARGIN NOTICE', warningText='Synthetic cancellation')]}
        data = {'grid': {'fetched': NOW, 'items': parse(records)}}
        with patch.object(view, 'text', wraps=view.text) as text:
            view.draw(data, NOW, 53, '')
            calls = {c.args[0]: c.args for c in text.call_args_list}
            self.assertLess(calls['Cancellation / check source'][2], 241)
            self.assertIn('GB system; scope unspecified', calls)

    def test_focused_active_path_draws_grid(self):
        import pygame
        from focused_ui import FocusedDesktop
        pygame.display.init();pygame.font.init()
        screen=pygame.display.set_mode((1280,720))
        ui=FocusedDesktop(screen,{'name':'Example'},preview=True)
        try:
            ui.draw(0,55,55,NOW,None,False,{},set(),{},set(),{},set(),terminal_hidden=True)
            self.assertEqual(ui.clicked_url((500,300)),URL)
        finally:
            pygame.quit()


if __name__=='__main__': unittest.main()
