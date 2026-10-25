#!/bin/sh
set -eu
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
cp "$SOURCE/scripts/auto-update.sh" "$HOME/.local/bin/nexus-auto-update"
cp "$SOURCE/deploy/nexus-update.service" "$SOURCE/deploy/nexus-update.timer" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now nexus-update.timer
