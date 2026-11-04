"""Low-cost G/R/S meters, bulletin validity and UK forecast context."""
import pygame
from space_weather import utc

BG = (10, 21, 29)
TEXT = (229, 240, 241)
DIM = (139, 166, 178)
TEAL = (72, 213, 200)
AMBER = (249, 185, 104)
LINE = (31, 52, 63)


class SpaceWeatherPanel:
    def __init__(self, feeds):
        self.feeds = feeds
        self.fonts = {}
        self.key = None
        self.image = None

    def draw(self, size, now, age):
        compact = size[1] < 200
        page = int(age//8) % 3
        key = (size, int(now), page)
        if key == self.key:
            return self.image
        self.key = key
        surface = pygame.Surface(size)
        surface.fill(BG)
        width, height = size
        margin = 9 if compact else 20

        def text(value, x, y, font_size=14, colour=TEXT, max_width=None):
            if font_size not in self.fonts:
                self.fonts[font_size] = pygame.font.SysFont('dejavusans', font_size)
            font = self.fonts[font_size]
            available = width-x-margin if max_width is None else max_width
            value = str(value)
            if font.size(value)[0] > available:
                while value and font.size(value+'…')[0] > available:
                    value = value[:-1]
                value += '…'
            surface.blit(font.render(value, True, colour), (x, y))

        def wrap(value, y, count=3, font_size=18):
            row, rows = '', []
            font = self.fonts.get(font_size) or pygame.font.SysFont('dejavusans', font_size)
            for word in value.split():
                trial = (row+' '+word).strip()
                if row and font.size(trial)[0] > width-margin*2:
                    rows.append(row)
                    row = word
                else:
                    row = trial
            rows.append(row)
            if len(rows) > count:
                rows[count-1] += ' …'
            for i, line in enumerate(rows[:count]):
                text(line, margin, y+i*(font_size+4), font_size)

        data = self.feeds.snapshot(now)
        source = data['scales' if page == 0 else 'met' if page == 1 else 'alerts']
        status = source['status'].upper()
        text('SPACE WEATHER' if compact else 'INFRASTRUCTURE / SPACE WEATHER', margin, 4 if compact else 14, 13 if compact else 18, TEAL)
        text((('NOAA / global' if page != 1 else 'Met Office / UK') if compact else ('NOAA SWPC / global' if page != 1 else 'Met Office / UK context'))+' / '+status,
             margin, 23 if compact else 47, 12 if compact else 16,
             AMBER if status in ('STALE', 'UNAVAILABLE') else DIM)
        if page == 0:
            rows = source.get('rows', [])
            observed = next((r for r in rows if r['kind'] == 'observation'), {})
            values = observed.get('levels', {})
            for i, axis in enumerate('GRS'):
                x = margin+i*(width-2*margin)//3
                value = values.get(axis)
                text(axis+(' —' if value is None else str(value)), x, 41 if compact else 90,
                     24 if compact else 40, DIM if value is None else TEXT)
                for index in range(5):
                    pygame.draw.rect(surface, AMBER if value is not None and index < value else LINE,
                                     (x+index*(min(17,(width-2*margin)//15) if compact else 27), 73 if compact else 149,
                                      min(13,(width-2*margin)//15-3) if compact else 21, 4 if compact else 9))
                if not compact:
                    text({'G': 'Geomagnetic', 'R': 'Radio blackout', 'S': 'Solar radiation'}[axis], x, 172, 14)
            text('Observed '+utc(observed.get('issued'))+' / global scales', margin,
                 82 if compact else 209, 12 if compact else 15, DIM)
            if not compact:
                text('NOAA forecasts / UTC days', margin, 253, 17, TEAL)
                forecasts = [r for r in rows if r['kind'] == 'forecast']
                if not forecasts:
                    text('Forecast data unavailable', margin, 286, 15, DIM)
                for i, row in enumerate(forecasts):
                    state = 'expired' if now >= row['end'] else 'forecast'
                    g = row['levels']['G']
                    text(utc(row['start']).split(' 00:')[0]+' / '+state+' / G'+(str(g) if g is not None else '—'), margin, 286+i*48, 15)
                    p = row['probabilities']
                    fmt = lambda value: '—' if value is None else str(value)+'%'
                    text('R1–2 '+fmt(p['RMinorProb'])+' / R3–5 '+fmt(p['RMajorProb'])+' / S1+ '+fmt(p['SProb']), margin, 307+i*48, 12, DIM)
                text('R: sunlit side; G/S: impacts vary by latitude and system', margin, 450, 12, DIM)
                text('Zero = below scale threshold; — = missing, never zero', margin, 475, 12, DIM)
        elif page == 1:
            if source.get('headline'):
                wrap(source['headline'], 43 if compact else 103, 2 if compact else 6, 16 if compact else 24)
                text('Issued '+utc(source['issued']), margin, 86 if compact else 318, 12 if compact else 16, DIM)
                text('Four-day outlook / '+('EXPIRED' if now >= source['end'] else 'forecast'), margin,
                     102 if compact else 353, 12 if compact else 16, DIM)
                if not compact:
                    wrap('UK context; global space-weather forecast. Headline only: open Met Office for day-by-day detail.', 401, 3, 17)
                    text('Met Office', margin, 482, 12, DIM)
            else:
                wrap('UK forecast unavailable. Open Met Office for context.', 48 if compact else 120, 2 if compact else 4, 16 if compact else 24)
        else:
            rows = source.get('rows', [])
            active = [r for r in rows if r['state'] == 'active']
            candidates = active or rows
            row = candidates[int(age//24)%len(candidates)] if candidates else None
            if row:
                text(('LAST KNOWN ' if status == 'STALE' else '')+row['state'].upper()+' / '+row['kind'], margin, 42 if compact else 92, 14 if compact else 22, AMBER)
                wrap(row['title'], 61 if compact else 140, 1 if compact else 4, 15 if compact else 23)
                text('Valid '+utc(row['start'])+' → '+utc(row['end']), margin, 84 if compact else 282, 11 if compact else 14, DIM)
                text('Issued '+utc(row['issued']), margin, 100 if compact else 312, 11 if compact else 14, DIM)
                if not compact:
                    wrap(row['geography'], 358, 3, 17)
                    text(str(len(active))+' in-window warnings/watches in returned feed', margin, 451, 13, DIM)
                    text('Tests, historical observations and unknown validity are not active', margin, 479, 12, DIM)
            else:
                wrap('No bulletins returned; not an all-clear.' if status == 'EMPTY' else 'Bulletin check unavailable.',
                     48 if compact else 120, 2 if compact else 4, 16 if compact else 24)
        if compact and page == 0:
            text('G geomagnetic / R radio / S radiation', margin, 101, 11, DIM)
        if not compact:
            text('Last successful check '+utc(source.get('fetched')), margin, 503, 11, DIM)
        text('Local grid/GPS status not assessed', margin, height-22, 12 if compact else 14, DIM)
        self.image = surface
        return surface
