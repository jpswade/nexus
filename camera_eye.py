"""A small non-flashing motion iris; never changes navigation or alerts."""
import math
import pygame


def draw(surface, sample, now, center, radius=12):
    if not sample or sample.get('observe', True):
        return
    online = sample.get('online', False)
    last = sample.get('last_motion')
    elapsed = now-last if last is not None else 1000
    strength = max(0., min(1., (32-elapsed)/20)) if online else 0
    colour = tuple(round(a+(b-a)*strength) for a,b in zip((75,104,112),(72,213,200)))
    x,y = center
    pygame.draw.circle(surface, colour, center, radius, 1)
    if not online:
        pygame.draw.line(surface, colour, (x-radius+3,y+radius-3),(x+radius-3,y-radius+3),1)
        return
    aperture = max(2, round(radius*(.25+.35*strength)))
    pygame.draw.ellipse(surface, colour, (x-radius+3,y-aperture,2*radius-6,2*aperture),1)
    pygame.draw.circle(surface, colour, center, max(1,round(2+strength)))
    pulse = sample.get('last_pulse')
    if pulse is not None and 0 <= now-pulse <= 2:
        angle = (now-pulse)*math.pi
        pygame.draw.arc(surface,colour,(x-radius,y-radius,2*radius,2*radius),angle,angle+.7,2)
