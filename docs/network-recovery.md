# Offline LED and Wi-Fi recovery

`nexus-warning-led.service` uses `warning_led.py --offline-only`: flash the red PWR
LED for fresh, confirmed repeated probe failures and turn it off when recovered.
This mode does not flash for threat/weather bulletins. It runs its own bounded
probe worker, so it does not depend on a display loop. Existing LED permissions
are still required (`sudo sh ~/dashboard/enable-warning-led.sh`).

Optional root installation, from a checked-out release with Wi-Fi connected:

```
sudo sh scripts/enable-network-recovery.sh wlan0
```

The installer copies recovery code into a root-owned directory, records the
connected profile UUID and USB identity privately, disables that profile's Wi-Fi
power saving and the adapter's USB autosuspend, enables a 30-second timer, and
retains at most 32 MiB / seven days of system journal. No automatic Pi reboot.

Recovery only considers sustained local failure: neither WAN probe nor router
ping responds. A healthy router with failed WAN checks is left alone. After two
minutes reconnect the saved Wi-Fi profile; after another five minutes of failure
reset only the identified USB adapter. At most two USB resets/hour. Radio-disabled
and other default-route interfaces are left alone. The counters reset on a new
boot; recovery actions and probe classifications are journalled. Internet or
router outages and hardware faults are not guaranteed to be repairable.

Inspect `journalctl -u nexus-network-recovery` and `journalctl -k -b -1` after a
recurrence. To disable recovery: `sudo systemctl disable --now
nexus-network-recovery.timer`. Power-saving changes and journal retention can be
reverted separately. Root-owned recovery code is deliberately not replaced by the
unprivileged dashboard updater; rerun the installer to update it.
