"""Source-specific layouts; leave persistent threat and network areas untouched."""
from grid_notices import card, CREDIT


def desktop(ui, sample, now, phase):
    row = card(sample, now, (phase//240)*64)
    ui.panel(330,105,580,537,'INFRASTRUCTURE / ELECTRICITY',row['state'])
    ui.wrap(row['title'],350,150,535,24,lines=2)
    ui.text(row['scope'],350,219,14)
    ui.text(row['issued'],350,247,13)
    ui.text(row['validity'],350,274,13)
    ui.text(row['category']+' / '+row['meaning'],350,300,12)
    ui.wrap(row['detail'],350,320,535,13,lines=2)
    ui.wrap(row['text'],350,356,535,16,lines=5)
    ui.text('National system notices do not confirm a local power cut.',350,484,13)
    ui.text(row['checked'],350,512,12)
    ui.text(row['source'],350,540,13)
    ui.wrap(CREDIT,350,573,535,11,lines=2)
    ui.register((330,105,580,537),row['url'])


def companion(ui, sample, now, phase, x):
    row = card(sample, now, phase)
    ui.box((x,110,225,148),'GRID / '+row['state'],ink='accent')
    ui.text(row['title'],x+9,137,15,'text',207)
    ui.text('GB system; scope unspecified' if int(phase//4)%2 else row['category'],
            x+9,157,12,'muted',207)
    ui.text(row['issued'],x+9,174,12,'muted',207)
    # The GOV.UK strip covers y=242: keep lifecycle caveats above it.
    status = ('Cancellation / check source' if 'cancellation' in row['detail']
              and int(phase//4)%2 else 'Validity / active unknown')
    ui.text(status,x+9,191,12,'muted',207)
    # Alternate metadata with the full attribution, without reducing font size.
    if int(phase//8)%2:
        ui.text('contains BMRS data © Elexon',x+9,210,11,'muted',207)
        ui.text('Limited copyright and database right',x+9,226,10,'muted',207)
    else:
        ui.text('Elexon Insights / BMRS',x+9,210,12,'accent',207)
        ui.text('Local power cut not confirmed',x+9,226,12,'muted',207)
