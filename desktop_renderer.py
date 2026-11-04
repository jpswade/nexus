"""Two-column HDMI presentation of #46 cards; selection belongs to briefing_policy.

No feed fetching, risk inference or replacement rotation lives here. The optional
policy argument is dependency injection for synthetic, offline contract previews.
"""
import datetime as dt
import importlib
import math
import pygame
from camera_eye import draw as draw_camera_eye
from status_summary import live_checks
from terrorism import threat_details
from live_telemetry import Telemetry

BG=(7,14,20); TEXT=(229,240,241); DIM=(139,166,178)
TEAL=(72,213,200); LIME=(188,230,115); AMBER=(249,185,104)
GROUPS=('situation','cyber','infrastructure','node','observatory')
NAMES=('Situation','Cyber','Infrastructure','Local node','Observatory')


def stamp(value):
    return 'unknown' if value is None else dt.datetime.fromtimestamp(value,dt.timezone.utc).strftime('%d %b %Y %H:%M UTC')


def rows_for(font, value, width):
    """Wrap every character, including unbroken advisory identifiers and URLs."""
    result=[]
    for paragraph in str(value).split('\n'):
        row=''
        for word in paragraph.split():
            candidate=(row+' '+word).strip()
            if font.size(candidate)[0]<=width:
                row=candidate
                continue
            if row:result.append(row);row=''
            for char in word:
                if row and font.size(row+char)[0]>width:
                    result.append(row);row=''
                row+=char
        result.append(row)
    return result


