import unittest
from companion import Companion


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
