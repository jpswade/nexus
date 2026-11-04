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
# Compile every runtime module in memory before changing the installation.
/usr/bin/python3 - "$SOURCE" <<'CHECK'
from pathlib import Path
import sys
root = Path(sys.argv[1])
paths = list(root.glob('*.py'))
for package in ('pi_dashboard', 'plugins'):
    paths.extend((root / package).rglob('*.py'))
for path in paths:
    compile(path.read_bytes(), str(path), 'exec')
CHECK
mkdir -p "$DEST" "$HOME/.config/systemd/user" "$HOME/.config/autostart"
if [ -f "$DEST/dashboard.py" ]; then
    cp "$DEST/dashboard.py" "$DEST/dashboard.backup-$(date +%Y%m%d-%H%M%S).py"
fi
# Root Python files are runtime modules; include new policy/renderers automatically.
# This deliberately excludes private JSON configuration and acceptance fixtures.
cp "$SOURCE/"*.py "$DEST/"
cp "$SOURCE/scripts/enable-warning-led.sh" "$DEST/"
cp "$SOURCE/deploy/nexus-warning-led.service" "$HOME/.config/systemd/user/"
mkdir -p "$DEST/docs"
cp "$SOURCE/docs/space-weather.md" "$DEST/docs/"
mkdir -p "$DEST/data"
cp "$SOURCE/data/uk-map.geojson" "$DEST/data/"
cp "$SOURCE/deploy/nexus-camera-motion.service" "$HOME/.config/systemd/user/"
cp "$SOURCE/scripts/enable-companion-boot.sh" "$DEST/"
cp "$SOURCE/deploy/nexus-companion.service" "$HOME/.config/systemd/user/"
cp "$SOURCE/home.example.json" "$DEST/"
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
