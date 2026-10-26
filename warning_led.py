"""Optional red PWR LED warning indicator, running without root."""
import json
import signal
import time
from pathlib import Path
from alert_state import AlertState
from preparedness import PreparednessFeeds


def should_flash(alerts):
    return any(not a['stale'] and (a['source'] != 'weather' or a['detail'].startswith('IN FORCE')) for a in alerts)


def main():
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
            if time.monotonic()-refreshed >= 10:
                feeds = PreparednessFeeds(root/'.cache'/'preparedness', config)
                data, errors = feeds.snapshot()
                refreshed = time.monotonic()
            flash = should_flash(alerts.update(data, errors, now))
            try:
                if original is None:
                    original = (led/'trigger').read_text().split('[')[1].split(']')[0]
                desired = int(time.monotonic()*2)%2 if flash else None
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
        if original is not None and previous is not None:
            try:
                (led/'trigger').write_text(original)
            except OSError:
                pass


if __name__ == '__main__':
    main()
