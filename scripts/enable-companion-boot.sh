#!/bin/sh
# Run with sudo once, after testing the temporary piscreen overlay.
set -eu
CONFIG=/boot/firmware/config.txt
if [ "$(id -u)" != 0 ]; then
    echo 'Run this script with sudo to persist the tested LCD driver.' >&2
    exit 1
fi
if grep -q '^dtoverlay=piscreen' "$CONFIG"; then
    echo 'An existing piscreen entry is present; leaving it unchanged.'
    exit 0
fi
cp "$CONFIG" "$CONFIG.nexus-backup-$(date +%Y%m%d-%H%M%S)"
cat >> "$CONFIG" <<'SETTINGS'

[all]
# Nexus MPI3501 companion display; HDMI remains enabled.
dtparam=spi=on
dtoverlay=piscreen,speed=16000000,rotate=270,fps=10
SETTINGS
echo 'LCD driver enabled for next boot; no reboot needed now.'
