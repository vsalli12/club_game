import pygame
from pygame import Vector2 as v2
import math
import random
from parentActor import ParentActor

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import App


class Reinforcement(ParentActor):

    def __init__(self, app: "App", pos, path="texture/reinforcement.png"):
        super().__init__(app, pos, path)
        self.player  = False
        self.speed   = 800
        self.running = True
        self.runOffset = 1

        self.route   = None
        self.walkTo  = None

        self.aimTimer    = 0.0
        self.shootTimer  = 0.0   # cooldown between bursts
        self.ignoreSpottedStatus = True

    # ------------------------------------------------------------------
    def tick(self):
        self.mandatoryTick()
        self.LOS = self.app.nav.can_see(self.pos, self.app.player.pos)

        self._walk()
        self._shoot()

        self.render()

        if self.weapon:
            self.weapon.tick()
            self.weapon.fireTick()

    # ------------------------------------------------------------------
    def duplicate(self, atPos=v2(0, 0)):
        p = Reinforcement(self.app, atPos, path="")
        if self.USESPRITE:
            p.sprites = self.sprites
        else:
            p.image = self.image
            p.imageBat = self.imageBat
            p.hudImage = self.hudImage
        return p
            

    # ------------------------------------------------------------------
    def _shoot(self):
        if not self.LOS:
            self.running = True
            self.runOffset = 1
            return
        
        self.running = False
        self.runOffset = 0

        if self.AIWeaponPointingAtPlayer() and not self.weapon.isReloading():
            self.weapon.holdToFire()
            self.weapon.aimAt = self.app.player.pos.copy()
            
            

    # ------------------------------------------------------------------
    def _walk(self):

        if not self.walkTo and self.route:
            self.walkTo = self.route.pop(0)

        if self.walkTo:
            diff = v2(self.walkTo) - v2(self.pos)
            if diff.length() < 10:
                self.walkTo = None
            elif diff.length() > 0:
                self.vel = diff.normalize()

            for x in self.app.interactables:
                if x.collides(self.hitBox):
                    x.openFor(1.5)

            if self.touchingWall > 0.25:
                self.walkTo    = None
                self.route     = None
                self.touchingWall = 0

        if not self.route and not self.walkTo:
            self.route = self.app.nav.get_path(self.pos, self.app.player.pos.copy())