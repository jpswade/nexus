"""Rotating geographic globe; only the configured location is marked."""
import json
import math
from pathlib import Path
import pygame


def vector(lon, lat):
    lon,lat=math.radians(lon),math.radians(lat)
    return math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)


class ObservatoryGlobe:
    def __init__(self, location=None):
        self.location=location or {}
        rings=json.loads((Path(__file__).parent/'data/land.json').read_text())
        self.coasts=[[vector(*p) for p in ring] for ring in rings]
        self.grid=[[vector(lon,lat) for lon in range(-180,181,6)] for lat in range(-60,61,30)]
        self.grid += [[vector(lon,lat) for lat in range(-90,91,6)] for lon in range(-180,180,30)]
        self.surface=pygame.Surface((568,370))

    def draw(self, seconds):
        s=self.surface
        s.fill('#091321')
        cx,cy,r=284,185,162
        longitude=math.radians(-15+seconds*2.5)
        latitude=math.radians(28)
        cs,sn,ct,st=math.cos(longitude),math.sin(longitude),math.cos(latitude),math.sin(latitude)
        def project(v):
            x,y,z=v
            return cx+r*(-x*sn+y*cs),cy-r*(ct*z-st*(x*cs+y*sn)),ct*(x*cs+y*sn)+st*z
        pygame.draw.circle(s,'#1b3b49',(cx,cy),r+12,1)
        pygame.draw.circle(s,'#32505a',(cx,cy),r,1)
        for angle in range(0,360,10):
            a=math.radians(angle)
            pygame.draw.line(s,'#41606a',(cx+(r+18)*math.cos(a),cy+(r+18)*math.sin(a)),(cx+(r+22)*math.cos(a),cy+(r+22)*math.sin(a)))
        for rings,colour in ((self.grid,'#203843'),(self.coasts,'#91adb1')):
            for ring in rings:
                points=[]
                for v in ring:
                    x,y,z=project(v)
                    if z>=0:points.append((x,y))
                    else:
                        if len(points)>1:pygame.draw.lines(s,colour,False,points)
                        points=[]
                if len(points)>1:pygame.draw.lines(s,colour,False,points)
        if 'longitude' in self.location and 'latitude' in self.location:
            x,y,z=project(vector(self.location['longitude'],self.location['latitude']))
            if z>0:
                pygame.draw.circle(s,'#66865d',(int(x),int(y)),7+int(seconds*5)%14,1)
                pygame.draw.circle(s,'#d4e7a0',(int(x),int(y)),3)
        return s
