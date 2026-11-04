import unittest
from briefing_policy import build_cards, Rotation

NOW=1793793600
class IntegrationTests(unittest.TestCase):
    def test_real_feed_errors_retain_warning_and_score_enrichment(self):
        context={'uk_errors':{'weather'},'uk':{'weather':{'fetched':NOW,'items':[{'title':'Wind','colour':'amber','url':'https://example.invalid/wind'}]},'news':{'fetched':NOW,'items':[{'id':'CVE-DEMO','score':9.8,'cvss_version':'3.1'}]}},'security':{'kev':{'fetched':NOW,'items':[{'id':'CVE-DEMO','added':'2026-11-04','title':'Demonstration'}]}}}
        cards=build_cards(context,NOW)
        warning=next(c for c in cards if c['id'].startswith('weather:'))
        self.assertTrue(warning['pinned']);self.assertEqual(warning['state'],'stale')
        kev=next(c for c in cards if c['id']=='kev:CVE-DEMO')
        self.assertIn('9.8',' '.join(kev['body']))

    def test_unavailable_sources_are_summary_only_not_a_rotation_of_errors(self):
        cards=build_cards({},NOW)
        self.assertIsNone(Rotation().select(cards,NOW))
        self.assertTrue(any(c['state']=='unavailable' for c in cards))

    def test_ended_outage_reports_remain_historical_not_active_alerts(self):
        context={'radar':{'fetched':NOW,'items':[{'start':NOW-100,'end':NOW-20,'provider':'Synthetic','location':'GB','scope':'GB','kind':'outage'}]}}
        cards=build_cards(context,NOW)
        selected=Rotation().select(cards,NOW,'infrastructure')
        self.assertEqual(selected['state'],'info');self.assertFalse(selected['pinned'])
        self.assertIn('historical',' '.join(selected['body']))

    def test_expired_weather_does_not_return_to_normal_rotation(self):
        context={'uk':{'weather':{'fetched':NOW,'items':[{'title':'Expired warning','colour':'red','valid_until':NOW-1}]}}}
        self.assertIsNone(Rotation().select(build_cards(context,NOW),NOW))


class SnapshotCadenceTests(unittest.TestCase):
    def test_lcd_parses_source_snapshots_once_per_second(self):
        from companion import Companion
        from unittest.mock import patch
        view=Companion()
        with patch.object(view.space_weather,'snapshot',return_value={}) as snapshot:
            view.draw({},10000,0,'')
            view.draw({},10000.1,.1,'')
            view.draw({},10000.9,.9,'')
            self.assertEqual(snapshot.call_count,1)
            view.draw({},10001,1,'')
            self.assertEqual(snapshot.call_count,2)
