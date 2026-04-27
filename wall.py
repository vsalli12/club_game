import pygame
from pygame import Vector2 as v2

class Wall:
    def __init__(self, app, tile, size):
        self.app = app
        tilesize = 100
        self.rect = pygame.Rect(v2(tile) * tilesize, v2(size) * tilesize)

    def resolve_collision(self, hb):
        if not self.rect.colliderect(hb):
            return None

        # compute overlap on both axes
        dx1 = self.rect.right - hb.left   # push right
        dx2 = hb.right - self.rect.left   # push left
        dy1 = self.rect.bottom - hb.top   # push down
        dy2 = hb.bottom - self.rect.top   # push up

        # choose minimal displacement
        min_dx = dx1 if dx1 < dx2 else -dx2
        min_dy = dy1 if dy1 < dy2 else -dy2

        if abs(min_dx) < abs(min_dy):
            hb.x += min_dx
        else:
            hb.y += min_dy

        return hb.center
    
    def render(self):
        r = self.rect.copy()
        r.topleft = self.rect.topleft - self.app.camPD
        pygame.draw.rect(self.app.screen, (20,0,0), r)