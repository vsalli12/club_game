import pygame
import math
import random
from pygame.math import Vector2 as v2
class BloodParticle:
    def __init__(self, pos, magnitude=1.0, screen=None, app=None):
        self.pos = pos
        self.magnitude = magnitude
        self.direction = math.radians(random.randint(0, 360))
        self.lifetime = round(random.randint(3, 10) * magnitude * 1.3)
        self.max_life = 10 * magnitude * 1.3
        self.color3 = [
            random.randint(200, 220),
            random.randint(0, 50),
            random.randint(0, 50),
        ]
        self.intensity = random.uniform(0.03, 0.10)
        self.app = app

    def tick(self):
        if self.lifetime <= 0:
            self.app.bloodSplatters.remove(self)
            return

        self.pos = [
            self.pos[0] + (math.sin(self.direction) * self.lifetime*1.5),
            self.pos[1] + (math.cos(self.direction) * self.lifetime*1.5)
        ]

        size = self.lifetime * 3
        self.dim = [
            self.pos[0] - round(self.lifetime),
            self.pos[1] - round(self.lifetime),
            size,
            size,
        ]

        self.color = [
            self.color3[0],
            self.color3[1] / self.lifetime,
            self.color3[2] / self.lifetime,
        ]

        pos = [self.dim[0], self.dim[1]] 
        pos.append(self.dim[2])
        pos.append(self.dim[3])

        for _ in range(random.randint(2, 4)):
            try:
                w = round(pos[2]) - random.randint(-2, 2)
                h = round(pos[3]) - random.randint(-2, 2)
                surf = pygame.Surface((w, h))
                surf.fill([
                    round((255 - self.color[0]) * self.intensity),
                    round((255 - self.color[1]) * self.intensity),
                    round((255 - self.color[2]) * self.intensity),
                ])
                self.app.MAP.blit(
                    surf,
                    (pos[0] - random.randint(-2, 2), pos[1] - random.randint(-2, 2)),
                    None,
                    pygame.BLEND_RGB_SUB
                )
            except:
                continue

        mult = random.uniform(0.25, 0.75)
        pygame.draw.rect(
            self.app.MAP,
            [
                round(self.color[0] * mult),
                round(self.color[1] * mult),
                round(self.color[2] * mult),
            ],
            [
                pos[0] + random.randint(-10, 10) + random.randint(0, round(pos[2])),
                pos[1] + random.randint(-10, 10) + random.randint(0, round(pos[3])),
                random.randint(1, 3),
                random.randint(1, 3),
            ],
        )


        self.lifetime -= 1
