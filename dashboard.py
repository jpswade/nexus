import os
import argparse

arguments = argparse.ArgumentParser(description="Nexus desktop dashboard")
arguments.add_argument('--snapshot', help='Render one cached-data frame to a PNG without opening the monitor')
arguments.add_argument('--workspace', type=int, choices=range(1,5), default=1)
arguments.add_argument('--age', type=float, default=0, help='Workspace animation age for snapshots')
ARGS = arguments.parse_args()
if ARGS.snapshot:
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_RENDER_DRIVER'] = 'software'
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
CACHE_DIR = pathlib.Path(os.environ.get("NEXUS_CACHE", str(pathlib.Path(__file__).parent / ".cache")))
CACHE = CACHE_DIR / "weather.json"
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

if not ARGS.snapshot:
    threading.Thread(target=fetch_weather, daemon=True).start()

import collections
import math
from feeds import PlanetFeeds, MAX_AGES, age_label
from security import SecurityFeeds
from security_ui import SecurityDesktop
from workspaces import WorkspaceCycle, NAMES
from terminal_theme import PALETTE, font as terminal_font, switch_view
from types import SimpleNamespace

planet = PlanetFeeds(CACHE_DIR)
if not ARGS.snapshot:
    planet.start()
security = SecurityFeeds(CACHE_DIR / "security")
if not ARGS.snapshot:
    security.start()

os.environ.setdefault("SDL_RENDER_DRIVER", "opengles2")
pygame.display.init()
pygame.font.init()
# Render a smaller canvas and let SDL scale it through the GPU when available.
# The Pi 2 is limited by software drawing at native 1080p.
if ARGS.snapshot:
    screen = pygame.display.set_mode((1280,720))
else:
    try:
        screen = pygame.display.set_mode((1280, 720), pygame.FULLSCREEN | pygame.SCALED, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption('NEXUS / TERMINAL')
pygame.mouse.set_visible(False)
W, H = screen.get_size()
S = min(W/1280, H/720)
OX, OY = (W-1280*S)/2, (H-720*S)/2
# Shared phosphor terminal palette.
BG=pygame.Color(PALETTE['background']); PANEL=pygame.Color(PALETTE['panel'])
LINE=pygame.Color(PALETTE['border']); TEXT=pygame.Color(PALETTE['text'])
DIM=pygame.Color(PALETTE['muted']); TEAL=TEXT; LIME=TEXT; BLUE=TEXT
AMBER=pygame.Color(PALETTE['error']); TAB=TEXT; WHITE=TEXT; SHADOW=BG
fonts = {}
labels = collections.OrderedDict()

def pos(x,y): return (round(OX+x*S),round(OY+y*S))
def rect(x,y,w,h): return pygame.Rect(*pos(x,y),round(w*S),round(h*S))
def line(a,b,color=LINE,width=1): pygame.draw.line(screen,color,pos(*a),pos(*b),max(1,round(width*S)))
def circle(x,y,r,color,width=0): pygame.draw.circle(screen,color,pos(x,y),max(1,round(r*S)),0 if not width else max(1,round(width*S)))
def text(value,x,y,size=12,color=TEXT,right=False):
    value=str(value)
    color=tuple(pygame.Color(color))
    key=(value,size,color)
    if key not in labels:
        if size not in fonts: fonts[size]=terminal_font(max(16,size)*S)
        labels[key]=fonts[size].render(value,True,color)
        if len(labels)>450: labels.popitem(last=False)
    image=labels[key]
    xx,yy=pos(x,y)
    screen.blit(image,(xx-image.get_width() if right else xx,yy))

def mono(value,x,y,size=12,color=(185,231,207)):
    key=('mono',size)
    if key not in fonts:
        fonts[key]=terminal_font(max(16,size)*S)
    label=fonts[key].render(str(value),True,color)
    screen.blit(label,pos(x,y))

def bevel(x,y,w,h,fill=PANEL,sunken=False):
    pygame.draw.rect(screen,PANEL,rect(x,y,w,h))
    pygame.draw.rect(screen,LINE,rect(x,y,w,h),max(1,round(S)))

def panel(x,y,w,h,label,tag):
    bevel(x,y,w,h)
    text(label.upper(),x+16,y+8,18,TEXT)
    # Narrow panels reserve the heading for the section name.
    if w>650:text(tag.upper(),x+w-16,y+10,16,DIM,True)
    line((x+12,y+34),(x+w-12,y+34),LINE)

def bar(x,y,w,value,color):
    bevel(x,y,w,7,(176,182,180),True)
    pygame.draw.rect(screen,color,rect(x+1,y+1,max(0,(w-2)*max(0,min(100,value))/100),5))

desktop = SecurityDesktop(SimpleNamespace(text=text, mono=mono, panel=panel, bevel=bevel,
                                         line=line, TEXT=TEXT, DIM=DIM, TEAL=TEAL, AMBER=AMBER, LIME=LIME))
cycle=WorkspaceCycle(duration=32,initial=ARGS.workspace-1)
if ARGS.snapshot:cycle.automatic=False
manual_terminal=False
terminal_since=0.
terminal_hidden=False
last_workspace=None

def vector(lon,lat):
    lon,lat=math.radians(lon),math.radians(lat)
    return math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)

