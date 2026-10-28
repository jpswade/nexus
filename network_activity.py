"""Read-only Pi network activity: no packet capture or device scanning."""
from collections import deque
from pathlib import Path
import threading
import time
import subprocess
from companion_network import NetworkMonitor


def counters(raw):
    result={}
    for line in raw.splitlines()[2:]:
        name,values=line.split(':',1)
        values=values.split();name=name.strip()
        if name!='lo':result[name]=(int(values[0]),int(values[8]))
    return result


def wireless(raw):
    for line in raw.splitlines()[2:]:
        fields=line.split()
        if len(fields)>=4:
            level=float(fields[3].rstrip('.'))
            if -127<=level<0:return level
    return None


class Activity:
    def __init__(self, monitor=None):
        self.monitor=monitor or NetworkMonitor()
        self.owns_monitor=monitor is None
        self.lock=threading.Lock();self.previous=None
        self.history=deque(maxlen=60);self.state={};self.dns=None;self.dns_checked=0

    def sample(self, now=None):
        now=time.monotonic() if now is None else now
        rx=tx=signal=None
        try:
            current=counters(Path('/proc/net/dev').read_text())
            if self.previous:
                stamp,old=self.previous;elapsed=now-stamp
                if elapsed>0 and current.keys()==old.keys() and all(current[k][i]>=old[k][i] for k in current for i in (0,1)):
                    rx=sum(v[0]-old[k][0] for k,v in current.items())/elapsed/1024
                    tx=sum(v[1]-old[k][1] for k,v in current.items())/elapsed/1024
            self.previous=now,current
        except (OSError,ValueError,IndexError):self.previous=None
        try:signal=wireless(Path('/proc/net/wireless').read_text())
        except (OSError,ValueError,IndexError):pass
        self.history.append((signal,rx,tx))
        with self.lock:
            self.state=dict(signal=signal,rx=rx,tx=tx,history=list(self.history),checked=time.time(),dns=self.dns)

    def snapshot(self):
        with self.lock:state=dict(self.state)
        state['connection']=self.monitor.snapshot()
        return state

    def start(self):
        if self.owns_monitor:self.monitor.start()
        def worker():
            while True:
                if time.monotonic()-self.dns_checked>30:
                    self.dns_checked=time.monotonic()
                    try:
                        self.dns=subprocess.run(['getent','ahostsv4','example.com'],stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,timeout=2).returncode==0
                    except (OSError,subprocess.SubprocessError):self.dns=False
                self.sample();time.sleep(1)
        threading.Thread(target=worker,daemon=True).start()


class ActivityPanel:
    def __init__(self):self.fonts={}

    def draw(self,state,size=(225,148)):
        import pygame
        from terminal_theme import FONT
        w,h=size;s=w/225
        surface=pygame.Surface(size);surface.fill('#08141a')
        def text(value,x,y,n=13,colour='#d8ecee'):
            px=max(10,round(n*s))
            if px not in self.fonts:self.fonts[px]=pygame.font.Font(str(FONT),px)
            surface.blit(self.fonts[px].render(value,True,colour),(round(x*s),round(y*s)))
        text('NETWORK / THIS PI',8,5,14,'#35dccc')
        net=state.get('connection',{});label=net.get('label','CHECKING')
        if label=='CONNECTED' and state.get('dns') is False:label='DNS CHECK FAILED'
        text(label,8,25,16)
        sig=state.get('signal');text('Wi-Fi '+(f'{sig:.0f} dBm' if sig is not None else 'unavailable'),8,46,13,'#70949f')
        hist=state.get('history',[])
        for column,tone in ((0,'#35dccc'),(1,'#b9f45b'),(2,'#509ac5')):
            prev=None
            ceiling=max(1,max((row[column] or 0 for row in hist),default=1))
            for i,row in enumerate(hist):
                value=row[column]
                if value is None:prev=None;continue
                fraction=max(0,min(1,(value+100)/90)) if column==0 else value/ceiling
                x=8+(60-len(hist)+i)*3.5;y=(91 if column==0 else 117)-fraction*(26 if column==0 else 19)
                point=(round(x*s),round(y*s))
                if prev:pygame.draw.line(surface,tone,prev,point,max(1,round(s)))
                prev=point
        def rate(key):return '--' if state.get(key) is None else f'{state[key]:.1f}'
        text('RX '+rate('rx')+'  TX '+rate('tx'),8,121,13)
        text('KiB/s / signal, not motion',8,137,10,'#70949f')
        return surface
