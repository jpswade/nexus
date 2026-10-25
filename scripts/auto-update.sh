#!/bin/sh
# Runs as the display user; no credentials or sudo required for the public repo.
set -eu
umask 077
STATE="$HOME/.local/state/nexus-updater"
DEST="$HOME/dashboard"
mkdir -p "$STATE"
exec 9>"$STATE/lock"
flock -n 9 || exit 0
export GIT_TERMINAL_PROMPT=0
if [ ! -d "$STATE/repo/.git" ]; then
    git clone --depth 1 --branch main https://github.com/jpswade/nexus.git "$STATE/repo"
fi
git -C "$STATE/repo" fetch --depth 1 origin main
REV=$(git -C "$STATE/repo" rev-parse FETCH_HEAD)
if [ -f "$DEST/DEPLOYED_COMMIT" ] && [ "$(cat "$DEST/DEPLOYED_COMMIT")" = "$REV" ]; then
    echo "Nexus already current: $REV"
    exit 0
fi
STAGE=$(mktemp -d "$STATE/stage.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT HUP INT TERM
git -C "$STATE/repo" archive "$REV" | tar -x -C "$STAGE"
cp "$DEST/config.json" "$STAGE/config.json"
(cd "$STAGE" && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy /usr/bin/python3 -m unittest discover -s tests)
# Keep a complete copy including private local state for rollback.
rm -rf "$STATE/previous"
cp -a "$DEST" "$STATE/previous"
mkdir -p "$STATE/units"
cp "$HOME/.config/systemd/user/pi-dashboard.service" "$STATE/units/"
cp "$HOME/.config/systemd/user/nexus-companion.service" "$STATE/units/"
COMPANION=0
systemctl --user is-active --quiet nexus-companion.service && COMPANION=1
rollback() {
    echo "Update failed; restoring previous installation" >&2
    systemctl --user stop pi-dashboard.service nexus-companion.service || true
    rm -rf "$DEST"
    cp -a "$STATE/previous" "$DEST"
    cp "$STATE/units/"*.service "$HOME/.config/systemd/user/"
    systemctl --user daemon-reload
    systemctl --user restart pi-dashboard.service
    if [ "$COMPANION" = 1 ]; then systemctl --user restart nexus-companion.service; fi
    exit 1
}
systemctl --user stop pi-dashboard.service
if [ "$COMPANION" = 1 ]; then systemctl --user stop nexus-companion.service; fi
sh "$STAGE/scripts/install.sh" || rollback
if [ "$COMPANION" = 1 ]; then systemctl --user restart nexus-companion.service || rollback; fi
sleep 15
systemctl --user is-active --quiet pi-dashboard.service || rollback
[ "$(systemctl --user show pi-dashboard.service -p NRestarts --value)" = 0 ] || rollback
if [ "$COMPANION" = 1 ]; then
    systemctl --user is-active --quiet nexus-companion.service || rollback
    [ "$(systemctl --user show nexus-companion.service -p NRestarts --value)" = 0 ] || rollback
    echo "$REV" > "$DEST/COMPANION_DEPLOYED_COMMIT"
fi
echo "$REV" > "$DEST/DEPLOYED_COMMIT"
echo "Nexus updated successfully: $REV"
