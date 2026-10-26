# UK preparedness profile

`python3 launch.py nexus` opens the UK-first profile. F6 switches between this and the original technical profile; F5 switches to Home. The chosen profile persists across F5 switches within the running session. Set `NEXUS_PROFILE=technical` to start in the technical profile by default, or pass `--profile technical`.

## Focused layout

The main desktop restores the original NEXUS hierarchy: a permanent clock/weather sidebar, one central subject, and PHP priority plus regional warnings at the right. All source workers continue refreshing in both profiles. A PHP advisory therefore remains visible while the UK map is selected.

Views rotate every 60 seconds:

1. **Local situation:** one large UK map, labelled as geographic context rather than hazard coverage.
2. **PHP watch:** readable vendor details, supplied fixed versions and CISA KEV matching.
3. **Public briefing:** a small number of source-labelled NCSC/BBC headlines, with publication/check dates.
4. **World view:** one rotating globe, sampled ISS statistics and the Bulletin's explicitly symbolic, dated Doomsday Clock setting.

The bottom strip records source changes, not repeated playback. Initial caches and unchanged polls do not generate alerts. A short central terminal briefing appears once per four-minute cycle or after a material security update; it leaves the priority sidebars visible. **T** opens or dismisses it manually.

Press **O** to open the priority source, or click a source card. This invokes the installed browser and may leave the dashboard view. Source opening happens outside the render loop. **1–4** and the numbered header controls choose a view, **A** toggles rotation, and **Space** pauses animation/rotation while feed refreshes continue. Detailed source semantics below remain unchanged.

## Local configuration

Keep your settings in the ignored `config.json`; do not commit your postcode or coordinates. Set `latitude`, `longitude` and `name` at the top level as usual. Add:

```json
"preparedness": {
  "weather_region": "nw",
  "nation": "england",
  "local_alerts": true,
  "local_label": "Your local area",
  "flood_radius_km": 25
}
```

`nw` selects North West England. Other supported region codes are listed in `preparedness.REGIONS`. Without this block, weather coverage is UK-wide and flood coverage is England-wide. Changing region or coordinates uses a separate cache, so old-location alerts do not leak into the new view.

Local flood search uses the Environment Agency's `lat`, `long` and `dist` filters. Its search may be approximated by a bounding box; an alert within the search area is not proof that the configured property is affected. Coverage is **England only**. If `local_alerts` is enabled with a different nation, the EA feed is disabled and the display links to [national flood services](https://www.gov.uk/check-flooding). Scotland, Wales and Northern Ireland do not yet have live flood adapters in this app.

Met Office warnings cover a region, not an individual postcode. The display calls them bulletins, retains the original severity title and links to the source for exact affected places and validity times. It does not infer active warning intervals from free-text descriptions or treat an empty bulletin feed as an all-clear.

## Sources and refresh

