"""Offline contract fixtures: these do not implement or validate #47 selection."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import pygame
from focused_ui import FocusedDesktop
from desktop_renderer import rows_for

NOW=1793793600


def card(**changes):
    value=dict(id='warning-demo',group='situation',title='Synthetic regional wind warning',
        body=['Source-backed demonstration; check the official area and timing.',
              'Local applicability is unconfirmed.'],source='Met Office / synthetic fixture',
        url='https://example.com/warning',published=NOW-300,checked=NOW-30,
        valid_until=NOW+3600,state='current',severity='warning',pinned=True,duration=30)
    value.update(changes)
    return value


class ContractPolicy:
    """Return explicitly assigned outputs; deliberately no sorting or scheduling."""
    def __init__(self,cards,outputs):
        self.cards=cards;self.outputs=outputs;self.calls=[];self.context=None;self.rotations=[]

    def build_cards(self,context,now):
        self.context=context
        return self.cards

    def Rotation(self):
        index=len(self.rotations)
        def select(cards,now,group=None):
            self.calls.append((index,cards,now,group))
            return self.outputs[index]
        rotation=SimpleNamespace(select=select)
        self.rotations.append(rotation)
        return rotation


class DesktopRendererTests(unittest.TestCase):
    def setUp(self):
        pygame.display.init();pygame.font.init()
        self.screen=pygame.display.set_mode((1280,720))

    def tearDown(self):pygame.quit()

    def make(self,cards=None,outputs=None):
        self.policy=ContractPolicy(cards or [],outputs or [None,None])
        self.ui=FocusedDesktop(self.screen,{'name':'Example area'},preview=True,policy=self.policy)
        return self.ui

    def draw(self,workspace=0,now=NOW,automatic=True,uk=None):
        self.ui.draw(workspace,0,0,now,None,False,{},set(),uk or {},set(),{},set(),automatic=automatic)

    def test_selection_and_duration_are_passed_through_unchanged(self):
        first=card(duration=73);second=card(id='cyber',group='cyber',severity='advisory')
        self.make([first,second],[first,second]);self.draw()
        self.assertEqual(self.ui.renderer.selected,(first,second))
        self.assertEqual(self.policy.calls[0],(0,[first,second],NOW,None))
        self.assertEqual(self.policy.calls[1],(1,[second],NOW,None))
        self.assertEqual(first['duration'],73)
        self.assertEqual(self.ui.clicked_url((900,300)),first['url'])
        self.assertEqual(self.ui.active_url,first['url'])

    def test_observatory_is_manual_only_and_workspaces_pass_group(self):
        background=card(id='iss',group='observatory')
        self.make([background]);self.draw()
        self.assertEqual(self.policy.calls[0][1],[])
        self.assertEqual(self.policy.calls[1][1],[])
        for index,group in enumerate(('situation','cyber','infrastructure','node','observatory')):
            self.draw(index,NOW+index+1,automatic=False)
            self.assertEqual(self.policy.calls[-1][3],group)
        self.assertEqual(self.policy.calls[-1][1],[background])

    def test_stale_warning_and_unknown_validity_remain_visible(self):
        warning=card(state='stale',valid_until=None)
        self.make([warning],[warning,None])
        with patch.object(self.ui,'text',wraps=self.ui.text) as text:
            self.draw()
            labels=[c.args[0] for c in text.call_args_list]
        self.assertIn('STALE / WARNING',labels)
        self.assertIn('Valid until unknown',labels)
        self.assertIn('Published 04 Nov 2026 11:55 UTC',labels)

    def test_expiry_and_new_warning_follow_policy_output(self):
        first=card();self.make([first],[first,None]);self.draw()
        self.policy.cards=[];self.policy.outputs[:]=[None,None]
        self.draw(now=NOW+3601)
        self.assertEqual(self.ui.renderer.selected,(None,None))
        second=card(id='new-warning');self.policy.cards=[second];self.policy.outputs[0]=second
        self.draw(now=NOW+3602)
        self.assertEqual(self.ui.renderer.selected[0]['id'],'new-warning')

    def test_quiet_empty_and_failed_sources_are_not_all_clear(self):
        self.make()
        with patch.object(self.ui,'text',wraps=self.ui.text) as text:
            self.draw()
        words=' '.join(str(c.args[0]) for c in text.call_args_list)
        self.assertIn('UNREADABLE',words);self.assertIn('not an all-clear',words)
        self.assertIn('UNKNOWN',words)

    def test_missing_policy_is_explicit_and_does_not_select_locally(self):
        with patch('desktop_renderer.importlib.import_module',side_effect=ModuleNotFoundError(name='briefing_policy')):
            self.ui=FocusedDesktop(self.screen,{},preview=True)
        with patch.object(self.ui,'text',wraps=self.ui.text) as text:self.draw()
        self.assertIn('Shared briefing policy is not installed.',' '.join(c.args[0] for c in text.call_args_list))
        self.assertEqual(self.ui.renderer.selected,(None,None))

    def test_camera_motion_does_not_change_workspace_or_policy_candidates(self):
        self.make()
        for i,state in enumerate(('unavailable','activity','quiet')):
            with patch.object(self.ui.motion,'snapshot',return_value={'state':state,'online':state!='unavailable','observe':True}):
                self.draw(2,NOW+i,False)
                self.assertEqual(self.policy.context['motion']['state'],state)
                self.assertEqual(self.policy.calls[-1][3],'infrastructure')
                self.assertEqual(self.policy.calls[-1][1],[])

    def test_network_unknown_offline_and_recovery_remain_distinct(self):
        self.make()
        for i,label in enumerate(('CHECKING','OFFLINE','CONNECTED')):
            network={'connection':{'label':label,'offline':label=='OFFLINE','latency':None if i<2 else 22},'signal':None}
            with patch.object(self.ui.network_activity,'snapshot',return_value=network),patch.object(self.ui,'text',wraps=self.ui.text) as text:
                self.draw(now=NOW+i)
                self.assertIn('PI LINK / '+label,[c.args[0] for c in text.call_args_list])
                self.assertEqual(self.policy.context['network'],network)

    def test_long_text_and_unbroken_urls_are_accessible_through_pages(self):
        value='word '*900+'X'*400
        warning=card(body=[value],url='https://example.com/'+'x'*200)
        self.make([warning],[warning,None]);self.draw()
        self.assertTrue(self.ui.click_detail((900,610)));self.draw()
        self.assertGreater(self.ui.renderer.page_count,1)
        seen=[]
        for page in range(self.ui.renderer.page_count):
            self.ui.renderer.page=page;self.ui.key=None
            with patch.object(self.ui,'text',wraps=self.ui.text) as text:self.draw()
            seen.extend(str(c.args[0]) for c in text.call_args_list if len(c.args)>2 and c.args[1]==48 and 220<=c.args[2]<=508)
        compact=''.join(seen).replace(' ','')
        self.assertIn(value.replace(' ',''),compact)
        self.assertIn(warning['url'],compact)
        self.assertEqual(self.ui.clicked_url((100,570)),warning['url'])
        self.assertTrue(self.ui.click_detail((1100,190)))
        self.assertIsNone(self.ui.renderer.detail)

    def test_wrapping_never_exceeds_width(self):
        for value in ('A'*600,'A long sentence with words', 'α'*400):
            rows=rows_for(pygame.font.SysFont('dejavusans',18),value,200)
            self.assertTrue(all(pygame.font.SysFont('dejavusans',18).size(row)[0]<=200 for row in rows))

    def test_both_hdmi_sizes_have_bounded_links_and_label_cache(self):
        for size in ((1280,720),(1920,1080)):
            self.screen=pygame.display.set_mode(size)
            warning=card();self.make([warning],[warning,None])
            for i in range(20):self.draw(now=NOW+i)
            self.assertLessEqual(len(self.ui.labels),600)
            for (x,y,w,h),url in self.ui.links:
                self.assertTrue(0<=x<x+w<=1280 and 0<=y<y+h<=720)
            self.assertEqual(self.ui.static.get_size(),size)

    def test_disagreement_provenance_and_source_details_persist(self):
        self.make()
        threat={'level':'LOW','fetched':NOW,'disagreement':True,
                'observations':{'GOV.UK':{'level':'LOW'},'MI5':{'level':'CRITICAL'}}}
        with patch.object(self.ui,'text',wraps=self.ui.text) as text:self.draw(uk={'threat':threat})
        words=' '.join(c.args[0] for c in text.call_args_list)
        self.assertIn('SOURCES DIFFER',words);self.assertNotIn('GOV.UK LOW / MI5 CRITICAL',words)
        self.ui.click_detail((45,120));self.draw()
        self.assertEqual(self.ui.source_detail,'gov')
        self.assertTrue(self.ui.clicked_url((370,615)).startswith('https://'))


if __name__=='__main__':unittest.main()
