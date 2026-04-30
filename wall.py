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
        dx1 = self.rect.right - hb.left +1  # push right
        dx2 = hb.right - self.rect.left -1  # push left
        dy1 = self.rect.bottom - hb.top +1  # push down
        dy2 = hb.bottom - self.rect.top -1  # push up

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
        r.topleft = self.app.convertPos(self.rect.topleft)
        r.size = v2(self.rect.size) * self.app.RENDER_SCALE
        pygame.draw.rect(self.app.screen, (0,0,0), r)