class DesktopRenderer:
    def __init__(self, ui, policy=None):
        self.ui=ui
        if policy is None:
            try:policy=importlib.import_module('briefing_policy')
            except ModuleNotFoundError as error:
                if error.name!='briefing_policy':raise
        self.policy=policy
        self.priority=policy.Rotation() if policy else None
        self.stream=policy.Rotation() if policy else None
        self.selected=(None,None)
        self.detail=None;self.page=0;self.page_count=1
        self.detail_buttons=[]
        self.tick=None;self.context={};self.telemetry=Telemetry()
        self.ping_history=[]

    def click(self, point):
        x,y=point
        if self.detail:
            if 1000<=x<=1236 and 176<=y<=211:
                self.detail=None;self.ui.key=None;return True
            if 48<=x<=380 and 598<=y<=630:
                self.scroll(-1);return True
            if 390<=x<=730 and 598<=y<=630:
                self.scroll(1);return True
            # Modal blocks underlying card/source actions.
            return not (48<=x<=1230 and 553<=y<=590)
        for rect,card in self.detail_buttons:
            if pygame.Rect(rect).collidepoint(point):
                self.detail=dict(card);self.page=0;self.ui.key=None;return True
        return False

    def scroll(self, delta):
        self.page=max(0,min(self.page_count-1,self.page+delta))
        self.ui.key=None

    def lines(self,value,x,y,width,size=16,color=TEXT,limit=None):
        ui=self.ui
        rows=rows_for(ui.font(size),value,width*ui.scale)
        for i,row in enumerate(rows if limit is None else rows[:limit]):
            ui.text(row,x,y+i*(size+6),size,color)
        return rows

    def card(self, card, rect, label):
        ui=self.ui;x,y,w,h=rect
        ui.panel(x,y,w,h,label)
        if card is None:
            self.lines('No briefing selected',x+18,y+59,w-36,23,DIM)
            self.lines('Source coverage remains in the live checks above. No returned items is not an all-clear.',x+18,y+118,w-36,17,DIM)
            return
        # Labels are supplied by policy, not inferred from colour or feed health.
        state=card['state'].upper(); severity=card['severity'].upper()
        ui.text(state+' / '+severity,x+18,y+42,13,AMBER if state=='STALE' else TEAL,True)
        self.lines(card['title'],x+18,y+70,w-36,24,TEXT,3)
        body='\n'.join(card['body'])
        self.lines(body,x+18,y+170,w-36,18,TEXT,5)
        self.lines(card['source'],x+18,y+h-120,w-36,14,TEAL,1)
        ui.text('Published '+stamp(card['published']),x+18,y+h-98,12,DIM)
        ui.text('Checked '+stamp(card['checked']),x+18,y+h-78,12,DIM)
        ui.text('Valid until '+stamp(card['valid_until']),x+18,y+h-58,12,DIM)
        ui.text('DETAILS / FULL TEXT',x+18,y+h-36,13,LIME)
        ui.text(f"Dwell {card['duration']:g}s",x+w-18,y+h-36,12,DIM,right=True)
        self.detail_buttons.append(((x+8,y+h-48,w-16,42),card))
        ui.register((x+8,y+65,w-16,h-120),card['url'],ui.active_url is None)

    def local(self,weather,failed,now):
        ui=self.ui
        ui.panel(28,166,690,472,'LOCAL CONDITIONS / OPEN-METEO')
        self.lines(ui.location.get('name','Configured area'),48,220,646,28,TEAL,2)
        if weather:
            ui.text(f"{weather['temp']:.0f}°",48,310,64,TEXT,True)
            ui.text(ui.conditions(weather.get('code')),48,403,24,TEXT)
            checked=weather.get('fetched')
            stale=failed or checked is None or not 0<=now-checked<=1800
            ui.text('STALE' if stale else 'CURRENT',48,457,16,AMBER if stale else TEAL)
            ui.text('Checked '+stamp(checked),48,497,15,DIM)
            ui.text('High '+str(weather.get('high','--'))+'° / Low '+str(weather.get('low','--'))+'°',48,535,20,TEAL)
            # Small procedural weather icon; source conditions determine its form.
            cx,cy=ui.point(595,345);r=max(8,round(35*ui.scale))
            code=weather.get('code')
            if code in (0,1,2):
                pygame.draw.circle(ui.target,LIME,(cx,cy),r,2)
                for i in range(8):
                    a=i*math.pi/4+now*.015
                    pygame.draw.line(ui.target,LIME,(cx+math.cos(a)*r*1.3,cy+math.sin(a)*r*1.3),(cx+math.cos(a)*r*1.6,cy+math.sin(a)*r*1.6),2)
            if code not in (0,1):
                for dx,dy,rr in [(-28,5,24),(0,-10,32),(29,7,23)]:
                    pygame.draw.circle(ui.target,TEAL,(cx+round(dx*ui.scale),cy+round(dy*ui.scale)),round(rr*ui.scale),2)

        else:
            self.lines('Local weather unavailable',48,320,640,28,DIM)
            self.lines('No successful check; conditions unknown.',48,397,640,18,DIM)
        ui.text('Forecast conditions are not an official warning.',48,591,16,DIM)

    def details(self):
        ui=self.ui;card=self.detail
        ui.panel(28,166,1224,472,'CARD DETAILS / CACHED EVIDENCE','CLOSE ×')
        content=[card['title'],card['state'].upper()+' / '+card['severity'].upper(),
                 *card['body'],'Source: '+card['source'],
                 'Published: '+stamp(card['published']),'Checked: '+stamp(card['checked']),
                 'Valid until: '+stamp(card['valid_until']),'URL: '+(card['url'] or 'unavailable')]
        rows=[]
        for value in content:rows.extend(rows_for(ui.font(18),value,1180*ui.scale))
        self.page_count=max(1,(len(rows)+12)//13)
        self.page=min(self.page,self.page_count-1)
        for i,row in enumerate(rows[self.page*13:(self.page+1)*13]):ui.text(row,48,220+i*24,18,TEXT)
        ui.text('OPEN ORIGINAL SOURCE →' if card['url'] else 'SOURCE LINK UNAVAILABLE',48,566,14,TEAL)
        ui.links=[]
        ui.register((48,553,1180,37),card['url'],True)
        ui.text('← PREVIOUS',48,606,14,LIME)
        ui.text('NEXT →',400,606,14,LIME)
        ui.text(f'Page {self.page+1}/{self.page_count} · PgUp/PgDn or wheel',1230,606,13,DIM,right=True)

    def network(self,state):
        ui=self.ui;connection=state.get('connection',{})
        latency=connection.get('latency')
        signal=state.get('signal')
        label=connection.get('label','CHECKING')
        ui.line((28,649),(1252,649))
        ui.text('PI LINK / '+label,28,658,13,TEAL,True)
        ui.text('Ping '+('--' if latency is None else f'{latency:.0f}')+'/'+str(round(connection['maximum']) if connection.get('maximum') is not None else '--')+' ms',320,658,13,DIM)
        ui.text('Wi-Fi '+('--' if signal is None else f'{signal:.0f} dBm'),500,658,13,DIM)
        ui.text('DNS '+('OK' if state.get('dns') is True else 'FAILED' if state.get('dns') is False else 'UNKNOWN'),700,658,13,DIM)
        for values,x,color,ceiling,floor in ((self.ping_history,880,LIME,200,0),
                ([r[0] for r in state.get('history',[])][-60:],1070,TEAL,90,-100)):
            previous=None
            for i,value in enumerate(values):
                if value is None:previous=None;continue
                point=(x+i*2.8,678-max(0,min(1,(value-floor)/ceiling))*24)
                if previous:ui.line(previous,point,color)
                previous=point

    def draw(self,workspace,seconds,now,weather,weather_failed,security,sec_errors,uk,uk_errors,planet,planet_errors,automatic,paused):
        ui=self.ui
        # Rebuild cached snapshots and cards at 1 Hz. No networking in render calls.
        if int(now)!=self.tick:
            self.tick=int(now)
            network=ui.network_activity.snapshot()
            self.telemetry.sample()
            self.ping_history=(self.ping_history+[network.get('connection',{}).get('latency')])[-60:]
            self.context=dict(uk=uk,security=security,weather=weather,emergency=ui.emergency_data,
                radar=ui.radar.snapshot(now,offline=network.get('connection',{}).get('offline',False)),
                space=ui.space_weather.snapshot(now),network=network,motion=ui.motion.snapshot(now),
                source_records=ui.source_records,planet=planet,location=ui.location,
                telemetry=dict(cpu=self.telemetry.cpu,memory=self.telemetry.memory,temperature=self.telemetry.temperature,checked=now,signal=network.get('signal'),traffic=network.get('history',[])[-1:] ),
                uk_errors=uk_errors,sec_errors=sec_errors,planet_errors=planet_errors,weather_failed=weather_failed)
            self.cards=self.policy.build_cards(self.context,now) if self.policy else []
        selection_now=now
        visible=[c for c in self.cards if c['group']!='observatory']
        pinned=[c for c in visible if c['pinned'] and c['duration']>0]
        primary=self.priority.select(pinned,selection_now) if self.policy else None
        group=None if automatic else GROUPS[workspace]
        remaining=[c for c in (visible if automatic else self.cards) if primary is None or c['id']!=primary['id']]
        briefing=self.stream.select(remaining,selection_now,group=group) if self.policy else None
        self.selected=(primary,briefing)
        key=(int(now),workspace,automatic,paused,str(self.selected),self.page, bool(self.detail),ui.source_detail)
        if key!=ui.key:
            ui.key=key;ui.target=ui.static;ui.target.fill(BG);ui.links=[];ui.active_url=None;self.detail_buttons=[]
            ui.text('N E X U S',28,22,25,TEXT,True)
            ui.text(dt.datetime.fromtimestamp(now).strftime('%H:%M:%S'),28,55,18,LIME,True)
            # Summary may count source rows, but does not choose priority content.
            from alert_state import AlertState
            alerts=AlertState().update(uk,uk_errors,now)
            for i,(label,value,state) in enumerate(live_checks(uk,ui.emergency_data,now,uk_errors,alerts)):
                x=245+i*251
                ui.text(label,x,16,12,DIM,True)
                ui.text(value,x,39,19,AMBER if state in ('alert','stale') else TEAL if state=='ok' else DIM,True)
            threat=uk.get('threat');source,checked=threat_details(threat,now,'threat' in uk_errors)
            assessment='SOURCES DIFFER' if threat and threat.get('disagreement') else (threat or {}).get('level','UNKNOWN')
            ui.text('UK TERRORISM / '+assessment,28,91,17,TEXT,True)
            ui.text(source,530,89,13,TEAL)
            ui.text(checked,530,110,12,DIM)
            ui.register((28,84,1224,45),(threat or {}).get('url','https://www.gov.uk/terrorism-national-emergency'))
            ui.text(('AUTO BRIEFING' if automatic else NAMES[workspace].upper())+(' / PAUSED' if paused else ''),28,137,12,LIME,True)
            ui.text('1 Situation   2 Cyber   3 Infrastructure   4 Node   5 Observatory (manual)',1252,137,12,DIM,right=True)
            if primary:self.card(primary,(28,166,690,472),'PRIORITY / SOURCE WARNING')
            else:self.local(weather,weather_failed,now)
            self.card(briefing,(736,166,516,472),'BRIEFING / '+('AUTO' if automatic else NAMES[workspace].upper()))
            if not self.policy:
                ui.panel(736,166,516,472,'BRIEFING / DEPENDENCY UNAVAILABLE')
                self.lines('Shared briefing policy is not installed.',756,235,476,25,AMBER)
                self.lines('Priority selection unavailable. Integrate issue #47 before rollout. Live source checks remain above.',756,350,476,19,DIM)
            if self.detail:self.details()
            if ui.source_detail:ui.source_panel(uk,now)
            self.network(self.context['network'])
            ui.text('A auto/manual   O source   Click details / PgUp PgDn   F5 home   F6 profile',28,696,12,DIM)
        ui.target=ui.screen;ui.target.blit(ui.static,(0,0))
        connection=self.context['network'].get('connection',{})
        if connection.get('offline') and 0 <= now-connection.get('checked',0) <= 35:
            ui.target.fill(BG)
            tone=(255,100,100) if int(seconds*2)%2==0 else (139,48,56)
            ui.text('OFFLINE',640,265,90,tone,True,right=True)
            ui.text('Repeated probe failures / retrying',340,390,24,DIM)
            self.network(self.context['network'])
            return
        draw_camera_eye(ui.target,self.context['motion'],now,ui.point(208,35),max(6,round(12*ui.scale)))
