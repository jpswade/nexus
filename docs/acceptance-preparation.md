# Display acceptance preparation (#50)

Status: the four implementation branches are integrated in PR #54. The preparation
harness below is retained as a contract check. `acceptance.combined` exercises the
real scheduler and both renderers against all 14 synthetic boundary scenarios;
raw feed and policy integration is covered by the unit suite. Hardware rollout
results are recorded in PR #54, separately from synthetic checks.

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m acceptance.combined --out /tmp/nexus-acceptance
```

The integration also propagates source failures, retains stale warnings, skips
summary-only empty cards, preserves enriched CVSS scores, deduplicates displayed
content and packages every root runtime module. Tests use explicit camera fixtures
and do not depend on a developer's local preview directories.

The remaining sections describe the original acceptance checklist and rollback
procedure; they are not a claim that preparation alone completes rollout.

## Reproduce locally

From the repository root, using Python 3.10+ with project dependencies:

```sh
python -m acceptance.harness
python -m unittest discover -s tests -p test_acceptance_preparation.py -v
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -v
sh -n scripts/install.sh
```

The harness reports preparation status and exits nonzero on a packaging error or
invalid fixture. A zero exit is **not combined acceptance**. Fixtures use a fixed
clock and synthetic `example.invalid` URLs, with no private camera input or images.
`scenarios()` returns independent objects, so one run cannot contaminate another.

The 14 cases cover quiet/empty, new warning, retained stale warning, expiry,
conflicting threat sources, failed feed, long text, unconfirmed/confirmed/stale
offline evidence, recovery, camera loss/movement and manual observatory content.
Each includes review oracles. They are card-boundary inputs for rendering, not
expected output from raw feed adapters. Empty context means unknown; the quiet
case still needs a fresh-empty raw source fixture after #47 supplies its schema.
Expiry includes a retained informational card with a source warning severity:
that is not evidence of current active danger. Final #47 semantics must decide
whether history is retained in cards or only in source details.

## Contract and integration work still required

Use `briefing_policy.build_cards(context, now)` with optional context keys `uk`,
`security`, `weather`, `emergency`, `radar`, `space`, `network`, `motion`,
`telemetry`, `source_records`, `planet`, `location`. Absent data is unknown.
Validate output with `acceptance.harness.validate_cards`:

- `id`: stable string; `group`: situation/cyber/infrastructure/node/observatory.
- `title`, `source`, `url`: strings; `body`: list of strings.
- `published`, `checked`, `valid_until`: epoch numbers or null.
- `state`: current/stale/unavailable/info.
- `severity`: info/advisory/warning/critical, source-backed, never an aggregate score.
- `pinned`: boolean; `duration`: positive seconds.

The validator checks shape, not truthful provenance or semantic correctness.
Do not manufacture provider payload schemas to make these fixtures pass policy.

1. **#47:** add real synthetic raw-source contexts and assert the produced cards,
   stable IDs and deduplication. Exercise `Rotation.select(cards, now, group=None)`
   before/at/after dwell and validity boundaries. Assert warning preemption,
   sustained non-starvation across multiple cycles, stable selection within dwell,
   explicit group filtering and observatory exclusion by default. Check missing,
   fresh-empty, stale-empty, failed and recovered source records separately.
2. **#48:** connect card fixtures and actual policy outputs to the desktop renderer.
   Render every case at 1280x720; verify any additional supported HDMI resolution.
   Check two columns, one clock, source controls, dates/validity and persistent
   threat/provenance/network/camera. No permanent PHP sidebar or duplicate maps.
3. **#49:** render at 480x320, including the final 180-degree framebuffer transform.
   Verify single readable item, checks/weather and persistent network strip.
   Replay unconfirmed -> confirmed -> recovered outage in one renderer instance,
   and stale offline evidence separately. Feed failure must not trigger takeover.
4. **Combined:** run the complete suite on the actual integrated SHA and repeat
   every scenario in both renderers. Review at beginning/middle/end of dwell and
   after warning arrival, expiry and recovery. Save synthetic previews outside the
   repository; record their paths and SHA in the parent acceptance report.

For each render, check essential text without overlap/truncation, readable font and
dwell, accessible source link/publication/check/expiry details, and no fast ticker.
A nonempty PNG or successful draw is not visual acceptance. Capture layout bounds
from renderers when available and inspect previews at native resolution. There are
no redesigned previews in this preparation PR; existing baseline snapshot tests
create temporary images and delete them.

Coverage must include official threat primary/fallback disagreement and blocked
MI5 access; Emergency Alerts, Met Office warnings and EA floods; Open-Meteo,
Elexon, Radar, NOAA G/R/S/bulletins and Met Office space forecast; dated NCSC,
CISA KEV/CVSS, PHP and filtered official briefings; node health/history and optional
ISS/quakes/solar/Doomsday Clock. Preserve unknown grid validity/cancellation,
source limitations, source dates, and correct BBC/CISA attribution. Never turn
feed health, symbolic context or camera movement into invented danger levels,
occupancy or battery percentage.

## Packaging gate

The installer copies every root `.py` runtime module, including future policy and
renderers, and compiles all runtime Python sources in memory before installation.
It does not install `acceptance/` or tests. Keep new runtime modules at root or add
new package directories explicitly to both installer and audit. The static audit
covers nested imports, local modules and declared pip dependencies. Dynamic
imports, distribution/import name aliases, OS commands and assets need explicit
review. It does not prove availability on a Pi or validate dependency versions.

Pygame is mandatory (`requirements.txt`). Pillow is documented separately in
`docs/camera-eye.md` and required only for the optional camera worker; its scoped
exception in the audit is not evidence that Pillow is installed. On a coordinated
target check, verify Python, pygame, Pillow if camera enabled, systemd services,
fonts/maps/assets and permissions before restarting anything. Do not enable the
camera or warning LED as a packaging test. New third-party imports must have
appropriate requirements/installer changes coordinated with their owner.

The copy test executes only the installer module-copy statement in temporary
folders (including paths with spaces), verifies future runtime modules are copied,
and verifies private JSON is excluded from that statement. It never executes the
installer. The real installer still copies operator config and restarts the main
service: do not run it as a test on the Pi. Use a clean checkout as its source;
root Python globs also copy any untracked Python files present there.

## Parent-coordinated Pi validation and rollback (not executed)

Before authorizing rollout, record baseline and candidate SHAs, OS/Python/package
versions, screen sizes/orientation, service state and existing FPS/CPU/RSS using
the same workload, duration and measurement method. Agree performance tolerances
before measuring; none are invented here. Include quiet, warning, long-text and
outage/recovery workloads, warm-up and sustained operation. Compare frame-time
percentiles and sustained FPS, CPU, RSS and memory growth. Check bounded cache/log
sizes and absence of render-thread networking; synthetic offline renders must not
fetch feeds. Document collection tooling, sample duration and any missing metrics.

Keep the current display available. Make a private, permission-preserving backup
of the **entire** installed dashboard tree and affected user service/autostart
files, plus their enabled/running states. A dashboard.py-only backup from the
installer is insufficient for multi-module rollback. Preserve private config,
layout and camera configuration outside git; never upload those backups, logs,
credentials, camera images or host addresses. Confirm the red camera hardware LED
is off before and after any authorized run; do not change that setting. Camera
movement must stay subtle, without page switching, escalation or image retention.

Roll out only after parent approval and complete local gates. Restart only the
approved services; check both screens, physical rotation, source details, offline
confirmation/recovery and private camera permissions. Stop if crash loops, missing
modules/assets, unreadable essential content, lost warning evidence, false offline
takeover, LED activation, image retention or agreed performance limits fail.

On rollback, stop the affected display services, restore the complete previous
code/assets and service/autostart definitions with their permissions, preserve
current private configuration deliberately, reload user systemd, and restore the
recorded enabled/running states. Recheck both screens, rotation, offline takeover
and LED-off state against the baseline. Do not restore only dashboard.py or blindly
copy old cache data over current evidence. Record rollback result and remaining
gaps privately; the parent decides when to retry. No agent merges or deploys.
