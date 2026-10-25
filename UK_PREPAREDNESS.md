# UK preparedness profile

`python3 launch.py nexus` opens the UK-first profile. F6 switches between this and the original technical profile; F5 switches to Home. The chosen profile persists across F5 switches within the running session. Set `NEXUS_PROFILE=technical` to start in the technical profile by default, or pass `--profile technical`.

## Screens

1. **UK status brief:** the UK-wide terrorism assessment from GOV.UK, separately displayed regional Met Office warning bulletins, and last successful check timestamps.
2. **Incident & cyber watch:** alternates NCSC official publications and BBC UK media reports. BBC headlines are selected by explicit topic keywords such as cyber, flood, storm, outage and attack. This selection is not incident verification or risk scoring; political statements and historical reports can appear if their headlines match. Source publication dates remain visible where supplied.
3. **Local readiness:** Environment Agency flood alerts/warnings, geographic scope, update time, and rotating household reminders based on the government Prepare campaign.
4. **Minutes to midnight:** real elapsed time to the next midnight in Europe/London, including daylight-saving transitions. This is neither the symbolic Doomsday Clock nor a forecast of an emergency.

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

## Checks and cached previews

```sh
python3 -m unittest discover -s tests -v
python3 dashboard.py --snapshot /tmp/uk-status.png --workspace 1
python3 dashboard.py --snapshot /tmp/readiness.png --workspace 3
python3 dashboard.py --snapshot /tmp/midnight.png --workspace 4
```

Snapshots perform no network access; they use cache files and show a connecting state if none exists. `NEXUS_CACHE` can redirect caches for isolated tests. Tests cover source parsing, missing data, local scope, cache separation, stale data after failures, daylight-saving countdowns, and empty/populated screen rendering. Hardware startup, browser handoff and Pi performance still need an on-device check.
