"""Widget API: draw(surface, now), optional update(now) and close()."""
import datetime as dt
import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pygame
from terminal_theme import font as terminal_font
from bitmap_font import ascii_box

LOG = logging.getLogger(__name__)


class Widget:
    def __init__(self, spec, context):
        self.spec = spec
        self.context = context
        self.options = spec.get("options", {})
        self.theme = {**context["theme"], **spec.get("theme", {})}
        self.fonts = {}

    def update(self, now):
        pass

    def close(self):
        pass

    def font(self, size):
        size = max(10, int(size * float(self.options.get("font_scale", 1))))
        if size not in self.fonts:
            filename = self.theme.get("font")
            if filename:
                filename = str(self.context["base"] / filename)
            self.fonts[size] = pygame.font.Font(filename, size) if filename else terminal_font(size)
        return self.fonts[size]

    def text(self, surface, text, xy, size=24, color="text", max_width=None):
        font = self.font(size)
        text = str(text)
        if max_width is None:
            max_width = surface.get_width() - xy[0] - 16
        if font.size(text)[0] > max_width:
            while text and font.size(text + "…")[0] > max_width:
                text = text[:-1]
            text += "…"
        surface.blit(font.render(text, True, self.theme.get(color, color)), xy)

    def panel(self, surface):
        surface.fill(self.theme["panel"])
        pygame.draw.rect(surface, self.theme["border"], surface.get_rect(), 1)
        pygame.draw.line(surface, self.theme["accent"], (0, 0), (60, 0), 3)
        self.text(surface, self.spec.get("title", self.spec["type"]).upper(), (22, 17), 20, "accent")
        pygame.draw.line(surface, self.theme["border"], (22, 43), (surface.get_width()-22, 43))

    def draw(self, surface, now):
        self.panel(surface)


class Clock(Widget):
    def draw(self, surface, now):
        self.panel(surface)
        size = min(surface.get_height() * .48, surface.get_width() * .24)
        self.text(surface, now.strftime(self.options.get("format", "%H:%M")), (20, 60), size)
        self.text(surface, now.strftime(self.options.get("date_format", "%A, %d %B %Y")),
                  (24, surface.get_height() - 48), 27, "accent")


class Text(Widget):
    def draw(self, surface, now):
        self.panel(surface)
        y = 60
        size = self.options.get("size", 26)
        # Word wrapping also respects explicit newlines.
        for paragraph in self.options.get("text", "Edit this widget in config.json").split("\n"):
            line = ""
            for word in paragraph.split():
                candidate = (line + " " + word).strip()
                if line and self.font(size).size(candidate)[0] > surface.get_width() - 44:
                    self.text(surface, line, (22, y), size)
                    y += self.font(size).get_linesize()
                    line = word
                else:
                    line = candidate
            self.text(surface, line, (22, y), size)
            y += self.font(size).get_linesize()


