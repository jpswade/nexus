"""Preparation-only checks: these do not exercise redesigned displays."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from acceptance.harness import ROOT, packaging_errors, report, validate_cards
from acceptance.scenarios import card, scenarios


class AcceptancePreparationTests(unittest.TestCase):
    def test_all_scenarios_have_valid_contract_and_review_oracle(self):
        cases = scenarios()
        self.assertEqual(len({case['name'] for case in cases}), 14)
        for case in cases:
            with self.subTest(case=case['name']):
                validate_cards(case['cards'])
                self.assertTrue(case['review'])
        cases[1]['cards'][0]['body'].append('mutation')
        self.assertNotIn('mutation', scenarios()[1]['cards'][0]['body'])

    def test_rejects_contract_corruption(self):
        for changes in ({'id': ''}, {'body': 'text'}, {'body': [1]},
                        {'pinned': 1}, {'state': 'safe'}, {'severity': 'risk-7'},
                        {'group': 'emergency'}, {'duration': 0}, {'duration': True},
                        {'checked': float('nan')}, {'published': 'today'},
                        {'valid_until': float('inf')}, {'source': None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_cards([card(**changes)])
        with self.assertRaises(ValueError):
            validate_cards([card(), card()])
        missing = card()
        del missing['checked']
        with self.assertRaises(ValueError):
            validate_cards([missing])

    def test_null_dates_unknown_and_empty_cards_are_valid(self):
        validate_cards([])
        validate_cards([card(published=None, checked=None, valid_until=None,
                             state='unavailable', severity='info')])

    def test_report_cannot_be_mistaken_for_combined_acceptance(self):
        result = report()
        self.assertTrue(result['combined_acceptance'].startswith('NOT RUN'))
        self.assertTrue(result['hardware'].startswith('NOT RUN'))
        self.assertTrue(result['previews'].startswith('NOT GENERATED'))
        self.assertEqual(result['packaging_errors'], [])

    def test_runtime_dependency_audit(self):
        self.assertEqual(packaging_errors(), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'scripts').mkdir()
            shutil.copy(ROOT/'scripts/install.sh', root/'scripts/install.sh')
            shutil.copy(ROOT/'requirements.txt', root/'requirements.txt')
            (root/'future_renderer.py').write_text('def draw():\n    import undeclared_renderer_dependency\n')
            self.assertEqual(packaging_errors(root),
                             ['future_renderer.py: undeclared import undeclared_renderer_dependency'])

    def test_installer_root_copy_includes_future_modules_not_private_json(self):
        # Execute only the actual module-copy line against temporary directories.
        # Never run install.sh: it restarts services and requires private config.
        line = next(line for line in (ROOT/'scripts/install.sh').read_text().splitlines()
                    if line == 'cp "$SOURCE/"*.py "$DEST/"')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source with spaces'
            dest = Path(directory)/'dest with spaces'
            source.mkdir(); dest.mkdir()
            for path in ROOT.glob('*.py'):
                shutil.copy(path, source/path.name)
            (source/'briefing_policy.py').write_text('# Synthetic future runtime module\n')
            (source/'future_renderer.py').write_text('# Synthetic future runtime module\n')
            (source/'camera.json').write_text('{}')
            (source/'config.json').write_text('{}')
            subprocess.run(['sh', '-eu', '-c', line], check=True,
                           env={'SOURCE': str(source), 'DEST': str(dest), 'PATH': '/usr/bin:/bin'})
            self.assertEqual({p.name for p in dest.iterdir()},
                             {p.name for p in source.glob('*.py')})

    def test_installer_shell_syntax(self):
        subprocess.run(['sh', '-n', str(ROOT/'scripts/install.sh')], check=True)


if __name__ == '__main__':
    unittest.main()
