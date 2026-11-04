# UK national terrorism assessment

GOV.UK is the primary publisher; MI5 is an official fallback. Both are checked once
per hour by the existing preparedness worker (25-second timeout and 4 MiB limit
per request). This is not a combined threat score or an incident warning.

Sources verified through the web on 4 November 2026:

- [GOV.UK guide](https://www.gov.uk/terrorism-national-emergency), using its
  [Content API representation](https://www.gov.uk/api/content/terrorism-national-emergency):
  `details.parts`, part slug `terrorism-threat-levels`, HTML `body`, optional
  `public_updated_at` (existing adapter contract). The
  [official API documentation](https://content-api.publishing.service.gov.uk/)
  confirms the path-to-JSON interface; the live API response was unavailable during
  verification, so its exact current payload was not revalidated. Only the complete national assessment paragraph is accepted.
- [MI5 terrorism threat levels](https://www.mi5.gov.uk/threats-and-advice/terrorism-threat-levels):
  the section headed “Current national threat level” contains the UK assessment
  paragraph, with the level sometimes in inline markup. The parser stops at the
  next heading. Navigation banners, definitions, historical tables and the
  separate Northern Ireland-related assessment are never fallback candidates.
  The national assessment excludes Northern Ireland-related terrorism in Northern
  Ireland, which has its own assessment. The old `/threat-levels` URL redirects.

MI5 has no assumed JSON schema here. The fixture is a minimal reconstruction of
its verified public heading/paragraph structure with deliberately varied example
levels; it is not a full captured page. Direct HTTP fetching encountered a
Cloudflare challenge during development. Challenges, HTTP errors, unknown levels,
changed wording, missing sections and duplicate statements fail closed. No browser
challenge bypass is attempted. Successful live network fetching on the Pi remains
an operational check; deterministic fixtures exercise parsing and failure paths.

On each cycle, valid GOV.UK takes precedence. MI5 is selected only if GOV.UK cannot
be parsed or fetched. When both succeed and differ, both source-labelled values
are stored in `observations` with their individual successful fetch timestamps.
`disagreement` is true; both active displays say sources differ and show both
values, instead of presenting one value as a reconciled assessment. The internal
`level` remains the explicitly attributed GOV.UK value for compatibility; it is
never the minimum, maximum or average. A later successful pair can clear the flag;
a single-source result makes no claim of agreement.

`source` is the actual retrieval URL, `source_name` identifies the publisher,
`url` is the public source link, and `fetched` is the selected source's last
successful read, not a claimed assessment change date. Both failures preserve the
last-good sample and its timestamp, with a separate atomic `threat-status.json`
failure marker for the companion's cache reader. The UI shows stale immediately
on known failure or after two hours. With no prior success it shows unavailable.
Old GOV.UK caches remain readable. No new configuration or credentials are needed.

## Attribution

Source: MI5 and GOV.UK. Contains public sector information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
© Crown copyright. [MI5's terms](https://www.mi5.gov.uk/terms-and-conditions)
permit reuse with source acknowledgement and an OGL link; images, logos and
third-party material are excluded. No source images or logos are reproduced.
Source names appear on both displays and the HDMI card opens the selected source.

## Integration hooks

`PreparednessFeeds.refresh('threat')`, its cache loader, and the existing threat
blocks in `focused_ui.py` and `companion.py` are the shared integration points.
The new `terrorism.py` owns parsing and provenance formatting. On the companion,
two permanent provenance lines replace the masthead's three small source-summary
boxes (those sources retain their rotating cards/emergency banner); the
threat masthead, clock, weather strip, ping/Wi-Fi and full-screen offline takeover
remain in place. No LED, deployment or legacy preparedness UI changes are made.
