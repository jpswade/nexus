# UK preparedness profile

`python3 launch.py nexus` opens the UK-first profile. F6 switches between this and the original technical profile; F5 switches to Home. The chosen profile persists across F5 switches within the running session. Set `NEXUS_PROFILE=technical` to start in the technical profile by default, or pass `--profile technical`.

## Screens

1. **UK status brief:** the UK-wide terrorism assessment from GOV.UK, separately displayed regional Met Office warning bulletins, and last successful check timestamps.
2. **Incident & cyber watch:** alternates NCSC official publications and BBC UK media reports. BBC headlines are selected by explicit topic keywords such as cyber, flood, storm, outage and attack. This selection is not incident verification or risk scoring; political statements and historical reports can appear if their headlines match. Source publication dates remain visible where supplied.
3. **Local readiness:** Environment Agency flood alerts/warnings, geographic scope, update time, and rotating household reminders based on the government Prepare campaign.
4. **Minutes to midnight:** the Bulletin of the Atomic Scientists’ published Doomsday Clock setting: 85 seconds, announced 27 January 2026 and verified against its original statement on 25 October 2026. The setting remains fixed while decorative graphics animate.

Green is routine information, amber draws attention, and red is used for Met Office red warning bulletins or official severe flood warnings. Colours are not combined into an overall threat level. The app labels itself as an independent public-source display, not a government service.

Press **O** to open the primary source for the current screen, or click an `OPEN SOURCE` row. This invokes your installed browser directly and may leave the dashboard view. On a browser-free Pi, consult the source links below on another device. Source opening happens outside the render loop.

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

The status screen emphasises the national assessment with a large, steady word and its plain-language meaning. The five-position strip highlights the official category; its numeric position is not a probability. Animated brackets and a rotating wireframe sphere with orbiting nodes decorate the interface without cycling through threat levels. The same sphere appears beside the midnight clock. Geometry is precomputed and rendering is bounded for the Pi 2; no shader or browser is required. Space pauses these animations with workspace rotation. The primary O shortcut on this screen opens the national assessment; the weather source row remains clickable.

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

### Briefing stream

All four UK workspaces now pair the main assessment with weather and local flood
readouts plus a source-labelled, type-on briefing transcript. The transcript replays
headlines and household guidance; replay is not a new event or a new publication.
It continues across automatic workspace changes. Space pauses animation; Page Up
and Page Down (or the mouse wheel) browse the transcript, and End returns to replay.
Click a headline to open its original source. Source check times and stale status
remain visible. The Doomsday Clock remains the fixed published setting.

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

Both physical displays keep time, UK terrorism assessment, weather bulletin summary,
flood alert count and the published Doomsday Clock visible. All four UK workspaces
share the same status strip. Weather colour is the highest colour returned by the
feed, not an inference that every warning applies at the current instant. Original
source area and validity checks still apply. The LCD keeps weather details fixed
and rotates only its secondary news line.

### Map-led console

The UK workspaces use a map-led composition inspired by the user's selected
Fireart dashboard reference. A cached Natural Earth 1:50m basemap shows the UK
and Ireland with separate country fills. The only pulsing marker is the configured
location; it is not an incident. The moving scan is decorative. The current feeds
do not provide usable incident coordinates, so no attack or warning-area pins
are fabricated. Threat assessment and source stream remain visible while the
secondary card rotates through weather, publications, flooding and Doomsday.

Map data: Natural Earth, public domain,
https://www.naturalearthdata.com/about/terms-of-use/
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson
Only UK and Ireland geometries are bundled in `data/uk-map.geojson`.

### Restored observatory composition

The default layout follows the original Nexus clips: rotating geographic globe
centrally, large local clock and official threat assessment at left, current
Open-Meteo temperature plus Met Office bulletins and flood summary at right.
Doomsday and a two-line scrolling briefing occupy the bottom strip. The clock,
weather, threat and flood readouts remain visible during all UK workspace changes.
Workspace 3 shows the UK map in the central instrument area. The globe uses the
existing Natural Earth coastline data and marks only the configured location,
not inferred incidents. Motion remains paused with Space; transcript history
controls are unchanged. Local temperature refresh now also runs in the UK profile.

### UK-focused hybrid layout

The UK map is now the primary visual on every UK workspace. The original large
clock and threat panel remain on the left; weather, flooding and the published
Doomsday setting stay fixed below. The briefing transcript occupies the full-height
right column again. It advances one complete line every four seconds, without
typewriter truncation; up to 18 lines remain visible. Space pauses, Page Up/Down
browse history, and End returns to automatic replay. The globe remains available
in the technical observatory (F6).

The map uses a perspective camera with gentle yaw/tilt drift, a ground grid,
shadow and uniformly raised country surfaces. This is decorative extrusion, not
measured terrain or risk height. The location marker uses the same projection as
the coastline. Geometry is cached at four frames per second to limit Pi CPU use.

The map is now confined to UK view 3. Other UK views use the centre for the
highest-colour weather bulletin with its issued time, local flood details, and a
featured NCSC/BBC publication with date and source. Validity is checked at the
original weather source rather than inferred from the publication timestamp.
Each card opens its source when clicked. Fixed readouts and the four-second
right-hand briefing remain visible.

Briefing cards include small decorative vector animations: travelling weather
strokes, flowing water lines and a rotating wireframe orb. These are labelled
VISUAL FX and do not encode warning intensity, river height or network activity.
They use the paused animation clock and bounded caches at six frames per second.
The clock's seconds sweep reflects actual time. Text continues to advance only
once every four seconds, independently of these effects.

The shared palette matches the original near-black/turquoise/lime reference.
All main panel borders have decorative moving tracers, plus a moving header-node
pattern. The footer samples real Linux CPU counters, available memory and core
temperature every two seconds; its CPU history retains up to three minutes. Missing
measurements remain unavailable. Space freezes decorative motion and telemetry
sampling; actual wall-clock time continues. Warning text and source data are not
randomised to create activity.

### Persistent warning strip

All four UK views and the companion LCD keep a warning strip visible whenever
weather bulletins, flood alerts or a severe/critical national threat are listed.
Its border pulses once every two seconds; words never blink off. Multiple alerts
rotate every eight seconds with a persistent total. New or changed warning
identities/severities get a NEW announcement for 60 seconds, then remain in the
strip. Initial cached warnings are shown without being called new.

Weather validity is read from the RSS description using UK local time and the
warning link's date. Upcoming warnings are labelled; expired warnings leave the
strip. Unknown formats say CHECK VALIDITY AT SOURCE. Weather coverage remains the
configured region, not a claim that every warning applies at your address.
Successful empty feeds clear warnings; failed/missing/stale sources retain the
last known warning with a STALE label. News headlines do not trigger alarms.
Space freezes animation; data refresh and warning lifecycle continue. The strip
replaces footer telemetry while warnings are present. Click it or press O to
open the displayed warning. The Home and technical profiles retain their own UI.
