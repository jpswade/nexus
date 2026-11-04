# Source health and check history

Click any desktop LIVE CHECKS header cell (GOV.UK, GRID, WEATHER, FLOODS)
to open its central detail panel. Click the same cell again or CLOSE to return.
The panel shows last completed attempt, last successful fetch, feed health,
recent checks and an official-source link; O also opens that source. Sidebars
remain visible. The companion's right-hand channel includes a 16-second health
card every 48 seconds, cycling these four sources over 192 seconds. Threat,
clock, weather strip, ping/Wi-Fi and the existing offline takeover remain intact.
A failed feed is never evidence that the Pi is offline. LED behavior is unchanged.

History is local to the existing `NEXUS_CACHE` directory. Each instrumented
source has `health-<name>.json` and a small lock file alongside its existing cache.
Weather/flood and other preparedness history uses the existing location-specific
cache directory, so changing scope starts a new baseline. No extra HTTP requests
are made for either display. History reads occur every ten seconds. Existing
caches can supply a last successful fetch; a last attempt is never invented.

The journal keeps at most 64 completed attempts per source, restricted to seven
days on read and the next write. Inactive files are not periodically rewritten;
old location directories follow existing cache lifecycle. Each file is capped at
64 KiB on read; generated files are smaller than 8 KiB. Cross-process file locks
and atomic replacement serialize writers. Corrupt/oversized history is ignored
and rebuilt on the next check; an unwritable journal does not fail the feed.
Stop both services before deleting `health-*.json` to reset history. There is no
remote upload or new configuration/credential requirement.

Events are BASELINE, CHECKED, FAILED, RECOVERED or CHANGED. Successful empty
results count as data; failures retain the previous successful fingerprint.
Reordering rows and poll timestamps do not count as changes. A changed parsed
payload is a source-content change, **not** an incident or severity judgment.
The journal intentionally stores no headlines, URLs, raw errors, coordinates,
configuration or payloads: only fixed event codes, timestamps and SHA-256 hashes.
It cannot reconstruct old bulletins; follow the official source for their text.
Routine checks can evict older changes within the 64-entry bound. In-flight
attempts and process crashes before completion are not journaled.

Instrumented hooks: `PreparednessFeeds.refresh` (all its sources),
`GridNotices.refresh`, `EmergencyAlerts.refresh`, and the shared `PlanetFeeds`
worker for its security subclass's php/kev/phpnews feeds. Planet telemetry,
Open-Meteo, space weather, radar and local network probes are not journaled.
UI integration is confined to `focused_ui.py`, `dashboard.py`, `companion.py`
and the new `source_details.py`; adapters keep their existing schemas and cadence.

## Official source limitations checked 4 November 2026

- [GOV.UK Emergency Alerts](https://www.gov.uk/alerts) is a published web listing,
  not a cell-broadcast receiver. It does not replace other warning channels.
- [Met Office RSS guidance](https://weather.metoffice.gov.uk/guides/rss) describes
  regional severe-weather warning feeds. An empty configured feed is not an all-clear.
- [Environment Agency API reference](https://environment.data.gov.uk/flood-monitoring/doc/reference)
  documents warning severity filters and explicitly disclaims safety-critical use
  and guaranteed service. The configured England feed is not UK-wide coverage.
- [Elexon SYSWARN schema](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/SYSWARN/stream)
  exposes publication time, warning type and text. These do not establish local
  impact, active status, or cancellation matching; no adapter interpretation changed.

Verification: `python -m unittest discover -s tests -q`; headless Pygame renders
at 1280×720 and 480×320 with synthetic data. Hardware timing/touch/framebuffer
behavior requires a Pi; no device was deployed to during this implementation.
