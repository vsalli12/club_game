import pygame
import math
from pygame.math import Vector2 as v2
import random
from numba import njit
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from player import Player
@njit
def line_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
        denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
        if denom == 0:
            return False
        ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
        ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
        return 0 <= ua <= 1 and 0 <= ub <= 1

@njit
def line_intersects_rect(x1, y1, x2, y2, rx, ry, rw, rh):
    # rectangle edges
    left   = (rx, ry, rx, ry + rh)
    right  = (rx + rw, ry, rx + rw, ry + rh)
    top    = (rx, ry, rx + rw, ry)
    bottom = (rx, ry + rh, rx + rw, ry + rh)

    return (
        line_intersect(x1, y1, x2, y2, *left) or
        line_intersect(x1, y1, x2, y2, *right) or
        line_intersect(x1, y1, x2, y2, *top) or
        line_intersect(x1, y1, x2, y2, *bottom)
    )



class Bullet:
    def __init__(self, weapon, pos, angle, spread, damage):
        args = [weapon, pos, angle]
        kwargs = {}
        self.weapon = weapon
        self.owner = weapon.owner
        self.app = self.owner.app
        self.pos = pos
        self.angle = angle + random.uniform(-spread, spread)
        self.speed = 10000
        self.damage = damage
        self.vel = v2(math.cos(self.angle), math.sin(self.angle))
        self.pastPos = []
        self.dodged = []
        self.app.addEntity(self)
        self.lifetime = 2
        bType = "normal"
        if bType == "normal":
            self.bOrig = self.app.bulletSprite.copy()
        else:
            self.bOrig = self.app.energySprite.copy()
        self.b = pygame.transform.rotate(self.bOrig, -math.degrees(self.angle))
        self.bType = bType
        self.pos += self.vel * random.uniform(19,25)
        self.target = None
        
        self.ONSCREEN = False
        self.killed = False

        self.trail = [self.pos]
        #self.app.trails.append(self.trail)

    @staticmethod
    def renderTrail(app, trail):
        if len(trail) < 2:
            return
        points = [app.convertPos(p) for p in trail]
        pygame.draw.lines(app.screen, (200, 200, 50), False, points, 2)

    
    def tick(self):
       
        self.pastPos.append(self.pos.copy())
        if len(self.pastPos) > 3:
            self.pastPos.pop(0)
        #self.pos += self.vel * self.app.deltaTime * self.speed
        nextPos = self.pos + self.vel * self.app.dt * self.speed
        
        line = [list(self.pos), list(nextPos)]

        direction = self.vel.normalize()
        move_dist = self.speed * self.app.dt
        #hit, normal = raycast_grid(
        #    nextPos,
        #    direction,
        #    move_dist / self.app.tileSize,
        #    self.app.map.grid,
        #    self.app.tileSize
        #)
        hit = None

        #if hit is not None:
        #    self.pos = hit
#
        #    # reflect direction
        #    reflected = direction - 2 * direction.dot(normal) * normal
        #    reflected_angle = math.atan2(-reflected.y, reflected.x)
#
        #    self.app.particle_system.create_wall_sparks(
        #        hit.x,
        #        hit.y,
        #        normal_angle=reflected_angle
        #    )
#

        #    self.app.trails.append(self.trail)
        #    return

        self.pos += self.vel * move_dist
        self.trail.append(self.pos.copy())
        if len(self.trail) > 10:
            self.trail.pop(0)
        
        for x in self.app.entities["players"]:
            if x == self:
                continue

            if x == self.owner:
                continue

            if x in self.dodged:
                continue


            #if not isinstance(x, self.app.Player):
            #    continue

            collides = line_intersects_rect(
                line[0][0], line[0][1],
                line[1][0], line[1][1],
                x.hitBox.x, x.hitBox.y, x.hitBox.width, x.hitBox.height
            )
            if collides:

                self.app.removeEntity(self)
                self.app.trails.append(self.trail)

                #self.app.bloodSplatters.append(BloodParticle(x.pos.copy(), 0.7, app = self.app))

                damage = self.damage 

                x.takeDamage(damage, bloodAngle = self.angle) # TEST 


        self.lifetime -= self.app.dt
        if self.lifetime < 0:
            self.app.removeEntity(self)
            self.app.trails.append(self.trail)

        #if not self.app.room.floor.collidepoint(self.pos):
        #    self.app.removeEntity(self)
        #    self.app.trails.append(self.trail)

        self.render()


    def render(self):

        self.renderTrail(self.app, self.trail)

        POS = self.app.convertPos(self.pos)
        self.app.screen.blit(self.b, POS - v2(self.b.get_size())/2)

