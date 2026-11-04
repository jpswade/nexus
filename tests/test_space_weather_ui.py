import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import tempfile
import unittest
from unittest.mock import patch
import pygame
from space_weather import SpaceWeather
from space_weather_ui import SpaceWeatherPanel
from test_space_weather import fixture, NOW


class Layout(unittest.TestCase):
    def setUp(self):
        pygame.display.init(); pygame.font.init()
        self.screen = pygame.display.set_mode((1280, 720))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'NEXUS_CACHE':self.temp.name})
        self.env.start(); self.addCleanup(self.env.stop)
        self.feeds = SpaceWeather(self.temp.name, fixture, lambda:NOW)
        self.feeds.refresh()
        self.addCleanup(pygame.quit)

    def test_all_pages_missing_fresh_stale_fit_both_displays(self):
        for service in (self.feeds, SpaceWeather(self.temp.name+'/empty')):
            panel = SpaceWeatherPanel(service)
            for size in ((580,537),(225,148)):
                for now in (NOW, NOW+86400*3):
                    for age in (0,8,16):
                        self.assertEqual(panel.draw(size,now,age).get_size(), size)
                        self.assertIs(panel.draw(size,now,age), panel.image)

    def test_companion_rotation_preserves_header_and_ping_wifi_strip(self):
        from companion import Companion
        view=Companion();view.space_weather=self.feeds
        data={'threat':{'level':'moderate','fetched':NOW}}
        actual=view.draw(data,NOW,80,'').copy()
        with patch.object(view.card_renderer,'draw'):
            reference=view.draw(data,NOW,80,'').copy()
        for box in ((0,0,480,110),(0,266,480,54)):
            self.assertEqual(pygame.image.tostring(actual.subsurface(box),'RGB'),pygame.image.tostring(reference.subsurface(box),'RGB'))
        self.assertTrue(view.card_renderer.active[0].startswith('space:'))

    def test_desktop_rotation_uses_active_focused_ui_and_preserves_sidebar(self):
        from focused_ui import FocusedDesktop
        view=FocusedDesktop(self.screen,{},preview=True);view.space_weather=self.feeds
        view.draw(2,0,0,NOW,None,False,{},set(),{'threat':{'level':'moderate','fetched':NOW}},set(),{},set(),automatic=False)
        self.assertTrue(any(c and c['id'].startswith('space:') for c in view.renderer.selected))
        selected=next(c for c in view.renderer.selected if c and c['id'].startswith('space:'))
        self.assertIn(selected['url'],[url for _,url in view.links])
        for i in range(20):view.draw(2,i,i,NOW+i,None,False,{},set(),{},set(),{},set(),automatic=False)
        self.assertLess(len(view.links),20)


if __name__=='__main__':unittest.main()
