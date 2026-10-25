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

if not ARGS.snapshot:
    threading.Thread(target=fetch_weather, daemon=True).start()

import collections
import math
from feeds import PlanetFeeds, MAX_AGES, age_label
from security import SecurityFeeds
from security_ui import SecurityDesktop
from workspaces import WorkspaceCycle, NAMES
from types import SimpleNamespace

planet = PlanetFeeds(pathlib.Path(__file__).parent / '.cache')
if not ARGS.snapshot:
    planet.start()
security = SecurityFeeds(pathlib.Path(__file__).parent / ".cache/security")
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
pygame.display.set_caption('Nexus — Observatory desktop')
pygame.mouse.set_visible(False)
W, H = screen.get_size()
S = min(W/1280, H/720)
OX, OY = (W-1280*S)/2, (H-720*S)/2
# BeOS-inspired chrome: yellow tabs, warm grey controls and a teal desktop.
BG=(47,104,119); PANEL=(219,220,216); LINE=(102,105,105)
TEXT=(28,32,35); DIM=(83,89,93); TEAL=(17,94,137); LIME=(36,102,65); BLUE=(51,99,163); AMBER=(165,66,24)
TAB=(255,218,67); WHITE=(250,250,243); SHADOW=(32,67,78)
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
        if size not in fonts: fonts[size]=pygame.font.SysFont('dejavusansmono' if size>=18 else 'dejavusans',max(9,round(size*S)))
        labels[key]=fonts[size].render(value,True,color)
        if len(labels)>450: labels.popitem(last=False)
    image=labels[key]
    xx,yy=pos(x,y)
    screen.blit(image,(xx-image.get_width() if right else xx,yy))

def mono(value,x,y,size=12,color=(185,231,207)):
    key=('mono',size)
    if key not in fonts:
        fonts[key]=pygame.font.SysFont('dejavusansmono',max(9,round(size*S)))
    label=fonts[key].render(str(value),True,color)
    screen.blit(label,pos(x,y))

def bevel(x,y,w,h,fill=PANEL,sunken=False):
    pygame.draw.rect(screen,fill,rect(x,y,w,h))
    light,dark=((100,105,107),WHITE) if sunken else (WHITE,(91,95,97))
    line((x,y),(x+w-1,y),light)
    line((x,y),(x,y+h-1),light)
    line((x,y+h-1),(x+w-1,y+h-1),dark)
    line((x+w-1,y),(x+w-1,y+h-1),dark)

