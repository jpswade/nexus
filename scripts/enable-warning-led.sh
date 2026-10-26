#!/bin/sh
# Run once with sudo: grants only the two PWR LED control files to the caller.
set -eu
if [ "$(id -u)" != 0 ] || [ -z "${SUDO_USER:-}" ]; then
    echo 'Run with sudo from your normal Pi account.' >&2
    exit 1
fi
case "$SUDO_USER" in *[!a-zA-Z0-9_-]*|'') exit 1;; esac
 test -e /sys/class/leds/PWR/brightness
cat > /etc/systemd/system/nexus-led-access.service <<UNIT
[Unit]
Description=Grant Nexus user access to the red PWR LED
After=systemd-udev-trigger.service

[Service]
Type=oneshot
ExecStart=/bin/chown $SUDO_USER /sys/class/leds/PWR/brightness /sys/class/leds/PWR/trigger
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
chmod 644 /etc/systemd/system/nexus-led-access.service
systemctl daemon-reload
systemctl enable --now nexus-led-access.service
echo 'Red LED control enabled, including after reboot.'
