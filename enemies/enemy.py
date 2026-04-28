import pygame
from pygame import Vector2 as v2
import random
from parentActor import ParentActor

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import App
class Enemy(ParentActor):

    def __init__(self, app: "App", pos, path = "texture/khaled2.png"):
        super().__init__(app, pos, path)

        self.route = None
        self.walkTo = None
        self.speed = 700
        self.player = False

    def tick(self):
        self.mandatoryTick()

        self.LOS = self.app.nav.can_see(self.pos, self.app.player.pos)

        if (self.app.enemiesSpottedPlayer and self.LOS) or self.shooting:
            self.botShoot()
            if self.shooting:
                self.aimTimer -= self.app.dt
                if self.aimTimer <= 0:
                    self.weapon.holdToFire()

                if self.weapon.isReloading():
                    self.shooting = False

        self.botWalk()
        
        self.render()
        

        if self.weapon:
            self.weapon.tick()
            self.weapon.fireTick()

    def duplicate(self, atPos = v2(0,0)):
        p = Enemy(self.app, atPos, path="") 
        p.image = self.image
        p.imageBat = self.imageBat
        p.hudImage = self.hudImage
        return p
    
    def botShoot(self):
        target = self.app.player.pos
        diff = (v2(target) - v2(self.pos))
        if diff.length() > 750 and not self.shooting and not self.weapon.isReloading():
            pass

        elif self.LOS and self.AIWeaponPointingAtPlayer() and not self.weapon.isReloading():
            self.walkTo = None
            self.route = None
            if not self.shooting:
                self.aimTimer = 0.5
                self.shooting = True
            

    def botWalk(self):

        d = self.pos.distance_to(self.app.player.pos)


        if self.app.enemiesSpottedPlayer and not self.shooting:
            self.speed = 700
            self.running = True
            self.runOffset = 1

        else:
            self.speed = 500
            self.running = False
            self.runOffset = 0

        if self.LOS and d < 750 and ((not self.app.player.holster or self.app.playerInRestricted) or self.app.enemiesSpottedPlayer):
            self.app.sightToPlayer = True

        if self.shooting:
            self.vel = v2(0,0)
            return
    
        if not self.walkTo and self.route:
            self.walkTo = self.route.pop(0)

        if self.walkTo:
            diff = (v2(self.walkTo) - v2(self.pos))
            
            if diff.length() < 10:
                self.walkTo = None

            if diff.length() > 0:
                self.vel = diff.normalize()

            for x in self.app.interactables:
  
                if x.collides(self.hitBox):
                    x.openFor(1.5)

            if self.touchingWall > 0.25:
                self.walkTo = None
                self.route = None
                self.touchingWall = 0

        if not self.route and not self.walkTo:
            if self.LOS and self.app.enemiesSpottedPlayer:
                self.walkTo = self.app.player.pos.copy()
                
            else:
                if self.app.enemiesSpottedPlayer:
                    target = self.app.player.pos
                else:
                    target = self.app.getPatrolPoint()


                self.route = self.app.nav.get_path(self.pos, v2(target))
        
