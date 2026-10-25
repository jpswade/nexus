import unittest
from unittest.mock import patch
from live_telemetry import Telemetry


class TelemetryTests(unittest.TestCase):
    def test_cpu_uses_counter_deltas_and_sampling_is_throttled(self):
        values=['cpu 100 0 0 100 0 0 0 0\n','MemTotal: 100 kB\nMemAvailable: 25 kB\n','42000',
                'cpu 250 0 0 150 0 0 0 0\n','MemTotal: 100 kB\nMemAvailable: 20 kB\n','43000']
        with patch('live_telemetry.Path.read_text',side_effect=values) as read:
            meter=Telemetry()
            meter.sample(0)
            self.assertIsNone(meter.cpu)
            meter.sample(1)
            self.assertEqual(read.call_count,3)
            meter.sample(2)
            self.assertEqual(meter.cpu,75)
            self.assertEqual(meter.memory,80)
            self.assertEqual(meter.temperature,43)
            self.assertEqual(list(meter.history),[75])

    def test_missing_measurements_stay_unknown(self):
        with patch('live_telemetry.Path.read_text',side_effect=OSError):
            meter=Telemetry()
            meter.sample(0)
            self.assertIsNone(meter.cpu)
            self.assertIsNone(meter.memory)
            self.assertIsNone(meter.temperature)
            self.assertEqual(list(meter.history),[])
