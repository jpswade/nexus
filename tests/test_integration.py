import os
import json
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from terminal_theme import FONT, switch_view

ROOT = Path(__file__).resolve().parents[1]


def sample_cache(directory):
    """Clearly synthetic records for rendering populated layouts offline."""
    now = time.time()
    directory = Path(directory)
    (directory/'security').mkdir(parents=True, exist_ok=True)
    php = {'id': 'DEMO-ADVISORY-001', 'ghsa': 'DEMO-GHSA',
           'summary': 'Demonstration advisory: a deliberately long title checks readable wrapping across the terminal briefing.',
           'severity': 'critical', 'score': 9.2, 'cvss_version': '4.0',
           'published': now, 'patches': ['DEMO 8.x.1', 'DEMO 8.y.2']}
    for name, items in [('php', [php]), ('kev', [
        {'id': f'DEMO-CVE-{i:03}', 'vendor': 'Example vendor', 'product': 'Demonstration product',
         'added': '2026-10-25', 'action': 'Follow demonstration vendor guidance', 'ransomware': 'Unknown'}
        for i in range(4)]), ('phpnews', [{'title': 'Demonstration follow-up announcement with a long descriptive title',
                                        'published': now, 'cves': ['DEMO-ADVISORY-001']}])]:
        (directory/'security'/f'{name}.json').write_text(json.dumps({'items': items, 'fetched': now}))
    for name, sample in {
        'iss': {'latitude': 28, 'longitude': 12, 'altitude': 410, 'velocity': 27600},
        'kp': {'value': 4.2}, 'wind': {'value': 450},
        'quakes': {'events': [{'time': now, 'lat': 34, 'lon': 14, 'mag': 4.1, 'place': 'Demo location'}]},
        'weather': {'temp': 12, 'code': 2},
    }.items():
        (directory/f'{name}.json').write_text(json.dumps({**sample, 'observed': now, 'fetched': now}))


class IntegrationTests(unittest.TestCase):
    def test_launch_both_views_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, 'NEXUS_CONFIG': str(ROOT/'config.example.json'),
                   'NEXUS_CACHE': directory}
            for workspace in range(1, 5):
                result = subprocess.run([sys.executable, 'launch.py', 'nexus', '--snapshot',
                                         str(Path(directory)/f'{workspace}.png'),
                                         '--workspace', str(workspace), '--age', '3'],
                                        cwd=ROOT, env=env, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertTrue((Path(directory)/f'{workspace}.png').exists())
            result = subprocess.run([sys.executable, 'launch.py', 'home', '--config',
                                     str(ROOT/'home.example.json'), '--check'],
                                    cwd=ROOT, env=env, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            sample_cache(directory)
            for workspace, age in [(1, 3), (2, 3), (2, 15), (3, 3), (4, 3)]:
                result = subprocess.run([sys.executable, 'launch.py', 'nexus', '--snapshot',
                                         str(Path(directory)/'populated.png'), '--workspace',
                                         str(workspace), '--age', str(age)], cwd=ROOT, env=env,
                                        capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_switch_replaces_process_with_shared_launcher(self):
        with patch('os.execv') as execute:
            switch_view('home')
        execute.assert_called_once_with(sys.executable,
                                        [sys.executable, str(ROOT/'launch.py'), 'home'])
        self.assertTrue(FONT.exists())


if __name__ == '__main__':
    unittest.main()
