import unittest
import pygame
from uk_map import UKMap, project


class UKMapTests(unittest.TestCase):
    def test_location_projection_and_animation(self):
        pygame.font.init()
        renderer=UKMap({'longitude':-2.2,'latitude':53.2})
        x,y=project(-2.2,53.2)
        self.assertTrue(0<x<480 and 0<y<440)
        a=renderer.draw(0)
        b=renderer.draw(2)
        self.assertIs(b,renderer.draw(2.1))
        bx,by=project(-2.2,53.2,2)
        self.assertEqual(b.get_at((int(bx),int(by)))[:3],(104,239,255))
        self.assertEqual(a.get_size(),(480,480))
        self.assertEqual(a.get_at((int(x),int(y)))[:3],(104,239,255))
        self.assertNotEqual(pygame.image.tobytes(a,'RGB'),pygame.image.tobytes(b,'RGB'))
        # No default marker in unconfigured or out-of-extent locations.
        for config in ({},{'longitude':120,'latitude':0}):
            plain=UKMap(config).draw(0)
            self.assertNotEqual(plain.get_at((int(x),int(y)))[:3],(104,239,255))
