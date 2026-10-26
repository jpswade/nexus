import unittest
from warning_led import should_flash

class LEDTests(unittest.TestCase):
    def test_only_fresh_current_warnings_flash(self):
        for source,detail in [('weather','IN FORCE / UNTIL 21:00'),('floods','FLOOD ALERT'),('threat','OFFICIAL NATIONAL ASSESSMENT')]:
            self.assertTrue(should_flash([dict(source=source,detail=detail,stale=False)]))
            self.assertFalse(should_flash([dict(source=source,detail=detail,stale=True)]))
        for detail in ('UPCOMING','LISTED / CHECK VALIDITY AT SOURCE'):
            self.assertFalse(should_flash([dict(source='weather',detail=detail,stale=False)]))
        self.assertFalse(should_flash([]))
