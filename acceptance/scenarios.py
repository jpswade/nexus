"""Synthetic card-boundary fixtures; not raw feed adapter acceptance evidence."""
from copy import deepcopy

NOW = 1793793600
CONTEXT_KEYS = ('uk', 'security', 'weather', 'emergency', 'radar', 'space',
                'network', 'motion', 'telemetry', 'source_records', 'planet', 'location')


def card(**changes):
    value = dict(id='synthetic-warning', group='situation', title='SYNTHETIC warning',
                 body=['Synthetic source explicitly issued this warning.'],
                 source='SYNTHETIC authority', url='https://example.invalid/warning',
                 published=NOW - 60, checked=NOW, valid_until=NOW + 600,
                 state='current', severity='warning', pinned=True, duration=20)
    value.update(changes)
    return value


def scenarios():
    """Fresh objects on every call; explicit review oracles belong to each case."""
    cases = [
        ('quiet-empty', [], {}, ['Fresh empty sources remain in summary; no empty rotation slots.']),
        ('new-warning', [card()], {}, ['Source-backed warning takes priority; retain source and validity.']),
        ('retained-stale-warning', [card(state='stale', checked=NOW-7200)], {},
         ['Retain unresolved evidence with stale label; failed refresh is not cancellation.']),
        ('expiry', [card(valid_until=NOW, state='info', pinned=False)], {},
         ['At expiry remove active priority, retain accessible history; test before/at/after boundary.']),
        ('conflicting-threat', [card(id='threat', title='SYNTHETIC threat disagreement',
          body=['Synthetic primary assessment: SUBSTANTIAL; checked now.',
                'Synthetic fallback assessment: MODERATE; checked earlier.',
                'Primary and fallback disagree; neither is a new overall risk score.'],
          severity='info', pinned=False, valid_until=None)], {},
         ['Show both source dates and provenance; source failure does not change threat severity.']),
        ('failed-feed', [card(id='feed', group='node', title='SYNTHETIC feed unavailable',
          body=['Fetch failed; warning status unknown.'], state='unavailable', severity='info',
          published=None, checked=NOW, valid_until=None, pinned=False)],
         {'network': {'offline': False, 'checked': NOW, 'failures': 0}},
         ['Failed check stays visible; no offline takeover or invented warning.']),
        ('long-text', [card(title='SYNTHETIC long warning ' * 12,
          body=['Long source-backed briefing with readable wrapping. ' * 40], duration=90)], {},
         ['Readable dwell; no fast ticker; essential text and detail controls accessible.']),
        ('offline-unconfirmed', [], {'network': {'offline': False, 'failures': 2, 'checked': NOW}},
         ['No takeover before confirmed Pi-offline state.']),
        ('offline-confirmed', [], {'network': {'offline': True, 'failures': 3, 'checked': NOW}},
         ['Preserve confirmed-offline takeover and persistent network strip.']),
        ('offline-stale', [], {'network': {'offline': True, 'failures': 3, 'checked': NOW-120}},
         ['Old offline evidence must not trigger fresh takeover.']),
        ('recovery', [], {'network': {'offline': False, 'failures': 0, 'checked': NOW}},
         ['Recovery clears takeover; verify in sequence after confirmed outage.']),
        ('camera-loss', [], {'motion': {'online': False, 'state': 'unavailable', 'checked': NOW}},
         ['Quiet unavailable eye; no emergency escalation or page switch.']),
        ('camera-movement', [], {'motion': {'online': True, 'state': 'activity', 'checked': NOW,
          'last_motion': NOW, 'last_pulse': NOW, 'observe': False}},
         ['Subtle eye only; movement is not occupancy; LED remains off; no image retention.']),
        ('observatory-manual', [card(id='observatory', group='observatory', title='SYNTHETIC ISS context',
          body=['Background context only.'], severity='info', pinned=False, valid_until=None)], {},
         ['Excluded from automatic emergency rotation; available manually.']),
    ]
    return deepcopy([dict(name=name, now=NOW, cards=cards, context=context, review=review)
                     for name, cards, context, review in cases])
