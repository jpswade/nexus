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
        view = Companion(); view.space_panel = SpaceWeatherPanel(self.feeds)
        data = {'threat':{'level':'severe','fetched':NOW}}
        actual = view.draw(data,NOW,48,'').copy()
        # Render same frame with only the space panel disabled; surrounding pixels
        # must be byte-identical, including the existing animated network strip.
        with patch.object(view.space_panel,'draw',return_value=pygame.Surface((225,148))):
            reference = view.draw(data,NOW,48,'').copy()
        for box in ((0,0,480,110),(247,110,225,148),(0,266,480,54)):
            self.assertEqual(pygame.image.tostring(actual.subsurface(box),'RGB'),
                             pygame.image.tostring(reference.subsurface(box),'RGB'))
        self.assertEqual(len(bytes(actual.get_buffer())),480*320*2)

    def test_desktop_rotation_uses_active_focused_ui_and_preserves_sidebar(self):
        from focused_ui import FocusedDesktop
        view = FocusedDesktop(self.screen,{},preview=True)
        view.space_panel = SpaceWeatherPanel(self.feeds)
        args=(3,48,48,NOW,None,False,{},set(),{'threat':{'level':'severe','fetched':NOW}},set(),{},set())
        view.draw(*args); actual=self.screen.copy()
        self.assertIn('swpc.noaa.gov',view.clicked_url((500,300)))
        with patch.object(view.space_panel,'draw',return_value=pygame.Surface((580,537))):
            view.draw(*args); reference=self.screen.copy()
        for box in ((0,0,330,720),(910,0,370,720)):
            self.assertEqual(pygame.image.tostring(actual.subsurface(box),'RGB'),
                             pygame.image.tostring(reference.subsurface(box),'RGB'))
        for _ in range(20):view.draw(*args)
        self.assertLess(len(view.links),20)


if __name__=='__main__':unittest.main()
