import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"]="1"
os.environ["SDL_VIDEO_ALLOW_SCREENSAVER"]="0"
import datetime
import signal
import pygame
import json
import pathlib
import threading
import time
import urllib.request
import urllib.parse

CONFIG_PATH = pathlib.Path(os.environ.get("NEXUS_CONFIG", str(pathlib.Path(__file__).with_name("config.json"))))
try:
    LOCATION = json.loads(CONFIG_PATH.read_text())
    for key in ("latitude", "longitude"):
        LOCATION[key] = float(LOCATION[key])
    if not (-90 <= LOCATION["latitude"] <= 90 and -180 <= LOCATION["longitude"] <= 180):
        raise ValueError("Coordinates out of range")
except (OSError, ValueError, KeyError, TypeError) as error:
    raise SystemExit(f"Invalid NEXUS config at {CONFIG_PATH}: {error}. See config.example.json.")
CACHE = pathlib.Path(__file__).parent / ".cache/weather.json"
CACHE.parent.mkdir(parents=True, exist_ok=True)
weather = None
weather_failed = False
try:
    weather = json.loads(CACHE.read_text())
except (OSError, ValueError):
    pass

def conditions(code):
    if code == 0: return "Clear sky"
    if code == 1: return "Mostly clear"
    if code == 2: return "Partly cloudy"
    if code == 3: return "Overcast"
    if code in (45, 48): return "Fog"
    if code in (51, 53, 55): return "Drizzle"
    if code in (56, 57, 66, 67): return "Freezing rain"
    if code in (61, 63, 65): return "Rain"
    if code in (71, 73, 75, 77): return "Snow"
    if code in (80, 81, 82): return "Rain showers"
    if code in (85, 86): return "Snow showers"
    if code in (95, 96, 99): return "Thunderstorms"
    return "Weather"

def fetch_weather():
    global weather, weather_failed
    query = urllib.parse.urlencode({
        "latitude": LOCATION["latitude"], "longitude": LOCATION["longitude"],
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/London", "forecast_days": 1,
    })
    while True:
        try:
            req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + query,
                                         headers={"User-Agent": "PiClockDashboard/1.0"})
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.load(response)
            sample = {"temp": float(data["current"]["temperature_2m"]),
                      "code": int(data["current"]["weather_code"]),
                      "high": float(data["daily"]["temperature_2m_max"][0]),
                      "low": float(data["daily"]["temperature_2m_min"][0]),
                      "date": data["daily"]["time"][0], "fetched": time.time()}
            weather = sample
            weather_failed = False
            try:
                temporary = CACHE.with_suffix(".tmp")
                temporary.write_text(json.dumps(sample))
                temporary.replace(CACHE)
            except OSError as error:
                print(f"Weather cache unavailable: {error}", flush=True)
            print("Weather updated successfully", flush=True)
        except Exception as error:
            weather_failed = True
            print(f"Weather update failed: {error}", flush=True)
        time.sleep(600 if not weather_failed else 60)

threading.Thread(target=fetch_weather, daemon=True).start()

import collections
import math
import random
import shutil
import socket
import platform

# Existing weather fetching runs independently of the display.
state = {"cpu": 0., "ram": 0., "temp": 0., "up": 0., "rx": 0., "tx": 0., "disk": 0., "ready": False}
history = collections.deque([0.] * 90, maxlen=90)
net_history = collections.deque([0.] * 90, maxlen=90)
events = collections.deque(maxlen=7)
lock = threading.Lock()

def log(message):
    with lock:
        events.append((datetime.datetime.now().strftime("%H:%M:%S"), message))

