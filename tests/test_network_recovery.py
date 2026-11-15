import unittest
from network_recovery import decide
from warning_led import offline_flash

class RecoveryTests(unittest.TestCase):
    def test_transient_failure_and_recovery_clear_pending_repair(self):
        s,a=decide({}, {}, 0);self.assertIsNone(a)
        s,a=decide(s,{},119);self.assertIsNone(a)
        s,a=decide(s,{'lan':True},120);self.assertIsNone(a);self.assertIsNone(s['since'])
        s,a=decide(s,{},130);self.assertIsNone(a)
    def test_escalation_cooldown_and_reset_limit(self):
        s,_=decide({}, {}, 0)
        s,a=decide(s,{},120);self.assertEqual(a,'reconnect')
        s,a=decide(s,{},419);self.assertIsNone(a)
        s,a=decide(s,{},420);self.assertEqual(a,'usb-reset')
        s,a=decide(s,{},720);self.assertEqual(a,'usb-reset')
        s,a=decide(s,{},1020);self.assertIsNone(a)
        s,a=decide(s,{'latency':40},1021);self.assertIsNone(a);self.assertEqual(s['attempts'],0)
    def test_wan_outage_with_healthy_router_does_not_reset_wifi(self):
        s={}
        for now in (0,120,600,3600):
            s,a=decide(s,{'lan':True,'latency':None},now);self.assertIsNone(a)
    def test_led_only_flashes_on_fresh_confirmed_offline(self):
        self.assertTrue(offline_flash({'checked':100,'offline':True},110))
        for state in ({},{'checked':100,'offline':False},{'checked':0,'offline':True}):
            self.assertFalse(offline_flash(state,110))
