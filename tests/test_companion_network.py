import unittest
from unittest.mock import patch
from companion_network import classify, NetworkMonitor, sweep_duration

class NetworkTests(unittest.TestCase):
    def test_distinguishes_link_failure_and_upstream_probe_failure(self):
        self.assertEqual(classify(False,None,False,None)[0], 'LOCAL DOWN')
        self.assertEqual(classify(True,'0',False,None)[0], 'LOCAL DOWN')
        self.assertEqual(classify(True,'1',True,None)[0], 'WAN CHECK')
        self.assertEqual(classify(True,'1',False,None)[0], 'LINK CHECK')
        self.assertEqual(classify(True,'1',False,25)[0], 'CONNECTED')

    def test_no_route_records_failed_probe_without_network_requests(self):
        monitor=NetworkMonitor()
        with patch('companion_network.gateway', return_value=(None,None)), patch('companion_network.socket.create_connection') as connect:
            monitor.probe()
        self.assertEqual(monitor.snapshot()['label'], 'LOCAL DOWN')
        self.assertEqual(monitor.snapshot()['history'], [None])
        connect.assert_not_called()

    def test_tcp_latency_does_not_claim_dns_or_feed_health(self):
        monitor=NetworkMonitor()
        with patch('companion_network.gateway',return_value=('192.0.2.1','eth0')), patch('companion_network.Path.read_text',return_value='1'), patch('companion_network.subprocess.run') as ping, patch('companion_network.socket.create_connection'):
            ping.return_value.returncode=1
            monitor.probe()
        state=monitor.snapshot()
        self.assertEqual(state['label'],'CONNECTED')
        self.assertIsNotNone(state['latency'])
        self.assertIn('TCP',state['detail'])

    def test_sweep_speed_tracks_latency_and_stays_bounded(self):
        self.assertLess(sweep_duration(10),sweep_duration(500))
        self.assertGreaterEqual(sweep_duration(0),1.5)
        self.assertLessEqual(sweep_duration(10000),6)

    def test_counter_advances_only_when_a_real_probe_finishes(self):
        monitor=NetworkMonitor()
        self.assertEqual(monitor.snapshot().get('sequence',0),0)
        with patch('companion_network.gateway',return_value=(None,None)):
            monitor.probe()
            self.assertEqual(monitor.snapshot()['sequence'],1)
            monitor.probe()
            self.assertEqual(monitor.snapshot()['sequence'],2)
