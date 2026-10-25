import os
import argparse

arguments = argparse.ArgumentParser(description="Nexus desktop dashboard")
arguments.add_argument('--profile', choices=('uk', 'technical'), default=os.environ.get('NEXUS_PROFILE', 'uk'))
arguments.add_argument('--snapshot', help='Render one cached-data frame to a PNG without opening the monitor')
arguments.add_argument('--workspace', type=int, choices=range(1,5), default=1)
arguments.add_argument('--age', type=float, default=0, help='Workspace animation age for snapshots')
ARGS = arguments.parse_args()
os.environ['NEXUS_PROFILE'] = ARGS.profile
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

from feeds import PlanetFeeds
from security import SecurityFeeds
from preparedness import PreparednessFeeds
from workspaces import WorkspaceCycle
from focused_state import UK_NAMES
from focused_ui import FocusedDesktop
from terminal_theme import switch_view

# Critical sources stay fresh regardless of which workspace/profile is visible.
planet = PlanetFeeds(CACHE_DIR)
security = SecurityFeeds(CACHE_DIR / 'security')
preparedness = PreparednessFeeds(CACHE_DIR / 'preparedness', LOCATION)
if not ARGS.snapshot:
    for source in (planet, security, preparedness):
        source.start()

os.environ.setdefault('SDL_RENDER_DRIVER', 'opengles2')
pygame.display.init()
pygame.font.init()
if ARGS.snapshot:
    screen = pygame.display.set_mode((1280,720))
else:
    try:
        screen = pygame.display.set_mode((1280,720),pygame.FULLSCREEN | pygame.SCALED,vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode((0,0),pygame.FULLSCREEN)
pygame.display.set_caption('NEXUS / Focused observatory')
pygame.mouse.set_visible(True)
ui = FocusedDesktop(screen,LOCATION,preview=bool(ARGS.snapshot))
cycle = WorkspaceCycle(duration=60,initial=ARGS.workspace-1)
if ARGS.snapshot:cycle.automatic=False
names = UK_NAMES if ARGS.profile=='uk' else ('Security overview','PHP watch','Known exploited','World view')
manual_terminal=False
terminal_hidden=False
last_workspace=None
paused=False
running=True
start=time.monotonic()
frozen=0.
last_pause=0.
clock=pygame.time.Clock()
frame=0


def stop(*_):
    global running
    running=False


def open_source(url):
    if not url:return
    import webbrowser
    threading.Thread(target=webbrowser.open,args=(url,),daemon=True).start()


signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
print(f'NEXUS focused desktop ready: {screen.get_size()}, target=12fps',flush=True)
while running:
    input_time=(last_pause if paused else time.monotonic())-start-frozen
    if ARGS.snapshot:input_time=ARGS.age
    for event in pygame.event.get():
        if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
            running=False
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            x=(event.pos[0]-ui.offset[0])/ui.scale
            y=(event.pos[1]-ui.offset[1])/ui.scale
            if 1010<=x<1150 and 20<=y<=57:
                cycle.select(min(3,max(0,int((x-1010)//34))),input_time)
                manual_terminal=False;terminal_hidden=False
            else:open_source(ui.clicked_url((x,y)))
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
                currently_visible=ui.terminal_visible
                manual_terminal=not currently_visible
                terminal_hidden=currently_visible
            elif event.key==pygame.K_o:
                open_source(ui.active_url)
            elif event.key==pygame.K_F5:
                pygame.quit();switch_view('home')
            elif event.key==pygame.K_F6:
                os.environ['NEXUS_PROFILE']='technical' if ARGS.profile=='uk' else 'uk'
                pygame.quit();switch_view('nexus')
    seconds=(last_pause if paused else time.monotonic())-start-frozen
    if ARGS.snapshot:seconds=ARGS.age
    workspace,age=cycle.tick(seconds)
    if workspace!=last_workspace:
        manual_terminal=False;terminal_hidden=False
        last_workspace=workspace
        print(f'Workspace {workspace+1}: {names[workspace]}',flush=True)
    planet_data,planet_errors=planet.snapshot()
    security_data,security_errors=security.snapshot()
    uk_data,uk_errors=preparedness.snapshot()
    ui.draw(workspace,age,seconds,time.time(),weather,weather_failed,
            security_data,security_errors,uk_data,uk_errors,planet_data,planet_errors,
            profile=ARGS.profile,automatic=cycle.automatic,paused=paused,
            manual_terminal=manual_terminal,terminal_hidden=terminal_hidden)
    if ARGS.snapshot:
        pygame.image.save(screen,ARGS.snapshot)
        running=False
    pygame.display.flip()
    clock.tick(12)
    frame+=1
    if frame%120==0:print(f'Render: {clock.get_fps():.1f}fps',flush=True)
pygame.quit()
