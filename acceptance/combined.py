"""Combined offline policy/render acceptance. No network, display device or private data."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import pygame
from acceptance.harness import validate_cards, packaging_errors
from acceptance.scenarios import scenarios
from briefing_policy import build_cards, Rotation
from focused_ui import FocusedDesktop
from companion import Companion


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    pygame.display.init();pygame.font.init()
    count=0
    for case in scenarios():
        now=case['now'];cards=case['cards'];context=case['context']
        validate_cards(build_cards(context,now))
        # Run the real scheduler against boundary fixtures, then both real renderers.
        policy=SimpleNamespace(build_cards=lambda ctx,stamp,cards=cards:cards,Rotation=Rotation)
        screen=pygame.display.set_mode((1280,720))
        ui=FocusedDesktop(screen,{'name':'SYNTHETIC AREA'},preview=True,policy=policy)
        net=context.get('network',{'checked':now,'offline':False,'latency':25,'maximum':40,'label':'CONNECTED','colour':'accent'})
        ui.network_activity.snapshot=lambda net=net:dict(connection=net,signal=-60,checked=now,history=[(-60,1,1)])
        ui.motion.snapshot=lambda:None  # replaced with timestamp-taking adapter below
        ui.motion.snapshot=lambda stamp,ctx=context:ctx.get('motion',{})
        uk={'threat':{'level':'MODERATE','fetched':now}}
        ui.draw(4 if case['name']=='observatory-manual' else 0,0,0,now,None,False,{},set(),uk,set(),{},set(),automatic=case['name']!='observatory-manual')
        pygame.image.save(screen,str(output/(case['name']+'-hdmi.png')))
        lcd=Companion();lcd.policy=policy;lcd.rotation=Rotation()
        lcd.motion.snapshot=ui.motion.snapshot
        lcd.draw(uk,now,0,'Synthetic scope',net)
        pygame.image.save(lcd.surface,str(output/(case['name']+'-lcd.png')))
        count+=1
    pygame.quit()
    assert not packaging_errors(),packaging_errors()
    result=dict(scenarios=count,renders=count*2,policy='real scheduler plus card-boundary fixtures; raw adapter tests in unit suite',hardware='separate Pi check required')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().out),indent=2))
