from pi_dashboard.widgets import BackgroundWidget


class Metric(BackgroundWidget):
    """Read {label, value, unit} from a local file or HTTPS endpoint."""
    def fetch(self):
        return self.read_json(self.options.get("source", "data/metric.json"))

    def draw(self, surface, now):
        self.panel(surface)
        data, error, updated = self.snapshot()
        if data:
            self.text(surface, f'{data["value"]} {data.get("unit", "")}', (22, 55), 48, "accent")
            self.text(surface, data.get("label", ""), (22, 110), 24)
        else:
            self.text(surface, "Unavailable" if error else "Loading…", (22, 55), 28)
        if error and data:
            self.text(surface, "Last known value · update failed", (22, surface.get_height()-25), 16, "error")
