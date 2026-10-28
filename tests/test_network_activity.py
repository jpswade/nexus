import unittest
from unittest.mock import patch
from network_activity import Activity,counters,wireless,ActivityPanel

class ActivityTests(unittest.TestCase):
    def test_reads_interfaces_and_excludes_loopback(self):
        raw='header\nheader\n lo: 100 0 0 0 0 0 0 0 100\n eth0: 1024 0 0 0 0 0 0 0 2048\n'
        self.assertEqual(counters(raw),{'eth0':(1024,2048)})
        self.assertEqual(wireless('h\nh\n wlan0: 0000 70. -51. -256\n'),-51)
        self.assertIsNone(wireless('h\nh\n'))

    def test_rates_use_elapsed_time_and_reset_on_counter_rollover(self):
        view=Activity()
        with patch('network_activity.Path.read_text',return_value=''),patch('network_activity.counters',side_effect=[{'eth0':(1000,2000)},{'eth0':(3048,3024)},{'eth0':(0,0)}]):
            view.sample(1);self.assertIsNone(view.snapshot()['rx'])
            view.sample(3);self.assertEqual(view.snapshot()['rx'],1)
            self.assertEqual(view.snapshot()['tx'],0.5)
            view.sample(4);self.assertIsNone(view.snapshot()['rx'])

    def test_missing_measurements_and_render(self):
        import pygame
        pygame.font.init()
        view=Activity()
        with patch('network_activity.Path.read_text',side_effect=OSError):view.sample(1)
        self.assertIsNone(view.snapshot()['signal'])
        self.assertIsNone(view.snapshot()['rx'])
        panel=ActivityPanel()
        self.assertEqual(panel.draw(view.snapshot()).get_size(),(225,148))