land = json.loads((pathlib.Path(__file__).parent/'data/land.json').read_text())
coast = [[vector(lon,lat) for lon,lat in ring] for ring in land]
grid = [[vector(lon,lat) for lon in range(-180,181,5)] for lat in range(-60,61,30)]
grid += [[vector(lon,lat) for lat in range(-90,91,5)] for lon in range(-180,180,30)]

screen.fill(BG)
# Clean black background: no scanlines or blur.
bevel(28,672,1224,29,(209,212,209))
background=screen.copy()
running=True
paused=False
start=time.monotonic()
frozen=0.
last_pause=0.
clock=pygame.time.Clock()
frame=0
camera_lon=None
camera_has_iss=False

def stop(*_):
    global running
    running=False
signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
print(f'NEXUS observatory ready: {W}x{H}, target=12fps',flush=True)
def draw_observatory(age):
    global camera_lon,camera_has_iss
    panel(28,105,770,551,'04 / ORBITAL OBSERVATORY','ISS + USGS')
    cx,cy,radius=413,345,172
    target=(iss['longitude']-25 if iss else 0)+18*math.sin(t*.045)
    if camera_lon is None or (iss and not camera_has_iss):
        camera_lon=target
        camera_has_iss=bool(iss)
    if not paused: camera_lon+=((target-camera_lon+180)%360-180)*.035
    lon0=math.radians(camera_lon)
    cs,sn=math.cos(lon0),math.sin(lon0)
    lat0=math.radians(12)
    ct,st=math.cos(lat0),math.sin(lat0)

    def project(v):
        x,y,z=v
        depth=ct*(x*cs+y*sn)+st*z
        return cx+radius*(-x*sn+y*cs),cy-radius*(ct*z-st*(x*cs+y*sn)),depth

    def globe_lines(ring,color):
        points=[]
        for v in ring:
            x,y,z=project(v)
            if z>=0:
                points.append(pos(x,y))
            else:
                if len(points)>1:pygame.draw.lines(screen,color,False,points,max(1,round(S)))
                points=[]
        if len(points)>1:pygame.draw.lines(screen,color,False,points,max(1,round(S)))

    circle(cx+2,cy+3,radius+2,BG)
    circle(cx,cy,radius+13,LINE,1)
    circle(cx,cy,radius,BG)
    circle(cx,cy,radius,LINE,1)
    for ring in grid:globe_lines(ring,LINE)
    for ring in coast:globe_lines(ring,TEXT)
    for index,quake in enumerate(earthquakes):
        x,y,z=project(vector(quake['lon'],quake['lat']))
        if z>0:
            circle(x,y,2+max(0,quake['mag']-3)*.7,(255,159,65))
            pulse=(t*.35+index*.17)%1
            circle(x,y,4+pulse*10,(int(205-95*pulse),int(144-65*pulse),int(70-25*pulse)),1)
    if iss:
        ix,iy,iz=project(vector(iss['longitude'],iss['latitude']))
        if iz>0:
            circle(ix,iy,8,TEXT,1)
            circle(ix,iy,3,TEXT)
            text('ISS',ix+14,iy-14,20,TEXT)
        text(f'ISS {iss["latitude"]:+.1f} LAT / {iss["longitude"]:+.1f} LON',48,538,24,TEXT)
        text(f'{iss["altitude"]:.0f} KM ALT / {iss["velocity"]:,.0f} KM/H',48,573,22,DIM)
        text(stamp('iss'),778,579,18,AMBER if 'iss' in errors or epoch-iss['observed']>MAX_AGES['iss'] else DIM,True)
    else:
        text('ISS / '+stamp('iss'),48,550,26,DIM)
    text('GREEN: ISS / AMBER: M2.5+ EARTHQUAKES',48,620,18,DIM)

    panel(820,105,432,551,'LOCAL / PLANETARY STATUS','')
    text(now.strftime('%H:%M:%S'),842,152,48,TEXT)
    text(now.strftime('%a %d %b %Y').upper(),842,211,22,DIM)
    line((842,252),(1230,252))
    sample=weather
    text(str(LOCATION.get('name','LOCAL')).upper()[:25],842,270,20,DIM)
    if sample:
        stale=weather_failed or epoch-sample['fetched']>1800
        text(f'{sample["temp"]:.0f} C / '+conditions(sample['code']).upper(),842,304,24,TEXT)
        text('OPEN-METEO / '+('STALE' if stale else age_label(epoch-sample['fetched']).upper()),842,340,18,AMBER if stale else DIM)
    else:
        text('WEATHER / CONNECTING',842,310,24,DIM)
    line((842,380),(1230,380))
    text('NOAA / GEOMAGNETIC Kp',842,400,20,DIM)
    text(f'{kp["value"]:.2f} / '+('STORM' if kp['value']>=5 else 'QUIET' if kp['value']<4 else 'UNSETTLED') if kp else stamp('kp'),842,432,28,AMBER if kp and kp['value']>=4 else TEXT)
    text(stamp('kp'),842,469,18,DIM)
    line((842,506),(1230,506))
    text('USGS / LAST 24 HOURS',842,526,20,DIM)
    text(f'{len(earthquakes)} M2.5+ EVENTS' if quakes else stamp('quakes'),842,559,26,TEXT)
    text(stamp('quakes'),842,604,18,DIM)

