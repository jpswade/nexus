"""Cached Natural Earth basemap with a configured-location marker, not attack telemetry."""
import json
import math
from pathlib import Path
import pygame
from terminal_theme import font


def project(lon, lat):
    return 24+(lon+11)*31, 26+(61.2-lat)*38


class UKMap:
    def __init__(self, location=None):
        self.location = location or {}
        self.base = pygame.Surface((480, 480))
        self.base.fill('#071321')
        for x in range(0,480,24):
            for y in range(0,480,24):
                self.base.set_at((x,y),'#163044')
        document=json.loads((Path(__file__).parent/'data/uk-map.geojson').read_text())
        for feature in document['features']:
            for polygon in feature['geometry']['coordinates']:
                ring=polygon[0]
                if not all(-12 <= lon <= 3 and 49 <= lat <= 62 for lon,lat in ring):
                    continue
                points=[project(lon,lat) for lon,lat in ring]
                pygame.draw.polygon(self.base,'#11334b' if feature['properties']['name']=='United Kingdom' else '#0c2131',points)
                pygame.draw.lines(self.base,'#285970',True,points,1)
        pygame.draw.circle(self.base,'#285970',(76,94),33,1)
        pygame.draw.circle(self.base,'#163044',(76,94),42,1)
        pygame.draw.lines(self.base,'#68c6df',False,[(69,100),(76,72),(83,100)],2)
        self.base.blit(font(14).render('N',True,'#8cd3df'),(72,48))
        face=font(13)
        for label,lon,lat in [('SCOTLAND',-5.3,57.5),('ENGLAND',-2.0,52.7),('WALES',-5.0,52),('N. IRELAND',-8.1,55.3),('IRELAND',-9.5,53.1),('SHETLAND',-1.6,61.0)]:
            self.base.blit(face.render(label,True,'#6f9aad'),project(lon,lat))
        self.small=font(13)

    def draw(self, age):
        frame=self.base.copy()
        # A narrow moving scan line is display decoration, not a detected event.
        y=20+int(age*14)%425
        pygame.draw.line(frame,'#163b50',(10,y),(468,y))
        lon,lat=self.location.get('longitude'),self.location.get('latitude')
        if lon is not None and lat is not None and -11<lon<3 and 49<lat<61.2:
            x,y=project(lon,lat)
            radius=8+int(age*5)%16
            pygame.draw.circle(frame,'#215d76',(int(x),int(y)),radius,1)
            pygame.draw.circle(frame,'#68efff',(int(x),int(y)),4)
            pygame.draw.lines(frame,'#68efff',False,[(x,y),(x+30,y-30),(min(450,x+115),y-30)])
            frame.blit(self.small.render('CONFIGURED AREA',True,'#a3e6ef'),(min(345,x+32),y-47))
        frame.blit(self.small.render('BASEMAP / UK + IRELAND',True,'#78a8bb'),(12,446))
        frame.blit(self.small.render('SCAN = VISUAL FX / NO INCIDENT PINS',True,'#52798b'),(12,466))
        return frame
