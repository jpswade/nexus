#!/bin/sh
# Run as the desktop user on the Pi, without sudo.
set -eu
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEST="$HOME/dashboard"
/usr/bin/python3 -c 'import pygame' >/dev/null
if [ ! -f "$SOURCE/config.json" ]; then
    echo "Copy config.example.json to config.json and set your location first." >&2
    exit 1
fi
/usr/bin/python3 - "$SOURCE/config.json" <<'CHECK'
import json, sys
with open(sys.argv[1]) as source:
    config = json.load(source)
assert -90 <= float(config['latitude']) <= 90, 'Invalid latitude'
assert -180 <= float(config['longitude']) <= 180, 'Invalid longitude'
CHECK
/usr/bin/python3 -m py_compile "$SOURCE/dashboard.py"
mkdir -p "$DEST" "$HOME/.config/systemd/user" "$HOME/.config/autostart"
if [ -f "$DEST/dashboard.py" ]; then
    cp "$DEST/dashboard.py" "$DEST/dashboard.backup-$(date +%Y%m%d-%H%M%S).py"
fi
cp "$SOURCE/dashboard.py" "$DEST/dashboard.py"
cp "$SOURCE/feeds.py" "$DEST/feeds.py"
cp "$SOURCE/security.py" "$SOURCE/security_ui.py" "$SOURCE/workspaces.py" "$SOURCE/preparedness.py" "$SOURCE/preparedness_ui.py" "$DEST/"
cp "$SOURCE/observatory_globe.py" "$DEST/"
cp "$SOURCE/uk_map.py" "$DEST/"
mkdir -p "$DEST/data"
cp "$SOURCE/data/uk-map.geojson" "$DEST/data/"
cp "$SOURCE/status_summary.py" "$DEST/"
cp "$SOURCE/companion.py" "$DEST/"
cp "$SOURCE/scripts/enable-companion-boot.sh" "$DEST/"
cp "$SOURCE/deploy/nexus-companion.service" "$HOME/.config/systemd/user/"
cp "$SOURCE/launch.py" "$SOURCE/terminal_theme.py" "$SOURCE/bitmap_font.py" "$SOURCE/cyber_graphics.py" "$SOURCE/home.example.json" "$DEST/"
cp -R "$SOURCE/pi_dashboard" "$SOURCE/plugins" "$SOURCE/assets" "$DEST/"
mkdir -p "$DEST/data"
cp "$SOURCE/data/land.json" "$DEST/data/land.json"
cp "$SOURCE/data/doomsday-clock.json" "$DEST/data/doomsday-clock.json"
for name in agenda.json agenda.example.json metric.json; do
    if [ ! -f "$DEST/data/$name" ]; then
        cp "$SOURCE/data/$name" "$DEST/data/$name"
    fi
done
# Never overwrite an installed layout during an upgrade.
if [ ! -f "$DEST/home.json" ]; then
    if [ -f "$SOURCE/home.json" ]; then
        cp "$SOURCE/home.json" "$DEST/home.json"
    else
        cp "$SOURCE/home.example.json" "$DEST/home.json"
    fi
fi
cp "$SOURCE/config.json" "$DEST/config.json"
chmod 600 "$DEST/config.json"
mkdir -p "$DEST/.cache"
if [ -f "$DEST/weather-cache.json" ] && [ ! -f "$DEST/.cache/weather.json" ]; then
    cp "$DEST/weather-cache.json" "$DEST/.cache/weather.json"
fi
cp "$SOURCE/deploy/pi-dashboard.service" "$HOME/.config/systemd/user/"
cp "$SOURCE/deploy/pi-dashboard.desktop" "$HOME/.config/autostart/"
/usr/bin/systemctl --user daemon-reload
/usr/bin/systemctl --user restart pi-dashboard.service
echo "NEXUS installed in $DEST; desktop autostart configured."
