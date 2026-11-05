"""Synthetic #46 contract fixtures; no competing implementation of policy."""
import unittest
from unittest.mock import Mock, patch

import pygame
from companion import Companion
from lcd_renderer import wrap

NOW = 1793793600


def card(**changes):
    return dict(id='fixture:warning', group='situation', title='Synthetic flood warning',
                body=['Local warning evidence. Check the official source.'],
                source='Environment Agency (fixture)', url='https://example.org/warning',
                published=NOW-600, checked=NOW, valid_until=None, state='current',
                severity='warning', pinned=True, duration=90, **changes) if not changes else {
                    **card(), **changes}


def view_for(selected):
    view = Companion()
    view.policy = Mock()
    view.rotation = Mock()
    view.policy.build_cards.return_value = [selected] if selected else []
    view.rotation.select.return_value = selected
    return view


class ContractTests(unittest.TestCase):
    def test_selection_and_context_pass_through_to_shared_policy(self):
        selected = card()
        view = view_for(selected)
        view.context = {'weather': {'temperature': 12}, 'security': {}, 'telemetry': {}}
        view.draw({}, NOW, 0, 'synthetic locality')
        context, now = view.policy.build_cards.call_args.args
        self.assertEqual(now, NOW)
        self.assertEqual(context['weather'], {'temperature': 12})
        self.assertEqual(context['location'], {'floods_scope':'synthetic locality'})
        for name in ('uk','emergency','network','motion','source_records','space','radar'):
            self.assertIn(name, context)
        view.rotation.select.assert_called_once_with([selected], NOW)
        self.assertEqual(view.card_renderer.active[0], selected['id'])

    def test_retained_stale_warning_and_expiry_follow_policy(self):
        view = view_for(card(state='stale', valid_until=NOW-1))
        with patch.object(view,'text',wraps=view.text) as text:
            view.draw({},NOW,0,'')
        self.assertIn('SITUATION / STALE / WARNING',[c.args[0] for c in text.call_args_list])
        view.rotation.select.return_value = None
        view.draw({},NOW+1,1,'')
        self.assertIsNone(view.card_renderer.active)

    def test_complete_long_text_url_dates_are_reachable_and_fit(self):
        selected = card(title='Long warning title '*30, body=['Unbroken' * 80],
                        url='https://example.org/'+'abcdefghij'*40)
        view = view_for(selected)
        view.draw({},NOW,0,'')
        renderer = view.card_renderer
        pages = renderer.pages[:]
        rows = [row for page in pages for row in page]
        joined = ''.join(rows).replace(' ','')
        for value in [selected['title'], *selected['body'], selected['url'], selected['source'],
                      'Published:', 'Checked:', 'Valid until: unknown']:
            self.assertIn(value.replace(' ',''), joined)
        for row in rows:
            self.assertLessEqual(view.face(22).size(row)[0],438)
        for i in range(len(pages)):
            view.draw({},NOW+i*renderer.PAGE_SECONDS,i*renderer.PAGE_SECONDS,'')
            self.assertEqual(renderer.page,i)
        self.assertTrue(all(len(page)<=4 for page in pages))

    def test_page_holds_fifteen_seconds_and_countdown_matches_next_change(self):
        view=view_for(card(body=['Long evidence '*40]))
        view.draw({},NOW,0,'')
        self.assertEqual(view.card_renderer.remaining,15)
        view.draw({},NOW+14,14,'')
        self.assertEqual(view.card_renderer.page,0)
        self.assertEqual(view.card_renderer.remaining,1)
        view.draw({},NOW+15,15,'')
        self.assertEqual(view.card_renderer.page,1)
        self.assertEqual(view.card_renderer.remaining,15)
        view.card_renderer.draw(view,card(),16,card_remaining=3)
        self.assertEqual(view.card_renderer.remaining,3)

    def test_wrap_preserves_unbroken_text(self):
        view=Companion()
        value='https://example.org/'+'z'*500
        self.assertEqual(''.join(wrap(value,view.face(22),438)),value)

    def test_progress_survives_visits_and_is_bounded(self):
        view=view_for(card())
        view.draw({},NOW,0,'')
        view.draw({},NOW+9,9,'')
        page=view.card_renderer.page
        view.rotation.select.return_value=card(id='other')
        view.draw({},NOW+10,10,'')
        view.rotation.select.return_value=card()
        view.draw({},NOW+11,11,'')
        self.assertEqual(view.card_renderer.page,page)
        for i in range(70):
            view.rotation.select.return_value=card(id=str(i))
            view.draw({},NOW+12+i,12+i,'')
        self.assertEqual(len(view.card_renderer.progress),64)

    def test_offline_bypasses_policy_and_recovery_resumes(self):
        view=view_for(card())
        view.draw({},NOW,0,'',{'checked':NOW,'offline':True})
        view.policy.build_cards.assert_not_called()
        view.draw({},NOW+1,1,'',{'checked':NOW,'offline':False})
        view.policy.build_cards.assert_called_once()

    def test_camera_does_not_override_policy_or_page(self):
        view=view_for(card())
        for state in ({'observe':False,'online':False},
                      {'observe':False,'online':True,'last_motion':NOW},
                      {'observe':False,'online':True,'last_motion':NOW-500}):
            view.motion.snapshot=Mock(return_value=state)
            view.draw({},NOW,0,'')
            self.assertEqual(view.card_renderer.active[0],'fixture:warning')
            self.assertEqual(view.card_renderer.page,0)

    def test_disagreement_and_checks_remain_visible(self):
        view=view_for(card())
        threat=dict(level='severe', fetched=NOW, disagreement=True,
                    observations={'GOV.UK':{'level':'SEVERE'},'MI5':{'level':'SUBSTANTIAL'}})
        with patch.object(view,'text',wraps=view.text) as text:
            view.draw({'threat':threat},NOW,0,'')
        values=[c.args[0] for c in text.call_args_list]
        self.assertTrue(any('SOURCES DIFFER' in v for v in values))
        self.assertNotIn('GOV.UK SEVERE / MI5 SUBSTANTIAL',values)
        self.assertIn('GRID',values);self.assertIn('UNREADABLE',values)
        self.assertIn('FLOODS',values)

    def test_physical_rotation_preserves_rgb565(self):
        view=view_for(card())
        surface=view.draw({},NOW,0,'')
        rotated=pygame.transform.rotate(surface,180)
        self.assertEqual(rotated.get_size(),(480,320))
        self.assertEqual(rotated.get_masks(),surface.get_masks())
        self.assertEqual(rotated.get_at((479,319)),surface.get_at((0,0)))

    def test_offline_time_does_not_skip_evidence_pages(self):
        view=view_for(card())
        view.draw({},NOW,0,'')
        view.draw({},NOW+2,2,'',{'checked':NOW+2,'offline':True})
        view.draw({},NOW+100,100,'')
        self.assertEqual(view.card_renderer.page,0)

    def test_failed_feed_remains_explicit_in_summary_and_context(self):
        view=view_for(card(state='unavailable',severity='info'))
        view.source_records={'floods':{'failed':True,'attempted':NOW}}
        with patch.object(view,'text',wraps=view.text) as text:
            view.draw({'floods':{'fetched':NOW,'items':[]}},NOW,0,'')
        self.assertIn('STALE',[c.args[0] for c in text.call_args_list])
        context=view.policy.build_cards.call_args.args[0]
        self.assertTrue(context['source_records']['floods']['failed'])