def panel(x,y,w,h,label,tag):
    pygame.draw.rect(screen,SHADOW,rect(x+4,y+4,w,h))
    bevel(x,y,w,h)
    # A short yellow title tab rather than a full-width title bar.
    title=label.title().replace('Iss','ISS').replace('Noaa','NOAA').replace('Php','PHP').replace('Cve','CVE').replace('Kev','KEV')
    tabwidth=min(w-8,max(116,len(title)*6.7+39))
    bevel(x,y-19,tabwidth,20,TAB)
    bevel(x+7,y-14,10,10,(244,201,49))
    text(title,x+25,y-16,11,TEXT)
    for k in range(3):
        line((x+tabwidth-12+k*2,y-13),(x+tabwidth-12+k*2,y-6),(160,128,25))
    text(tag,x+w-12,y+11,9,DIM,True)
    line((x+10,y+29),(x+w-10,y+29),(177,181,179))
    line((x+10,y+30),(x+w-10,y+30),WHITE)
    # Familiar resize-grip detail in the lower-right corner.
    for i in range(3):
        line((x+w-5-i*4,y+h-4),(x+w-4,y+h-5-i*4),(140,144,142))

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
# Subtle desktop pinstripes, drawn once rather than on each frame.
for y in range(0,720,4):line((0,y),(1280,y),(46,101,116))
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
    panel(28,105,320,184,'Time & date','UTC'+now.astimezone().strftime('%z'))
    text(now.strftime('%H:%M'),44,137,62,TEXT)
    text(now.strftime('%S'),306,177,18,TEAL,True)
    text(now.strftime('%A').upper(),46,222,12,LIME)
    text(now.strftime('%d %b %Y').upper(),46,246,13,DIM)
    bar(220,253,108,now.second/60*100,TEAL)

    panel(28,307,320,247,'Solar monitor','NOAA / SWPC')
    text('PLANETARY Kp INDEX',44,346,11,DIM)
    if kp:
        text(f'{kp["value"]:.2f}',44,366,42,TEXT)
        activity='STORM LEVEL' if kp['value']>=5 else 'UNSETTLED' if kp['value']>=4 else 'QUIET'
        text(activity,330,391,11,AMBER if kp['value']>=4 else LIME,True)
        for i in range(9):
            color=TEAL if i<kp['value'] else (174,181,178)
            pygame.draw.rect(screen,color,rect(44+i*32,423,26,7))
        text(stamp('kp'),44,441,9,DIM)
    else:
        text(stamp('kp'),44,382,13,DIM)
    text('SOLAR WIND',44,475,11,DIM)
    text(f'{wind["value"]:.0f} km/s' if wind else '-- km/s',330,470,20,TEAL,True)
    text(stamp('wind'),44,510,9,AMBER if wind and epoch-wind['observed']>MAX_AGES['wind'] else DIM)
    text('Kp 0-9 / GEOMAGNETIC ACTIVITY',44,533,9,DIM)

    panel(366,105,540,449,'Orbital navigator','ISS + SEISMIC')
    cx,cy,radius=636,326,169
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

    circle(cx+2,cy+3,radius+2,(132,140,141))
    circle(cx,cy,radius+13,(157,166,165),1)
    circle(cx,cy,radius,(18,47,76))
    circle(cx,cy,radius,(7,31,53),1)
    for ring in grid:globe_lines(ring,(40,78,108))
    for ring in coast:globe_lines(ring,(133,193,188))
    for index,quake in enumerate(earthquakes):
        x,y,z=project(vector(quake['lon'],quake['lat']))
        if z>0:
            circle(x,y,2+max(0,quake['mag']-3)*.7,(255,159,65))
            pulse=(t*.35+index*.17)%1
            circle(x,y,4+pulse*10,(int(205-95*pulse),int(144-65*pulse),int(70-25*pulse)),1)
    if iss:
        ix,iy,iz=project(vector(iss['longitude'],iss['latitude']))
        if iz>0:
            circle(ix,iy,10+3*math.sin(t*2),TAB,1)
            circle(ix,iy,4,TAB)
            line((ix+9,iy-9),(ix+27,iy-27),TAB)
            text('ISS',ix+30,iy-39,12,TAB)
        text(f'{iss["latitude"]:+06.2f} LAT / {iss["longitude"]:+07.2f} LON',386,477,11,TEAL)
    else:
        text('AWAITING ORBITAL POSITION',386,477,11,DIM)
    text('Orange: M2.5+ earthquakes',386,503,9,AMBER)
    text('Yellow: ISS position',386,523,9,LIME)
    text(stamp('iss'),887,523,9,DIM,True)

    panel(924,105,328,184,'Weather / '+str(LOCATION.get('name','LOCAL')).upper()[:18],'LOCAL')
    sample=weather
    if sample:
        stale=weather_failed or epoch-sample['fetched']>1800
        text(f'{sample["temp"]:.0f}°',940,139,50,TEXT)
        wx,wy=1204,178
        circle(wx,wy,23,(180,184,177),1)
        circle(wx,wy,12,TEAL,1)
        for k in range(8):
            a=t*.12+k*math.pi/4
            line((wx+math.cos(a)*29,wy+math.sin(a)*29),(wx+math.cos(a)*34,wy+math.sin(a)*34),TEAL)
        text(conditions(sample['code']).upper(),940,211,14,TEAL)
        daily=f'HI {sample["high"]:.0f}° / LO {sample["low"]:.0f}°' if sample['date']==now.strftime('%Y-%m-%d') else 'DAILY FORECAST STALE'
        text(daily,940,240,11,DIM)
        text(('STALE / ' if stale else '')+age_label(epoch-sample['fetched']).upper(),1236,263,9,AMBER if stale else DIM,True)
        text('OPEN-METEO',940,263,9,DIM)
    else:
        text('WEATHER OFFLINE' if weather_failed else 'ACQUIRING WEATHER',940,160,16,DIM)
        text('RETRYING IN BACKGROUND',940,215,11,DIM)

    panel(924,307,328,247,'Seismic monitor','USGS / 24H')
    if quakes:
        text(str(len(earthquakes)),940,343,43,TEXT)
        text('M2.5+ EVENTS',1236,373,11,DIM,True)
        text(f'STRONGEST / M{strongest["mag"]:.1f}' if strongest else 'NO EVENTS REPORTED',940,405,12,AMBER)
        place=strongest['place'] if strongest else ''
        # Wrap the source location rather than silently truncating it.
        words=place.split(); lines=['']
        for word in words:
            if len(lines[-1])+len(word)+1>36:lines.append(word)
            else:lines[-1]=(lines[-1]+' '+word).strip()
        for i,row in enumerate(lines[:2]):text(row,940,435+i*18,10,DIM)
        if earthquakes:
            text('LATEST / M'+f'{earthquakes[0]["mag"]:.1f} / '+age_label(epoch-earthquakes[0]['time']),940,488,10,TEAL)
    else:
        text(stamp('quakes'),940,365,13,DIM)
    text(stamp('quakes'),940,531,9,DIM)

    panel(28,573,1224,83,'International Space Station','WHERE THE ISS AT? / 20s')
    if iss:
        period=2*math.pi*math.sqrt((6371+iss['altitude'])**3/398600.4418)/60
        for x,label,value in [
            (44,'GROUND POSITION',f'{iss["latitude"]:+.1f}° / {iss["longitude"]:+.1f}°'),
            (373,'ALTITUDE',f'{iss["altitude"]:.1f} km'),
            (641,'VELOCITY',f'{iss["velocity"]:,.0f} km/h'),
            (990,'ORBIT / CIRCULAR EST.',f'{period:.1f} min'),
        ]:
            text(label,x,608,9,DIM)
            text(value,x,627,18,LIME if x==641 else TEXT)
    else:
        text('ACQUIRING ORBITAL DATA / GRAPHICS CONTINUE OFFLINE',44,617,13,DIM)

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
            elif event.key==pygame.K_a:
                cycle.automatic=not cycle.automatic
                cycle.since=input_time
            elif event.key==pygame.K_t:
                currently_visible=manual_terminal or (not terminal_hidden and 7<=input_time-cycle.since<23)
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
    bevel(28,18,32,32,(29,69,113))
    text('N',35,20,23,TAB)
    text('Nexus',72,14,27,WHITE)
    text(NAMES[workspace]+'  /  '+('Auto rotation' if cycle.automatic else 'Manual workspace'),74,49,12,(217,235,231))
    # A compact Deskbar-inspired status tray.
    bevel(1016,14,236,56)
    bevel(1021,19,72,23,TAB)
    text('NEXUS',1030,23,11,TEXT)
    text(now.strftime('%H:%M:%S'),1238,23,12,TEXT,True)
    count=len(feeds)+len(security_data)
    circle(1030,55,3,LIME if count==7 and not errors and not security_errors else AMBER)
    text(f'{count} of 7 feeds connected',1042,47,11,DIM)
    for i in range(4):
        bevel(862+i*30,21,25,21,TAB if i==workspace else (175,196,197),i==workspace)
        text(str(i+1),870+i*30,24,10,TEXT)
    text(f'Next: {max(0,int(cycle.duration-age))}s' if cycle.automatic else 'Manual / A: auto',861,48,10,(217,235,231))

    if workspace==3:
        draw_observatory(age)
    else:
        desktop.draw(workspace,age,security_data,security_errors,epoch)
    briefing_age=7.65+(t-terminal_since) if manual_terminal else age
    if not terminal_hidden:
        desktop.terminal(workspace,briefing_age,security_data,security_errors,epoch,
                         (workspace,cycle.since,manual_terminal),forced=manual_terminal)
    facts=['1 SECURITY / 2 PHP / 3 EXPLOITED / 4 OBSERVATORY / 32s AUTO ROTATION', 'ARROWS SWITCH / A AUTO / T TERMINAL', 'ADVISORY WATCH / NO ASSET INVENTORY']
    if strongest:facts.append(f'M{strongest["mag"]:.1f} / {strongest["place"].upper()} / LAST 24H')
    if kp:facts.append(f'GEOMAGNETIC Kp {kp["value"]:.2f} / NOAA')
    if wind:facts.append(f'SOLAR WIND {wind["value"]:.0f} KM/S / {stamp("wind")}')
    php_rows=security_data.get('php',{}).get('items',[])
    if php_rows:
        facts.append('PHP / '+php_rows[0]['id']+' / '+php_rows[0]['summary'])
    ticker='    +++    '.join(facts)+'    +++    '
    clip=screen.get_clip()
    screen.set_clip(rect(36,676,940,20))
    if 10 not in fonts:fonts[10]=pygame.font.SysFont('dejavusansmono',max(10,round(10*S)))
    span=fonts[10].size(ticker)[0]/S
    offset=(t*34)%span
    text(ticker,36-offset,677,10,DIM)
    text(ticker,36-offset+span,677,10,DIM)
    screen.set_clip(clip)
    text('Space: pause  /  Esc: exit',1240,677,10,DIM,True)
    if ARGS.snapshot:
        pygame.image.save(screen,ARGS.snapshot)
        running=False
    pygame.display.flip()
    clock.tick(12)
    frame+=1
    if frame%120==0:print(f'Render: {clock.get_fps():.1f}fps',flush=True)
pygame.quit()
