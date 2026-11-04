# Official UK service-disruption briefings

Issue #37 adds informational briefings, separate from GOV.UK Emergency Alerts,
NCSC, CISA KEV, and the official terrorism assessment. It does not generate
persistent alerts, change threat levels, or enable LEDs.

## Verified official contract

Verified 4 November 2026:

- [GOV.UK reuse guidance](https://www.gov.uk/help/reuse-govuk-content)
- [Search API documentation](https://docs.publishing.service.gov.uk/repos/search-api/using-the-search-api.html)
- [Live public API](https://www.gov.uk/api/search.json?count=1&filter_format=news_story&order=-public_timestamp&fields=title,description,link,public_timestamp,organisations,format)
- [Whitehall timestamp semantics](https://docs.publishing.service.gov.uk/repos/whitehall/timestamps.html)

The public Search API supports repeated `filter_format` parameters (OR within a
field), `filter_public_timestamp=from:...,to:...`, descending `public_timestamp`,
and explicit returned fields. Comma-separated *format filter values* are not
used. `fields` uses the documented comma-separated field list.
Live JSON verified `results`, `total`, `title`, `description`, relative `link`,
`public_timestamp`, `format` and organisation objects with `slug` and `title`.
Public timestamp represents publication/major update, **not incident onset or
validity**. The desktop labels it Published/updated; the LCD abbreviates Updated.
Content remains attributable to GOV.UK and its publishing department; reuse is
under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

A live seven-day query returned 431 records and zero matches after filtering.
This demonstrates a healthy empty result, not the absence of emergencies.
The committed fixture is entirely synthetic and follows that verified schema.

## Deliberately narrow coverage

Only news stories, press releases and guidance from the explicit domestic-service
publisher allowlist in `govuk_briefings.py` are candidates. These formats can
contain operational advice; the app does not display an unfiltered press feed.
A headline must name an incident (for example outage, flooding, closure or major
incident), and headline/summary must name an energy, water, transport or public
service. Funding, investment, appointments, speeches, policy plans, exercises,
and similar routine headline terms reject the record. Foreign-policy publishers
are excluded. This is an auditable conservative lexical filter, not a general
news classifier. It can miss relevant guidance or ambiguous headlines and cannot
prove domestic geographic relevance or active incident status from prose alone.
The allowlist also omits devolved-government sites and non-GOV.UK service operators.

Canonical GOV.UK paths deduplicate updates, retaining the newest timestamp;
identical headline/timestamp pairs also collapse. Query fragments and tracking
parameters are removed. Only relative `/government/` paths are accepted. Updates
and cancellations remain source text, never inferred to cancel another incident.
Old and future publications are excluded at render time, including cached data.
The rolling window is seven days; publication age does not prove expiry.

## Fetching and failure behavior

One request per 15 minutes, 15-second socket timeout, 8 MiB response cap and 1,000
record cap. The timeout bounds socket operations, not total download duration.
The worker runs outside rendering. If `total` exceeds the returned record count,
the refresh fails instead of presenting a truncated search as complete; no
unbounded pagination is attempted. Broad news volume can therefore cause stale
coverage. No user location, credentials, or private information is sent.

`govuk-briefings-v1.json` is a separate atomic cache under the preparedness cache
root. Last-good content and retrieval time survive failures and process restarts;
failed refreshes immediately mark it STALE. A first failure is UNAVAILABLE.
Success is CHECKED for one hour; future cache timestamps are STALE. Recovery to
an empty success clears old results. Failed-attempt timestamps persist to bound
retry frequency. Corrupt/wrong-source caches are ignored; failed disk writes do
not discard usable in-memory data. Simultaneous dashboard/companion startup can
still make one request per process; there is no cross-process HTTP lock.

## Display and integration hooks

- `preparedness.py`: separate worker, refresh dispatch, merged `govuk` snapshot.
- `focused_ui.py`: GOV.UK uses seconds 56–64 of the existing 64-second local
  visual cycle; grid retains seconds 48–56. Normal one-minute auto navigation
  shows the first four seconds of that GOV.UK slot. Items advance on successive
  four-minute desktop cycles. The full card links to the selected official page.
- `companion.py`: GOV.UK is the third 16-second news slot after NCSC and CISA;
  item rotation advances every 48 seconds. The LCD is not interactive; full
  headlines and source links are available on HDMI. The shared-cache fallback
  observes the same 15-minute retry interval.
- `scripts/install.sh`: copies both new modules.

These are the shared merge hooks. Preserve other cards when combining rotations.
Persistent threat, clock, weather, emergency-alert overlay, ping/Wi-Fi and
full-screen offline takeover are unchanged. Legacy preparedness_ui.py is unused.
Long text is clipped to the card; the official linked source is authoritative.

Validation: synthetic positive/negative parser fixtures; dedupe, recency, malformed
and incomplete payloads; bounded requests, disk restart/failure/recovery; shared
cache and fallback integration; both active displays, source hit-testing and
LCD offline precedence. Both 1280×720 HDMI and 480×320 LCD renders were inspected.
No physical Pi/LCD deployment was performed.
