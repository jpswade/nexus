"""Perspective, uniformly raised basemap; depth is styling, not terrain elevation."""
import json
import math
from pathlib import Path
import pygame
from terminal_theme import font


def project(lon, lat, age=0, height=18):
    """Project geography and markers through the same slowly drifting camera."""
    x,y=(lon+4.5)*32,(55.5-lat)*38
    yaw=-.18+.065*math.sin(age*.12)
    x,y=x*math.cos(yaw)-y*math.sin(yaw),x*math.sin(yaw)+y*math.cos(yaw)
    tilt=.57+.035*math.sin(age*.09)
    depth=y*math.sin(tilt)+height*math.cos(tilt)
    scale=760/(760+depth)
    return 240+x*scale,244+(y*math.cos(tilt)-height*math.sin(tilt))*scale


class UKMap:
    def __init__(self, location=None):
        self.location=location or {}
        document=json.loads((Path(__file__).parent/'data/uk-map.geojson').read_text())
        self.rings=[]
        for feature in document['features']:
            for polygon in feature['geometry']['coordinates']:
                ring=polygon[0]
                if all(-12<=lon<=3 and 49<=lat<=62 for lon,lat in ring):
                    self.rings.append((feature['properties']['name']=='United Kingdom',ring))
        self.labels=[(font(13).render(label,True,'#8eb3bf'),lon,lat) for label,lon,lat in
                     [('SCOTLAND',-5.1,57.5),('ENGLAND',-2.4,52.7),('WALES',-5.1,52),
                      ('N. IRELAND',-8.5,55.3),('IRELAND',-9.3,53.1),('SHETLAND',-1.7,61)]]
        self.small=font(13)
        self.last_tick=None
        self.cached=None

    def draw(self, age):
        # Geometry redraw is capped at four frames per second for the Pi 2.
        tick=int(max(0,age)*4)
        if tick==self.last_tick:
            return self.cached
        age=tick/4
        frame=pygame.Surface((480,480))
        frame.fill('#091321')
        for lon in range(-11,4):
            points=[project(lon,lat,age,0) for lat in range(49,63)]
            pygame.draw.lines(frame,'#142d3e',False,points)
        for lat in range(49,63):
            pygame.draw.line(frame,'#142d3e',project(-11,lat,age,0),project(3,lat,age,0))
        # Shadow, lower edge and raised face create a shallow geographic model.
        # All land has equal height: no invented altitude or hazard intensity.
        for height in (-14,0,8,18):
            for uk,ring in self.rings:
                points=[project(lon,lat,age,height) for lon,lat in ring]
                colour=('#050d17' if height==-14 else '#143447' if height==0 else '#1c4b60' if height==8 else '#18465d' if uk else '#102e40')
                pygame.draw.polygon(frame,colour,points)
                if height in (0,18):
                    pygame.draw.lines(frame,'#367d95' if height==18 and uk else '#20495a',True,points,1)
        for label,lon,lat in self.labels:
            frame.blit(label,project(lon,lat,age))
        # Orientation instrument uses the same projection as the map.
        anchor=project(-9,60,age,0)
        north=project(-9,61,age,0)
        pygame.draw.circle(frame,'#31566b',tuple(map(int,anchor)),25,1)
        pygame.draw.line(frame,'#7cbfd4',anchor,north,2)
        frame.blit(self.small.render('N',True,'#9ddbe6'),(north[0]-4,north[1]-16))
        lon,lat=self.location.get('longitude'),self.location.get('latitude')
        if lon is not None and lat is not None and -11<lon<3 and 49<lat<61.2:
            x,y=project(lon,lat,age)
            pygame.draw.circle(frame,'#3f7e91',(int(x),int(y)),8+int(age*5)%16,1)
            pygame.draw.lines(frame,'#68efff',False,[(x,y),(x+25,y-35),(min(455,x+110),y-35)])
            frame.blit(self.small.render('CONFIGURED AREA',True,'#b5e6ed'),(min(345,x+27),y-52))
            pygame.draw.circle(frame,'#68efff',(int(x),int(y)),4)
        frame.blit(self.small.render('UK + IRELAND / PERSPECTIVE VIEW',True,'#78a8bb'),(12,446))
        frame.blit(self.small.render('RAISED BASEMAP / NOT TERRAIN',True,'#52798b'),(12,466))
        self.last_tick,self.cached=tick,frame
        return frame
