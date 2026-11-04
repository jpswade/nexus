# Space weather in the infrastructure rotation

The active `dashboard.py` → `focused_ui.py` path shows the infrastructure card
in the latter 30 seconds of world view (view 4). `companion.py` shows it for
16 seconds in each 64-second cycle, above the persistent ping/Wi-Fi strip and
below the existing terrorism/warnings header. The card cycles between NOAA
scales, Met Office UK forecast context and NOAA bulletins. Existing manual view
controls and the companion's pre-existing offline takeover retain their behaviour.
Space weather never feeds the terrorism assessment, warning LED, local weather
warnings or a local infrastructure outage score.

## Official sources and semantics

Verified on 4 November 2026 using direct HTTPS responses:

- [NOAA SWPC alerts JSON](https://services.swpc.noaa.gov/products/alerts.json):
  array of `product_id`, `issue_datetime`, `message`; 87 messages in the sample.
  The official [product page](https://www.swpc.noaa.gov/products/alerts-watches-and-warnings)
  links this feed. Free text contains identity, type, explicit validity windows,
  serial references and sometimes a NOAA scale and geographic impact context.
- [NOAA scales JSON](https://services.swpc.noaa.gov/products/noaa-scales.json):
  object keys `0` (latest observed), `-1` (previous maximum, deliberately unused),
  `1`–`3` (forecast UTC days). The sampled latest observation was G0/R0/S0;
  forecast R/S scale fields were null but probability fields were present.
  We never turn probabilities into observed severity, infer a scale from generic
  impact wording, equate missing with zero, or treat a forecast timestamp as an
  observation. [Scale definitions and geographic effects](https://www.swpc.noaa.gov/noaa-scales-explanation).
- [Met Office public space-weather forecast](https://weather.metoffice.gov.uk/specialist-forecasts/space-weather):
  official HTML, not a documented stable JSON API. The overview's own issued-at
  field was `00:10 (GMT) on Wed 4 Nov 2026`; aurora and imagery had different
  timestamps. The parser isolates `overview-content`, requires the four-day
  summary heading and reads its associated issuance time (GMT/UTC/BST).
  It displays the forecast headline, issue time and four-day period as UK
  context. The period end is a nominal four-day outlook boundary, not a warning
  expiry. No numeric Met Office G/R/S assessment is inferred from prose.

An observation bulletin remains historical; even `Active Warning: YES` is not
proof of a current warning. Warnings/watches require a known start/end and a
current time within that window. Explicit cancellation serials and extension
serials apply within their message code. New all-prior-watch supersession
messages apply across watch codes, including downgrade cases. Feed ordering is
irrelevant. Watch daily dates infer the nearest year to issuance, including
December/January rollover. Tests are never operational. Unknown formats or
missing validity remain unknown, not active. Time windows are re-evaluated on
snapshot, so a cached message expires without another download. Classification
is deliberately conservative: unrecognised free-text relationships are not
invented. The feed is finite and is not an authoritative full active-alert ledger.

G/R/S meters draw only returned numeric levels. G is geomagnetic, R radio
blackout, S solar radiation; these are global environmental scales with differing
impact geographies. The detailed NOAA page shows forecast G levels and R/S
probabilities separately, by UTC day. Bulletin pages rotate through in-window
warnings/watches when present, otherwise through returned historical messages.
The desktop also shows each bulletin's supplied geographic context. Compact
views label NOAA as global; neither display asserts a local grid/GPS outage.
Click the desktop infrastructure card or press O to open that page's official
source. The companion has no new interaction requirement.

## Fetching, cache and failures

No third-party package, API credential, Cloudflare token or local location is
required by these public sources. No unrelated Cloudflare/Internet-outage check
is made or implied by this module. Access denial/challenge responses fail parsing
and produce unavailable/stale state, with no credential request or bypass.

`SpaceWeather` runs one daemon worker per display process. Advisory locks share
checks between processes: check/load/fetch/atomic replace happen under the same
nonblocking file lock. It polls due sources every 30 seconds; NOAA checks have a
five-minute minimum interval, Met Office one hour, including after failures.
Each request uses an eight-second socket timeout, a one-MiB response cap and no
application-level retries. Three fixed official URLs are the only targets.
The timeout is a socket inactivity timeout, not a guaranteed overall deadline
against a server trickling data. Rendering performs no network requests or disk
writes. Panels cache drawing for one second and use simple rectangles/text.

Cache lives at `$NEXUS_CACHE/space-weather`, defaulting to `.cache/space-weather`
beside the modules. Source snapshots retain raw last-good data, successful-fetch
and last-attempt times, and failure status. Atomic replacement prevents torn
reads; corrupt/oversized cache files are ignored. Empty successful alert lists
are distinct from unavailable checks and are never called an all-clear.
Failures preserve last-known data labelled STALE, including across restarts.
Cached in-window bulletins are labelled LAST KNOWN when their source is stale.
NOAA checks age out after 15 minutes; latest scales also age out against their
observation time. Met Office checks age out after six hours, or when its
forecast issue time exceeds 24 hours, even if fetching still succeeds. A
four-day-old outlook is additionally labelled EXPIRED. Future observation/issue
timestamps are stale. Source availability and bulletin validity are independent.

## Attribution and licences

- NOAA/NWS/SWPC data: public domain unless explicitly stated otherwise, per the
  [NWS data/product terms](https://www.weather.gov/disclaimer). NEXUS identifies
  NOAA SWPC, retains times and links to originals. Its parsed summaries and
  visual meters are NEXUS presentations, not official NOAA products or an
  endorsement. NOAA data is not covered by any NEXUS copyright claim. No NOAA
  logo is used. Delivery over the Internet is not guaranteed.
- Met Office forecast text: © Crown copyright, Met Office. Contains public sector
  information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
  The Met Office [legal/licensing policy](https://www.metoffice.gov.uk/policies/legal)
  identifies OGL provisions for website material unless different terms are
  stated. This adapter uses only the text forecast headline and timestamp,
  with source attribution/link and no endorsement. It does not reuse logos,
  third-party imagery (e.g. NASA), videos, or licensed commercial/DataHub products.
- Fixture content is synthetic, modelled on the verified schemas. The public
  live samples used during development are not included in the repository.
- Wary was conceptual inspiration only; no code, imagery, data or branding was
  copied from it.

## Tests and integration

Run `python -m unittest discover -s tests -p 'test_space_weather*.py'` with
`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` on a development machine. Fixture
coverage includes separate scales/probabilities, absent/null values, unordered
bulletins, cancellation/extension, expiry, future windows, test messages,
observations, watch supersession/year rollover, stale producer timestamps,
malformed schemas, bounded fetches and restart/shared-cache behaviour. Render
checks cover every card at both sizes and compare unchanged persistent UI pixels.

The source-specific files are `space_weather.py`, `space_weather_ui.py`, tests,
fixtures and this document. Shared-file edits only add imports/instances and
rotation hooks to `focused_ui.py` and `companion.py`, and install these two modules
plus this document in `scripts/install.sh`. When combining other infrastructure
patches, merge these small hooks into the shared rotation rather than running
multiple cards on top of one another. No change to `preparedness_ui.py`,
`dashboard.py`, threat assessment, private config or persistent network code is
needed. No Pi hardware/deployment validation is claimed.
