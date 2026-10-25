# NEXUS

A Pygame terminal for Raspberry Pi and HDMI monitors. One repository contains both the security/observatory display and the configurable home dashboard. Both share a black background, phosphor-green monospace text, amber warnings, and thin section borders. The bundled font makes the look consistent across computers. There are no scanlines, glow filters, or overlapping windows.

## Two views, one launcher

```sh
python3 launch.py nexus   # UK preparedness (default)
python3 launch.py nexus --profile technical  # Cyber and observatory
python3 launch.py home    # Configurable clock, weather, agenda and plugins
```

**F5 switches between the views**, replacing the current process so the existing systemd service continues to own the dashboard. Press **S** to save home layout edits before switching. The install script includes both views and preserves an existing `home.json` and local agenda on upgrades.

Nexus uses `config.json` for location. Home uses `home.json` for layout and widgets; the launcher creates it from `home.example.json` on first use. Its weather widget shares the Nexus location unless explicitly overridden. `NEXUS_CONFIG` and `NEXUS_HOME_CONFIG` select alternate config paths (use absolute paths for switching). [Home dashboard setup and plugin API](HOME_DASHBOARD.md).

## UK-first preparedness

The default profile rotates through UK status, incident/cyber reporting, local readiness, and a London-time midnight clock. **F6** switches to the technical profile; **F5** switches to the configurable home dashboard. In the UK profile, **O** opens the selected source in your installed browser; source rows are also clickable.

Official terrorism assessments, weather bulletins, flood warnings, and news reports remain distinct. No combined threat score is calculated. The midnight counter is a local clock, not the Bulletin of the Atomic Scientists’ Doomsday Clock. [Sources, local setup and data limitations](UK_PREPAREDNESS.md).

## Technical profile workspaces

The display rotates every 32 seconds through four workspaces:

1. **Security overview**: recent critical PHP counts and one priority advisory.
2. **PHP watch**: one vendor advisory or PHP.net announcement at a time, advancing every 12 seconds.
3. **Exploited in the wild**: four readable CISA KEV entries per page, advancing every 12 seconds.
4. **Observatory**: green wireframe globe with ISS and earthquake markers, local clock/weather, geomagnetic Kp and earthquake counts.

**1–4** select a workspace, **Left/Right** switch workspace, **A** toggles rotation, **T** opens a full-screen read-only briefing, **Space** pauses animation/rotation, and **Escape** quits. Briefing text has a short reveal and blinking cursor; it does not execute commands. Feed refreshes continue in background threads. The bottom controls stay still for readability.

## Security data

PHP core advisories come directly from the public `php/php-src` repository security advisories API (up to the latest 100 published records). Withdrawn records are excluded. The display preserves vendor severity, the supplied CVSS version and score, and each supplied fixed-version string. Priority focuses on recent advisories, with known exploitation and critical severity ahead of lower-severity records. PHP count panels cover the last 30 days of publication, not all historical vulnerabilities or Composer packages.

Official PHP security announcements are read from PHP.net's current-year news archive. This includes follow-up configuration notices that may precede a full CVE advisory. Titles, dates, CVE identifiers and source URLs are retained; exploit writeups are not displayed.

CISA KEV entries are matched by exact CVE ID. A match indicates inclusion in CISA's exploited-vulnerability catalog; no match does not establish absence of exploitation. The catalog view sorts by date added, not CVE year, so newly exploited older bugs remain visible. Counts describe catalog records, not live attacks. Source checks and failures are visible. This is an advisory watch with no asset inventory, package scan or claim that your systems are affected or patched.

GitHub, CISA and PHP.net feeds refresh every 15, 30 and 15 minutes respectively. No credentials, tokens or local infrastructure details are sent to these public sources. GitHub's public rate limits apply; failures retain cached records and show stale status.

## Planetary data

The observatory shows the clock, local weather, a globe with Natural Earth coastlines, modelled ISS coordinates, altitude and velocity, global M2.5+ USGS earthquake counts in the last 24 hours, and NOAA Kp observations. Solar wind data continues to be fetched and cached for extensions; the compact status display prioritises Kp.

The globe's camera moves for presentation; markers use the source coordinates. Pulsing earthquake rings are decorative and do not represent real-time seismic waves. ISS coordinates are modelled satellite positions, not a live camera or an overhead-pass prediction.

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

Initially deployed on a Raspberry Pi 2 Model B Rev 1.1, running 32-bit Raspbian 13 with a labwc Wayland desktop and a 1920×1080 HDMI monitor. Rendering targets 12 fps using a 1280×720 canvas, GPU-scaled to the monitor. The original Pi 2 measured about 8 fps with the planetary view; native 1080p software rendering was about 4 fps. If SDL scaling is unavailable, the app falls back to native fullscreen rendering.

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
