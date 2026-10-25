# Pi Dashboard

A configurable Pygame display for clock, weather, appointments and your own information. Python 3.9+ and Pygame 2.5+; no browser, web server, or cloud account required for the dashboard. Designed to keep work modest on a Pi 2: one redraw per second, cached fonts, and background data fetching. Actual Pi performance and display access still need testing on your hardware.

## Run on your computer

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp home.example.json home.json
.venv/bin/python -m pi_dashboard --windowed
```

Run these commands from this project directory. On Windows use `.venv\Scripts\python` instead of `.venv/bin/python`; install `tzdata` if Python cannot find timezone data. The included `home.json` can be used directly if already present.

## Controls

- **E** toggles layout editing. Drag a widget to move it; drag its bottom-right corner to resize.
- **Tab** selects the next widget in edit mode. **Arrow keys** move it; **Shift + arrows** resize.
- **S** saves the layout to your config file. Changes are otherwise held only in memory.
- **R** reloads configuration, discarding unsaved layout changes.
- **Esc / Q** quits.

The config file is also watched every two seconds outside edit mode. Invalid reloads preserve the working dashboard. Saving refuses to overwrite a config changed externally since the last successful load. Rectangles are fractions of the screen, so saved layouts adapt to resolution. Overlaps are allowed; later widgets draw on top. Resize a widget or adjust `font_scale` when changing to a much smaller screen.

## Configure your screen

Edit `home.json`. `timezone` is an IANA name such as `Europe/London`. `display` contains windowed `width` and `height`, `fullscreen` (uses the actual screen size), and input-polling `fps` (default 10). Rendering is once per second outside editing; seconds can be shown using `%H:%M:%S`.

`theme` accepts `background`, `panel`, `text`, `muted`, `accent`, `border`, `error` as colour strings, and optional `font` as a TTF file path relative to the config. Each widget can override theme entries. The bundled Share Tech Mono font is used by default.

Each entry in `widgets` has a unique `id`, `type`, `title`, `rect: [x, y, width, height]`, optional `enabled: false`, and `options`. Coordinates and dimensions range from 0 to 1 and must fit on screen. Duplicate any widget with a new ID to show multiple locations, clocks, or sources. All widgets accept `options.font_scale` (default 1).

Built-in widget types:

- `clock`: `format` and `date_format` use Python `strftime` formatting.
- `weather`: `latitude`, `longitude`, `temperature_unit` (`celsius` / `fahrenheit`), `wind_speed_unit` (`kmh`, `ms`, `mph`, `kn`), and `refresh_seconds` (default 600). The example uses 900 seconds. Set its title to your location.
- `agenda`: `source` is a local JSON file or an HTTPS URL; `limit` defaults to 3. Set `refresh_seconds` to 30 for a local file or a longer interval for a remote source.
- `text`: `text` supports wrapping and newlines; `size` is the font size.
- `countdown`: `date` is `YYYY-MM-DD`, `label` is your description, and optional `repeat_days` advances past dates in fixed day intervals (for example 14 for recycling collections). This is not a calendar-month recurrence.
- `system`: CPU load and, on Linux where available, CPU temperature. Load is the operating system's one-minute load average, not a percentage.

Weather uses Nexus’s location when `config.json` exists. You can override it by adding coordinates to its options, for example London:

```json
"options": {
  "latitude": 51.5074,
  "longitude": -0.1278,
  "temperature_unit": "celsius",
  "wind_speed_unit": "mph",
  "refresh_seconds": 900
}
```

Weather uses [Open-Meteo's forecast API](https://open-meteo.com/en/docs); current conditions are model data. Attribution is displayed in the widget. Check the provider's terms for commercial use. Failed refreshes preserve the last successful value in memory and show an offline indicator. There is no disk weather cache; after a restart without internet the widget shows unavailable.

Agenda data lives in `data/agenda.json`, initially an empty list. Example:

```json
[
  {"title": "Dentist", "start": "2026-11-02T10:00:00+00:00", "end": "2026-11-02T10:30:00+00:00"},
  {"title": "Day off", "start": "2026-11-03"}
]
```

Events remain visible until their end; a missing end defaults to one hour for timed events or the next day for all-day events. An explicit end is exclusive. Times without an offset use the configured timezone; explicit offsets are preferable around daylight-saving changes. The agenda accepts JSON only: Google/Outlook authentication, ICS feeds and recurring calendar expansion are extension work, not built-in integrations.

A countdown widget can replace the system widget:

```json
{
  "id": "bins", "type": "countdown", "title": "Recycling",
  "rect": [0.615, 0.725, 0.36, 0.23],
  "options": {"date": "2026-11-02", "repeat_days": 14, "label": "Put the blue bin out"}
}
```

## Add any custom widget

Create `plugins/my_widget.py`, subclass `Widget`, and use `"type": "plugins.my_widget:MyWidget"`. `plugins/example.py` contains a working JSON metric widget. To try it, replace a widget's type with `plugins.example:Metric` and set `options.source` to `data/metric.json`.

```python
from pi_dashboard.widgets import Widget

class MyWidget(Widget):
    def draw(self, surface, now):
        self.panel(surface)
        self.text(surface, "Hello from my widget", (22, 55), 30, "accent")
```

The constructor receives `spec` (the widget config) and `context` (`base`, `theme`, `timezone`). `draw(surface, now)` gets a clipped widget surface and a timezone-aware datetime. `update(now)` runs on the input loop. Keep both fast. `close()` releases resources on reload or shutdown. Python module changes require restarting the app; config changes do not.

For network or file sources, subclass `BackgroundWidget` and implement `fetch()` returning data. In `draw`, call `snapshot()` for `(data, error, last_success_timestamp)`. One daemon worker polls each widget; the helper `read_json` supports HTTPS with a 10-second timeout and a 1 MiB response limit, or a local file. Keep custom fetches bounded, and never call Pygame from a worker. A failing widget is isolated so the rest keep drawing. Minimum refresh interval is five seconds.

Custom modules are ordinary trusted Python code, with the permissions of the user running the app. Use environment variables for any API secrets your own plugin needs instead of committing them to config. Config-relative file paths work with `--config /path/to/home.json`; plugin modules must remain importable from the project or Python path.

## Run within Nexus

Both views are installed by the repository's `scripts/install.sh`; see [README.md](README.md) for Pi deployment. Run `python3 launch.py home` for this view, or `python3 launch.py nexus` for the security and observatory view. **F5** switches between them in the same service process. Save edits with **S** before switching; unsaved changes are discarded.

The home view reads `home.json`. Its weather widget uses `location_source: "config.json"` to share Nexus's location. Explicit latitude and longitude in the widget options override that source. Set `NEXUS_HOME_CONFIG` to use an alternate home config across F5 switches. The font and colours come from `terminal_theme.py`, with per-widget overrides still supported. The bundled Share Tech Mono font is distributed under the SIL Open Font License; see `assets/fonts/OFL.txt`.

## Verification and limitations

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pi_dashboard --config home.example.json --check
.venv/bin/python -m pi_dashboard --config home.example.json --screenshot preview.png
```

Screenshot mode renders immediately without fetching data, so remote/local background widgets initially say loading. Tests use SDL's dummy display, exercise editing/save/reload, event timezones, plugin rendering, and retention of data after a failed fetch. Pi 2 graphics, CPU usage, boot startup, and HDMI behaviour require a real-device test. Layout changes and widget configuration are supported; calendar service integrations, touch-specific gestures, and an on-screen settings form are not included.
