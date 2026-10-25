# NEXUS

An animated dashboard for a Raspberry Pi 2 and an HDMI monitor. Built with Python and Pygame, with a dark terminal layout and a procedural neural field.

## What it does

- Clock, date and seconds indicator.
- Animated nodes, orbiting sweeps and travelling pulses.
- Live CPU, memory, temperature, uptime and free disk space.
- CPU history and network traffic graphs, sampled every two seconds.
- Local event stream and a scrolling information ticker.
- Local weather, updated every ten minutes through Open-Meteo.

The system readings are real. The neural field is a visual effect; it does not run an AI model. No calendar integration.

**Space** pauses the animation. **Escape** closes the dashboard. Telemetry and weather keep updating while the animation is paused.

## Hardware and software

Initially deployed on a Raspberry Pi 2 Model B Rev 1.1, running 32-bit Raspbian 13 with a labwc Wayland desktop and a 1920×1080 HDMI monitor. Rendering targets 12 fps to suit the older hardware.

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

Weather cache: `~/dashboard/.cache/weather.json`. Configuration: `~/dashboard/config.json`. To use another config path, set the `NEXUS_CONFIG` environment variable.

To disable autostart, remove `~/.config/autostart/pi-dashboard.desktop` and stop the service:

```bash
/usr/bin/systemctl --user stop pi-dashboard
```

## Roll back

The installer keeps timestamped `dashboard.backup-*.py` files in `~/dashboard`. Copy the chosen backup over `~/dashboard/dashboard.py` and restart the service. Keep `config.json` in place for versions that use it.

## Development checks

```bash
python3 -m py_compile dashboard.py
sh -n scripts/install.sh
```

For display changes, run on the Pi, check the layout on the monitor or with a Wayland screenshot, and inspect frame rate, CPU use and temperature. The app logs measured frame rate periodically. Keep network calls off the render loop and keep telemetry read-only.

Weather conditions use the WMO codes supplied by Open-Meteo. Data attribution is shown on the dashboard.
