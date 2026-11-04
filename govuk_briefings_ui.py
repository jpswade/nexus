"""Briefing cards; no alert severity or threat-level inference."""
from govuk_briefings import card


def desktop(ui, sample, now, phase):
    row = card(sample, now, (phase//240)*48)
    ui.panel(330,105,580,537,'OFFICIAL UK / SERVICE BRIEFINGS',row['state'])
    ui.wrap(row['title'],350,150,535,24,lines=3)
    ui.text(row['issued'],350,244,13)
    ui.wrap(row['text'],350,282,535,17,lines=6)
    ui.wrap(row['source'],350,450,535,14,lines=2)
    ui.text(row['checked'],350,510,12)
    ui.text('7-day window / selected disruption briefings',350,546,13)
    ui.text('Publication is not proof of an active incident.',350,576,13)
    ui.text('Open official briefing for instructions and updates',350,608,13)
    ui.links=[entry for entry in ui.links if entry[0]!=(330,105,580,537)]
    ui.register((330,105,580,537),row['url'])


def companion(ui, sample, now, phase, x):
    row = card(sample, now, phase)
    ui.box((x,110,225,148),'GOV.UK / '+row['state'],ink='accent')
    # Two readable headline lines, with the full title available on HDMI.
    words=row['title'].split()
    first=[]
    while words and len(' '.join(first+[words[0]]))<=27:
        first.append(words.pop(0))
    if not first and words:
        first.append(words.pop(0))
    ui.text(' '.join(first),x+9,136,14,'text',207)
    ui.text(' '.join(words),x+9,154,14,'text',207)
    ui.text(row['issued'].replace('Published/updated ','Updated '),x+9,178,11,'muted',207)
    if int(phase//8)%2:
        ui.text(row['checked'],x+9,198,10,'muted',207)
    else:
        ui.text(row['source'],x+9,198,11,'accent',207)
    ui.text('7 days / not an all-clear',x+9,220,12,'muted',207)
