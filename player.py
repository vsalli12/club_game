import random

from pygame import Vector2 as v2
import pygame
import io
from imageprocessing.imageProcessing import gaussian_blur, trim_surface, remove_background, remove_background_bytes, generate_corpse_sprite, set_image_hue_rgba, colorize_to_blood, get_or_remove_background, brighten_surface, outline_surface
from PIL import Image
import numpy as np
import math
from bullet import Bullet
from animationHelper import *
from weapon import Weapon
from objects.pill import Pill
from parentActor import ParentActor
class Player(ParentActor):
    def __init__(self, app, pos, path = "texture/crack.png", player = False, weapon = False, aiType = "none"):

        super().__init__(app, pos, path)

        self.player = player
        self.aiType = aiType

        self.name = "Player" if player else "NPC"

        
        self.ableToFire = True

        if weapon:
            self.weapon = Weapon(app, self, texture = "texture/ak47.png", name = "AK-47")
        else:
            self.weapon = None


    def tickPlayerHealth(self):
        self.outOfCombat -= self.app.dt
        if self.outOfCombat <= 0:
            self.health += 100 * self.app.dt
            self.health = min(100, self.health)
            self.outOfCombat = 0


    def duplicate(self, atPos = v2(0,0)):
        p = Player(self.app, atPos, path="", aiType=self.aiType)
        p.image = self.image
        p.imageBat = self.imageBat
        p.hudImage = self.hudImage
        return p

    


    

    def _playerDetectInteraction(self):
        closest = float("inf")
        closestEntity = None
        for entity in self.app.entities["players"]:
            if entity is not self and hasattr(entity, "pos") and (entity.pos - self.pos).length() < 200:
                distance = (entity.pos - self.pos).length()
                if distance < closest:
                    closest = distance
                    closestEntity = entity
        return closestEntity
    

    def tryToWalk(self):

        if self.isRolling():
            return

        self.vel = v2(0,0)
        if "w" in self.app.keypress_held_down:
            self.vel.y = -1
        elif "s" in self.app.keypress_held_down:
            self.vel.y = 1
        if "a" in self.app.keypress_held_down:
            self.vel.x = -1
        elif "d" in self.app.keypress_held_down:
            self.vel.x = 1

        if self.vel.length() > 0:
            self.vel = self.vel.normalize()
            if "space" in self.app.keypress:

                if self.running:
                    self.rollTime = 0.75
                else:
                    self.rollTime = 0.6

                self.rolling = self.rollTime
                self.rollDir = self.vel.normalize()
                self.rollingRight = self.rollDir.x >= 0
                if self.weapon:
                    self.weapon.holdoutAmount -= 8

                self.app.playPositionalAudio("audio/jump.wav", self.pos, volume = 0.5)
                self.landed = False

        if "shift" in self.app.keypress_held_down:
            self.vel *= 1.5
            self.runOffset += self.app.dt * 5
            self.runOffset = min(self.runOffset, 1)
            self.running = True
        else:
            self.runOffset -= self.app.dt * 2
            self.runOffset = max(self.runOffset, 0)
            self.running = False

        

    

    def AIWalk(self):

        target = self.app.player.pos
        diff = (v2(target) - v2(self.pos))
        if diff.length() > 750 and not self.shooting and not self.weapon.isReloading():
            self.vel = diff.normalize()

        elif self.AIWeaponPointingAtPlayer() and not self.weapon.isReloading():
            self.vel = v2(0,0)
            if not self.shooting:
                self.aimTimer = 0.5
                self.shooting = True
            
        self.dvel = self.vel * 0.1 + self.dvel * 0.9

    

    def isPistolAI(self):
        return self.aiType == "pistol"
    
    



    def tick(self):

        self.mandatoryTick()
        

        if self.player and self.weapon and not self.weapon.isMeleeing():
            if "q" in self.app.keypress:
                self.holster = not self.holster
                if self.holster:
                    self.app.playPositionalAudio("audio/holster.wav", self.pos, volume=0.5)
                else:
                    self.app.playPositionalAudio("audio/unholster.wav", self.pos, volume=0.5)

                self.weapon.holdoutAmount = 5


        if self.player and self.weapon and not self.holster and not self.weapon.isReloading() and not self.weapon.isMeleeing():
            if "mouse2" in self.app.keypress:
                self.weapon.melee()

        self.ableToFire = (not self.isRunning() or (self.isRunning() and self.weapon.isReloading())) and not self.holster and self.weapon and not self.app.interactingWith


        

        if self.player:
            self.tryToWalk()
        else:
            if self.isPistolAI():
                self.AIWalk()

        if self.holster and self.weapon:
            self.weapon.tick()

        self.render()
        
        if self.player:
            if not self.holster and self.weapon:
                self.weapon.tick()
                self.weapon.fireTick()
                if self.ableToFire:
                    if "mouse0" in self.app.keypress_held_down:
                        self.weapon.holdToFire()
        else:

            if self.isPistolAI():
                if self.weapon:
                    self.weapon.tick()
                    self.weapon.fireTick()

                if self.shooting:
                    self.aimTimer -= self.app.dt
                    if self.aimTimer <= 0:
                        self.weapon.holdToFire()

                    if self.weapon.isReloading():
                        self.shooting = False

        

        
