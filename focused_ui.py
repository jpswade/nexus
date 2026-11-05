"""HDMI shell: cached feeds and drawing primitives for the policy-driven renderer."""
import datetime as dt
from collections import OrderedDict
import pygame
from source_details import HEADERS, describe
from camera_motion import MotionReader
from space_weather import SpaceWeather
from network_activity import Activity
from radar_outages import RadarFeed
from preparedness import LINKS
from desktop_renderer import DesktopRenderer

BG=(7,14,20); PANEL=(10,21,29); LINE=(31,52,63)
TEXT=(229,240,241); DIM=(139,166,178); TEAL=(72,213,200)
LIME=(188,230,115); AMBER=(249,185,104)


class FocusedDesktop:
    def __init__(self, screen, location, preview=False, policy=None):
        self.network_activity=Activity()
        self.space_weather=SpaceWeather()
        self.radar=RadarFeed()
        if not preview:
            self.network_activity.start()
            self.space_weather.start()
            self.radar.start()
        self.motion=MotionReader()
        self.screen=screen
        self.width,self.height=screen.get_size()
        self.scale=min(self.width/1280,self.height/720)
        self.offset=((self.width-1280*self.scale)/2,(self.height-720*self.scale)/2)
        self.target=screen
        self.static=pygame.Surface(screen.get_size()).convert()
        self.fonts={}; self.labels=OrderedDict(); self.key=None
        self.location=location
        self.links=[]; self.active_url=None
        self.source_detail=None; self.source_records={}; self.emergency_data={}
        self.terminal_visible=False
        self.renderer=DesktopRenderer(self, policy)

    def point(self,x,y):
        return round(self.offset[0]+x*self.scale),round(self.offset[1]+y*self.scale)

    def box(self,x,y,w,h):
        return pygame.Rect(*self.point(x,y),round(w*self.scale),round(h*self.scale))

    def line(self,a,b,color=LINE,width=1):
        pygame.draw.line(self.target,color,self.point(*a),self.point(*b),max(1,round(width*self.scale)))

    def font(self,size,mono=False):
        key=(size,mono)
        if key not in self.fonts:
            self.fonts[key]=pygame.font.SysFont('dejavusansmono' if mono else 'dejavusans',max(9,round(size*self.scale)))
        return self.fonts[key]

    def text(self,value,x,y,size=14,color=TEXT,mono=False,right=False):
        value=str(value);key=(value,size,color,mono)
        if key not in self.labels:
            self.labels[key]=self.font(size,mono).render(value,True,color)
            if len(self.labels)>600:self.labels.popitem(last=False)
        image=self.labels[key];xx,yy=self.point(x,y)
        self.target.blit(image,(xx-image.get_width() if right else xx,yy))

    def wrap(self,value,x,y,width,size=16,color=TEXT,lines=3,mono=False):
        words=str(value).split(); rows=[]; row=''
        for word in words:
            candidate=(row+' '+word).strip()
            if row and self.font(size,mono).size(candidate)[0]>width*self.scale:
                rows.append(row);row=word
            else:row=candidate
        if row:rows.append(row)
        if len(rows)>lines:
            rows=rows[:lines]
            while rows[-1] and self.font(size,mono).size(rows[-1]+'…')[0]>width*self.scale:
                rows[-1]=rows[-1][:-1]
            rows[-1]+='…'
        for i,row in enumerate(rows):self.text(row,x,y+i*(size+7),size,color,mono)
        return len(rows)*(size+7)

    def panel(self,x,y,w,h,title,tag=''):
        pygame.draw.rect(self.target,PANEL,self.box(x,y,w,h))
        pygame.draw.rect(self.target,LINE,self.box(x,y,w,h),max(1,round(self.scale)))
        self.line((x,y),(x+25,y),TEAL,2)
        self.text(title,x+16,y+13,12,DIM,True)
        if tag:self.text(tag,x+w-16,y+13,11,TEAL,True,True)

    def clicked_url(self,point):
        x,y=point
        for (rx,ry,w,h),url in reversed(self.links):
            if rx<=x<=rx+w and ry<=y<=ry+h:return url
        return None

    def click_detail(self, point):
        x,y=point
        for rect,source in getattr(self.renderer,'status_hits',[]):
            if source in HEADERS and pygame.Rect(rect).collidepoint(point):
                self.source_detail=None if self.source_detail==source else source
                self.key=None
                return True
        if self.source_detail and 810<=x<=900 and 110<=y<=145:
            self.source_detail=None
            self.key=None
            return True
        return self.renderer.click(point)

    def source_panel(self, uk, now):
        name,url,caveat,state,attempted,successful,events=describe(
            self.source_detail,self.source_records,uk,self.emergency_data,now)
        self.links=[entry for entry in self.links if not (330<=entry[0][0]<910)]
        self.panel(330,105,580,537,'SOURCE DETAILS','CLOSE ×')
        self.text(name,350,157,22,TEAL)
        self.text(state+' / FEED HEALTH',350,194,16,AMBER if state!='CHECKED' else TEAL)
        self.text(attempted,350,232,15,DIM)
        self.text(successful,350,261,15,DIM)
        self.wrap(caveat,350,304,530,16,DIM,lines=2)
        self.text('RECENT CHECKS / UTC',350,373,12,TEAL)
        for i,event in enumerate(reversed(events[-6:])):
            stamp=dt.datetime.fromtimestamp(event['time'],dt.timezone.utc).strftime('%d %b %H:%M')
            self.text(stamp+'  '+event['kind'].upper(),350,402+i*26,14,TEXT,True)
        if not events:self.text('No local history recorded yet',350,402,15,DIM)
        self.text('Feed failure does not mean the Pi is offline',350,570,12,DIM)
        self.text('OPEN OFFICIAL SOURCE →',350,609,14,TEAL)
        self.register((350,599,530,35),url,True)

    def register(self,box,url,primary=False):
        if url:
            self.links.append((box,url))
            if primary:self.active_url=url

    @staticmethod
    def conditions(code):
        if code==0:return 'Clear sky'
        if code==1:return 'Mostly clear'
        if code==2:return 'Partly cloudy'
        if code==3:return 'Overcast'
        if code in (45,48):return 'Fog'
        if code in (51,53,55):return 'Drizzle'
        if code in (56,57,66,67):return 'Freezing rain'
        if code in (61,63,65):return 'Rain'
        if code in (71,73,75,77):return 'Snow'
        if code in (80,81,82):return 'Rain showers'
        if code in (85,86):return 'Snow showers'
        if code in (95,96,99):return 'Thunderstorms'
        return 'Conditions unavailable'


    def draw(self,workspace,age,seconds,now,weather,weather_failed,security,sec_errors,uk,uk_errors,
             planet,planet_errors,profile='uk',automatic=True,paused=False,manual_terminal=False,
             terminal_hidden=False):
        self.renderer.draw(workspace, seconds, now, weather, weather_failed, security,
                           sec_errors, uk, uk_errors, planet, planet_errors, automatic, paused)

    def scroll_detail(self, delta):
        self.renderer.scroll(delta)
