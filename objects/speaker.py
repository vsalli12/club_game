import pygame
from imageprocessing.imageProcessing import trim_surface
import math
from pygame import Vector2 as v2

class Speaker:
    def __init__(self, app, pos):
        self.app = app
        self.pos = pos
        self.image = pygame.image.load("texture/speaker.png").convert_alpha()
        self.image = trim_surface(self.image)
        self.image = pygame.transform.scale_by(self.image, 100 / self.image.get_height())
        self.phase = 0
        self.app.entities["misc"].append(self)

    def tick(self):
        TEMPO = 155
        timestep = 60/TEMPO
        self.phase += self.app.dt
        self.phase %= timestep
        jump = math.sin(1/timestep*math.pi*self.phase)
        yAdd = jump * 40

        scalex = self.image.get_width() * (1.25 - jump*0.25)
        scaley = self.image.get_height() * (1 + jump*0.25)

        im = pygame.transform.scale(self.image, [scalex, scaley])
        self.app.screen.blit(im, self.pos - self.app.camPD - v2(im.get_size())/2 - [0, yAdd])