"""Offline preparation checks. Run with python -m acceptance.harness.

Does not import application modules, fetch feeds, open devices or claim acceptance.
"""
import ast
import json
import math
from pathlib import Path
import re
import sys

from .scenarios import CONTEXT_KEYS, scenarios

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'id', 'group', 'title', 'body', 'source', 'url', 'published', 'checked',
          'valid_until', 'state', 'severity', 'pinned', 'duration'}


def validate_cards(cards):
    if not isinstance(cards, list):
        raise ValueError('cards must be a list')
    ids = set()
    for card in cards:
        if not isinstance(card, dict) or not FIELDS <= card.keys():
            raise ValueError('missing card contract fields')
        for key in ('id', 'title', 'source', 'url'):
            if not isinstance(card[key], str):
                raise ValueError(f'{key} must be a string')
        if not card['id'] or card['id'] in ids:
            raise ValueError('empty or duplicate stable id')
        ids.add(card['id'])
        if not isinstance(card['body'], list) or any(not isinstance(x, str) for x in card['body']):
            raise ValueError('body must be a list of strings')
        for key, allowed in (
            ('group', {'situation', 'cyber', 'infrastructure', 'node', 'observatory'}),
            ('state', {'current', 'stale', 'unavailable', 'info'}),
            ('severity', {'info', 'advisory', 'warning', 'critical'}),
        ):
            if card[key] not in allowed:
                raise ValueError(f'invalid {key}')
        if type(card['pinned']) is not bool:
            raise ValueError('pinned must be boolean')
        for key in ('published', 'checked', 'valid_until', 'duration'):
            value = card[key]
            if value is None and key != 'duration':
                continue
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'{key} must be finite numeric epoch/duration')
            if key == 'duration' and value < 0:
                raise ValueError('duration must be nonnegative (zero is summary-only)')


def packaging_errors(root=ROOT):
    """Static import/dependency audit; no application import or installer execution.

Includes imports inside functions. Dynamic imports and OS tools require manual review.
    """
    root = Path(root)
    modules = list(root.glob('*.py'))
    packages = [root / name for name in ('pi_dashboard', 'plugins')]
    local = {p.stem for p in modules} | {p.name for p in packages}
    sources = modules + [p for package in packages for p in package.rglob('*.py')]
    # Pillow is intentionally optional, used only by the opt-in camera worker.
    # See docs/camera-eye.md; never waive PIL imports elsewhere.
    optional = {('camera_motion.py', 'PIL')}
    declared = {re.split(r'[<>=!~\[]', line.strip())[0].lower().replace('-', '_')
                for line in (root/'requirements.txt').read_text().splitlines()
                if line.strip() and not line.startswith('#')}
    errors = []
    for path in sources:
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split('.')[0]]
            for name in names:
                if ((str(path.relative_to(root)), name) not in optional
                        and name not in local and name not in sys.stdlib_module_names
                        and name.lower() not in declared):
                    errors.append(f'{path.relative_to(root)}: undeclared import {name}')
    installer = (root/'scripts/install.sh').read_text()
    if 'cp "$SOURCE/"*.py "$DEST/"' not in installer:
        errors.append('installer must include all root runtime Python modules')
    for name in ('pi_dashboard', 'plugins', 'assets'):
        if f'"$SOURCE/{name}"' not in installer:
            errors.append(f'installer missing {name}')
    return sorted(set(errors))


def report():
    cases = scenarios()
    for case in cases:
        validate_cards(case['cards'])
        if set(case['context']) - set(CONTEXT_KEYS):
            raise ValueError('unknown context key')
    errors = packaging_errors()
    return dict(scope='preparation only; synthetic card-boundary fixtures',
                scenarios=len(cases), packaging_errors=errors,
                optional_dependencies={'camera worker': 'Pillow / python3-pil; check on target before enabling'},
                combined_acceptance='NOT RUN: requires #47 policy and #48/#49 render adapters',
                previews='NOT GENERATED: redesigned renderers unavailable',
                hardware='NOT RUN: parent-coordinated Pi validation only')


if __name__ == '__main__':
    result = report()
    print(json.dumps(result, indent=2))
    sys.exit(bool(result['packaging_errors']))
