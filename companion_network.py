"""Bounded background reachability probes for the LCD; never simulated traffic."""
from collections import deque
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time


def sweep_duration(latency):
    """Visual/probe cadence: faster healthy links, bounded even on failure."""
    return 4.0 if latency is None else max(1.5, min(6.0, 1.5+latency/120))


def gateway():
    for line in Path('/proc/net/route').read_text().splitlines()[1:]:
        fields = line.split()
        if fields[1] == '00000000' and int(fields[3], 16) & 2:
            return socket.inet_ntoa(struct.pack('<I', int(fields[2], 16))), fields[0]
    return None, None


def classify(route, carrier, lan, wan):
    if not route or carrier == '0':
        return 'LOCAL DOWN', 'No link / route', 'error'
    if wan is not None:
        return 'CONNECTED', 'TCP '+str(round(wan))+' ms', 'accent'
    if lan:
        return 'WAN CHECK', 'LAN OK / probes fail', 'error'
    return 'LINK CHECK', 'Gateway / WAN silent', 'error'


class NetworkMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {'label': 'CHECKING', 'detail': 'Waiting for probe', 'colour': 'muted', 'checked': None, 'latency': None, 'history': []}
        self.history = deque(maxlen=22)
        self.sequence = 0

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def probe(self):
        address, interface = None, None
        carrier, lan, latency = None, False, None
        try:
            address, interface = gateway()
            try:
                carrier = Path('/sys/class/net', interface, 'carrier').read_text().strip() if interface else None
            except OSError:
                pass
            if address and carrier != '0':
                result = subprocess.run(['ping', '-n', '-c', '1', '-W', '1', address],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                lan = result.returncode == 0
                for endpoint in ('1.1.1.1', '8.8.8.8'):
                    start = time.monotonic()
                    try:
                        with socket.create_connection((endpoint, 443), timeout=2):
                            latency = (time.monotonic()-start)*1000
                        break
                    except OSError:
                        continue
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            pass
        label, detail, colour = classify(bool(address), carrier, lan, latency)
        self.history.append(latency)
        self.sequence += 1
        with self.lock:
            self.state = dict(label=label, detail=detail, colour=colour,
                              checked=time.time(), latency=latency, history=list(self.history), sequence=self.sequence)

    def start(self):
        def worker():
            while True:
                self.probe()
                time.sleep(sweep_duration(self.snapshot()["latency"]))
        threading.Thread(target=worker, daemon=True).start()
