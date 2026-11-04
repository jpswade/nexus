# Optional UK Internet disruption context

NEXUS uses the official [Cloudflare Radar outages API](https://developers.cloudflare.com/radar/investigate/outages/).
It is reported wider infrastructure context, never evidence of why this Pi is
offline and never an input to the UK terrorism assessment, warning LED or alerts.
An empty response is not an all-clear. Coverage and reporting can be incomplete.
Inspired by wary.org.uk; no Wary data, artwork or code is used.

## Configuration

No token is needed to run NEXUS or its tests. Without
`CLOUDFLARE_RADAR_TOKEN`, both displays show **NOT CONFIGURED** and the adapter
starts no worker and makes no HTTP requests. Do not put the token in config.json,
tracked files, command-line arguments, screenshots or logs.

Create a Cloudflare API token following the official
[API setup instructions](https://developers.cloudflare.com/radar/get-started/first-request/).
Store it in a private file outside the checkout, for example
`~/.config/nexus/radar.env`, with permissions 0600 and its directory 0700.
The file should contain the `CLOUDFLARE_RADAR_TOKEN` environment assignment.
An optional `NEXUS_RADAR_ASN` integer adds reports for a configured provider ASN;
it does not detect or infer your ISP. No postcode, IP or coordinates are sent.

For each display service, add a user systemd drop-in containing:

```ini
[Service]
EnvironmentFile=-%h/.config/nexus/radar.env
```

The services are `pi-dashboard.service` and `nexus-companion.service`.
Reload the user systemd configuration and restart the services after changing
credentials. The installer copies the modules but deliberately does not create,
copy or overwrite credential files. An invalid ASN disables requests with an
explicit configuration state. A 401/403 suspends that process until restart.

## Requests, cache and meaning

The endpoint is `/client/v4/radar/annotations/outages`, with `location=GB`,
`dateRange=7d`, `limit=50`, `offset=0`, `format=JSON`. With an ASN there is one
additional query using `asn` instead of `location`; these can describe provider
reports outside the UK and their reported location remains displayed. Results
are deduplicated. Only OUTAGE annotations are used. The live API reference schema
was checked on 2026-11-04, including optional ASN details and nullable end dates;
authenticated live results were not available during development.

At most two requests per 15 minutes per shared cache, with a nonblocking
cross-process lock and a persisted attempt timestamp, including failed attempts.
Responses are capped at 256 KiB; each socket operation times out after 5 seconds
and the read loop checks a 15-second deadline per request. Platform DNS resolution
may exceed socket timeout; fetching stays on one daemon worker, stop returns
within 0.2 seconds and cancelled results cannot be published. No overlapping
workers or retry loops are created. Redirects are refused to protect the token.
No HTTP response/error text or exception strings are logged or cached.

`NEXUS_CACHE/radar-outages.json` (default `.cache/radar-outages.json`) contains only
normalized reports and timestamps, written atomically with private permissions.
Both processes must use the same cache directory to share the rate limit.
Read-only or corrupt caches cannot cause fast retries. The worker never fetches
in a render call; previews never start the worker. The cached ASN is configuration
metadata and should remain outside version control, like the other caches.

Data becomes STALE after 30 minutes or any failed refresh, or immediately when
local probes report offline. The original fetch timestamp is retained on failure.
After seven days it is EXPIRED and reports are hidden. Missing, unavailable,
rejected credentials, stale empty results and fresh empty results are distinct.
A missing event end is shown as “not reported”, not a claim of an ongoing outage.
A full page is labelled LIMITED: there is no unbounded pagination and no claim
that all outages, including older ongoing events outside the window, are covered.

The desktop's local centre card rotates map / local network / infrastructure at
16-second intervals. The companion adds infrastructure to its local rotation,
using the full middle content area for readable report details. It retains the
threat header and ping/Wi-Fi strip during normal rotation. The existing
confirmed-offline full-screen takeover remains in place. Report selection advances
every eight seconds. Long source strings are bounded and clipped to the card.

## Attribution and data licence

Source: **Cloudflare, Inc., Cloudflare Radar**,
<https://radar.cloudflare.com/outage-center>.
Radar API data is licensed under
[Creative Commons Attribution–NonCommercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/),
as described in [Cloudflare's licensing policies](https://radar.cloudflare.com/about).
NEXUS filters, truncates, deduplicates and reformats these annotations; Cloudflare
does not endorse NEXUS. Retain attribution and the licence link when redistributing
cached data or screenshots. Commercial use requires appropriate separate permission.
This data licence does not relicense NEXUS software. Test fixtures are synthetic
examples shaped to the official schema, not live outage reports.

## Offline validation

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -p 'test_radar_outages.py'
```

Tests use fixtures and injected transports; no user token or live requests.
