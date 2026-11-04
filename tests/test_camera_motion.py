import json
from pathlib import Path
import tempfile
import unittest
import pygame
from camera_motion import Detector, MotionReader, configuration
from camera_eye import draw


class MotionTests(unittest.TestCase):
    def test_sustained_movement_hold_fade_and_cooldown(self):
        d=Detector(); a=[80]*768; b=[120]*100+[80]*668
        d.update(a,0)
        for t,p in [(2,b),(4,a),(6,b)]: d.update(p,t)
        self.assertEqual(d.state(6),'activity')
        self.assertEqual(d.last_pulse,6)
        d.update(a,8)
        self.assertEqual(d.last_pulse,6)
        self.assertEqual(d.state(25),'settled')
        self.assertEqual(d.state(41),'quiet')

    def test_lighting_and_single_flicker_do_not_activate(self):
        d=Detector();d.update([60]*768,0)
        d.update([120]*768,2)
        d.update([60]*768,4)
        self.assertIsNone(d.last_motion)
        d.update([100]*100+[60]*668,6)
        d.update([100]*100+[60]*668,8)
        self.assertIsNone(d.last_motion)
        d.reset(); d.update([0]*768,10)
        self.assertEqual(d.consecutive,0)

    def test_private_configuration_and_invalid_roi(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'camera.json'
            p.write_text(json.dumps({'capture_url':'http://camera.local/capture'}))
            self.assertTrue(configuration(p)['observe'])
            p.write_text(json.dumps({'capture_url':'http://camera.local/capture','roi':[1,0,0,1]}))
            with self.assertRaises(ValueError): configuration(p)

    def test_stale_camera_is_not_fresh_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'motion.json';p.write_text(json.dumps({'checked':100,'online':True,'observe':False}))
            r=MotionReader(p)
            self.assertTrue(r.snapshot(101)['online'])
            self.assertEqual(r.snapshot(116)['state'],'unavailable')

    def test_observation_draws_nothing_and_eye_stays_local(self):
        for radius,size,center in [(8,(480,320),(366,15)),(12,(1280,720),(208,35))]:
            s=pygame.Surface(size);s.fill('black')
            before=pygame.image.tostring(s,'RGB')
            draw(s,{'observe':True},100,center,radius)
            self.assertEqual(before,pygame.image.tostring(s,'RGB'))
            draw(s,{'observe':False,'online':True,'last_motion':100,'last_pulse':100},100,center,radius)
            self.assertNotEqual(before,pygame.image.tostring(s,'RGB'))
            outside=s.copy();pygame.draw.rect(outside,'black',(center[0]-radius-2,center[1]-radius-2,2*radius+4,2*radius+4))
            self.assertEqual(before,pygame.image.tostring(outside,'RGB'))
