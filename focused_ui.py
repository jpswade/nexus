from network_activity import Activity, ActivityPanel
"""Calm, original-style NEXUS: stable sidebars and one central subject."""
import datetime as dt
import math
from collections import OrderedDict
from pathlib import Path
import pygame
from alert_state import AlertState
from feeds import age_label
from focused_state import UK_NAMES, ChangeLog, automatic_brief, php_summary
from preparedness import LINKS, MAX_AGES as UK_AGES
from security import MAX_AGES as SEC_AGES
from uk_map import UKMap
from observatory_globe import ObservatoryGlobe
from preparedness_ui import load_doomsday_setting

BG=(7,14,20); PANEL=(10,21,29); LINE=(31,52,63)
TEXT=(229,240,241); DIM=(139,166,178); TEAL=(72,213,200)
LIME=(188,230,115); AMBER=(249,185,104)


class FocusedDesktop:
    def __init__(self, screen, location, preview=False):
        self.network_activity=Activity()
        self.network_panel=ActivityPanel()
        if not preview:self.network_activity.start()
        self.preview=preview
        self.screen=screen
        self.width,self.height=screen.get_size()
        self.scale=min(self.width/1280,self.height/720)
        self.offset=((self.width-1280*self.scale)/2,(self.height-720*self.scale)/2)
        self.target=screen
        self.static=pygame.Surface(screen.get_size()).convert()
        self.fonts={}; self.labels=OrderedDict(); self.key=None
        self.location=location
        self.map=UKMap(location)
        self.globe=ObservatoryGlobe(location)
        self.doomsday=load_doomsday_setting()
        self.visual_tick=None; self.visual=None
        self.alerts=AlertState(); self.changes=ChangeLog()
        self.links=[]; self.active_url=LINKS['weather']
        self.brief_key=None; self.brief_text=''; self.brief_started=0
        self.terminal_visible=False

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

    @staticmethod
    def status(name,data,errors,now,ages):
        sample=data.get(name)
        if not sample:return 'Connecting…' if name not in errors else 'Source unavailable'
        age=now-sample.get('fetched',0)
        return ('Stale · ' if name in errors or age>ages[name] else 'Checked ')+age_label(age)

    def register(self,box,url,primary=False):
        if url:
            self.links.append((box,url))
            if primary:self.active_url=url

    def sidebars(self,now,weather,weather_failed,security,sec_errors,uk,uk_errors,alerts,php):
        clock=dt.datetime.fromtimestamp(now)
        self.panel(28,105,284,186,'LOCAL TIME',clock.astimezone().tzname())
        self.text(clock.strftime('%H:%M'),44,146,63,TEXT,True)
        self.text(clock.strftime('%S'),292,186,17,TEAL,True,True)
        self.text(clock.strftime('%A'),44,233,17,TEAL)
        self.text(clock.strftime('%d %B %Y'),44,260,14,DIM)

        self.panel(28,309,284,194,'LOCAL WEATHER')
        if weather:
            self.text(f'{weather["temp"]:.0f}°',44,348,47,TEXT,True)
            self.text(str(self.location.get('name','Local area'))[:22],44,410,16,TEAL)
            self.wrap(self.conditions(weather.get('code')),44,438,250,16,lines=1)
            daily=(f'High {weather["high"]:.0f}°  /  Low {weather["low"]:.0f}°'
                   if weather.get('date')==clock.strftime('%Y-%m-%d') and 'high' in weather and 'low' in weather else '')
            self.text(daily,44,468,12,DIM)
            stale=weather_failed or now-weather.get('fetched',0)>1800
            self.text('Open-Meteo'+(' · stale' if stale else ''),292,324,10,AMBER if stale else DIM,right=True)
        else:self.wrap('Weather unavailable' if weather_failed else 'Loading local weather…',44,365,248,19,DIM)

        self.panel(28,521,284,121,'NATIONAL CONTEXT')
        threat=uk.get('threat')
        self.text('UK terrorism assessment',44,558,12,DIM)
        self.text(threat.get('level','Unknown') if threat else 'Unavailable',44,581,22,TEXT,True)
        self.text(self.status('threat',uk,uk_errors,now,UK_AGES),44,617,10,DIM)
        self.register((28,521,284,121),LINKS['threat'])

        self.panel(928,105,324,268,'PHP PRIORITY','ALWAYS VISIBLE')
        priority=php['priority']
        if priority:
            row=priority[0]
            severity=row.get('severity','unknown').upper()
            self.text(f'{php["critical"]} critical · published 30d',944,145,13,AMBER if php['critical'] else DIM)
            self.text(row['id'],944,176,19,TEXT,True)
            self.wrap(row.get('summary','Vendor security advisory'),944,208,290,15,lines=2)
            if row.get('score') is not None:
                self.text(f'CVSS {row.get("cvss_version") or "—"} · {row["score"]:.1f}',944,268,14,AMBER)
            self.text('Fixed versions / press 2',944,299,12,TEAL)
            self.text(self.status('php',security,sec_errors,now,SEC_AGES),944,340,11,DIM)
            self.register((928,105,324,268),row.get('url'),True)
        else:
            self.wrap('No priority advisories returned' if php['available'] else 'Loading PHP vendor advisories…',944,156,286,19,DIM)
            self.text(self.status('php',security,sec_errors,now,SEC_AGES),944,340,11,DIM)

        self.panel(928,391,324,251,'REGIONAL WARNINGS')
        local=[row for row in alerts if row['source'] in ('weather','floods')]
        if local:
            row=local[0]
            self.text(('STALE · ' if row['stale'] else '')+('Met Office' if row['source']=='weather' else 'Environment Agency'),944,431,13,AMBER)
            self.wrap(row['title'],944,461,286,18,lines=3)
            self.wrap(row['detail'].replace(' / ',' · '),944,549,286,11,DIM,lines=2)
            self.text(f'{len(local)-1} other regional bulletin'+('s' if len(local)!=2 else '') if len(local)>1 else 'Source-backed bulletin',944,610,11,DIM)
            self.register((928,391,324,251),row['url'],row['rank']>=3)
        else:
            self.wrap('No regional bulletins returned',944,438,285,19,DIM,lines=2)
            self.wrap('This is not an all-clear. Open the official sources for local coverage.',944,504,285,13,DIM,lines=3)
            for i,name in enumerate(('weather','floods')):
                self.text(self.status(name,uk,uk_errors,now,UK_AGES),944,590+i*20,11,DIM)
            self.register((928,391,324,251),LINKS['weather'])

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

    def php_detail(self,age,php,security,errors,now):
        self.panel(330,105,580,537,'PHP ADVISORY','VENDOR DETAILS')
        items=php['priority']
        notices=security.get('phpnews',{}).get('items',[])
        if notices and (not items or int(age//20)%3==2):
            notice=notices[0]
            self.text('PHP.net · official follow-up',350,157,15,TEAL)
            self.wrap(notice['title'],350,208,536,25,lines=4)
            self.wrap(' / '.join(notice.get('cves',[])),350,374,536,15,DIM,lines=3,mono=True)
            published=dt.datetime.fromtimestamp(notice['published']).strftime('%d %B %Y')
            self.text('Published '+published,350,483,14,DIM)
            self.text('Open the source for configuration-specific guidance',350,533,13,TEAL)
            self.text(self.status('phpnews',security,errors,now,SEC_AGES),350,608,11,DIM)
            self.register((330,105,580,537),notice.get('url'))
            return
        if not items:
            self.wrap('Waiting for PHP vendor advisories…',350,180,538,25,DIM)
            return
        row=items[int(age//20)%min(len(items),3)]
        self.text(row['id'],350,160,26,TEXT,True)
        score=f'{row["score"]:.1f}' if row.get('score') is not None else '—'
        self.text(row.get('severity','unknown').upper()+'  /  CVSS '+str(row.get('cvss_version') or '—')+'  '+score,350,209,15,AMBER,True)
        self.wrap(row.get('summary',''),350,254,535,23,lines=3)
        self.text('Fixed versions',350,363,14,TEAL)
        patches=row.get('patches') or ['See vendor advisory']
        for i,patch in enumerate(patches[:4]):
            self.text(patch,350+(i%2)*266,399+(i//2)*39,22,TEXT,True)
        listed=row['id'] in php['kev_ids']
        self.text('CISA KEV · known exploited' if listed else 'CISA KEV · no catalog match',350,508,14,AMBER if listed else DIM)
        self.text('Advisory watch · exposure not assessed',350,538,12,DIM)
        self.text(self.status('php',security,errors,now,SEC_AGES),350,608,11,DIM)
        self.register((330,105,580,537),row.get('url'))

    def briefing(self,uk,errors,now):
        self.panel(330,105,580,537,'PUBLIC BRIEFING','SOURCE HEADLINES')
        y=157
        for name,label in [('ncsc','NCSC · official publication'),('news','BBC · media report')]:
            sample=uk.get(name,{})
            items=sample.get('items',[])
            self.text(label,350,y,13,TEAL)
            if items:
                row=items[0]
                self.wrap(row['title'],350,y+32,536,23,lines=4)
                when=dt.datetime.fromtimestamp(row['published'],dt.timezone.utc).strftime('%d %b · %H:%M UTC') if row.get('published') else 'Publication date unavailable'
                self.text(when,350,y+170,12,DIM)
                self.text(self.status(name,uk,errors,now,UK_AGES),350,y+197,10,DIM)
                self.register((330,y-5,580,208),row.get('url'))
            else:self.wrap('No matching publications' if sample else 'Source unavailable',350,y+40,534,22,DIM)
            y+=233
        self.text('Headlines are not incident telemetry',350,612,11,DIM)

    def kev(self,security,errors,now):
        self.panel(330,105,580,537,'KNOWN EXPLOITED','CISA KEV')
        rows=security.get('kev',{}).get('items',[])
        for i,row in enumerate(rows[:4]):
            y=158+i*106
            self.text(row['id'],350,y,20,TEXT,True)
            self.wrap(row.get('vendor','')+' / '+row.get('product',''),350,y+33,535,17,lines=2)
            self.text('Added '+row.get('added','—'),350,y+78,11,DIM)
            self.register((330,y-2,580,102),row.get('url'))
        if not rows:self.wrap('Loading CISA catalog…',350,180,530,24,DIM)
        self.text(self.status('kev',security,errors,now,SEC_AGES),350,613,11,DIM)

    def draw(self,workspace,age,seconds,now,weather,weather_failed,security,sec_errors,uk,uk_errors,
             planet,planet_errors,profile='uk',automatic=True,paused=False,manual_terminal=False,
             terminal_hidden=False):
        # Compute text, layout and change detection once per second, never per frame.
        cache_key=(int(now),workspace,int(age//20),profile,automatic,paused)
        if cache_key!=self.key:
            self.key=cache_key;self.target=self.static;self.target.fill(BG)
            self.links=[]
            alerts=self.alerts.update(uk,uk_errors,now)
            self.changes.update(security,uk,alerts,now)
            php=php_summary(security,now)
            self.text('N E X U S',28,22,25,TEXT,True)
            names=UK_NAMES if profile=='uk' else ('Security overview','PHP watch','Known exploited','World view')
            self.text(names[workspace],245,32,15,DIM)
            for i in range(4):
                x=1019+i*34
                self.text(str(i+1),x,27,14,TEAL if workspace==i else DIM,True)
                if workspace==i:self.line((x-4,50),(x+15,50),TEAL,2)
            mode='Paused' if paused else f'Next view in {max(0,60-int(age))}s' if automatic else 'Manual view'
            self.text(mode,1252,32,11,DIM,right=True)
            self.line((28,70),(1252,70))
            self.sidebars(now,weather,weather_failed,security,sec_errors,uk,uk_errors,alerts,php)
            if workspace==1 or (profile=='technical' and workspace==0):self.php_detail(age,php,security,sec_errors,now)
            elif workspace==2:
                if profile=='technical':self.kev(security,sec_errors,now)
                else:self.briefing(uk,uk_errors,now)
            else:
                self.panel(330,105,580,537,'LOCAL SITUATION' if workspace==0 else 'WORLD VIEW','GEOGRAPHIC CONTEXT')
                caption='UK + Ireland · configured area' if workspace==0 else 'Earth · rotating geographic view'
                if workspace==3 and self.doomsday:
                    caption=f'Doomsday Clock: {self.doomsday["seconds_to_midnight"]}s (symbolic) · {self.doomsday["announced"]}'
                    self.register((330,599,580,25),self.doomsday['url'])
                self.text(caption,350,607,11,DIM)
                self.text('Basemap, not a hazard footprint' if workspace==0 else self.orbit_label(planet,planet_errors,now),350,628,10,DIM)
            self.line((28,662),(1252,662))
            if self.changes.events:
                event=self.changes.events[-1]
                stamp=dt.datetime.fromtimestamp(event['time']).strftime('%H:%M')
                self.text('CHANGED '+stamp,28,676,11,TEAL,True)
                self.wrap(event['title'],143,673,750,13,DIM,lines=1)
                self.register((28,665,870,34),event.get('url'))
            else:self.text('Watching for source changes · routine refreshes stay quiet',28,676,12,DIM)
            self.text('1–4 views  A auto  T brief  O source  F5 home  F6 mode',1252,676,11,DIM,right=True)
        self.target=self.screen;self.target.blit(self.static,(0,0))
        if workspace in (0,3) and not(profile=='technical' and workspace==0):
            tick=int(seconds*3)
            key=(workspace,tick)
            if self.visual_tick!=key:
                image=self.map.draw(seconds*.35) if workspace==0 else self.globe.draw(seconds*.65)
                if workspace==0:
                    # The focused card supplies one caption; omit the legacy in-image footer.
                    image=image.subsurface((0,0,image.get_width(),440))
                logical=(480,442) if workspace==0 else (548,407)
                # Uniform scaling preserves geography; no per-frame image resize.
                factor=min(logical[0]/image.get_width(),logical[1]/image.get_height())
                size=(round(image.get_width()*factor*self.scale),round(image.get_height()*factor*self.scale))
                self.visual=pygame.transform.smoothscale(image,size)
                self.visual_tick=key
            x=(330+290-self.visual.get_width()/self.scale/2)
            y=155 if workspace==0 else 172
            self.target.blit(self.visual,self.point(x,y))
        if workspace==0 and profile=='uk' and int(seconds/16)%2:
            state=self.network_activity.snapshot()
            self.panel(330,105,580,537,'NETWORK OBSERVATORY','LIVE / LOCAL')
            panel=self.network_panel.draw(state,(560,370))
            panel=pygame.transform.smoothscale(panel,(round(560*self.scale),round(370*self.scale)))
            self.target.blit(panel,self.point(340,155))
            dns=state.get('dns')
            self.text('DNS: '+('RESOLVING' if dns is True else 'CHECK FAILED' if dns is False else 'CHECKING'),350,562,16,TEAL if dns else DIM)
            self.text('Traffic is this Pi only / no device tracking',350,602,13,DIM)
            self.text('Wi-Fi strength is not a person or movement detector',350,627,12,DIM)
        show=manual_terminal or (not terminal_hidden and automatic_brief(workspace,age,self.changes,now))
        fresh=show and not self.terminal_visible
        self.terminal_visible=show
        if show:self.terminal(now,security,sec_errors,workspace,age,manual_terminal,fresh)

    @staticmethod
    def orbit_label(planet,errors,now):
        iss=planet.get('iss')
        if not iss:return 'ISS source connecting…'
        age=now-iss.get('observed',0)
        state='stale · ' if 'iss' in errors or age>120 else ''
        return f'ISS {state}{iss["altitude"]:.0f} km · {iss["velocity"]:,.0f} km/h · {age_label(age)}'

    def terminal(self,now,security,errors,workspace,age,manual,fresh=False):
        key=(workspace,manual,self.changes.events[-1]['time'] if self.changes.events else None)
        if fresh or key!=self.brief_key:
            self.brief_key=key;self.brief_started=now
            php=php_summary(security,now)
            row=php['priority'][0] if php['priority'] else None
            lines=['  .--------.   NEXUS / ADVISORY BRIEF',
                   '  | [ == ] |   ----------------------',
                   '  | [____] |   Public sources / read-only',
                   '  `--------\'','']
            if row:
                lines += [row['id']+' / '+row.get('severity','unknown').upper(),
                          'Fixed: '+' / '.join(row.get('patches') or ['See vendor']),
                          self.status('php',security,errors,now,SEC_AGES)]
            else:lines+=['PHP source is connecting.','No exposure conclusion available.']
            lines+=['','T to dismiss / sidebars remain visible']
            self.brief_text='\n'.join(lines)
        box=self.box(342,257,556,264)
        pygame.draw.rect(self.target,(5,15,22),box)
        pygame.draw.rect(self.target,TEAL,box,max(1,round(self.scale)))
        reveal=int(max(0,age-44 if self.preview else now-self.brief_started)*100)
        for i,row in enumerate(self.brief_text[:reveal].split('\n')):
            self.text(row,355,271+i*22,12,LIME,True)
