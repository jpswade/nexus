"""Compact cached-source summaries shared by both physical displays."""
from preparedness import MAX_AGES


def summary(name, data, now, errors=()):
    sample = data.get(name)
    if not sample:
        return 'UNAVAILABLE'
    stale = name in errors or now-sample['fetched'] > MAX_AGES[name]
    if name == 'threat':
        value = sample['level'].upper()
    elif name == 'weather':
        items = sample.get('items', [])
        rank = {'red': 3, 'amber': 2, 'yellow': 1}
        highest = max((str(item.get('colour', '')).lower() for item in items),
                      key=lambda colour: rank.get(colour, 0), default='')
        value = f'{len(items)} BULLETINS' if items else 'NONE RETURNED'
        if highest in rank:
            value = highest.upper()+f' / {len(items)}'
    else:
        value = f"{len(sample.get('items', []))} ALERTS"
    return value+(' [STALE]' if stale else '')


def live_checks(data, emergency, now, errors=(), alerts=()):
    """Check health and source results, never a combined emergency severity."""
    from emergency_alerts import presentation
    from grid_notices import MAX_AGE as GRID_AGE, WINDOW
    _, rows, stale = presentation(emergency, now)
    current = [r for r in rows if r['status'] == 'current']
    real = sum(not r.get('test', False) for r in current)
    tests = len(current)-real
    value = f'{real} LISTED' if real else f'{tests} TEST' if tests else 'NONE LISTED'
    gov = ('GOV.UK', 'UNREADABLE' if emergency.get('failed') else 'NOT CHECKED', 'unknown') if emergency.get('fetched') is None else ('GOV.UK', 'STALE' if stale else value, 'stale' if stale else 'alert' if real else 'ok')
    grid = data.get('grid') or {}
    fetched = grid.get('fetched')
    if fetched is None:
        grid_check = ('GRID', 'UNREADABLE', 'unknown')
    elif grid.get('failed') or not 0 <= now-fetched <= GRID_AGE:
        grid_check = ('GRID', 'STALE', 'stale')
    else:
        count = sum(0 <= now-r['published'] <= WINDOW for r in grid.get('items', []))
        grid_check = ('GRID', f'{count} BULLETINS', 'ok')
    result = [gov, grid_check]
    for source, label in [('weather', 'WEATHER'), ('floods', 'FLOODS')]:
        sample = data.get(source)
        if not sample:
            result.append((label, 'UNREADABLE', 'unknown'))
        elif source in errors or sample.get('failed') or not 0 <= now-sample['fetched'] <= MAX_AGES[source]:
            result.append((label, 'STALE', 'stale'))
        else:
            count = sum(a['source'] == source for a in alerts)
            result.append((label, f'{count} LISTED' if count else 'NONE LISTED', 'alert' if count else 'ok'))
    return result


def status_board(context, now):
    """All measured checks, without inferred household risk or source-label clutter."""
    from preparedness import display_items
    from alert_state import AlertState
    data=context.get('uk') or {}; errors=set(context.get('uk_errors') or ())
    records=context.get('source_records') or {}
    errors.update(k for k,v in records.items() if v.get('failed'))
    data={k:dict(v,failed=True) if k in errors and isinstance(v,dict) else v for k,v in data.items()}
    checks=live_checks(data,context.get('emergency') or {},now,errors,AlertState().update(data,errors,now))
    rows=[]
    def add(key,label,value,state):rows.append(dict(id=key,label=label,value=value,state=state))
    for key,label,check in zip(('gov','grid','weather','floods'),('EMERGENCY ALERTS','ELECTRICITY GRID','WEATHER WARNINGS','LOCAL FLOODS'),checks):
        value,state=check[1:]
        if key=='weather' and state=='alert':
            colours=[str(r.get('colour','')).lower() for r in (data.get('weather') or {}).get('items',[])]
            highest=max(colours,key=lambda c:{'red':3,'amber':2,'yellow':1}.get(c,0),default='')
            if highest in ('red','amber','yellow'):value=highest.upper()+' / '+value.split()[0]
        add(key,label,value.replace('NONE LISTED','NONE ACTIVE'),state)
    radar=context.get('radar') or {}; status=radar.get('status','unavailable').lower()
    if status=='checked':value=f"{len(radar.get('items',[]))} REPORTS / 7D";state='info'
    else:value='NOT SET UP' if status=='not configured' else 'STALE' if 'stale' in status else 'UNKNOWN';state='stale' if 'stale' in status else 'unknown'
    add('internet','UK INTERNET',value,state)
    scales=(context.get('space') or {}).get('scales') or {}
    observed=next((r for r in scales.get('rows',[]) if r.get('kind')=='observation'),{})
    for axis,label in [('G','GEOMAGNETIC'),('R','RADIO BLACKOUT'),('S','SOLAR RADIATION')]:
        level=observed.get('levels',{}).get(axis)
        stale=scales.get('status')=='stale'
        value='UNKNOWN' if level is None else f'{axis}{level}'+(' / STALE' if stale else '')
        add(axis,label,value,'unknown' if level is None else 'stale' if stale else 'alert' if int(level)>0 else 'ok')
    for key,label,window in [('ncsc','CYBER / TODAY',3600),('govuk','OFFICIAL BRIEFINGS',3600)]:
        sample=data.get(key) or {}; fetched=sample.get('fetched')
        stale=key in errors or sample.get('failed') or fetched is not None and not 0<=now-fetched<=window
        items=display_items('ncsc',sample,now) if key=='ncsc' else [r for r in sample.get('items',[]) if isinstance(r.get('published'),(int,float)) and 0<=now-r['published']<=7*86400]
        value='UNKNOWN' if fetched is None else 'STALE' if stale else f'{len(items)} '+('TODAY' if key=='ncsc' else 'REPORTS / 7D')
        add(key,label,value,'unknown' if fetched is None else 'stale' if stale else 'info')
    motion=context.get('motion') or {}; age=now-motion.get('checked',0)
    online=motion.get('online') and -2<=age<=15
    add('camera','CAMERA', 'ONLINE' if online else 'UNAVAILABLE', 'ok' if online else 'unknown')
    unknown=sum(r['state'] in ('unknown','stale') for r in rows)
    add('health','CHECK COVERAGE',f'{len(rows)-unknown}/{len(rows)} CURRENT','stale' if unknown else 'ok')
    return rows
