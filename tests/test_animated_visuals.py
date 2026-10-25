import unittest
import pygame
from animated_visuals import Visuals


class VisualTests(unittest.TestCase):
    def test_motion_is_repeatable_and_cache_stays_bounded(self):
        visuals=Visuals()
        for kind in ('wind','water','orb'):
            first=visuals.frame(kind,0)
            self.assertIs(first,visuals.frame(kind,.1))
            self.assertNotEqual(pygame.image.tobytes(first,'RGB'),pygame.image.tobytes(visuals.frame(kind,2),'RGB'))
            self.assertEqual(first.get_size(),(112,82))
        for age in range(50):
            for kind in ('wind','water','orb'):visuals.frame(kind,age)
        self.assertLessEqual(len(visuals.cache),3)