while running:
    input_time=(last_pause if paused else time.monotonic())-start-frozen
    if ARGS.snapshot:input_time=ARGS.age
    for event in pygame.event.get():
        if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):running=False
        elif event.type==pygame.KEYDOWN:
            if event.key==pygame.K_SPACE:
                paused=not paused
                if paused:last_pause=time.monotonic()
                else:frozen+=time.monotonic()-last_pause
            elif pygame.K_1<=event.key<=pygame.K_4:
                cycle.select(event.key-pygame.K_1,input_time)
                manual_terminal=False;terminal_hidden=False
            elif event.key in (pygame.K_LEFT,pygame.K_RIGHT):
                cycle.step(1 if event.key==pygame.K_RIGHT else -1,input_time)
                manual_terminal=False;terminal_hidden=False
            elif event.key==pygame.K_F5:
                pygame.quit()
                switch_view('home')
            elif event.key==pygame.K_a:
                cycle.automatic=not cycle.automatic
                cycle.since=input_time
            elif event.key==pygame.K_t:
                currently_visible=manual_terminal
                manual_terminal=not currently_visible
                terminal_hidden=currently_visible
                terminal_since=input_time
    t=(last_pause if paused else time.monotonic())-start-frozen
    if ARGS.snapshot:t=ARGS.age
    workspace,age=cycle.tick(t)
    if workspace!=last_workspace:
        manual_terminal=False;terminal_hidden=False
        last_workspace=workspace
        print(f'Workspace {workspace+1}: {NAMES[workspace]}',flush=True)
    now=datetime.datetime.now()
    epoch=time.time()
    feeds, errors=planet.snapshot()
    security_data,security_errors=security.snapshot()
    iss=feeds.get('iss')
    quakes=feeds.get('quakes')
    kp=feeds.get('kp')
    wind=feeds.get('wind')
    earthquakes=[e for e in quakes['events'] if epoch-86400<=e['time']<=epoch] if quakes else []
    strongest=max(earthquakes,key=lambda e:e['mag']) if earthquakes else None

    def stamp(name):
        sample=feeds.get(name)
        if not sample: return 'FEED UNAVAILABLE' if name in errors else 'CONNECTING...'
        age=epoch-sample['observed']
        stale=name in errors or age>MAX_AGES[name]
        return ('STALE / ' if stale else 'OBS / ')+age_label(age).upper()

    screen.blit(background,(0,0))
    text('N E X U S',28,16,36,TEXT)
    text(NAMES[workspace].upper(),260,27,22,DIM)
    text(now.strftime('%H:%M:%S'),1252,18,32,TEXT,True)
    text(' '.join(f'[{i+1}]' if i==workspace else f' {i+1} ' for i in range(4)),28,64,20,TEXT)
    mode=f'AUTO / {max(0,int(cycle.duration-age))}s' if cycle.automatic else 'MANUAL'
    text(mode,420,64,20,DIM)
    count=len(feeds)+len(security_data)
    text(f'{count}/7 SOURCES' + (' / RETRYING' if errors or security_errors else ''),1252,64,20,
         AMBER if errors or security_errors else DIM,True)
    briefing_age=7.65+(t-terminal_since) if manual_terminal else age
    # Briefings replace the main view instead of covering it with a popup.
    show_brief=manual_terminal and not terminal_hidden
    if show_brief:
        desktop.terminal(workspace,briefing_age,security_data,security_errors,epoch,
                         (workspace,cycle.since,manual_terminal),forced=True)
    elif workspace==3:
        draw_observatory(age)
    else:
        desktop.draw(workspace,age,security_data,security_errors,epoch)
    text('1-4 VIEWS   ARROWS SWITCH   A AUTO   T BRIEF   F5 HOME',44,679,18,DIM)
    text('SPACE PAUSE / ESC EXIT',1236,679,18,DIM,True)
    if ARGS.snapshot:
        pygame.image.save(screen,ARGS.snapshot)
        running=False
    pygame.display.flip()
    clock.tick(12)
    frame+=1
    if frame%120==0:print(f'Render: {clock.get_fps():.1f}fps',flush=True)
pygame.quit()
