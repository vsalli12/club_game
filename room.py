from pygame import Vector2 as v2
import pygame

class Room:
    def __init__(self, app, tile):
        self.app = app
        self.tile = tile
        self.tileSize = v2(2000,2000)
        self.pos = self.tile.elementwise() * self.tileSize  - self.tileSize/2
        self.floor = pygame.Rect(self.pos, self.tileSize)
        self.exit = pygame.Rect(self.floor.right + 50, self.floor.centerx, 0,0)
        self.exit.inflate_ip(100, 200)

    def determineConnections(self):
        for x in self.app.rooms:
            if x == self:
                continue

            if (x.tile - self.tile).length == 1:
                pass

    def render(self):
        cam = self.app.camPD

        # floor (already in world coords)
        floor_d = self.floor.copy()
        floor_d.topleft = self.pos - self.app.camPD
        exit_d = self.exit.copy()
        exit_d.topleft = self.exit.topleft - self.app.camPD
        pygame.draw.rect(self.app.screen, (50,50,50), floor_d)
        pygame.draw.rect(self.app.screen, (50,50,50), exit_d)

        # vertical lines
        for x in range(0, 2001, 100):
            start = (floor_d.left + x, floor_d.top)
            end   = (floor_d.left + x, floor_d.bottom)
            pygame.draw.line(self.app.screen, (100,100,100), start, end)

        # horizontal lines
        for y in range(0, 2001, 100):
            start = (floor_d.left, floor_d.top + y)
            end   = (floor_d.right, floor_d.top + y)
            pygame.draw.line(self.app.screen, (100,100,100), start, end)

    
    def detectLevelTransition(self, hb):
        return False
        if self.exit.colliderect(hb):
            return True
        return False
    
    def detect_collision(self, hb):

        # --- X axis ---
        modified = False
        if hb.left < self.floor.left:
            modified = True
            hb.left = self.floor.left
        if hb.right > self.floor.right:
            modified = True
            hb.right = self.floor.right

        # --- Y axis ---
        if hb.top < self.floor.top:
            modified = True
            hb.top = self.floor.top
        if hb.bottom > self.floor.bottom:
            modified = True
            hb.bottom = self.floor.bottom
        if modified:
            return hb.center
        else:
            return
