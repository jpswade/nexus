import unittest
from companion import Companion, find_lcd, refresh_overdue
from unittest.mock import patch
from preparedness import INTERVALS
from pathlib import Path
import tempfile


class CompanionTests(unittest.TestCase):
    def test_all_pages_render_with_missing_and_long_data(self):
        view = Companion()
        for data in ({}, {'threat': {'level': 'SUBSTANTIAL', 'fetched': 0},
                         'weather': {'items': [{'title': 'Long weather warning ' * 20}], 'fetched': 0}}):
            for age in (0, 15, 30, 45):
                surface = view.draw(data, 10000, age, 'LOCAL AREA / WITHIN APPROX 25 KM')
                self.assertEqual(surface.get_size(), (480, 320))
                self.assertEqual(surface.get_masks()[:3], (0xf800, 0x07e0, 0x001f))
                self.assertEqual(len(bytes(surface.get_buffer())), 307200)

    def test_lcd_discovery_ignores_hdmi_and_handles_reordered_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for lcd,hdmi in [('fb0','fb1'),('fb1','fb0')]:
                for name,driver in [(lcd,'fb_ili9486'),(hdmi,'vc4drmfb')]:
                    (root/name).mkdir(exist_ok=True)
                    (root/name/'name').write_text(driver)
                self.assertEqual(find_lcd(root),'/dev/'+lcd)
            (root/'fb1'/'name').write_text('vc4drmfb')
            with self.assertRaises(RuntimeError):find_lcd(root)


class RefreshFallbackTests(unittest.TestCase):
    def test_fresh_shared_cache_does_not_make_duplicate_requests(self):
        with patch('companion.PreparednessFeeds') as factory:
            feeds = factory.return_value
            feeds.snapshot.return_value = ({name: {'fetched': 10000} for name in INTERVALS}, set())
            refresh_overdue(None, {}, {}, 10001)
            feeds.refresh.assert_not_called()

    def test_overdue_sources_refresh_with_bounded_failure_retries(self):
        attempted = {}
        with patch('companion.PreparednessFeeds') as factory:
            feeds = factory.return_value
            feeds.snapshot.return_value = ({}, set())
            refresh_overdue(None, {}, attempted, 10000)
            self.assertEqual([call.args[0] for call in feeds.refresh.call_args_list], ['threat', 'weather', 'floods', 'ncsc', 'news'])
            feeds.refresh.reset_mock()
            refresh_overdue(None, {}, attempted, 10030)
            feeds.refresh.assert_not_called()
            refresh_overdue(None, {}, attempted, 10300)
            self.assertEqual(feeds.refresh.call_count, 5)

    def test_long_text_keeps_requested_font_size(self):
        view = Companion()
        view.text('A very long status ' * 20, 12, 12, 28)
        self.assertEqual(set(view.fonts), {28})


class PersistentConsoleTests(unittest.TestCase):
    def test_warning_colour_stays_visible_on_every_page(self):
        view=Companion()
        data={'threat':{'level':'severe','fetched':10000}}
        for age in (0,12,24):
            pixel=view.draw(data,10000,age,'').get_at((2,150))
            self.assertGreater(pixel.r,200)
            self.assertGreater(pixel.g,100)
            self.assertLess(pixel.b,150)

    def test_unknown_weather_colour_is_not_invented(self):
        from companion import weather_label
        self.assertEqual(weather_label({'title':'Unknown warning'}, {'items':[{'title':'Unknown warning'}]}),'BULLETIN')

    def test_full_assessment_labels_fit_the_status_box(self):
        view=Companion()
        for level in ('LOW','MODERATE','SUBSTANTIAL','SEVERE','CRITICAL','UNKNOWN'):
            size=38 if len(level)>6 else 54
            self.assertLessEqual(view.face(size).size(level)[0],262,level)


class ScifiMotionTests(unittest.TestCase):
    def test_threat_box_stays_visible_during_secondary_reveals(self):
        view=Companion()
        data={'threat':{'level':'severe','fetched':10000}}
        for age in (0,12.9,13,13.2,19,26,39):
            surface=view.draw(data,10000,age,'')
            pixel=surface.get_at((20,115))
            self.assertGreater(pixel.r,180)
            self.assertGreater(pixel.g,100)

    def test_yellow_weather_has_a_yellow_fill(self):
        view=Companion()
        data={'weather':{'fetched':10000,'items':[{'title':'Yellow wind warning','colour':'yellow'}]}}
        surface=view.draw(data,10000,3,'')
        pixel=surface.get_at((310,190))
        self.assertGreater(pixel.r,200)
        self.assertGreater(pixel.g,180)
        self.assertLess(pixel.b,100)

    def test_refresh_reveal_does_not_restart_other_slot(self):
        view=Companion()
        data={'weather':{'fetched':10000,'items':[]},'floods':{'fetched':10000,'items':[]}}
        view.draw(data,10000,3,'')
        side=view.tiles['side']
        data['weather']['fetched']=10001
        view.draw(data,10001,4,'')
        self.assertEqual(view.tiles['side'],side)
        self.assertEqual(view.tiles['main'][1],4)
