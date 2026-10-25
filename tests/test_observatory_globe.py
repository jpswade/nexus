import unittest
import pygame
from observatory_globe import ObservatoryGlobe


class ObservatoryGlobeTests(unittest.TestCase):
    def test_rotation_changes_geography_without_changing_surface_size(self):
        globe=ObservatoryGlobe({'longitude':-2,'latitude':53})
        first=pygame.image.tobytes(globe.draw(0),'RGB')
        later=pygame.image.tobytes(globe.draw(15),'RGB')
        self.assertNotEqual(first,later)
        self.assertEqual(globe.surface.get_size(),(568,370))
        self.assertEqual(pygame.image.tobytes(globe.draw(15),'RGB'),later)
