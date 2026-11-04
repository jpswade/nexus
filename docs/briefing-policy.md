# Shared briefing policy (#46 / #47)

`build_cards(context, now)` is deterministic and performs no I/O. `now` is epoch
seconds. It returns plain dictionaries with exactly these fields:

- `id`: stable source-prefixed string, unaffected by check time or freshness.
- `group`: situation, cyber, infrastructure, node, or observatory.
- `title`, `source`, `url`: strings; unknown links are empty.
- `body`: list of full strings. Renderers must wrap/page them, not discard essential text.
- `published`, `checked`, `valid_until`: epoch seconds or null. Checked is the
  latest recorded attempt, falling back to successful fetch; it is not publication.
- `state`: current, stale, unavailable, or info (ended/historical evidence).
- `severity`: info, advisory, warning, critical. This is a source classification,
  never a combined threat score or claim about asset exposure.
- `pinned`: priority candidate, not a request to monopolise rotation.
- `duration`: seconds; **zero means compact summary only**. Positive dwell is
  at least 30 seconds, plus enough time for full text at 120 words/minute.
  LCD pages hold for 15 seconds. Both displays show a draining countdown bar;
  the LCD counts down to whichever comes first: the next page or card.
  `Rotation.timing(now)` returns the remaining and total seconds for the current
  visit, so a feed refresh does not restart or distort its countdown.

## Input adapter contract

All keys are optional. Missing measurements remain explicit unknowns. Inputs are
snapshots, not feed objects. No private config, images, URLs for camera capture,
exception strings, or network addresses are copied into cards.

- `uk`: PreparednessFeeds data dictionary or `(data, errors)` snapshot pair.
  Includes threat, weather warnings, floods, ncsc, legacy news (CISA KEV), grid,
  govuk. Pass source-filtered feeds for the configured location.
- `security`: SecurityFeeds data dictionary or `(data, errors)` pair, containing
  php, kev, phpnews. If both KEV paths exist, security.kev wins; no duplicate
  UK news presentation. KEV is labelled CISA, never BBC.
- `weather`: Open-Meteo cache (`temp`, `high`, `low`, `code`, `fetched`); attach
  `failed=True` when the separate weather failure flag is set.
- `emergency`, `radar`: existing EmergencyAlerts / RadarFeed snapshot dictionaries.
- `space`: SpaceWeatherFeeds.snapshot(now), including scales, alerts, met.
- `network`: NetworkMonitor.snapshot(), including checked, label, latency, offline.
  Only explicit `offline=True` is described as confirmed offline. The existing
  confirmed-offline takeover remains the caller's responsibility.
- `motion`: CameraMotion snapshot. Always info and summary-only; never controls
  pages, threat escalation, camera configuration, or the disabled hardware LED.
- `telemetry`: dictionary with epoch `checked`, cpu, memory, temperature, uptime,
  signal, traffic when available. Telemetry.checked internally is monotonic:
  **the UI adapter must supply epoch checked**, not copy that attribute. No battery
  is fabricated. Missing values display unknown.
- `source_records`: source-name → History.read result (failed/attempted etc.).
  Failed records override otherwise fresh cached payloads. This is source health,
  never hazard severity. Raw history remains available to source-detail renderers.
- `planet`: PlanetFeeds dictionary or `(data, errors)` pair. Optional doomsday
  snapshot uses label/fetched; no clock value is invented. Observatory is manual.
- `location`: optional `weather_scope`, `floods_scope` strings for display.
  Without them local applicability is explicitly unconfirmed. No geolocation
  inference is made from a national warning.

Retention is owned by the existing feed caches. Supply the last successful
payload plus failure metadata after a failed refresh. A pure builder cannot
recover evidence discarded by a caller. Fresh empty sources produce summary-only
cards; missing/stale sources remain readable rotation items. Unknown warning
expiry is null and must not be replaced by a freshness deadline. Known expiry
removes priority at the boundary, retaining an informational card for detail view.
Emergency tests/withdrawals and historical space bulletins never escalate.
Grid validity/cancellation remains unstructured and is explicitly labelled.

Severity mappings: Met Office yellow/amber/red → advisory/warning/critical;
EA 3/2/1 → advisory/warning/critical; national severe/critical → warning/critical;
PHP source medium/high/critical → advisory/warning/critical; current real GOV.UK
alerts and active NOAA warnings → warning; active NOAA watches → advisory.
Everything else is informational, including CVSS scores shown with their source,
NOAA scales, internet reports, camera movement and check failures. Threat-source
disagreement is displayed without synthesising a new assessment.

NCSC includes only explicitly dated articles from the current Europe/London day,
excluding future dates and legacy inferred article dates. KEV uses a 30-day window,
PHP advisories/releases 90 days, grid and official briefings 7 days, excluding
future/unknown publication dates. Older raw evidence remains accessible to detail
renderers. Flood timestamps and source publication dates are not check timestamps.

## Rotation

Instantiate `Rotation()` once per independent stream. Call
`select(cards, now, group=None)` each frame with rebuilt cards when inputs/time
change. Returns a card or None. Default excludes observatory; an explicit group
selects only that group. Cards with zero duration or expired validity do not rotate.
Group changes and backward clock jumps reset scheduling. Removal/expiry ends
current dwell immediately; check-time updates and input reordering do not.

At each round boundary, eligible IDs are sorted pinned first, then severity,
then stable ID. Each is served once. New arrivals join the next round, so they
cannot starve existing low-priority items. Warnings do not interrupt readable
dwell: a new warning waits for the current finite round, at most the remaining
sum of its durations. A renderer can show a persistent priority indicator from
pinned cards while the briefing stream finishes its round. There is no hard
upper dwell cap: long source text gets proportionate reading time.

## Synthetic preview and integration

`tests/fixtures/briefing_policy/scenarios.json` contains a fixed clock and synthetic
contexts for quiet/empty, new warning, retained stale warning, expiry, conflicting
sources, failed feed, long text, offline/recovery, camera loss/movement. Preview
any scenario by calling `build_cards(context, fixture['now'])`; no network needed.
Tests assert the fixed public shape as well as semantics and rotation behavior.

UI agents must preserve the persistent frame, source links/dates and accessible
raw details; consume duration=0 checks in compact summaries. Rebuild on UK midnight
and expiry, not only feed refresh. Render full body text with paging where needed.
Installation/integration must include briefing_policy.py and its existing imports
(alert_state/preparedness and their dependencies). No UI or installer is changed
by #47. Combined HDMI/LCD renders, installer validation and Pi performance checks
belong to #50. This policy has no hardware side effects and does not claim Pi
validation, LED changes or deployment.
