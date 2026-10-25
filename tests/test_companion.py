import unittest
from companion import Companion, find_lcd
from pathlib import Path
import tempfile


class CompanionTests(unittest.TestCase):
    def test_all_pages_render_with_missing_and_long_data(self):
        view = Companion()
        for data in ({}, {'threat': {'level': 'SUBSTANTIAL', 'fetched': 0},
                         'weather': {'items': [{'title': 'Long weather warning ' * 20}], 'fetched': 0}}):
            for age in (0, 15, 30, 45):
                surface = view.draw(data, 10000, age, 'CW12 AREA / WITHIN APPROX 25 KM')
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
