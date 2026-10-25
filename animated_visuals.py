"""Small decorative vector animations, cached at six frames per second."""
import math
import pygame


class Visuals:
    def __init__(self):
        self.cache={}

    def frame(self, kind, seconds):
        tick=int(max(0,seconds)*6)
        key=(kind,tick%144)
        if key in self.cache:
            return self.cache[key]
        t=key[1]/6
        s=pygame.Surface((112,82))
        s.fill('#091321')
        cyan,dim,violet=(85,230,237),(30,71,88),(117,108,177)
        if kind=='water':
            for band in range(4):
                points=[(x,23+band*11+5*math.sin(x*.08-t*1.6+band*.8)) for x in range(5,108,3)]
                pygame.draw.lines(s,cyan if band==1 else dim,False,points,1)
        elif kind in ('wind','weather'):
            for band in range(3):
                y=18+band*22
                pygame.draw.line(s,dim,(6,y),(89,y))
                pygame.draw.arc(s,cyan,(78,y-12,22,24),-math.pi/2,math.pi/2,1)
                x=8+int((t*28+band*29)%76)
                pygame.draw.line(s,cyan,(x,y),(min(89,x+18),y),2)
        else:
            cx,cy,r=56,40,29
            pygame.draw.circle(s,dim,(cx,cy),r,1)
            yaw=t*.5
            for meridian in range(6):
                points=[]
                longitude=yaw+meridian*math.pi/6
                for i in range(25):
                    latitude=-math.pi/2+i*math.pi/24
                    points.append((cx+r*math.cos(latitude)*math.sin(longitude),cy+r*math.sin(latitude)))
                pygame.draw.lines(s,cyan if math.cos(longitude)>0 else dim,False,points)
            for offset in (-15,0,15):
                width=math.sqrt(r*r-offset*offset)
                pygame.draw.ellipse(s,dim,(cx-width,cy+offset-4,width*2,8),1)
            pygame.draw.ellipse(s,violet,(9,28,94,24),1)
            x,y=cx+47*math.cos(t*.8),40+12*math.sin(t*.8)
            pygame.draw.circle(s,cyan,(round(x),round(y)),3)
            for quadrant in range(4):
                start=t*.25+quadrant*math.pi/2
                pygame.draw.arc(s,cyan,(18,2,76,76),start,start+.6,1)
        # Cache only the current frame for each animation kind.
        self.cache={k:v for k,v in self.cache.items() if k[0]!=kind}
        self.cache[key]=s
        return s
