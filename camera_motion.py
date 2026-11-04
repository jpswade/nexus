"""Optional local camera motion worker. Images exist only in memory."""
import argparse
import datetime as dt
import io
import json
import math
import os
from pathlib import Path
import statistics
import time
import urllib.request
from urllib.parse import urlsplit

CONFIG = Path.home()/'.config/nexus/camera.json'
STATE = Path.home()/'.local/state/nexus-camera'


def configuration(path=CONFIG):
    raw = json.loads(Path(path).read_text())
    url = raw.get('capture_url', '')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Invalid camera URL')
    roi = raw.get('roi', [0, 0, 1, 1])
    if len(roi) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in roi):
        raise ValueError('Invalid ROI')
    if not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
        raise ValueError('Invalid ROI')
    return dict(capture_url=url, roi=roi, observe=bool(raw.get('observe', True)),
                interval=max(2., min(30., float(raw.get('interval', 2)))),
                pixel_threshold=max(8, min(80, int(raw.get('pixel_threshold', 18)))),
                fraction=max(.02, min(.5, float(raw.get('fraction', .08)))))


class Detector:
    def __init__(self, threshold=18, fraction=.08):
        self.threshold, self.fraction = threshold, fraction
        self.previous = None
        self.consecutive = 0
        self.last_motion = None
        self.last_pulse = None

    def reset(self):
        self.previous = None
        self.consecutive = 0

    def update(self, pixels, now):
        old, self.previous = self.previous, list(pixels)
        if old is None:
            return 0., False
        differences = [a-b for a,b in zip(pixels, old)]
        shift = statistics.median(differences)
        changed = sum(abs(d-shift) >= self.threshold for d in differences)/len(differences)
        # Broad lighting/exposure changes are not treated as movement.
        detected = abs(shift) < 20 and self.fraction <= changed <= .75
        self.consecutive = self.consecutive+1 if detected else 0
        if self.consecutive >= 3:
            self.last_motion = now
            if self.last_pulse is None or now-self.last_pulse >= 30:
                self.last_pulse = now
        return changed, detected

    def state(self, now):
        elapsed = now-self.last_motion if self.last_motion is not None else float('inf')
        return 'activity' if elapsed <= 12 else 'settled' if elapsed <= 32 else 'quiet'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def capture(url, roi):
    from PIL import Image
    start = time.monotonic()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(url, timeout=4) as response:
        if response.status != 200:
            raise ValueError('Unexpected camera status')
        chunks, size = [], 0
        while True:
            chunk = response.read(16384)
            if not chunk:
                break
            size += len(chunk)
            if size > 524288 or time.monotonic()-start > 6:
                raise ValueError('Camera response limit exceeded')
            chunks.append(chunk)
    with Image.open(io.BytesIO(b''.join(chunks))) as image:
        if image.format != 'JPEG' or image.width*image.height > 2000000:
            raise ValueError('Unsupported camera image')
        w,h = image.size
        box = (int(roi[0]*w), int(roi[1]*h), max(int(roi[0]*w)+1,int(roi[2]*w)), max(int(roi[1]*h)+1,int(roi[3]*h)))
        small = image.crop(box).convert('L').resize((32,24), Image.Resampling.BOX)
        return list(small.getdata()), size


def write_state(root, sample):
    pending = root/'motion.tmp'
    pending.write_text(json.dumps(sample)+'\n')
    os.replace(pending, root/'motion.json')


def run(config_path=CONFIG, root=STATE):
    os.umask(0o077)
    root.mkdir(parents=True, exist_ok=True)
    detector, settings, last_log = None, None, 0
    previous_ok = False
    while True:
        started = time.monotonic()
        now = time.time()
        try:
            config = configuration(config_path)
            if config != settings:
                settings = config
                detector = Detector(config['pixel_threshold'], config['fraction'])
                previous_ok = False
            pixels, size = capture(config['capture_url'], config['roi'])
            score, candidate = detector.update(pixels, now)
            sample = dict(checked=now, online=True, observe=config['observe'],
                          state=detector.state(now), score=round(score,4), candidate=candidate,
                          last_motion=detector.last_motion, last_pulse=detector.last_pulse,
                          bytes=size)
        except Exception as error:
            if detector: detector.reset()
            sample = dict(checked=now, online=False, observe=True if settings is None else settings['observe'],
                          state='unavailable', error=type(error).__name__)
        write_state(root, sample)
        if now-last_log >= 10 or sample['online'] != previous_ok:
            day = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime('%Y-%m-%d')
            with (root/('motion-'+day+'.jsonl')).open('a') as log:
                log.write(json.dumps(sample)+'\n')
            for path in root.glob('motion-????-??-??.jsonl'):
                if now-path.stat().st_mtime > 7*86400: path.unlink()
            last_log = now
        previous_ok = sample['online']
        time.sleep(max(.1, (settings or {}).get('interval',2)-(time.monotonic()-started)))


class MotionReader:
    """No network or decoding on either render thread."""
    def __init__(self, path=STATE/'motion.json'):
        self.path, self.last_read, self.sample = path, float('-inf'), {}

    def snapshot(self, now):
        if now-self.last_read >= 1 or now < self.last_read:
            self.last_read = now
            try: self.sample = json.loads(self.path.read_text())
            except (OSError, ValueError): self.sample = {}
        sample = dict(self.sample)
        if sample and not 0 <= now-sample.get('checked',0) <= 15:
            sample.update(online=False, state='unavailable')
        return sample


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--state-dir', type=Path, default=STATE)
    args = parser.parse_args()
    run(args.config, args.state_dir)
