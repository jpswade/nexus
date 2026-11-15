#!/bin/sh
# Install deliberately as root-owned code, never execute user-writable modules as root.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run with sudo'; exit 1; }
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INTERFACE=${1:-wlan0}
install -d -m 755 /usr/local/lib/nexus-network
install -m 644 "$SOURCE/network_recovery.py" "$SOURCE/companion_network.py" /usr/local/lib/nexus-network/
python3 - "$INTERFACE" <<'PY'
import json,sys,subprocess
from pathlib import Path
interface=sys.argv[1]
if not interface.replace('_','').isalnum():raise SystemExit('Invalid interface')
uuid=subprocess.check_output(['nmcli','-g','GENERAL.CON-UUID','device','show',interface],text=True).strip()
if not uuid or uuid=='--':raise SystemExit('Connect Wi-Fi first')
device=(Path('/sys/class/net')/interface/'device').resolve().parent
config=dict(interface=interface,uuid=uuid,usb_path=str(device),vendor=(device/'idVendor').read_text().strip(),product=(device/'idProduct').read_text().strip())
path=Path('/etc/nexus-network.json');path.write_text(json.dumps(config));path.chmod(0o600)
subprocess.run(['nmcli','connection','modify','uuid',uuid,'802-11-wireless.powersave','2','connection.autoconnect','yes','connection.autoconnect-retries','0'],check=True)
(device/'power/control').write_text('on')
rule=Path('/etc/udev/rules.d/81-nexus-wifi-power.rules')
rule.write_text('ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="'+config['vendor']+'", ATTR{idProduct}=="'+config['product']+'", TEST=="power/control", ATTR{power/control}="on"\n')
PY
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/nexus.conf <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=32M
MaxRetentionSec=7day
EOF
cat > /etc/systemd/system/nexus-network-recovery.service <<'EOF'
[Unit]
Description=Nexus bounded local Wi-Fi recovery
After=NetworkManager.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/nexus-network/network_recovery.py
TimeoutStartSec=90
EOF
cat > /etc/systemd/system/nexus-network-recovery.timer <<'EOF'
[Unit]
Description=Check Nexus Wi-Fi recovery every 30 seconds
[Timer]
OnBootSec=2min
OnUnitInactiveSec=30s
[Install]
WantedBy=timers.target
EOF
udevadm control --reload-rules
systemctl restart systemd-journald
journalctl --flush
systemctl daemon-reload
systemctl enable --now nexus-network-recovery.timer
# Apply power settings without taking the connection down.
nmcli device reapply "$INTERFACE" || true
echo 'Recovery installed: reconnect after 2 minutes local failure, then at most two USB resets/hour. No automatic reboot.'
