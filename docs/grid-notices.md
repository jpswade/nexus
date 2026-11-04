# Electricity infrastructure notices

NEXUS reads the public Elexon Insights/BMRS SYSWARN API. Inspired by
https://wary.org.uk/. The display contains BMRS data © Elexon Limited copyright
and database right.

Official references verified 4 November 2026:

- https://developer.data.elexon.co.uk/ (public APIs; no API key required)
- https://data.elexon.co.uk/swagger/v1/swagger.json (`/system/warnings`)
- https://data.elexon.co.uk/bmrs/api/v1/system/warnings

The bare endpoint returns **only the latest message**, not the active warning
set. The adapter requests `publishDateTimeFrom` and `publishDateTimeTo` for a
rolling seven-day publication window, with `format=json`. One request per five
minutes, 15-second socket timeout, 1 MiB response cap, 2,000-record cap. No retry
loop within a refresh. Worker threads keep HTTP off both render loops. The
socket timeout bounds individual socket operations, not a total download deadline.

Live verification returned eight records in the 28 October–4 November window:
seven SO-SO TRADES bulletins and one planned IT SYSTEMS OUTAGE bulletin. The latter
concerns Balancing Mechanism API users, not household power supply. The fixture
contains the first three unchanged public records from that response.

## Interpretation and limits

The official schema exposes only `publishTime`, `warningType`, `warningText`.
It does **not** expose an incident/revision identifier, affected geographic scope,
valid-from/to timestamps, or a cancellation/active flag. Publication time is not
validity. A type is not an incident identity. No invented response fields or
unverified free-text time parsing are used.

The card shows issue time in UTC, explicitly unavailable structured validity
and affected scope, source, latest bulletin text on HDMI, and source credit.
The GB system context is not a claim about an affected region. The LCD rotates
source credit and a local-outage caveat within its infrastructure card. Longer
text is truncated; the official source is clickable on HDMI.

Every successful refresh replaces the bounded bulletin snapshot; exact duplicates
are removed. Older revisions remain in the cache until the next replacement, but
the card shows the latest publication of each type. This is a display policy,
not proof that one event supersedes another. Cancellation wording is labelled
"cancellation mentioned / check source", never matched to an invented incident.
Old and future publications are excluded from the seven-day display at render
time. There is no assumption that an older notice has expired: coverage outside
that window is explicitly unavailable.

**SYSWARN notices cannot currently prove active, relevant, uncancelled status.**
Consequently none enters persistent AlertState or affects warning LEDs or the
terrorism assessment. `persistent_alerts` is an explicit fail-closed policy gate.
Supporting automatic active alerts requires verified source semantics and
representative lifecycle fixtures; this patch intentionally does not claim that
feature is established by this API. An empty window is not an all-clear.

First failure is UNAVAILABLE; failed refresh with a previous success is STALE
immediately. Successful data becomes STALE after 15 minutes; future cache times
are also stale. Last good data and its original retrieval time survive errors.
Failure and last-attempt time are persisted for the companion and restart retry
spacing. Recovery to a successful empty result removes old rows. Cache writes
are atomic and optional; corrupt/wrong-source caches are ignored.

No credentials, Cloudflare token or local location are required or transmitted.
If an upstream deployment blocks unauthenticated access, the safe result is
UNAVAILABLE/STALE; this adapter does not bypass it or request a user secret.

## Integration

`PreparednessFeeds` owns a separate `GridNotices` worker and merges its snapshot
under `grid`; it uses a source-specific cache outside the existing URL-derived
cache identity, preserving all existing regional caches. The companion fallback
refreshes the same source. Simultaneous process startup can make one request per
process; there is no cross-process HTTP mutex. Subsequent companion fallback
checks use the shared attempt timestamp.

`dashboard.py -> focused_ui.py` shows the card in the final 16-second portion of
the local workspace's 64-second visual cycle; normal auto navigation leaves
roughly 12 seconds before the next workspace (the existing brief may cover five
seconds). Notice types advance on successive four-minute desktop cycles. The
LCD adds `grid` as the fourth local-channel slot (16 seconds every 64 seconds).
It advances notice types each cycle. Threat and regional-warning areas, PHP
priority, and the LCD ping/Wi-Fi strip are unchanged.

Installer copies both `grid_notices.py` and `grid_notices_ui.py`. No configuration
migration or additional dependencies are needed. Shared integration edits are
small hooks in preparedness.py, focused_ui.py, companion.py and install.sh;
merge these hooks with other source cards instead of overwriting their rotations.

## Follow-up: topic classification, not active-warning detection (#29)

Rechecked the official OpenAPI schema and endpoint on 4 November 2026.
`warningType` is a free string, not an enumerated severity or lifecycle field.
The display now uses a narrow, exact type-name map (case/whitespace normalized):

- `SO-SO TRADES`: Market bulletin. The official schema's dataset example and
  existing public fixture describe operator transaction settlement prices.
- `IT SYSTEMS OUTAGE`: IT service bulletin. The existing 3 November fixture
  addresses Balancing Mechanism API users; it is not a household power-cut notice.
- `ELECTRICITY MARGIN NOTICE`: Margin notice, a request for spare capacity.
- `HIGH RISK OF DEMAND REDUCTION` and `DEMAND CONTROL IMMINENT`: Demand-control
  notice. These are operational warning names documented by NESO. No live
  demand-control lifecycle fixture was verified; this label only describes topic.
- All other types, including abbreviations and prefixed/suffixed names, remain
  Unclassified bulletin. No body keywords assign a topic or urgency.

Evidence:

- [NESO explanation of system notices](https://www.neso.energy/energy-101/electricity-explained/how-do-we-balance-grid/what-are-system-notices)
  distinguishes spare-capacity requests from demand-control notifications.
- [NESO industry information](https://gbcmn.nationalenergyso.com/faq/capacity-market-notices/what-other-information-is-available-to-the-industry)
  explicitly names Electricity Margin Notice, High Risk of Demand Reduction and
  Demand Control Imminent on BMRS.
- [Official July 8–9 SYSWARN history](https://data.elexon.co.uk/bmrs/api/v1/system/warnings?publishDateTimeFrom=2026-07-08T00%3A00%3A00Z&publishDateTimeTo=2026-07-10T00%3A00%3A00Z&format=json)
  returned an EMN issue (8 July 20:31 UTC), updates (9 July 08:28 and 12:49 UTC)
  and cancellation (18:30 UTC), all with the **same** `warningType`.
  The validity period and cancellation are prose only. The synthetic regression
  sequence models this shape without interpreting times or identity from prose.

This is useful classification for reading bulletins, **not** evidence that a
warning is currently in force. In particular an EMN body mentions demand control
as a request to industry: keyword matching would incorrectly escalate it.
Cancellation wording in either title or body is only a check-source hint.
The persistent-alert blocker remains: a verified lifecycle parser/source with
identity, revisions, validity, cancellation and completeness semantics is needed.
A seven-day publication query cannot establish all still-active warnings.

Desktop shows topic and its meaning alongside the existing status caveat. LCD
alternates topic with GB/unspecified-scope metadata every four seconds; issue,
validity and active-status caveats remain. The lifecycle caveat is now at y=191,
above the GOV.UK strip which obscured the previous y=242 line. Cancellation hints
alternate with the combined validity/active-status caveat. Neither view asserts local supply loss.
This follow-up edits only the two grid modules, grid tests and this document;
it changes no shared rotation/feed hooks, AlertState or LED controls.
