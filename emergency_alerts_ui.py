"""Persistent emergency bulletin panel, independent of workspace rotation."""
import datetime as dt
import pygame
from emergency_alerts import CURRENT, presentation

def stamp(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).strftime('%d %b %H:%M UTC') if value is not None else 'not published'


def panel(data, now, age, size):
    compact = size[1] < 200
    width, height = size
    image = pygame.Surface(size)
    image.fill((12, 25, 33))
    font_size = 12 if compact else 17
    font = pygame.font.SysFont('dejavusans', font_size)
    step = 16 if compact else 25
    def fit(value):
        while value and font.size(value)[0] > width - 16: value = value[:-1]
        return value
    def text(value, y, colour=(225, 237, 239)):
        value = str(value)
        clipped = fit(value)
        if clipped != value: clipped = fit(clipped[:-2] + '…')
        image.blit(font.render(clipped, True, colour), (8, y))
    status, rows, stale = presentation(data, now)
    text(('GOV.UK ALERTS / ' if compact else 'GOV.UK EMERGENCY ALERTS / ') + status, 2, (249, 185, 104))
    if rows and height <= 30:
        row = rows[0]
        image.fill((12,25,33))
        text('GOV.UK ALERTS / ' + ('STALE / ' if stale else '') + row['status'].upper() + ' / not an all-clear', 2, (249,185,104))
        return image, row['url']
    if not rows:
        if height > 30:
            text('Local applicability unverified', step + 2)
            text('Checked: ' + stamp(data.get('fetched')), 2 * step + 2)
            text('gov.uk/alerts/current-alerts', 3 * step + 2)
        return image, CURRENT
    def wrapped(value):
        result = []; current = ''
        for word in value.split():
            candidate = (current + ' ' + word).strip()
            if current and font.size(candidate)[0] > width - 16:
                result.append(current); current = word
            else: current = candidate
        if current: result.append(current)
        return result
    count = 2 if compact else max(2, (height - 8 * step) // step)
    wrapped_rows = [wrapped(r['instructions'] + ' Area (as published): ' + r['area']) for r in rows]
    durations = [max(24, ((len(lines) + count - 1) // count) * 6) for lines in wrapped_rows]
    phase = age % sum(durations)
    selected = 0
    while phase >= durations[selected]:
        phase -= durations[selected]; selected += 1
    row = rows[selected]
    state = ('TEST / ' if row['test'] else '') + row['status'].upper()
    # Area remains explicitly attributed; never infer a match to local coordinates.
    text('%s [%s/%s] / Area: %s' % (state, selected + 1, len(rows), row['area']), step + 2)
    text('Issued: ' + stamp(row.get('issued')), 2 * step + 2)
    end = ('Broadcast stopped: ' + stamp(row['stopped'])) if row.get('stopped') else row['validity']
    text(end, 3 * step + 2)
    lines = wrapped_rows[selected]
    pages = max(1, (len(lines) + count - 1) // count)
    # Complete instruction text is paginated, not silently discarded.
    page = int(phase // 6) % pages
    for index, value in enumerate(lines[page * count:(page + 1) * count]):
        text(value, (4 + index) * step + 2)
    footer = height - 3 * step
    text('Instructions %s/%s / local applicability unverified' % (page + 1, pages), footer)
    text(row['url'].replace('https://www.', ''), footer + step)
    text(('LAST KNOWN / ' if stale else '') + 'GOV.UK Emergency Alerts', footer + 2 * step)
    return image, row['url']


def desktop(ui, data, now, age):
    _, rows, _ = presentation(data, now)
    # Persistent central card leaves threat/PHP/weather sidebars intact.
    box = (330, 105, 580, 537) if any(r['status'] == 'current' for r in rows) else (330, 74, 580, 25)
    x, y, w, h = box
    image, url = panel(data, now, age, (w, h))
    image = pygame.transform.smoothscale(image, (round(w * ui.scale), round(h * ui.scale)))
    ui.target.blit(image, ui.point(x, y))
    ui.register(box, url, bool(rows))


def companion(surface, data, now, age):
    _, rows, _ = presentation(data, now)
    box = (14, 110, 458, 148) if any(r['status'] == 'current' for r in rows) else (14, 241, 458, 20)
    x, y, w, h = box
    image, _ = panel(data, now, age, (w, h))
    surface.blit(image, (x, y))
