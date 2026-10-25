import copy
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from terminal_theme import PALETTE

THEME = {**PALETTE, "font": None}


def load_config(path):
    config = json.loads(Path(path).read_text())
    if not isinstance(config, dict):
        raise ValueError("Configuration must be an object")
    config.setdefault("display", {})
    display = config["display"]
    for key, default in (("width", 1280), ("height", 720), ("fps", 10)):
        value = display.setdefault(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"display.{key} must be a positive integer")
    if display["fps"] > 60:
        raise ValueError("display.fps must be at most 60")
    ZoneInfo(config.setdefault("timezone", "Europe/London"))
    config["theme"] = {**THEME, **config.get("theme", {})}
    widgets = config.get("widgets", [])
    if not isinstance(widgets, list):
        raise ValueError("widgets must be a list")
    ids = set()
    for widget in widgets:
        name = widget.get("id")
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("Every widget needs a unique string id")
        ids.add(name)
        if not isinstance(widget.get("type"), str):
            raise ValueError(f"{name}: missing widget type")
        options = widget.get("options", {})
        if not isinstance(options, dict):
            raise ValueError(f"{name}: options must be an object")
        for key in ("refresh_seconds", "font_scale", "size"):
            if key in options and (not isinstance(options[key], (int, float)) or
                                   not math.isfinite(options[key]) or options[key] <= 0):
                raise ValueError(f"{name}: {key} must be a positive number")
        if "limit" in options and (not isinstance(options["limit"], int) or options["limit"] < 1):
            raise ValueError(f"{name}: limit must be a positive integer")
        rect = widget.get("rect")
        if not isinstance(rect, list) or len(rect) != 4 or any(
            not isinstance(v, (float, int)) or isinstance(v, bool) or not math.isfinite(v)
            for v in rect
        ):
            raise ValueError(f"{name}: rect must be [x, y, width, height] fractions")
        x, y, w, h = rect
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > 1.000001 or y + h > 1.000001:
            raise ValueError(f"{name}: rect must fit inside the screen (0 to 1)")
    return config


def save_config(path, config):
    """Replace atomically; never leave a partially written configuration."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(copy.deepcopy(config), indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
