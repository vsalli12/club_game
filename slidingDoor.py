import pygame
from pygame import Vector2 as v2
import numpy as np
import random
from multiPurposeHudElement import MPHE, CodeInputAnimation

def randomCode():
    return "".join([str(random.randint(0,9)) for _ in range(4)])

class SlidingDoor:
    def __init__(self, app, tile, size, axis="h"):
        """
        tile: (tx, ty) top-left in tile coords
        size: (tw, th) in tile coords  
        axis: "h" = slides horizontally to open, "v" = vertically
        """
        self.app = app
        TILESIZE = 100
        self.rect = pygame.Rect(v2(tile) * TILESIZE, v2(size) * TILESIZE)
        self.axis = axis
        self.open = False
        self.slide = 0.0      # 0.0 closed, 1.0 fully open
        self.slide_speed = 10.0
        self.open_for = 0.0
        self.forceClose = False
        self.pos = v2(self.rect.center)
        self.name = "Door"
        self.doorcode = randomCode()
        print(self.doorcode)

        self.AIcollideRect = self.rect.copy()
        if axis == "h":
            self.AIcollideRect.inflate_ip(0, TILESIZE)
        else:
            self.AIcollideRect.inflate_ip(TILESIZE, 0)

        # the LOS segment this door contributes when closed
        # horizontal door = vertical segment blocking passage, and vice versa
        self._build_segment()
        app.walls.append(self)
        app.interactables.append(self)


    def _build_segment(self):
        r = self.rect
        rs = self.app.RENDER_SCALE
        if self.axis == "h":
            # blocking segment runs along the top edge of the door rect
            self._seg = np.array([[
                r.left  * rs, r.centery * rs,
                r.right * rs, r.centery * rs
            ]], dtype=np.float64)
        else:
            self._seg = np.array([[
                r.centerx * rs, r.top    * rs,
                r.centerx * rs, r.bottom * rs
            ]], dtype=np.float64)

    @property
    def los_segment(self):
        """Returns (1,4) array if door is blocking, else (0,4) empty."""
        if self.slide > 0.99:
            return np.zeros((0, 4), dtype=np.float64)
        # scale segment by how much door is closed
        seg = self._seg.copy()
        if self.axis == "h":
            full_w = seg[0, 2] - seg[0, 0]
            seg[0, 2] = seg[0, 0] + full_w * (1.0 - self.slide)
        else:
            full_h = seg[0, 3] - seg[0, 1]
            seg[0, 3] = seg[0, 1] + full_h * (1.0 - self.slide)
        return seg
    
    def collides(self, hb):
        return self.AIcollideRect.colliderect(hb)
    

    def openFor(self, time):
        if not self.open:
            self.interact()
        self.open_for = time
        self.forceClose = True


    def interact(self):
        self.open = not self.open
        if self.open:
            self.app.playPositionalAudio("audio/door_open.wav", self.pos)
        else:
            self.app.playPositionalAudio("audio/door_close.wav", self.pos)
        self.forceClose = False

    def openNoHack(self):
        print("Trying to open")
        anim = CodeInputAnimation(randomCode(), on_complete=None, success=False)
        MPHE(self.app, self, animation=anim)

    def makeHudWidget(self):
        MPHE(self.app, self, options = {
            "1": ("Try to open", lambda: self.openNoHack()),
            "2": ("Hack", lambda: self.interact()),
        })

    def tick(self):
        target = 1.0 if self.open else 0.0
        self.slide += (target - self.slide) * min(1.0, self.slide_speed * self.app.dt)
        if self.open_for >= 0:
            self.open_for -= self.app.dt
        else:
            if self.forceClose:
                self.forceClose = False
                if self.open:
                    self.interact()

    def resolve_collision(self, hb):
        if self.slide > 0.99:
            return None
        # partially closed doors still block — use a shrunk rect
        r = self.rect.copy()
        if self.axis == "h":
            r.width = int(self.rect.width * (1.0 - self.slide))
        else:
            r.height = int(self.rect.height * (1.0 - self.slide))

        if not r.colliderect(hb):
            return None
        dx1 = r.right - hb.left
        dx2 = hb.right - r.left
        dy1 = r.bottom - hb.top
        dy2 = hb.bottom - r.top
        min_dx = dx1 if dx1 < dx2 else -dx2
        min_dy = dy1 if dy1 < dy2 else -dy2
        if abs(min_dx) < abs(min_dy):
            hb.x += min_dx
        else:
            hb.y += min_dy
        return hb.center

    def render(self):
        if self.slide > 0.99:
            return
        r = self.rect.copy()
        if self.axis == "h":
            r.width = int(self.rect.width * (1.0 - self.slide))
        else:
            r.height = int(self.rect.height * (1.0 - self.slide))

        screen_rect = r.copy()
        screen_rect.topleft = self.app.convertPos(r.topleft)
        screen_rect.size = v2(r.size) * self.app.RENDER_SCALE
        pygame.draw.rect(self.app.screen, (80, 60, 40), screen_rect)
        pygame.draw.rect(self.app.screen, (140, 100, 60), screen_rect, 2)
