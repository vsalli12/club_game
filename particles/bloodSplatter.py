from pygame.math import Vector2 as v2
import math
import random
import pygame
class BloodSplatter:
    def __init__(self, app, pos ,angle):
        self.app = app
        self.pos = pos
        self.a = angle + random.uniform(-0.25, 0.25)
        self.color = [125 + random.randint(-25,25), 0, 4]
        self.vel = v2(math.cos(self.a), math.sin(self.a)) * random.uniform(8,12) * 144
        self.lifetime = random.uniform(0.2, 0.4)
        self.lastTicks = 2
        self.lastPos = None
        self.size = random.uniform(3,7) * self.app.RENDER_SCALE
        self.app.particle_list.append(self)

    def tick(self):
        
        if self.lifetime < 0:
            self.lastTicks -= 1
            self.lastPos = self.pos.copy()
            if self.lastTicks <= 0:
                self.app.particle_list.remove(self)
        else:
            self.lifetime -= self.app.dt

        self.pos += self.vel * self.app.dt


    def render(self, screen):
        if self.lifetime >= 0:
            pos = self.app.convertPos(self.pos - [self.size/2,self.size/2])
            r = pygame.Rect(pos.x, pos.y, self.size,self.size)
            pygame.draw.rect(screen, self.color, r)

        #elif self.lastPos:
        #    pygame.draw.line(self.app.MAP, self.color, self.pos * self.app.RENDER_SCALE, self.lastPos * self.app.RENDER_SCALE, width=int(self.size/2))