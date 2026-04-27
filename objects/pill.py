import pygame
import random
from pygame import Vector2 as v2
import math
class Pill:
    def __init__(self, app, pos):
        self.app = app
        self.pos = pos
        self.im = random.choice(self.app.pillTextures)
        self.rot = random.randint(0,360)
        self.phase = 0
        self.vel = v2(random.randint(-500,500),random.randint(-500,500))
        self.lifeTime = 0
        self.maxLife = 60


    def tick(self):

        self.phase = (self.phase + self.app.dt) % 1.0
        rotMod = 15 * (1 - 4 * abs(self.phase - 0.5))

        jump = math.sin(2*math.pi*(self.phase%0.5))
        yAdd = jump * 8
        d = self.pos.distance_to(self.app.player.pos)
        if d < 500 and self.lifeTime >= 1:
            self.vel = (self.app.player.pos - self.pos).normalize() * 2000 * (1 - d/500)
            if d < 50:
                self.app.removeEntity(self)
                self.app.playPositionalAudio("audio/collect.wav", self.pos)
                self.app.pillAmount += 1

        self.pos += self.vel * self.app.dt

        if self.vel.length() > 0:
            self.vel *= 0.1 ** self.app.dt


        im = pygame.transform.rotate(self.im, rotMod + self.rot + self.vel.length() * 60 * self.app.dt)

        self.app.screen.blit(im, self.app.convertPos(self.pos - [0, yAdd]) - v2(im.get_size())/2)

        self.lifeTime += self.app.dt
        if self.lifeTime >= self.maxLife:
            self.app.removeEntity(self)