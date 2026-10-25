"""BeOS-styled security workspaces and an animated, read-only ASCII briefing."""
import datetime
import textwrap
from feeds import age_label
from security import MAX_AGES, php_priority
from workspaces import window_progress, terminal_progress


class SecurityDesktop:
    def __init__(self, ui):
        self.u = ui
        self.session = None
        self.briefing = ''

    def opening(self, box, title, tag, age, delay=0):
        x,y,w,h=box
        p=window_progress(age, delay)
        if p<=0: return False
        if p<1:
            p=1-(1-p)**3
            ww,hh=max(24,w*p),max(16,h*p)
            self.u.bevel(x+(w-ww)/2,y+(h-hh)/2,ww,hh)
            return False
        self.u.panel(x,y,w,h,title,tag)
        return True

    def wrap(self, value, x, y, width=75, size=12, color=None, lines=3):
        for i,row in enumerate(textwrap.wrap(str(value),width)[:lines]):
            self.u.text(row,x,y+i*(size+6),size,color or self.u.TEXT)

    def freshness(self,name,data,errors,now):
        sample=data.get(name)
        if not sample:return 'UNAVAILABLE / RETRYING' if name in errors else 'CONNECTING...'
        age=now-sample['fetched']
        return ('STALE / ' if name in errors or age>MAX_AGES[name] else 'CHECKED / ')+age_label(age).upper()

    def draw(self,index,age,data,errors,now):
        u=self.u; text=u.text
        php=data.get('php',{}).get('items',[])
        kev=data.get('kev',{}).get('items',[])
        ids={row['id'] for row in kev}
        priority=php_priority(php,ids,now)
        fresh=[row for row in php if now-row['published']<30*86400]
        critical=[row for row in fresh if row['severity']=='critical']
        newkev=[row for row in kev if now-datetime.datetime.fromisoformat(row['added']).replace(tzinfo=datetime.timezone.utc).timestamp()<7*86400]
        notices=data.get('phpnews',{}).get('items',[])
        if index==0:
            if self.opening((28,105,1224,88),'Security pulse','PUBLIC ADVISORY INTELLIGENCE',age):
                for x,value,label in [(45,len(critical) if 'php' in data else '--','Critical PHP / published 30d'),
                                      (365,len(fresh) if 'php' in data else '--','PHP advisories / published 30d'),
                                      (690,len(newkev) if 'kev' in data else '--','CISA KEV / added 7d'),
                                      (1015,len(kev) if 'kev' in data else '--','Known exploited / catalog')]:
                    text(value,x,139,26,u.AMBER if x==45 else u.TEAL)
                    text(label,x,174,10,u.DIM)
            if self.opening((28,229,752,319),'PHP priority watch','PHP / PHP-SRC',age,.25):
                for i,row in enumerate(priority[:3]):
                    y=271+i*86
                    text(row['id'],44,y,16,u.TEXT)
                    score=f'CVSS {row["cvss_version"]} / {row["score"]:.1f}' if row['score'] is not None else row['severity'].upper()
                    text(score,760,y,12,u.AMBER,True)
                    self.wrap(row['summary'],44,y+25,88,12,lines=1)
                    patches=' / '.join(row['patches']) or 'See vendor advisory'
                    text('Fixed: '+patches,44,y+49,11,u.TEAL)
                    u.line((44,y+73),(760,y+73),(182,184,180))
                if not priority:text(self.freshness('php',data,errors,now),44,280,14,u.DIM)
            if self.opening((798,229,454,319),'Exploited in the wild','CISA KEV',age,.5):
                for i,row in enumerate(kev[:3]):
                    y=273+i*85
                    text(row['id'],814,y,15,u.AMBER)
                    self.wrap(row['vendor']+' / '+row['product'],814,y+25,51,12,lines=2)
                    text('Added '+row['added'],814,y+63,10,u.DIM)
            if self.opening((28,587,1224,69),'Source status','PASSIVE WATCH / NO ASSET INVENTORY',age,.7):
                for x,name,label in [(44,'php','PHP'),(430,'kev','CISA KEV'),(840,'phpnews','PHP.NET')]:
                    text(label+' / '+self.freshness(name,data,errors,now),x,626,10,u.DIM)
        elif index==1:
            selected=priority[int(age/10)%len(priority)] if priority else None
            if self.opening((28,105,357,551),'PHP advisory index','CORE RUNTIME',age):
                for i,row in enumerate(priority[:7]):
                    y=148+i*66
                    if selected and row['id']==selected['id']:
                        u.bevel(38,y-5,337,58,(255,236,155),True)
                    text(row['id'],46,y,13,u.TEXT)
                    text(row['severity'].upper(),46,y+23,10,u.AMBER)
                    text(datetime.datetime.fromtimestamp(row['published']).strftime('%d %b'),366,y+23,10,u.DIM,True)
                text(self.freshness('php',data,errors,now),44,631,9,u.DIM)
            if self.opening((406,105,846,271),'Advisory inspector','VENDOR DETAILS',age,.25):
                if selected:
                    text(selected['id'],424,146,25,u.TEXT)
                    score=f'{selected["score"]:.1f} / CVSS {selected["cvss_version"]}' if selected['score'] is not None else 'CVSS not supplied'
                    text(score,1230,151,17,u.AMBER,True)
                    self.wrap(selected['summary'],424,195,96,15,lines=2)
                    text('Vendor severity: '+selected['severity'].upper(),424,252,12,u.AMBER)
                    text('Fixed versions: '+(' / '.join(selected['patches']) or 'See vendor advisory'),424,279,12,u.TEAL)
                    status='CISA KEV: listed / known exploited' if selected['id'] in ids else 'CISA catalog match: none' if 'kev' in data else 'CISA KEV: status unavailable'
                    text(status,424,306,12,u.DIM if selected['id'] not in ids else u.AMBER)
                    text(selected['ghsa']+' / github.com/php/php-src',424,346,10,u.DIM)
                else:text('Waiting for the PHP advisory feed...',424,163,16,u.DIM)
            if self.opening((406,410,846,246),'PHP security announcements','PHP.NET / FOLLOW-UP GUIDANCE',age,.5):
                for i,item in enumerate(notices[:3]):
                    y=452+i*59
                    text(datetime.datetime.fromtimestamp(item['published']).strftime('%d %b'),424,y,11,u.TEAL)
                    self.wrap(item['title'],486,y,93,12,lines=2)
                    text(' / '.join(item['cves'])[:108],486,y+35,10,u.DIM)
                text(self.freshness('phpnews',data,errors,now),424,635,9,u.DIM)
        elif index==2:
            if self.opening((28,105,810,451),'Known exploited vulnerabilities','CISA / RECENT CATALOG ADDITIONS',age):
                text('CVE',44,148,10,u.DIM);text('Vendor / product',275,148,10,u.DIM);text('Added',819,148,10,u.DIM,True)
                for i,row in enumerate(kev[:6]):
                    y=183+i*58
                    text(row['id'],44,y,14,u.AMBER)
                    self.wrap(row['vendor']+' / '+row['product'],275,y,58,12,lines=2)
                    text(row['added'],819,y,10,u.DIM,True)
                    u.line((44,y+45),(819,y+45),(179,182,179))
                text(self.freshness('kev',data,errors,now),44,532,9,u.DIM)
            if self.opening((860,105,392,211),'Catalog pulse','KNOWN EXPLOITATION',age,.25):
                text(len(newkev) if 'kev' in data else '--',878,148,38,u.AMBER)
                text('Added in the last 7 days',878,198,12,u.DIM)
                ransomware=sum(row['ransomware']=='Known' for row in newkev)
                text(f'{ransomware} with known ransomware use',878,231,12,u.TEXT)
                text('This is catalog activity, not attack volume.',878,278,10,u.DIM)
            if self.opening((860,352,392,204),'PHP in the KEV catalog','ALL CATALOG YEARS',age,.5):
                matches=[r for r in kev if 'php' in (r['vendor']+' '+r['product']).lower()]
                text(len(matches) if 'kev' in data else '--',878,390,33,u.TEAL)
                text('PHP / PHP ecosystem entries',878,438,12,u.DIM)
                for i,row in enumerate(matches[:3]):text(row['id']+' / '+row['product'][:18],878,468+i*22,10,u.TEXT)
            if self.opening((28,574,1224,90),'Response note','USE VENDOR GUIDANCE',age,.7):
                note=kev[int(age/8)%min(6,len(kev))] if kev else None
                message=(note['id']+' / '+note['action']) if note else 'Awaiting CISA response guidance.'
                self.wrap(message,44,612,180,11,lines=3)

    def terminal(self,index,age,data,errors,now,key,forced=False):
        u=self.u
        progress=1. if forced else terminal_progress(age)
        if progress<=0:return
        if self.session!=key:
            self.session=key
            php=data.get('php',{}).get('items',[])
            kev=data.get('kev',{}).get('items',[])
            priority=php_priority(php,{r['id'] for r in kev},now)
            top=priority[0] if priority else None
            lines=[
                '       .--------.     N E X U S  /  SECURITY BRIEF',
                '      /  [ == ]  \\    ============================',
                '      |  [____]  |    public sources / read-only',
                '      \\________/     PHP vendor + CISA KEV',
                '',
                '$ nexus brief --public-advisories',
                f'  PHP advisories loaded : {len(php) if "php" in data else "unavailable"}',
                f'  CISA exploited catalog: {len(kev) if "kev" in data else "unavailable"}',
            ]
            if top:
                score=f'{top["score"]:.1f}' if top['score'] is not None else 'not supplied'
                lines += [f'  Priority: {top["id"]} / {top["severity"].upper()}',
                          f'  CVSS {top["cvss_version"] or "--"}: {score} / '+top['summary'][:49],
                          '  Fixed: '+(' / '.join(top['patches']) or 'See vendor advisory')]
            else:lines.append('  PHP feed connecting; no severity conclusion available.')
            lines += ['', '  Scope: advisory watch. No fleet or package inventory.',
                      '  See PHP.net for configuration-specific follow-up guidance.',
                      '', '> brief complete / continuing background refresh']
            self.briefing='\n'.join(lines)
        x,y,w,h=225,212,830,362
        if progress<1:
            p=1-(1-progress)**3
            u.bevel(x+(w-w*p)/2,y+(h-h*p)/2,max(20,w*p),max(20,h*p))
            return
        u.panel(x,y,w,h,'Terminal / advisory briefing','AUTO BRIEF / T TO DISMISS')
        u.bevel(x+8,y+33,w-16,h-41,(12,28,36),True)
        count=int(max(0,age-7.65)*110)
        visible=self.briefing[:count]
        rows=visible.split('\n')
        for i,row in enumerate(rows):
            if i>=17:break
            u.mono(row,x+20,y+46+i*17,12,(185,231,207))
        if int(age*2)%2 and rows:
            last=rows[-1]
            u.mono('_',x+20+len(last)*7.2,y+46+(len(rows)-1)*17,12,(255,220,67))
