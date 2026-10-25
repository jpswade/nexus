"""Small Linux telemetry sampler. Missing measurements stay unavailable."""
from collections import deque
from pathlib import Path
import time


class Telemetry:
    def __init__(self):
        self.previous=None
        self.checked=-10
        self.cpu=self.memory=self.temperature=None
        self.history=deque(maxlen=90)

    def sample(self, now=None):
        now=time.monotonic() if now is None else now
        if now-self.checked<2:return
        self.checked=now
        try:
            values=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
            total,idle=sum(values),values[3]+values[4]
            if self.previous:
                delta=total-self.previous[0]
                if delta>0:
                    self.cpu=max(0,min(100,100*(1-(idle-self.previous[1])/delta)))
                    self.history.append(self.cpu)
            self.previous=total,idle
        except (OSError,ValueError,IndexError):self.cpu=None
        try:
            memory={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
            self.memory=100*(1-memory['MemAvailable']/memory['MemTotal'])
        except (OSError,ValueError,KeyError,ZeroDivisionError):self.memory=None
        try:self.temperature=float(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000
        except (OSError,ValueError):self.temperature=None

    def label(self):
        def value(v,suffix):return '--' if v is None else f'{v:.1f}{suffix}'
        return 'PI / CPU '+value(self.cpu,'%')+'   RAM '+value(self.memory,'%')+'   CORE '+value(self.temperature,'C')