- [GOV.UK terrorism threat levels](https://www.gov.uk/terrorism-national-emergency): hourly. The parser matches the UK national sentence specifically, not Northern Ireland's separate assessment or the list of definitions. A layout/wording change fails closed: the last known assessment is retained with a stale indicator. Page-update metadata is not interpreted as the date the threat level changed.
- [Met Office RSS](https://weather.metoffice.gov.uk/guides/rss): every five minutes. Original titles, source URLs and publication timestamps are retained. Regional bulletins may cover future periods or multiple areas; consult validity details at the source.
- [Environment Agency real-time API](https://environment.data.gov.uk/flood-monitoring/doc/reference): every 15 minutes. Severity levels 1–3 are retained; level 4 (no longer in force) is excluded. **This uses Environment Agency flood and river level data from the real-time data API (Beta).** Data is available under the Open Government Licence.
- [NCSC RSS](https://www.ncsc.gov.uk/information/rss-feeds): every 15 minutes. Official publications are not automatically labelled active attacks.
- [BBC UK RSS](https://feeds.bbci.co.uk/news/uk/rss.xml): every 15 minutes. Displays attributed headlines and direct source links, with no article-body scraping or generated incident claims.
- [Prepare campaign](https://prepare.campaign.gov.uk/): household reminders are static paraphrases reviewed on 25 October 2026. The campaign site itself is not a live emergency-information service.

The app runs bounded background requests, retains the last successful data on failure, and displays unavailable/stale state. Last-check timestamps describe retrieval, not continuous verification. The source's own publication/update date is shown separately when available. The API is not a replacement for official warnings or emergency notification channels.

The national assessment appears as a small, steady context card, separate from regional warning severity and CVSS. No combined threat score or attack volume is inferred. The large central visual moves gently; decorative border tracers and duplicate warning transcripts are omitted. Source failures keep known warnings visible with stale labels rather than clearing them.

## Checks and cached previews

```sh
python3 -m unittest discover -s tests -v
python3 dashboard.py --snapshot /tmp/uk-status.png --workspace 1
python3 dashboard.py --snapshot /tmp/readiness.png --workspace 3
python3 dashboard.py --snapshot /tmp/midnight.png --workspace 4
```

Snapshots perform no network access; they use cache files and show a connecting state if none exists. `NEXUS_CACHE` can redirect caches for isolated tests. Tests cover source parsing, missing data, local scope, cache separation, stale data after failures, published-setting invariance, and empty/populated screen rendering. Hardware startup, browser handoff and Pi performance still need an on-device check.

## Doomsday Clock source record

The published setting lives in `data/doomsday-clock.json`, with announcement date, verification date, publisher and original statement URL. It is editorially maintained, not automatically scraped. On a new Bulletin announcement, verify the original source and update that record; the installer deploys it with the app. The display shows the verification date rather than implying live monitoring. A malformed or missing record shows unavailable instead of a fabricated number.

Source: [2026 Doomsday Clock statement](https://thebulletin.org/doomsday-clock/2026-statement/). The clock is a symbolic assessment of global risks, separate from the UK national terrorism assessment.

### Source changes and briefings

The earlier replay transcript is replaced in the main view by a quiet change strip. It reports additions/edits and items leaving a feed; leaving a feed is not described as resolution or an all-clear. There is no automatic replay of the whole source catalog. The companion display uses the large-text rotating pages described below.

### MPI3501 companion LCD

`companion.py` renders a separate 480×320 Pygame view directly to the ILI9486
RGB565 framebuffer, without changing the HDMI desktop. It checks the framebuffer
name, dimensions, offsets, colour masks and stride before writing. It runs at two
frames per second and reloads the main dashboard's location-specific cache every
10 seconds, without additional network requests. Cached assessments and stale
sources are labelled; the clock uses the same dated Bulletin record as the main UI.
Touch navigation is not implemented.

For the tested MPI3501 board, first load the driver temporarily on the Pi:

```sh
sudo dtoverlay piscreen speed=16000000 rotate=270 fps=10
```

After installing the repository with `scripts/install.sh`, start the companion:

```sh
systemctl --user daemon-reload
systemctl --user enable --now nexus-companion.service
```

Once the physical screen is confirmed working, persist the driver:

```sh
sudo sh ~/dashboard/enable-companion-boot.sh
```

This backs up `/boot/firmware/config.txt` and appends an SPI/piscreen section.
It does not reboot or remove the HDMI configuration. A reboot remains untested
until performed on the hardware. To stop the companion, use
`systemctl --user disable --now nexus-companion.service`. Restore the dated boot
configuration backup to remove the persistent overlay.

The companion LCD uses a sci-fi two-column console. The threat assessment box
is always visible at top left; the connection box stays at top right. The main
content slot cycles every 13 seconds through weather, floods and NCSC; a smaller
slot changes on an independent 19-second schedule through floods, BBC and source
freshness. Slots briefly shutter closed and reveal their replacement, also when
their source cache refreshes. Threat text is never shuttered. Moving corner
accents and weather-type symbols provide motion without blinking warning words.
The render loop targets up to eight frames per second, bounded by framebuffer I/O.

Weather panels use solid yellow, amber or red backgrounds from the bulletin's
reported colour, with dark high-contrast text. Wind, rain and snow/ice get vector
symbols based on the warning title; other bulletins get a warning triangle.
These represent bulletin type, not invented current weather observations.
The continuous warning rail and explicit stale header/asterisks remain.

The connection box checks default route/carrier, pings the gateway and measures
TCP port-443 connection time to 1.1.1.1, with 8.8.8.8 as fallback. After a probe
completes, the bottom sweep travels in 1.5–6 seconds according to measured latency:
low latency is faster. The worker waits that duration before the next bounded
probe; its real completion counter and measured latency update on completion.
The sweep can briefly wait at the end while a probe is in flight. It never
increments a fake success count. Failure or stale results replace the sweep with
a broken animated trace. Failed probes retry after four seconds.

Missing link/route says LOCAL DOWN; gateway success with failed external probes
says WAN CHECK; ambiguous gateway/external silence says LINK CHECK. CONNECTED
proves only the tested TCP path, not DNS or every feed. Results older than 35
seconds are marked stale. Small chart bars retain measured latency history.
Snapshots do not start probes. Configured LCD orientation remains unchanged.

The LCD reads the shared cache every ten seconds. A background fallback checks
for overdue threat, weather, flood, NCSC and BBC sources every 30 seconds, requesting only
those past their normal refresh interval. Failed attempts retry at most every
five minutes and retain last known data with honest stale labels. This keeps
LCD refresh independent of the selected main launcher view. Concurrent cache
writes use unique temporary files and atomic replacement; snapshots never fetch.
The HDMI dashboard uses the persistent sidebars and central views described above.

### Map and warning semantics

The UK map uses a cached Natural Earth 1:50m basemap. Only the configured location
is marked; no incident coordinates are fabricated. Gentle perspective drift,
grid, shadow and uniformly raised country surfaces are decorative, not measured
terrain or risk height.

Map data: Natural Earth, public domain,
https://www.naturalearthdata.com/about/terms-of-use/
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson
Only UK and Ireland geometries are bundled in `data/uk-map.geojson`.

The main dashboard's regional warning card and the companion weather page use
the retained warning model. Initial cached warnings are shown without being
called new. New or changed warning identities and severities are tracked;
headlines do not trigger warning alarms.

Weather validity is read from the RSS description using UK local time and the
warning link's date. Upcoming warnings are labelled; expired warnings are omitted.
Unknown formats say CHECK VALIDITY AT SOURCE. Coverage remains the configured
region, not a claim that every warning applies at your address. Successful empty
feeds clear warnings; failed, missing or stale sources retain the last known
warning with a STALE label. A record leaving a current feed is not reported as
resolved or an all-clear. Space freezes animation while source refresh and
warning lifecycle continue. Click a source card or press O to open its source.

Set `"companion_rotation": 180` in your private `config.json` to turn the small LCD upside down (default `0`). Restart `nexus-companion.service` after changing it. This leaves HDMI orientation unchanged and survives updates.

The companion connection box shows current TCP latency plus MIN/MAX successful
latency since that companion service started (milliseconds, including fallback
probe targets). Failed probes do not change the extrema. Restarting the service
resets the session; no samples are displayed as `--`.

The compact LCD uses two persistent large status panels (threat and weather),
one full-width rotating briefing, and a bottom ping bar. Current, session MIN
and session MAX TCP latency all sit on that animated bar. There is no separate
connectivity box. Headline type is 32px and latency values are 24px; stale labels
and warning validity remain visible while repeated source metadata is reduced.

The LCD ping sweep is a continuous 1.1-second activity animation while the last
probe is successful and fresh. It does not represent individual packets or
probe completion. Numeric readings still come only from real probes; failures
and stale probes stop the healthy sweep. Frame pacing targets the LCD driver's
10 fps and includes render time.

### Optional red LED

After installing, run `sudo sh ~/dashboard/enable-warning-led.sh` once, then
`systemctl --user enable --now nexus-warning-led.service`. The helper grants your
account access only to the PWR LED brightness/trigger controls and reapplies that
access at boot. The indicator itself runs as your normal user. It flashes at
1 Hz for fresh in-force weather warnings, local flood alerts, or a severe/critical
national threat. Upcoming, unknown-validity and stale weather alerts do not flash.
With no qualifying warnings, or on a normal service stop, it restores the original
LED trigger. While flashing, the red LED is a Nexus indicator rather than the
normal power-status indicator. Disable with
`systemctl --user disable --now nexus-warning-led.service`.
