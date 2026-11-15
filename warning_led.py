"""Optional red PWR LED warning indicator, running without root."""
import argparse
import json
import signal
import time
from pathlib import Path
from alert_state import AlertState
from companion_network import NetworkMonitor
from preparedness import PreparednessFeeds


def should_flash(alerts):
    return any(not a['stale'] and (a['source'] != 'weather' or a['detail'].startswith('IN FORCE')) for a in alerts)


def offline_flash(state, now):
    checked=state.get("checked")
    return bool(state.get("offline") and checked is not None and 0 <= now-checked <= 35)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--offline-only",action="store_true")
    args=parser.parse_args()
    network=NetworkMonitor();network.start()
    root = Path(__file__).resolve().parent
    config = json.loads((root/'config.json').read_text())
    led = Path('/sys/class/leds/PWR')
    original = None
    previous = None
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    alerts = AlertState()
    refreshed = -100
    flash = False
    try:
        while running:
            now = time.time()
            if not args.offline_only and time.monotonic()-refreshed >= 10:
                feeds = PreparednessFeeds(root/'.cache'/'preparedness', config)
                data, errors = feeds.snapshot()
                refreshed = time.monotonic()
            flash = offline_flash(network.snapshot(),now) or (not args.offline_only and should_flash(alerts.update(data, errors, now)))
            try:
                if original is None:
                    original = (led/'trigger').read_text().split('[')[1].split(']')[0]
                desired = int(time.monotonic()*2)%2 if flash else 0
                if args.offline_only and previous is None:
                    (led/'trigger').write_text('none')
                if desired != previous:
                    if desired is None:
                        (led/'trigger').write_text(original)
                    else:
                        if previous is None:
                            (led/'trigger').write_text('none')
                        (led/'brightness').write_text((led/'max_brightness').read_text().strip() if desired else '0')
                    previous = desired
            except (OSError, IndexError):
                # Wait for the one-time permission setup without affecting displays.
                pass
            time.sleep(.1)
    finally:
        if args.offline_only:
            try:
                (led/'trigger').write_text('none')
                (led/'brightness').write_text('0')
            except OSError:pass
        elif original is not None and previous is not None:
            try:
                (led/'trigger').write_text(original)
            except OSError:
                pass


if __name__ == '__main__':
    main()
