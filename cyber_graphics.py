"""Decorative 3D wireframe instruments; no incident or location data."""
import math

TAU = math.tau
# Fixed topology keeps the Pi's per-frame work small and predictable.
RINGS = []
for latitude in (-60, -30, 0, 30, 60):
    lat = math.radians(latitude)
    RINGS.append(tuple((math.cos(lat)*math.cos(i*TAU/32), math.sin(lat),
                        math.cos(lat)*math.sin(i*TAU/32)) for i in range(33)))
for meridian in range(8):
    lon = meridian*math.pi/8
    RINGS.append(tuple((math.cos(i*TAU/32)*math.cos(lon), math.sin(i*TAU/32),
                        math.cos(i*TAU/32)*math.sin(lon)) for i in range(33)))


def draw_orb(ui, cx, cy, radius, seconds):
    yaw = seconds*.34
    tilt = .32 + .12*math.sin(seconds*.21)
    ca, sa, ct, st = math.cos(yaw), math.sin(yaw), math.cos(tilt), math.sin(tilt)

    def project(point):
        x, y, z = point
        x, z = x*ca+z*sa, z*ca-x*sa
        y, z = y*ct-z*st, y*st+z*ct
        return (cx+x*radius, cy+y*radius, z)

    for ring in RINGS:
        points = [project(point) for point in ring]
        for a, b in zip(points, points[1:]):
            front = (a[2]+b[2])/2 > 0
            ui.line(a[:2], b[:2], (42, 181, 201) if front else (16, 49, 67))
    # Two tilted orbital tracks with moving nodes, purely decorative.
    for band in range(2):
        phase = seconds*(.6 if band == 0 else -.45)+band*1.7
        rotation = .45 if band == 0 else -.55
        cr, sr = math.cos(rotation), math.sin(rotation)
        def orbit(angle):
            x, y = math.cos(angle)*radius*1.24, math.sin(angle)*radius*.37
            return cx+x*cr-y*sr, cy+x*sr+y*cr
        for i in range(48):
            ui.line(orbit(i*TAU/48), orbit((i+1)*TAU/48), (68, 60, 124) if band else (20, 81, 108))
        x, y = orbit(phase)
        color = (181, 151, 255) if band else (170, 244, 255)
        for a, b in [((x-5,y),(x,y-5)),((x,y-5),(x+5,y)),((x+5,y),(x,y+5)),((x,y+5),(x-5,y))]:
            ui.line(a,b,color,2)
    # Counter-rotating broken perimeter arcs, with a readable stationary core.
    for sector in range(4):
        start = sector*math.pi/2-seconds*.13
        for i in range(8):
            a, b = start+i*.075, start+(i+1)*.075
            ui.line((cx+math.cos(a)*radius*1.35, cy+math.sin(a)*radius*1.35),
                    (cx+math.cos(b)*radius*1.35, cy+math.sin(b)*radius*1.35), (88, 217, 231), 2)
    ui.line((cx-8,cy),(cx+8,cy),(166,233,245))
    ui.line((cx,cy-8),(cx,cy+8),(166,233,245))
