import argparse
import datetime as dt
import importlib
import logging
import os
from pathlib import Path
import signal
import sys
import time
from zoneinfo import ZoneInfo

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from .config import load_config, save_config
from .widgets import BUILTINS, Widget

LOG = logging.getLogger(__name__)


class Dashboard:
    def __init__(self, path, windowed=False, no_network=False):
        self.path = Path(path).resolve()
        self.windowed = windowed
        self.no_network = no_network
        self.widgets = []
        self.editing = False
        self.selected = None
        self.drag = None
        self.running = True
        self.message = ""
        self.message_until = 0
        self.config = None
        self.mtime = None
        self.observed_mtime = None
        self.last_watch = 0
        self.last_render = 0
        self.dirty = True
        self.reload(initial=True)

    def notify(self, message):
        self.message = message
        self.message_until = time.monotonic() + 6
        self.dirty = True

    def reload(self, initial=False):
        candidate = []
        try:
            config = load_config(self.path)
            for key, color in config["theme"].items():
                if key != "font":
                    pygame.Color(color)
            context = {"base": self.path.parent, "theme": config["theme"],
                       "timezone": ZoneInfo(config["timezone"])}
            for spec in config.get("widgets", []):
                if not spec.get("enabled", True):
                    continue
                kind = spec["type"]
                if kind in BUILTINS:
                    cls = BUILTINS[kind]
                else:
                    module, name = kind.split(":", 1)
                    cls = getattr(importlib.import_module(module), name)
                    if not issubclass(cls, Widget):
                        raise ValueError("Custom widgets must extend Widget")
                widget = cls(spec, context)
                candidate.append(widget)
                # Validate fonts/colours before replacing the working layout.
                widget.font(20)
                for key, color in widget.theme.items():
                    if key != "font":
                        pygame.Color(color)
            display = config["display"]
            fullscreen = display.get("fullscreen", True) and not self.windowed
            size = (0, 0) if fullscreen else (display["width"], display["height"])
            flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
            if initial or display != self.config["display"]:
                screen = pygame.display.set_mode(size, flags)
                self.screen = screen
                pygame.display.set_caption("Pi Dashboard")
            for widget in self.widgets:
                widget.close()
            self.widgets = candidate
            self.config = config
            self.context = context
            self.selected = None
            self.drag = None
            self.mtime = self.path.stat().st_mtime_ns
            self.observed_mtime = self.mtime
            self.dirty = True
            if not initial:
                self.notify("Configuration reloaded")
        except Exception as exc:
            for widget in candidate:
                widget.close()
            if initial:
                raise
            LOG.exception("Configuration reload failed")
            self.notify(f"Reload failed: {exc}")
        pygame.mouse.set_visible(self.editing)

    def rect(self, widget):
        w, h = self.screen.get_size()
        x, y, rw, rh = widget.spec["rect"]
        return pygame.Rect(round(x*w), round(y*h), max(1, round(rw*w)), max(1, round(rh*h)))

    def save(self):
        try:
            if self.path.stat().st_mtime_ns != self.mtime:
                self.notify("File changed externally. Press R to reload before saving.")
                return
            save_config(self.path, self.config)
            self.mtime = self.path.stat().st_mtime_ns
            self.observed_mtime = self.mtime
            self.notify("Layout saved")
        except OSError as exc:
            self.notify(f"Save failed: {exc}")

    def event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            self.dirty = True
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False
            elif event.key == pygame.K_e:
                self.editing = not self.editing
                self.drag = None
                pygame.mouse.set_visible(self.editing)
                self.notify("Edit mode: drag to move, corner to resize, S to save" if self.editing else "Edit mode off (S saves changes)")
            elif event.key == pygame.K_s:
                self.save()
            elif event.key == pygame.K_r:
                self.reload()
            elif event.key == pygame.K_F5:
                from terminal_theme import switch_view
                self.close()
                pygame.quit()
                switch_view("nexus")
            elif event.key == pygame.K_TAB and self.editing and self.widgets:
                self.selected = 0 if self.selected is None else (self.selected + 1) % len(self.widgets)
                self.dirty = True
            elif self.editing and self.selected is not None:
                delta = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
                         pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}.get(event.key)
                if delta:
                    widget = self.widgets[self.selected]
                    rect = self.rect(widget)
                    if event.mod & pygame.KMOD_SHIFT:
                        rect.width += delta[0] * 8
                        rect.height += delta[1] * 8
                    else:
                        rect.move_ip(delta[0] * 8, delta[1] * 8)
                    self.set_rect(widget, rect)
        elif self.editing and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in reversed(range(len(self.widgets))):
                rect = self.rect(self.widgets[i])
                if rect.collidepoint(event.pos):
                    self.selected = i
                    resize = pygame.Rect(rect.right-22, rect.bottom-22, 22, 22).collidepoint(event.pos)
                    self.drag = (event.pos, rect.copy(), resize)
                    self.dirty = True
                    break
        elif self.editing and event.type == pygame.MOUSEMOTION and self.drag:
            origin, rect, resize = self.drag
            dx, dy = event.pos[0]-origin[0], event.pos[1]-origin[1]
            rect = rect.copy()
            if resize:
                rect.size = (rect.width+dx, rect.height+dy)
            else:
                rect.move_ip(dx, dy)
            self.set_rect(self.widgets[self.selected], rect)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.drag = None

    def set_rect(self, widget, rect):
        w, h = self.screen.get_size()
        rect.width = min(w, max(min(150, w), rect.width))
        rect.height = min(h, max(min(100, h), rect.height))
        rect.clamp_ip(self.screen.get_rect())
        widget.spec["rect"] = [rect.x/w, rect.y/h, rect.width/w, rect.height/h]
        self.dirty = True

    def draw(self, now):
        self.screen.fill(self.config["theme"]["background"])
        for i, widget in enumerate(self.widgets):
            rect = self.rect(widget).clip(self.screen.get_rect())
            if rect.width < 1 or rect.height < 1:
                continue
            surface = self.screen.subsurface(rect)
            try:
                widget.draw(surface, now)
            except Exception:
                if not getattr(widget, "_draw_failed", False):
                    LOG.exception("Widget %s failed", widget.spec["id"])
                    widget._draw_failed = True
                surface.fill(self.config["theme"]["panel"])
                font = pygame.font.Font(None, 24)
                surface.blit(font.render(f'{widget.spec["id"]}: check settings / log', True,
                                         self.config["theme"]["error"]), (16, 16))
            if self.editing:
                color = self.config["theme"]["accent" if self.selected == i else "border"]
                pygame.draw.rect(self.screen, color, rect, 2)
                pygame.draw.rect(self.screen, color, (rect.right-14, rect.bottom-14, 12, 12))
        if self.editing or time.monotonic() < self.message_until:
            message = self.message if time.monotonic() < self.message_until else "EDIT · drag / resize · Tab + arrows · Shift to resize · S save · R reload · E done"
            pygame.draw.rect(self.screen, "#101820", (0, 0, self.screen.get_width(), 28))
            self.screen.blit(pygame.font.Font(None, 20).render(message, True, "#bce59b"), (10, 6))
        pygame.display.flip()

    def step(self):
        for event in pygame.event.get():
            self.event(event)
        monotonic = time.monotonic()
        if monotonic - self.last_watch >= 2 and not self.editing:
            self.last_watch = monotonic
            try:
                stamp = self.path.stat().st_mtime_ns
                if stamp != self.observed_mtime:
                    # Only attempt each broken version once; R explicitly retries.
                    self.reload()
                    self.observed_mtime = stamp
            except OSError:
                pass
        now = dt.datetime.now(self.context["timezone"])
        for widget in self.widgets:
            if self.no_network and hasattr(widget, "fetch"):
                continue
            try:
                widget.update(now)
            except Exception:
                if not getattr(widget, "_update_failed", False):
                    LOG.exception("Widget update failed: %s", widget.spec["id"])
                    widget._update_failed = True
        # Poll input at configured fps, render once/second unless editing.
        if self.dirty or self.editing or monotonic - self.last_render >= 1:
            self.draw(now)
            self.last_render = monotonic
            self.dirty = False

    def close(self):
        for widget in self.widgets:
            widget.close()


def main():
    parser = argparse.ArgumentParser(description="Configurable Pygame dashboard")
    parser.add_argument("--config", default="home.json")
    parser.add_argument("--windowed", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate config and widget construction using a dummy display")
    parser.add_argument("--screenshot", help="Render one frame to a PNG with dummy display (no data fetching)")
    args = parser.parse_args()
    if args.check or args.screenshot:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        args.windowed = True
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    pygame.display.init()
    pygame.font.init()
    app = None
    try:
        app = Dashboard(args.config, args.windowed, no_network=bool(args.check or args.screenshot))
        if args.check:
            print(f"Valid configuration: {len(app.widgets)} widgets")
            return 0
        if args.screenshot:
            app.draw(dt.datetime.now(app.context["timezone"]))
            pygame.image.save(app.screen, args.screenshot)
            return 0
        def stop(*_):
            app.running = False
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        timer = pygame.time.Clock()
        LOG.info("Display backend: %s", pygame.display.get_driver())
        while app.running:
            app.step()
            timer.tick(app.config["display"]["fps"])
        return 0
    except Exception:
        LOG.exception("Dashboard failed to start")
        return 1
    finally:
        if app:
            app.close()
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
