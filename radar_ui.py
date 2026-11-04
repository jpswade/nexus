"""Infrastructure cards; do not alter threat or network measurements."""
from radar_outages import SOURCE, display_lines


def desktop(view, sample, phase):
    view.panel(330,105,580,537,'INFRASTRUCTURE / INTERNET','REPORTED / 7 DAYS')
    for i, line in enumerate(display_lines(sample, phase)):
        view.wrap(line,350,157+i*67,535,17,lines=2)
    view.text('Context only; does not explain why this Pi is offline',350,532,13)
    view.text('Cloudflare Radar / CC BY-NC 4.0',350,567,13)
    view.text('radar.cloudflare.com/outage-center',350,594,12)
    view.text('Reports may be incomplete; no reports is not an all-clear',350,620,11)
    view.register((330,105,580,537),SOURCE)


def companion(view, sample, phase, x=14):
    view.box((x,110,225,148),'INTERNET / UK CONTEXT',ink='accent')
    for i, line in enumerate(display_lines(sample, phase)):
        view.text(line,x+9,132+i*17,12,'text',207)
    view.text('Reported / not Pi diagnosis',x+9,218,11,'muted',207)
    view.text('Cloudflare / CC BY-NC 4.0',x+9,234,11,'accent',207)
