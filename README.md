# NEXUS

An animated security and planetary desktop for a Raspberry Pi and an HDMI monitor. A rotating globe, orbital statistics and natural events, built with Python and Pygame. The interface takes its cues from BeOS: short yellow title tabs, bevelled grey windows, a teal desktop and a compact Deskbar-style status tray.

## Workspaces

The desktop rotates every 32 seconds through four workspaces:

1. **Security overview**: recent critical PHP advisories, recent CISA KEV additions and source freshness.
2. **PHP watch**: vendor CVEs, severity and CVSS version, fixed versions, CISA catalog matches and official PHP follow-up announcements.
3. **Exploited in the wild**: recent CISA Known Exploited Vulnerabilities entries, catalog statistics and vendor-response guidance.
4. **Observatory**: rotating globe, ISS statistics, earthquakes, solar conditions, clock and local weather.

Windows open in a staggered sequence. At seven seconds an ASCII terminal briefing opens, types a short report from the loaded advisory data, then closes at 23 seconds. It displays text; it does not execute shell commands. Automatic rotation continues while public feeds refresh in background threads.

| Key | Action |
| --- | --- |
| 1–4 | Select a workspace and reset its rotation timer |
| Left / Right | Previous / next workspace |
| A | Toggle automatic rotation |
| T | Show or dismiss the terminal briefing |
| Space | Pause animation and workspace rotation; feeds continue updating |
| Escape | Close the dashboard |

The numbered controls in the header indicate the current workspace. The layout uses fixed windows with animated entry and terminal exit. No calendar integration.

## Security data

PHP core advisories come directly from the public `php/php-src` repository security advisories API (up to the latest 100 published records). Withdrawn records are excluded. The display preserves vendor severity, the supplied CVSS version and score, and each supplied fixed-version string. Priority focuses on recent advisories, with known exploitation and critical severity ahead of lower-severity records. PHP count panels cover the last 30 days of publication, not all historical vulnerabilities or Composer packages.

Official PHP security announcements are read from PHP.net's current-year news archive. This includes follow-up configuration notices that may precede a full CVE advisory. Titles, dates, CVE identifiers and source URLs are retained; exploit writeups are not displayed.

CISA KEV entries are matched by exact CVE ID. A match indicates inclusion in CISA's exploited-vulnerability catalog; no match does not establish absence of exploitation. The catalog view sorts by date added, not CVE year, so newly exploited older bugs remain visible. Counts describe catalog records, not live attacks. Source checks and failures are visible. This is an advisory watch with no asset inventory, package scan or claim that your systems are affected or patched.

GitHub, CISA and PHP.net feeds refresh every 15, 30 and 15 minutes respectively. No credentials, tokens or local infrastructure details are sent to these public sources. GitHub's public rate limits apply; failures retain cached records and show stale status.

## Planetary data

The observatory retains the clock, local weather, a globe with Natural Earth coastlines, modelled ISS coordinates, altitude and velocity, global M2.5+ USGS earthquakes in the last 24 hours, and NOAA Kp / solar wind observations. The ISS orbit period is derived from altitude using a circular-orbit approximation.

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

No API keys are required. Public feeds do not receive your location; only the local weather request sends the coordinates configured in `config.json` to Open-Meteo.

## Hardware and software

Initially deployed on a Raspberry Pi 2 Model B Rev 1.1, running 32-bit Raspbian 13 with a labwc Wayland desktop and a 1920×1080 HDMI monitor. Rendering targets 12 fps using a 1280×720 canvas, GPU-scaled to the monitor. The original Pi 2 measured about 8 fps with the planetary view; native 1080p software rendering was about 4 fps. If SDL scaling is unavailable, the app falls back to native fullscreen rendering.

Requires Python 3 and Pygame 2.6 or newer. On Raspberry Pi OS:

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
python3 -m py_compile dashboard.py feeds.py security.py security_ui.py workspaces.py
python3 -m unittest discover -s tests -v
sh -n scripts/install.sh
```

For display changes, run on the Pi, check the layout on the monitor or with a Wayland screenshot, and inspect frame rate, CPU use and temperature. The app logs measured frame rate periodically. Keep network calls off the render loop.

Weather conditions use the WMO codes supplied by Open-Meteo. Data attribution is shown on the dashboard.

## Cached-data previews

For visual QA on the Pi, render a workspace without changing the monitor or making network requests:

```bash
python3 ~/dashboard/dashboard.py --snapshot /tmp/php-watch.png --workspace 2 --age 3
python3 ~/dashboard/dashboard.py --snapshot /tmp/terminal.png --workspace 1 --age 19
```

`--workspace` is 1–4. `--age` selects the point in the workspace animation. Previews use the installed config and local caches; empty feeds show a connecting state.