class BackgroundWidget(Widget):
    """One daemon worker per widget; no Pygame calls outside the main thread.

    Subclasses implement fetch() and return JSON-like data. Refresh failures
    retain the last successful result. close() stops future polls.
    """
    def __init__(self, spec, context):
        super().__init__(spec, context)
        self.data = None
        self.error = None
        self.updated = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker = None

    def update(self, now):
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                data = self.fetch()
                with self._lock:
                    self.data, self.error, self.updated = data, None, time.time()
            except Exception:
                LOG.warning("Data refresh failed for %s", self.spec["id"])
                with self._lock:
                    self.error = "Update failed"
            self._stop.wait(max(5, float(self.options.get("refresh_seconds", 600))))

    def snapshot(self):
        with self._lock:
            return self.data, self.error, self.updated

    def close(self):
        self._stop.set()

    def fetch(self):
        raise NotImplementedError

    def read_json(self, source):
        if source.startswith("https://"):
            request = urllib.request.Request(source, headers={"User-Agent": "PiDashboard/1.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read(1_048_577)
            if len(payload) > 1_048_576:
                raise ValueError("Response exceeds 1 MiB")
            return json.loads(payload)
        if "://" in source:
            raise ValueError("Use HTTPS or a local file")
        return json.loads((self.context["base"] / source).read_text())


def weather_description(code):
    if code == 0:
        return "Clear sky"
    if code in (1, 2, 3):
        return "Partly cloudy" if code != 3 else "Overcast"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunderstorms"
    return "Conditions unavailable"


class Weather(BackgroundWidget):
    def fetch(self):
        location = dict(self.options)
        if "latitude" not in location or "longitude" not in location:
            source = self.options.get("location_source")
            if source and (self.context["base"] / source).exists():
                location = {**self.read_json(source), **location}
        if "latitude" not in location or "longitude" not in location:
            return {"setup": True}
        params = urllib.parse.urlencode({
            "latitude": location["latitude"], "longitude": location["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "temperature_unit": self.options.get("temperature_unit", "celsius"),
            "wind_speed_unit": self.options.get("wind_speed_unit", "kmh"),
            "timezone": "auto",
        })
        data = self.read_json("https://api.open-meteo.com/v1/forecast?" + params)
        current, units = data["current"], data["current_units"]
        # Validate before publishing, retaining good data if the API changes.
        return {"temperature": f'{float(current["temperature_2m"]):.0f}{units["temperature_2m"]}',
                "feels": f'{float(current["apparent_temperature"]):.0f}{units["apparent_temperature"]}',
                "wind": f'{current["wind_speed_10m"]} {units["wind_speed_10m"]}',
                "description": weather_description(current["weather_code"])}

    def draw(self, surface, now):
        self.panel(surface)
        data, error, updated = self.snapshot()
        if data and data.get("setup"):
            self.text(surface, "Set your location", (22, 60), 32)
            self.text(surface, "Add latitude + longitude in config", (22, 105), 20, "muted")
        elif data:
            self.text(surface, data["temperature"], (20, 60), 64, "accent")
            self.text(surface, data["description"], (22, 123), 28)
            self.text(surface, f'Feels {data["feels"]}  /  Wind {data["wind"]}', (22, 159), 21, "muted")
        else:
            self.text(surface, "Weather unavailable" if error else "Loading weather…", (22, 62), 27)
        status = "Open-Meteo.com"
        if error:
            status += " · offline" + (" / showing last update" if data else "")
        elif updated and data and not data.get("setup"):
            stamp = dt.datetime.fromtimestamp(updated, self.context["timezone"])
            status += " · " + stamp.strftime("%H:%M")
        self.text(surface, status, (22, surface.get_height() - 27), 16, "muted")


def parse_event(event, timezone):
    start = dt.datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone)
    end = event.get("end")
    if end:
        end = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone)
    else:
        end = start + (dt.timedelta(days=1) if len(event["start"]) == 10 else dt.timedelta(hours=1))
    if end <= start:
        raise ValueError("Event end must be after start")
    return {**event, "start_dt": start.astimezone(timezone), "end_dt": end.astimezone(timezone)}


class Agenda(BackgroundWidget):
    def fetch(self):
        events = self.read_json(self.options.get("source", "data/agenda.json"))
        return sorted((parse_event(e, self.context["timezone"]) for e in events), key=lambda e: e["start_dt"])

    def draw(self, surface, now):
        self.panel(surface)
        data, error, _ = self.snapshot()
        events = [e for e in (data or []) if e["end_dt"] > now][:self.options.get("limit", 3)]
        y = 57
        if not events:
            self.text(surface, "Agenda unavailable" if error and data is None else
                      "Loading agenda…" if data is None else "Nothing scheduled", (22, y), 28)
        for event in events:
            start = event["start_dt"]
            when = start.strftime("%a %d %b")
            when += " · all day" if len(event["start"]) == 10 else start.strftime(" · %H:%M")
            self.text(surface, when, (22, y), 19, "accent")
            self.text(surface, event["title"], (22, y + 25), 29)
            y += 78
        if error:
            self.text(surface, "Update failed · retrying", (22, surface.get_height() - 27), 17, "error")


class Countdown(Widget):
    def draw(self, surface, now):
        self.panel(surface)
        target = dt.date.fromisoformat(self.options["date"])
        interval = int(self.options.get("repeat_days", 0))
        days = (target - now.date()).days
        if days < 0 and interval > 0:
            days %= interval
        label = "Today" if days == 0 else f"{days} days" if days > 0 else f"{abs(days)} days ago"
        self.text(surface, label, (22, 60), 48, "accent")
        self.text(surface, self.options.get("label", "Next event"), (22, 109), 25)


class System(Widget):
    def draw(self, surface, now):
        import os
        self.panel(surface)
        try:
            load = os.getloadavg()[0]
            value = f"Load  {load:.2f}"
        except (AttributeError, OSError):
            value = "Load unavailable"
        self.text(surface, value, (22, 60), 32)
        try:
            temperature = float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
            self.text(surface, f"CPU  {temperature:.0f}°C", (22, 96), 25, "accent")
        except (ValueError, OSError):
            self.text(surface, "Temperature unavailable", (22, 96), 20, "muted")


BUILTINS = {"clock": Clock, "weather": Weather, "agenda": Agenda,
            "text": Text, "countdown": Countdown, "system": System}
