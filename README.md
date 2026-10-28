# NEXUS

An ambient Pygame dashboard for Raspberry Pi and HDMI monitors. NEXUS uses the original dark instrument-panel layout: clear typography, one central subject, and persistent clock, weather, PHP priority and regional warnings. Static panels are cached; only the central map or globe animates. The configurable home view remains a separate launcher option.

## Two views, one launcher

```sh
python3 launch.py nexus   # UK preparedness (default)
python3 launch.py nexus --profile technical  # Cyber and observatory
python3 launch.py home    # Configurable clock, weather, agenda and plugins
```

**F5 switches between the views**, replacing the current process so the existing systemd service continues to own the dashboard. Press **S** to save home layout edits before switching. The install script includes both views and preserves an existing `home.json` and local agenda on upgrades.

Nexus uses `config.json` for location. Home uses `home.json` for layout and widgets; the launcher creates it from `home.example.json` on first use. Its weather widget shares the Nexus location unless explicitly overridden. `NEXUS_CONFIG` and `NEXUS_HOME_CONFIG` select alternate config paths (use absolute paths for switching). [Home dashboard setup and plugin API](HOME_DASHBOARD.md).

## Focused desktop

The sidebars remain in place across every workspace and both profiles:

- **Left:** large clock/date, local weather, and the official national assessment.
- **Centre:** one map, advisory or source briefing at a time.
- **Right:** PHP priority and retained regional warnings, including explicit stale/unknown states.
- **Bottom:** the latest meaningful source change; successful routine refreshes do not replay the entire feed.

The default UK profile rotates once per **60 seconds** through Local Situation, PHP Watch, Public Briefing and World View. The technical profile substitutes an advisory overview and CISA KEV list for the situation map and public-news briefing. **F6** changes profile; **F5** switches to the configurable home view. PHP, CISA, PHP.net, preparedness and planetary sources keep refreshing in both profiles.

**1–4** or the numbered header controls select a view; **Left/Right** switch view; **A** toggles rotation; **T** opens/dismisses a short central terminal briefing; **O** opens the priority source; **Space** pauses animation/rotation; **Escape** exits. Cards with sources are clickable. The terminal never covers the priority sidebars.

Automatic terminal briefings appear for nine seconds near the end of the map/overview workspace, once per four-minute cycle. A new critical PHP advisory or CISA addition can also trigger a short briefing. Initial cache loads and unchanged refreshes stay quiet. The terminal is a read-only presentation, not a shell. The former replaying transcript, moving panel borders and local-machine telemetry strip are absent from the focused layout.

The regional card uses the existing retained-alert model: fresh source failures do not clear previous warnings, and expired bulletins are still excluded using their known validity windows. No combined threat score is calculated. The Doomsday Clock remains an explicitly symbolic, dated publisher setting in the World View footer, rather than an urgent persistent status. [UK source setup and data limitations](UK_PREPAREDNESS.md).

## Security data

PHP core advisories come directly from the public `php/php-src` repository security advisories API (up to the latest 100 published records). Withdrawn records are excluded. The display preserves vendor severity, the supplied CVSS version and score, and each supplied fixed-version string. Priority focuses on recent advisories, with known exploitation and critical severity ahead of lower-severity records. PHP count panels cover the last 30 days of publication, not all historical vulnerabilities or Composer packages.

Official PHP security announcements are read from PHP.net's current-year news archive. This includes follow-up configuration notices that may precede a full CVE advisory. Titles, dates, CVE identifiers and source URLs are retained; exploit writeups are not displayed.

CISA KEV entries are matched by exact CVE ID. A match indicates inclusion in CISA's exploited-vulnerability catalog; no match does not establish absence of exploitation. The catalog view sorts by date added, not CVE year, so newly exploited older bugs remain visible. Counts describe catalog records, not live attacks. Source checks and failures are visible. This is an advisory watch with no asset inventory, package scan or claim that your systems are affected or patched.

GitHub, CISA and PHP.net feeds refresh every 15, 30 and 15 minutes respectively. No credentials, tokens or local infrastructure details are sent to these public sources. GitHub's public rate limits apply; failures retain cached records and show stale status.

## Planetary data

World View shows a rotating globe with Natural Earth coastlines and sampled ISS altitude/velocity with observation age. The UK map is geographic context, not a plotted hazard footprint. Earthquake, Kp and solar-wind data continue to be fetched/cached for the companion view and extensions.

