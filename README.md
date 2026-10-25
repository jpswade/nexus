# NEXUS

An animated planetary observatory for a Raspberry Pi and an HDMI monitor. A rotating globe, orbital statistics and natural events, built with Python and Pygame.

## What it does

- Local clock, date and weather.
- A rotating globe with Natural Earth coastlines.
- Modelled ISS coordinates, altitude and velocity, sampled every 20 seconds from Where the ISS at?.
- Global M2.5+ earthquakes reported by USGS in the last 24 hours, plotted on the globe. Shows the strongest and most recent event.
- NOAA planetary Kp index and solar-wind speed, with observation ages.
- Estimated ISS orbit period, derived from its altitude using a circular-orbit approximation.
- A scrolling ticker with facts from those feeds.

**Space** pauses the animation. **Escape** closes the dashboard. Data feeds keep updating while the animation is paused. There is no calendar integration or local machine telemetry.

The globe's camera moves for presentation; markers use the source coordinates. Pulsing earthquake rings are decorative and do not represent real-time seismic waves. ISS coordinates are modelled satellite positions, not a live camera or an overhead-pass prediction.

## Public feeds

| Feed | Refresh | Display |
| --- | --- | --- |
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
python3 -m py_compile dashboard.py feeds.py
python3 -m unittest discover -s tests -v
sh -n scripts/install.sh
```

For display changes, run on the Pi, check the layout on the monitor or with a Wayland screenshot, and inspect frame rate, CPU use and temperature. The app logs measured frame rate periodically. Keep network calls off the render loop.

Weather conditions use the WMO codes supplied by Open-Meteo. Data attribution is shown on the dashboard.
