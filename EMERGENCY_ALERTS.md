# GOV.UK Emergency Alerts

The independent `emergency_alerts.py` adapter monitors
https://www.gov.uk/alerts/current-alerts and its official linked detail pages.
It does not change the UK terrorism assessment or use private location data.
No Cloudflare service or token is needed for these public GOV.UK endpoints.
HTTP challenges, redirects, unexpected markup and failed requests are unreadable
checks, never an empty result. There is no token-dependent fallback.

## Publishing structure verified 4 November 2026

The current page explicitly said “There are no current alerts.” Its HTML also
advertises `/alerts/feed.atom`. The live Atom feed includes historical entries
(the first is a 2021 test), so feed membership is not evidence of an active alert.
`/alerts/past-alerts` groups historical messages under date and area headings.
Detail pages such as `/alerts/8-jan-2026-2` and `/alerts/7-sep-2025` have an
Emergency Alert h1, paragraph instructions, ISO timezone-aware `time` elements,
“Sent by” issue time, “This alert was sent to” area, and an h2 “Stopped sending”.
Broadcast cessation is **not hazard expiry**. No machine-readable hazard validity
or geographic boundary was found in those pages. Times in the UI are UTC.

Only an explicit empty current page or a complete recognised listing can replace
last-known state. Every linked detail must parse successfully. Tests are labelled
separately, using explicit test language; past/stopped, explicitly cancelled,
expired and removed-from-list records retain their distinct state. Removal is
labelled WITHDRAWN (from the listing), not proof that the emergency ended.
Explicit validity timestamps are respected; no TTL is invented for the hazard.
Unknown validity and issue time are displayed as not published. Freshness expires
after 15 minutes, independently from any source validity.

All published areas are shown conservatively with “local applicability unverified”.
No string matching/geocoding assumes a local match or suppresses potentially
relevant messages. Current records stay in a persistent central desktop panel
and companion panel across all workspaces, including technical mode and cached
network status. Multiple records rotate within that reserved panel; each stays
long enough to page through its full instructions. Desktop clicking opens the
source; the companion prints its URL. The header and ping/Wi-Fi strip remain.
When none are current, ended records collapse to an explicitly labelled status
strip; their full details remain cached and the desktop strip links to the source.

## Resource and failure policy

Poll at most every five minutes across processes using a nonblocking flock;
workers never run on the render thread. Limit each response to 1 MiB and each
check to 16 detail pages plus the index. A 45-second monotonic budget bounds the
check, with socket waits capped at eight seconds (an in-progress read may finish
up to eight seconds after the budget; platform DNS resolution is OS controlled).
No redirects, arbitrary hosts, query strings, scripts, APIs or third-party proxies
are followed. Atomic JSON caching retains the last successful timestamp and
records a failed check across restarts. Corrupt/oversized caches are unavailable.
Disk failures mark the in-memory state stale. The cache stores at most 16 current
and 16 retained records. It never contains private configuration or credentials.

## Integration and tests

`dashboard.py` starts the source for both profiles and passes its snapshot through
`FocusedDesktop.emergency_data`; `focused_ui.py` draws the card after animations
and the terminal. `companion.py` starts the same lock-coordinated source and draws
after content, outside the unchanged threat and ping rectangles. Its old whole-
screen offline takeover remains in place and takes priority on the companion
during confirmed local probe failures. Cached alerts reappear on recovery. `scripts/install.sh`
copies the two new modules. No PreparednessFeeds schema changes are required.

Run `python -m unittest discover -s tests -p test_emergency_alerts.py` with dummy
SDL video/audio drivers. Three HTML fixtures preserve the public main elements
fetched on 4 November; current, cancelled, expiry and challenge fixtures are
synthetic. There was no live current alert to validate the active-page branch;
it uses the verified historical structure and rejects unsupported layouts.

## Attribution

Contains public sector information licensed under the **Open Government Licence
v3.0**: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/.
Source: **GOV.UK Emergency Alerts**, https://www.gov.uk/alerts, © Crown copyright.
This attribution applies to reproduced alert text and recorded HTML fixtures.
The GOV.UK footer and Atom rights field identify OGL reuse; the licence site
returned HTTP 403 during verification. Synthetic fixtures are explicitly examples.
Nexus is a secondary display, not a replacement for official emergency channels.
