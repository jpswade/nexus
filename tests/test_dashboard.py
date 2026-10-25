import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from zoneinfo import ZoneInfo

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
from pi_dashboard.config import load_config, save_config
from pi_dashboard.__main__ import Dashboard
from pi_dashboard.widgets import BackgroundWidget, parse_event

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.font.init()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "config.json"
        self.config = json.loads((ROOT / "home.example.json").read_text())
        save_config(self.path, self.config)
        self.app = None

    def tearDown(self):
        if self.app:
            self.app.close()
        pygame.quit()
        self.temp.cleanup()

    def start(self):
        self.app = Dashboard(self.path, windowed=True, no_network=True)
        return self.app

    def test_bounds_and_duplicate_ids_rejected(self):
        self.config["widgets"][0]["rect"] = [0.9, 0, 0.5, 1]
        save_config(self.path, self.config)
        with self.assertRaises(ValueError):
            load_config(self.path)
        self.config["widgets"][0]["rect"] = [0, 0, 1, 1]
        self.config["widgets"][1]["id"] = "clock"
        save_config(self.path, self.config)
        with self.assertRaises(ValueError):
            load_config(self.path)

    def test_editor_move_resize_and_save_roundtrip(self):
        app = self.start()
        app.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
        app.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
        original = app.rect(app.widgets[0])
        app.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0))
        self.assertEqual(app.rect(app.widgets[0]).x, original.x+8)
        app.event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, mod=pygame.KMOD_SHIFT))
        self.assertEqual(app.rect(app.widgets[0]).height, original.height+8)
        app.save()
        self.assertEqual(load_config(self.path)["widgets"][0]["rect"], app.widgets[0].spec["rect"])
        app.set_rect(app.widgets[0], pygame.Rect(-100, -100, 9000, 9000))
        self.assertEqual(app.rect(app.widgets[0]), app.screen.get_rect())

    def test_bad_reload_preserves_layout_and_cannot_overwrite_external_edit(self):
        app = self.start()
        old = app.widgets
        self.path.write_text("{")
        with self.assertLogs(level="ERROR"):
            app.step()
        self.assertIs(app.widgets, old)
        app.save()
        self.assertEqual(self.path.read_text(), "{")
        self.assertIn("changed externally", app.message)
        save_config(self.path, self.config)
        app.reload()
        self.assertIsNot(app.widgets, old)

    def test_builtin_and_plugin_render(self):
        self.config["widgets"].extend([
            {"id": "countdown", "type": "countdown", "rect": [0, 0, .3, .3],
             "options": {"date": "2026-01-01", "repeat_days": 14}},
            {"id": "metric", "type": "plugins.example:Metric", "rect": [.3, 0, .3, .3]},
        ])
        save_config(self.path, self.config)
        app = self.start()
        for widget in app.widgets:
            if widget.spec["type"] == "weather":
                widget.data = {"temperature": "12°C", "feels": "10°C", "wind": "6 mph", "description": "Rain"}
                widget.error = "offline"
            if widget.spec["type"] == "agenda":
                widget.data = [parse_event({"title": "Appointment", "start": "2099-01-01"}, ZoneInfo("UTC"))]
            if widget.spec["type"] == "plugins.example:Metric":
                widget.data = {"value": 12, "unit": "books"}
            widget.draw(pygame.Surface((600, 360)), dt.datetime.now(ZoneInfo("Europe/London")))
        app.draw(dt.datetime.now(app.context["timezone"]))

    def test_one_broken_widget_does_not_stop_dashboard(self):
        app = self.start()
        def broken(*args):
            raise RuntimeError("test")
        app.widgets[0].draw = broken
        with self.assertLogs(level="ERROR"):
            app.step()
        self.assertTrue(app.running)

    def test_agenda_timezone_and_all_day(self):
        tz = ZoneInfo("Europe/London")
        event = parse_event({"start": "2026-06-01T10:00:00Z"}, tz)
        self.assertEqual(event["start_dt"].hour, 11)
        all_day = parse_event({"start": "2026-06-01"}, tz)
        self.assertEqual(all_day["end_dt"].date(), dt.date(2026, 6, 2))

    def test_background_failure_retains_good_data(self):
        class Failing(BackgroundWidget):
            def fetch(self):
                self._stop.set()
                raise OSError("offline")
        widget = Failing({"id": "test", "type": "test"},
                         {"theme": {}, "base": ROOT})
        widget.data = {"value": 42}
        with self.assertLogs(level="WARNING"):
            worker = threading.Thread(target=widget._run)
            worker.start()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(widget.snapshot()[:2], ({"value": 42}, "Update failed"))


if __name__ == "__main__":
    unittest.main()