The globe's camera moves for presentation; markers use the source coordinates. ISS coordinates are modelled satellite positions, not a live camera or an overhead-pass prediction.

## Public feeds

| Feed | Refresh | Display |
| --- | --- | --- |
| [PHP vendor advisories](https://github.com/php/php-src/security/advisories) | 15 minutes | PHP core CVEs, severity and fixed versions |
| [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) | 30 minutes | Known exploited CVEs |
| [PHP.net news](https://www.php.net/archive/) | 15 minutes | Security announcements and follow-up notices |
| [Where the ISS at?](https://wheretheiss.at/w/developer) | 20 seconds | Position, speed, altitude |
| [USGS](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php) | 5 minutes | Reported M2.5+ events, rolling 24 hours |
| [NOAA SWPC](https://services.swpc.noaa.gov/) | Kp: 10 minutes; wind: 5 minutes | Geomagnetic index and active solar-wind observations |
| [Open-Meteo](https://open-meteo.com/en/docs) | 10 minutes | Weather for your configured coordinates |

Feeds are fetched in background threads and cached locally. Each panel shows the observation age. Failed updates or old observations are marked stale; cached data is not presented as current. NOAA source observations can lag, even when requests succeed. Kp measures geomagnetic activity, not your local chance of seeing an aurora. The USGS feed is a reported-event catalogue, not a complete count of every earthquake worldwide.

No API keys are required. Weather requests send configured coordinates to Open-Meteo. When local flood alerts are enabled, the Environment Agency receives the configured coordinates and search radius. Met Office requests include the selected region. Config files and caches are excluded from Git.

## Hardware and software

Initially deployed on a Raspberry Pi 2 Model B Rev 1.1, running 32-bit Raspbian 13 with a labwc Wayland desktop and a 1920×1080 HDMI monitor. Rendering targets 12 fps using a 1280×720 canvas, GPU-scaled to the monitor. The earlier planetary view measured about 8 fps; the later dense UK console measured roughly 5 fps. The focused layout caches text/layout once per second and limits central geometry updates to reduce work. If SDL scaling is unavailable, the app falls back to native fullscreen rendering.

Requires Python 3.9+ and Pygame 2.6 or newer. On Raspberry Pi OS:

```bash
sudo apt update
sudo apt install python3-pygame
```

The installer expects a running Wayland desktop with desktop autologin enabled. It runs as your normal desktop user. It does not install an OS, change autologin or require sudo.

## Location settings

```bash
cp config.example.json config.json
```

Edit `config.json` with your display name, latitude and longitude. The example is central London. Your actual configuration is ignored by Git.

The Pi sends those coordinates to [Open-Meteo](https://open-meteo.com/en/docs) for the forecast. No account or API key is needed for personal, non-commercial use. Weather is cached locally and marked stale when updates fail. The clock and graphics keep running offline.

## Install on the Pi

Put this repository and your `config.json` on the Pi, then run from its desktop terminal:

```bash
sh scripts/install.sh
```

This backs up an existing dashboard, installs the app into `~/dashboard`, and writes a user service and desktop autostart entry. It starts the dashboard immediately and launches it on subsequent desktop logins.

If installing over SSH, the Pi's desktop must already be logged in. Its systemd user environment must contain `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR`; Raspberry Pi OS populated these on the original deployment.

To transfer a committed version from your Mac without giving the Pi GitHub credentials:

```bash
PI=your-user@your-pi-address
KEY=~/.ssh/pi-dashboard

git archive HEAD | ssh -i "$KEY" "$PI" 'mkdir -p ~/nexus && tar -x -C ~/nexus'
scp -i "$KEY" config.json "$PI":nexus/config.json
ssh -i "$KEY" "$PI" 'sh ~/nexus/scripts/install.sh'
```

The key stays on your Mac. Do not commit private keys, location settings, weather caches or screenshots of private information.

## Run and maintain

Run these on the Pi as the desktop user:

```bash
# Start again after pressing Escape
/usr/bin/systemctl --user start pi-dashboard

# Restart after an update
/usr/bin/systemctl --user restart pi-dashboard

# Status and recent output
/usr/bin/systemctl --user status pi-dashboard --no-pager
journalctl --user -u pi-dashboard -n 30 --no-pager
```

Some Raspberry Pi OS installations do not retain a user journal. `systemctl --user status` still shows recent service output.

Feed caches: `~/dashboard/.cache/*.json`. Configuration: `~/dashboard/config.json`. To use another config path, set the `NEXUS_CONFIG` environment variable.

To disable autostart, remove `~/.config/autostart/pi-dashboard.desktop` and stop the service:

```bash
/usr/bin/systemctl --user stop pi-dashboard
```

## Roll back

For a complete rollback, check out the desired Git commit and rerun the installer so the app, feed module and map assets stay together. The installer also keeps timestamped `dashboard.backup-*.py` files in `~/dashboard` for immediate recovery of the main script. Keep `config.json` in place.

## Development checks

```bash
python3 -m compileall -q dashboard.py feeds.py security.py security_ui.py workspaces.py preparedness.py preparedness_ui.py launch.py terminal_theme.py pi_dashboard plugins
python3 -m unittest discover -s tests -v
sh -n scripts/install.sh
```

For display changes, run on the Pi, check the layout on the monitor or with a Wayland screenshot, and inspect frame rate, CPU use and temperature. The app logs measured frame rate periodically. Keep network calls off the render loop.

Weather conditions use the WMO codes supplied by Open-Meteo. Data attribution is shown on the dashboard.

## Cached-data previews

For visual QA on the Pi, render a workspace without changing the monitor or making network requests:

```bash
python3 ~/dashboard/dashboard.py --profile technical --snapshot /tmp/php-watch.png --workspace 2 --age 3
python3 ~/dashboard/dashboard.py --profile technical --snapshot /tmp/observatory.png --workspace 4 --age 3
```

`--workspace` is 1–4. `--age` selects the point in the workspace rotation. Previews use the installed config and local caches; empty feeds show a connecting state.

## Retro display validation

The new layouts have been rendered at 1280×720 with SDL's dummy driver and checked locally. Previous Pi frame-rate figures above describe the old design; the retro layout and F5 switching still require an on-device check. No remote Pi deployment is performed by editing this repository.

`assets/fonts/ShareTechMono-Regular.ttf` comes from Google Fonts' Share Tech Mono distribution and is licensed under the included SIL Open Font License (`assets/fonts/OFL.txt`). Colours and font selection are shared in `terminal_theme.py`.

The default renderer uses the bundled Share Tech Mono font. The optional `bitmap_font.py` renderer and public-domain IBM-derived `font8x8` data remain available for custom widgets (see `assets/fonts/FONT8X8-LICENSE.txt`). Home widgets also accept a custom TTF via their theme.

## Automatic Pi updates

After installing, run `sh scripts/enable-auto-update.sh` as the display user.
The user timer checks the public `main` branch every five minutes (with up to
30 seconds of jitter), validates the revision using the test suite, then installs
and restarts the displays. No GitHub credentials or sudo are required. Local
`config.json`, `home.json`, agenda data and caches are preserved. The preceding
installation is stored privately in `~/.local/state/nexus-updater/previous` and
restored if installation or the initial service health check fails. There is a
brief display interruption during installation; the check is process health,
not a physical screen inspection. Upstream code is trusted to run as this user.
The timer runs while the user systemd manager is running (normally the desktop
session); it does not independently enable lingering.

Check with `systemctl --user status nexus-update.timer nexus-update.service`.
Disable with `systemctl --user disable --now nexus-update.timer`.
Run immediately with `systemctl --user start nexus-update.service`.
The updater itself is installed explicitly by the enable script; rerun that
script when updater changes are announced.

The preparedness cyber panel uses CISA’s Known Exploited Vulnerabilities catalogue instead of general news. It shows global advisories added within the last 30 days, newest first, with catalogue-added dates (not incident dates). It also fills quiet NCSC days. These entries do not imply the device is affected and do not trigger emergency alerts.

CVE cards show CVSS base scores from the NVD API, preferring v4.0 then v3.1/v3.0 and the primary assessor within that version. The stream names the assessor. Scores refresh every six hours; failed lookups retain labelled cached scores, and absent scores are explicit.

Network activity now rotates through the companion's local panel and alternates with the main local map. It shows this Pi's non-loopback RX/TX rates, driver-reported Wi-Fi signal history, bounded gateway/internet probes and a DNS lookup check. Signal variation is not interpreted as movement or occupancy. No packet capture, device scanning or tracking is enabled. Missing readings remain unavailable; counter resets do not create traffic spikes.