def counters():
    cpu = [int(v) for v in pathlib.Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
    traffic = {}
    for line in pathlib.Path('/proc/net/dev').read_text().splitlines()[2:]:
        name, values = line.split(':')
        if name.strip() != 'lo':
            v = values.split()
            traffic[name.strip()] = (int(v[0]), int(v[8]))
    return sum(cpu), cpu[3] + cpu[4], sum(v[0] for v in traffic.values()), sum(v[1] for v in traffic.values())

def telemetry():
    previous = counters()
    last = time.monotonic()
    count = 0
    last_weather = None
    while True:
        time.sleep(2)
        try:
            current = counters()
            tick = time.monotonic()
            dt = tick - last
            total = current[0] - previous[0]
            cpu = max(0., min(100., 100 * (1 - (current[1]-previous[1])/max(1,total))))
            mem = {line.split(':')[0]: int(line.split()[1]) for line in pathlib.Path('/proc/meminfo').read_text().splitlines()}
            ram = 100 * (1 - mem['MemAvailable']/mem['MemTotal'])
            temp = float(pathlib.Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
            up = float(pathlib.Path('/proc/uptime').read_text().split()[0])
            rx, tx = [max(0, (current[i]-previous[i])/dt/1024) for i in (2,3)]
            disk = shutil.disk_usage('/')
            state.update(cpu=cpu, ram=ram, temp=temp, up=up, rx=rx, tx=tx, disk=disk.free/2**30, ready=True)
            history.append(cpu)
            net_history.append(rx+tx)
            previous, last = current, tick
            count += 1
            if count % 8 == 1:
                log(f'CPU {cpu:04.1f}% / RAM {ram:04.1f}% / {temp:.1f}C')
            sample = weather
            if sample and sample.get('fetched') != last_weather:
                last_weather = sample['fetched']
                log('Weather feed synchronised')
            if temp >= 75 and count % 15 == 0:
                log('Thermal load elevated')
        except Exception as error:
            log('Telemetry retry: ' + type(error).__name__)

log('Display engine initialised')
log('Local telemetry / read-only')
log('Procedural network visualiser online')
threading.Thread(target=telemetry, daemon=True).start()

pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption('NEXUS // Pi terminal')
pygame.mouse.set_visible(False)
W, H = screen.get_size()
S = min(W/1280, H/720)
OX, OY = (W-1280*S)/2, (H-720*S)/2
BG=(5,11,16); PANEL=(9,19,26); LINE=(27,48,59)
TEXT=(221,239,240); DIM=(113,145,156); TEAL=(64,221,205); LIME=(192,243,111); BLUE=(78,146,201)
fonts = {}
labels = collections.OrderedDict()

def pos(x,y): return (round(OX+x*S),round(OY+y*S))
def rect(x,y,w,h): return pygame.Rect(*pos(x,y),round(w*S),round(h*S))
def line(a,b,color=LINE,width=1): pygame.draw.line(screen,color,pos(*a),pos(*b),max(1,round(width*S)))
def circle(x,y,r,color,width=0): pygame.draw.circle(screen,color,pos(x,y),max(1,round(r*S)),0 if not width else max(1,round(width*S)))
def text(value,x,y,size=12,color=TEXT,right=False):
    value=str(value)
    key=(value,size,color)
    if key not in labels:
        if size not in fonts: fonts[size]=pygame.font.SysFont('dejavusansmono',max(10,round(size*S)))
        labels[key]=fonts[size].render(value,True,color)
        if len(labels)>450: labels.popitem(last=False)
    image=labels[key]
    xx,yy=pos(x,y)
    screen.blit(image,(xx-image.get_width() if right else xx,yy))

def panel(x,y,w,h,label,tag):
    pygame.draw.rect(screen,PANEL,rect(x,y,w,h))
    pygame.draw.rect(screen,LINE,rect(x,y,w,h),max(1,round(S)))
    line((x,y),(x+22,y),TEAL,2)
    line((x,y),(x,y+12),TEAL,2)
    text(label,x+16,y+13,11,DIM)
    text(tag,x+w-15,y+13,10,TEAL,True)

def bar(x,y,w,value,color):
    pygame.draw.rect(screen,(20,37,46),rect(x,y,w,4))
    pygame.draw.rect(screen,color,rect(x,y,w*max(0,min(100,value))/100,4))

def spark(values,x,y,w,h,color,maxval=100):
    values=list(values)
    points=[pos(x+i*w/(len(values)-1),y+h-min(1,v/max(1,maxval))*h) for i,v in enumerate(values)]
    if len(points)>1: pygame.draw.lines(screen,color,False,points,max(1,round(S)))

screen.fill(BG)
for x in range(28,1260,32):
    for y in range(86,680,32): circle(x,y,.6,(18,33,41))
background=screen.copy()
kernel_release=platform.release()
rng=random.Random(23)
nodes=[]
for ring,n in [(55,9),(105,15),(160,22)]:
    for i in range(n):
        nodes.append((ring,2*math.pi*i/n+rng.uniform(-.08,.08),rng.random()))
running=True
paused=False
start=time.monotonic()
frozen=0.
last_pause=0.
clock=pygame.time.Clock()
frame=0
actual_fps=0.

def stop(*_):
    global running
    running=False
signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
print(f'NEXUS ready: {W}x{H}, target=12fps',flush=True)
while running:
    for event in pygame.event.get():
        if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE): running=False
        elif event.type==pygame.KEYDOWN and event.key==pygame.K_SPACE:
            paused=not paused
            if paused: last_pause=time.monotonic()
            else: frozen+=time.monotonic()-last_pause
    t=(last_pause if paused else time.monotonic())-start-frozen
    now=datetime.datetime.now()
    m=state.copy()
    screen.blit(background,(0,0))
    text('N E X U S',28,22,24,TEXT)
    text('// PERSONAL SYSTEMS TERMINAL',203,32,11,DIM)
    circle(1010,38,3,LIME if not paused else DIM)
    text('LOCAL NODE / PI-02',1023,30,12,LIME)
    line((28,68),(1252,68))
    text('01 / TEMPORAL',28,79,10,DIM)
    text(now.strftime('%Z') or 'EUROPE/LONDON',1252,79,10,DIM,True)

    panel(28,105,320,184,'SYSTEM TIME','SYNC / LOCAL')
    text(now.strftime('%H:%M'),44,137,62,TEXT)
    text(now.strftime('%S'),306,177,18,TEAL,True)
    text(now.strftime('%A').upper(),46,222,12,LIME)
    text(now.strftime('%d %b %Y').upper(),46,246,13,DIM)
    bar(220,253,108,now.second/60*100,TEAL)

    panel(28,307,320,247,'HARDWARE TELEMETRY','LIVE / 2s')
    for i,(name,value,suffix,color) in enumerate([
        ('CPU',m['cpu'],'%',TEAL),('MEM',m['ram'],'%',BLUE),('CORE',m['temp'],'C',LIME)]):
        y=347+i*48
        text(name,44,y,12,DIM)
        text(f'{value:04.1f}{suffix}',330,y,15,color,True)
        bar(44,y+25,286,value if name!='CORE' else value/85*100,color)
    text('CPU HISTORY / 3 MIN',44,496,9,DIM)
    spark(history,44,518,286,24,TEAL)

    panel(366,105,540,449,'PROCEDURAL NEURAL FIELD','VISUALISER')
    cx,cy=636,324
    for r in (55,105,160,181): circle(cx,cy,r,(22,46,55),1)
    line((cx-195,cy),(cx+195,cy),(18,37,46))
    line((cx,cy-185),(cx,cy+185),(18,37,46))
    points=[]
    for r,a,seed in nodes:
        angle=a+t*(.045 if r!=105 else -.06)
        rr=r+math.sin(t*.6+seed*9)*5
        points.append((cx+math.cos(angle)*rr,cy+math.sin(angle)*rr,seed))
    for i,(x,y,seed) in enumerate(points):
        for j in range(i+1,len(points)):
            xx,yy,ss=points[j]
            dist=(xx-x)**2+(yy-y)**2
            if dist<82**2 and ((i+j)%3==0):
                line((x,y),(xx,yy),(24,64,70))
                if (i+j)%7==0:
                    p=(t*.22+seed)%1
                    circle(x+(xx-x)*p,y+(yy-y)*p,1.8,TEAL)
        pulse=(math.sin(t*1.5+seed*15)+1)/2
        circle(x,y,2.2+pulse,TEAL if pulse>.7 else (43,113,119))
        if pulse>.93: circle(x,y,6,(39,79,83),1)
    for phase in (0,math.pi):
        angle=t*.34+phase
        end=(cx+math.cos(angle)*181,cy+math.sin(angle)*181)
        line((cx,cy),end,(30,80,83))
        circle(*end,3,LIME)
    circle(cx,cy,27,PANEL)
    circle(cx,cy,27,TEAL,1)
    circle(cx,cy,19,(24,54,60),1)
    text('N',cx-7,cy-13,19,LIME)
    text('46 NODES / GENERATIVE MOTION',386,516,10,DIM)
    text('PAUSED' if paused else 'ACTIVE',887,516,10,LIME,True)

    panel(924,105,328,184,'ENVIRONMENT / ' + str(LOCATION.get('name', 'LOCAL')).upper()[:18],'WEATHER')
    sample=weather
    if sample:
        stale=weather_failed or time.time()-sample['fetched']>1800
        text(f'{sample["temp"]:.0f}°',940,139,50,TEXT)
        # Abstract orbiting sun / cloud motif, intentionally geometric.
        wx,wy=1204,178
        circle(wx,wy,23,(24,56,62),1)
        circle(wx,wy,12,TEAL,1)
        for k in range(8):
            a=t*.12+k*math.pi/4
            line((wx+math.cos(a)*29,wy+math.sin(a)*29),(wx+math.cos(a)*34,wy+math.sin(a)*34),TEAL)
        text(conditions(sample['code']).upper(),940,211,14,TEAL)
        daily=f'HI {sample["high"]:.0f}° / LO {sample["low"]:.0f}°' if sample['date']==now.strftime('%Y-%m-%d') else 'DAILY FORECAST STALE'
        text(daily,940,240,11,DIM)
        updated=datetime.datetime.fromtimestamp(sample['fetched']).strftime('%H:%M')
        text(('STALE ' if stale else '')+updated,1236,263,9,LIME if stale else DIM,True)
        text('OPEN-METEO',940,263,9,DIM)
    else:
        text('WEATHER OFFLINE' if weather_failed else 'ACQUIRING WEATHER',940,160,16,DIM)
        text('RETRYING IN BACKGROUND',940,215,11,DIM)

    panel(924,307,328,247,'EVENT STREAM','LOCAL')
    with lock: entries=list(events)
    for i,(stamp,message) in enumerate(entries[-7:]):
        yy=346+i*27
        text(stamp,940,yy,9,TEAL)
        text(message[:29],1002,yy,9,TEXT if i==len(entries)-1 else DIM)
    cursor_on=int(t*2)%2
    text('>',940,534,10,LIME)
    if cursor_on: pygame.draw.rect(screen,LIME,rect(955,534,7,12))

    panel(28,573,1224,83,'NETWORK I/O','REAL TRAFFIC / KiB/s')
    traffic=max(1,max(net_history))
    spark(net_history,257,602,673,38,TEAL,traffic)
    sweep=257+(t*55)%673
    line((sweep,599),(sweep,644),(40,86,91))
    text(f'RX {m["rx"]:7.1f}',44,607,14,TEAL)
    text(f'TX {m["tx"]:7.1f}',44,632,11,DIM)
    up=int(m['up']); days,rem=divmod(up,86400); hours,rem=divmod(rem,3600)
    text(f'UP {days}d {hours:02}:{rem//60:02}',1234,607,13,LIME,True)
    text(f'DISK FREE {m["disk"]:.1f} GiB',1234,632,10,DIM,True)

    # Continuous ticker uses real machine facts, not invented security alerts.
    facts=(f'RASPBERRY PI 2 / ARMv7    +++    {kernel_release}    +++    '
           f'CPU {m["cpu"]:.1f}%    +++    RAM {m["ram"]:.1f}%    +++    '
           f'CORE {m["temp"]:.1f}C    +++    WEATHER / OPEN-METEO    +++    LOCAL TELEMETRY / NO CLOUD AI    +++    ')
    clip=screen.get_clip()
    screen.set_clip(rect(28,673,950,24))
    # Static text width calculation; scroll speed is independent of frame rate.
    font=fonts.get(10)
    if font is None:
        fonts[10]=pygame.font.SysFont('dejavusansmono',max(10,round(10*S)))
        font=fonts[10]
    span=font.size(facts)[0]/S
    offset=(t*34)%span
    text(facts,28-offset,677,10,DIM)
    text(facts,28-offset+span,677,10,DIM)
    screen.set_clip(clip)
    text('SPACE PAUSE / ESC EXIT',1252,677,10,DIM,True)
    pygame.display.flip()
    clock.tick(12)
    frame+=1
    if frame%120==0: print(f'Render: {clock.get_fps():.1f}fps / CPU {m["cpu"]:.1f}% / {m["temp"]:.1f}C',flush=True)
pygame.quit()
