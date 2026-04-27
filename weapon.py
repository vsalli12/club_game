
from pygame import Vector2 as v2
import pygame
from imageprocessing.imageProcessing import gaussian_blur, trim_surface, remove_background, remove_background_bytes, generate_corpse_sprite, set_image_hue_rgba, colorize_to_blood, get_or_remove_background, brighten_surface, outline_surface
from imageprocessing.faceMorph import getFaceLandMarks, processFaceMorph, get_or_load_landmarks
import numpy as np
import math
from bullet import Bullet
from animationHelper import *
from muzzleflash import MuzzleFlash
class Weapon:
    def __init__(self, app, player, **kwargs):
        texture = kwargs.get("texture", "texture/ak47.png")
        name = kwargs.get("name", "AK-47")
        sizeMult = kwargs.get("sizeMult", 1.0)
        holdoutPos = kwargs.get("holdoutPos", 0.0)
        shotSound = kwargs.get("shotSound", "audio/shot.wav")
        rps = kwargs.get("rps", 10)

        self.kwargs = kwargs
        self.kwargs["texture"] = None

        self.app = app
        self.owner = player

        if texture:
            self.processImage(texture, sizeMult)
        
        self.ROTATION = 0
        self.ROTATIONVEL = 0
        self.recoil = 0
        self.r_recoil = 0
        self.holdoutAmount = 0
        self.holdoutAmountDelta = 0
        self.rps = rps
        self.fireTimer = 0
        self.holdingOut = v2(0,0)
        self.damage = kwargs.get("damage", 34)

        if self.owner:
            self.BLITPOS = self.owner.pos.copy()

        self.name = name
        
        self.holdoutPos = holdoutPos

        self.shotSound = shotSound

        self.magCap = kwargs.get("magCap", 30)
        self.mag = self.magCap
        self.reloadTime = 1.0
        self.reloadTimer = 0

        self.meleeTime = 0.5
        self.meleeTimer = 0
        self.lockR = 0

        self.FINALROTATION = 0

    def processImage(self, texture, sizeMult):
        self.path = texture
        self.image = pygame.image.load(self.path).convert_alpha()
        self.image = trim_surface(self.image)
        self.image = self.app.scaleTexture(self.image, desiredHeight = 60 * sizeMult)
        #self.image = pygame.transform.scale_by(self.image, 60 * sizeMult / self.image.get_height())
        self.imageR = pygame.transform.flip(self.image.copy(), True, False)
        #self.hudImage = pygame.transform.scale_by(self.image, 100 / self.image.get_height())
        self.hudImage = self.app.scaleTexture(self.image, desiredHeight = 100)
        self.hudImage = colorize(self.hudImage, (255,255,255))
        self.hudImage.set_alpha(100)
        self.hudImageH = self.hudImage.copy()
        self.hudImageH.set_alpha(50)

    def duplicate(self, to):
        w = Weapon(self.app, to, **self.kwargs)
        w.path = self.path
        w.image = self.image
        w.imageR = self.imageR
        w.hudImage = self.hudImage
        w.hudImageH = self.hudImageH
        to.weapon = w
        return w


    def handleSprite(self):
        if 90 <= self.ROTATION <= 270:
            self.rotatedImage = pygame.transform.rotate(self.imageR, self.FINALROTATION + 180)

        else:
            self.rotatedImage = pygame.transform.rotate(self.image, self.FINALROTATION)


    def melee(self):
        self.meleeTimer = self.meleeTime
        self.app.playPositionalAudio("audio/whoosh.wav", self.owner.pos, volume=0.5)
        self.app.playPositionalAudio("audio/gunfoley.wav", self.owner.pos, volume=0.5)


    def isMeleeing(self):
        return self.meleeTimer > 0

    def bulletSpawnPoint(self):
        return self.BLITPOS + v2(math.sin((90-self.FINALROTATION) * math.pi / 180), -(math.cos((90-self.FINALROTATION) * math.pi / 180))) * self.image.get_width()/1.7 #

    def holdToFire(self):
        if self.fireTimer <= 0 and self.mag > 0 and not self.isReloading() and not self.isMeleeing():
            self.fireTimer += 1/self.rps
            self.r_recoil += 1
            self.holdoutAmount += 1.0
            self.app.playPositionalAudio(self.shotSound, self.owner.pos, volume=0.5)


            x,y = self.bulletSpawnPoint()
            r = math.radians(-self.FINALROTATION)
            self.app.PARTICLESYSTEM.create_muzzle_flash(x,y, r)

            if self.owner.player:
                mp = self.app.inverseConvertPos(self.app.mouse_pos)
                baseRot = (math.atan2(mp.y - self.BLITPOS.y, mp.x - self.BLITPOS.x)) # 
            else:
                baseRot = r

            Bullet(self, v2(x,y), baseRot, math.radians(self.getSpread()), self.damage)
            self.mag -= 1

            if self.owner.player:
                MuzzleFlash(self.app, self)

    def getSpread(self):
        return 0.5 + self.recoil * 5
    
    def fireTick(self):

        if self.meleeTimer > 0:
            self.meleeTimer -= self.app.dt
           
        if self.reloadTimer > 0 and not self.isMeleeing():
            self.reloadTimer -= self.app.dt
            if self.reloadTimer <= 0:
                self.mag = self.magCap
                self.app.playPositionalAudio("audio/reloadDone.wav", self.owner.pos, volume=0.5)

        if (self.mag <= 0 or (self.mag < self.magCap and "r" in self.app.keypress)) and not self.isReloading() and not self.isMeleeing():
            self.reloadTimer = self.reloadTime
            self.app.playPositionalAudio("audio/reloadIni.wav", self.owner.pos, volume=0.5)


    def mouseTooClose(self):
        mp = self.app.mouse_pos + self.app.camPD
        spawnPoint = self.BLITPOS
        dist = (mp - spawnPoint).length()
        return dist < 150
             

    def hudTick(self):

        if self.isReloading():
            progress = (self.reloadTime - self.reloadTimer) / self.reloadTime

            mousePos = self.app.inverseConvertPos(self.app.mouse_pos)
            radius = 30
            rect = pygame.Rect(0, 0, radius * 2, radius * 2)
            rect.center = self.app.convertPos(mousePos)

            start_angle = math.pi/2 + progress * 2 * math.pi
            end_angle = 5*math.pi/2

            pygame.draw.arc(self.app.screen, (255, 255, 255), rect, end_angle, start_angle, 12)

        else:
            
            mp = self.app.inverseConvertPos(self.app.mouse_pos)
            spawnPoint = self.BLITPOS
            dist = (mp - spawnPoint).length()

            baseRot = math.degrees(math.atan2(mp.y - spawnPoint.y, mp.x - spawnPoint.x)) - 270 # 

            baseRot2 = 90 - self.FINALROTATION

            diff = abs(angle_diff(baseRot2, baseRot))

            d = (diff - 60) / 360

            diff2 = 0.1 * max(1 - d*4, 0)

            angleDiff = self.getSpread()
            for j in range(-1, 2, 1):
                i = j * angleDiff
                dMod = 1 - 0.03 * abs(j)
                point1 = spawnPoint + v2(math.sin(math.radians(baseRot + i)), -math.cos(math.radians(baseRot + i))) * (1-diff2) * dist
                point2 = spawnPoint + v2(math.sin(math.radians(baseRot + i)), -math.cos(math.radians(baseRot + i))) * (1+diff2) * dist * dMod
                pygame.draw.line(self.app.screen, (255,255,255), self.app.convertPos(point1), self.app.convertPos(point2), 3)


        #baseRot2 = 90 - self.FINALROTATION

        #diff = abs(angle_diff(baseRot2, baseRot)) / 360
        #diff2 = 0.1 * max(1 - diff*4, 0)

        #point1 = self.BLITPOS + v2(math.sin(math.radians(baseRot2)), -math.cos(math.radians(baseRot2))) * (1-diff2) * dist
        #point2 = self.BLITPOS + v2(math.sin(math.radians(baseRot2)), -math.cos(math.radians(baseRot2))) * (1+diff2) * dist
        #pygame.draw.line(self.app.screen, (255,0,0), point1 - self.app.camPD, point2 - self.app.camPD, 2)

    def isReloading(self):
        return self.reloadTimer > 0

    def tick(self):

        ownerBreathe = math.cos(self.owner.breatheTimer * math.pi)
        ownerBreathe2 = math.sin(self.owner.breatheTimer * math.pi)

        self.fireTimer -= self.app.dt
        self.fireTimer = max(0, self.fireTimer)

        self.r_recoil += self.owner.walking * 3 * self.app.dt

        self.r_recoil = self.app.smoothe(self.r_recoil, 0, 7)
        self.holdoutAmount = self.app.smoothe(self.holdoutAmount, self.holdoutPos, 4)

        if self.owner.isRolling():
            self.recoil = self.app.smoothe(self.recoil, self.r_recoil, 20)
        else:
            self.recoil = self.app.smoothe(self.recoil, self.r_recoil, 20)

        self.holdoutAmountDelta = self.app.smoothe(self.holdoutAmountDelta, self.holdoutAmount, 8)

        rotationMod = ownerBreathe*5 - self.owner.rotation*0.5

        xA, yA, self.rA = 0,0,0

        

        if not self.owner.holster:


            if self.isReloading():
                r = 135 if not self.owner.facingRight else 45

            elif not self.owner.player:
                if not self.owner.shooting:
                    if self.app.enemiesSpottedPlayer and self.owner.LOS:
                        r = math.degrees(self.app.getAngleFrom(self.owner.pos, self.app.player.pos))
                    else:
                        r = 135 if not self.owner.facingRight else 45
                    self.lockR = r
                else:
                    r = self.lockR


            elif not self.owner.running:
                mouse_world = self.app.inverseConvertPos(self.app.mouse_pos)
                r = math.degrees(self.app.getAngleFrom(self.owner.pos, v2(mouse_world)))

                    
            else:
                r = -110 if not self.owner.facingRight else -70

            if self.owner.runOffset > 0:
                RO = self.owner.runOffset
                yA = -self.owner.runOffset * 30 * RO
                if not self.owner.facingRight:
                    xA = self.owner.runOffset * 20 * RO
                else:
                    xA = -self.owner.runOffset * 20 * RO



            if self.owner.walking:
                si = (self.owner.stepI * 2) % 1
                yA -= math.sin(si * math.pi) * 7 * min(1, self.owner.walking)
                rotationMod += math.sin(si * math.pi) * 7 * min(1, self.owner.walking)


        if self.isMeleeing() and not self.owner.holster:
            xA, yA, self.rA = melee_animation((self.meleeTime-self.meleeTimer)/self.meleeTime)
            if not self.owner.facingRight:
                xA = -xA

            self.r_recoil = abs(xA) * 0.05

            #r -= r2 if not self.owner.facingRight else -r2

        elif self.isReloading() and not self.owner.holster:
            r2 = reload_rotation((self.reloadTime - self.reloadTimer)/self.reloadTime) * 1.4

            r += r2 if not self.owner.facingRight else -r2
       
            
        if self.owner.holster:
            rotation = -110 if self.owner.facingRight else -70
            yA = -50 - self.owner.yComponent

        else:
            rotation = -r + rotationMod

        if self.owner.isRolling() and not self.owner.ableToFire:
            rotation -= self.owner.rollAngle

        rotation = rotation % 360

        if self.owner.isRolling():
            RGAIN = 3000
        elif self.owner.holster:
            RGAIN = 2000
        elif self.isReloading() or self.isMeleeing():
            RGAIN = 5000
        else:
            RGAIN = 2500

        DIFF = angle_diff(self.ROTATION, rotation)

        rotation_factor = self.app.smoothRotationFactor(
            self.ROTATIONVEL,  # Current angular velocity (no deltaTime here)
            RGAIN,               # Gain factor - acceleration rate (no deltaTime here)
            DIFF  # Angle difference
        )

        self.ROTATIONVEL += rotation_factor * self.app.dt

        self.ROTATION += self.ROTATIONVEL * self.app.dt
        self.ROTATION = self.ROTATION % 360

        if 90 <= self.ROTATION <= 270:
            self.FINALROTATION = self.ROTATION - self.recoil * 5 - self.rA
            meleeOffset = v2(-xA, yA)
        else:
            self.FINALROTATION = self.ROTATION + self.recoil * 5 + self.rA
            meleeOffset = v2(xA, yA)


        self.holdingOut = v2(math.sin((90-self.FINALROTATION) * math.pi / 180), -(math.cos((90-self.FINALROTATION) * math.pi / 180))) * (20 - 20*(self.holdoutAmountDelta))
        self.handleSprite()

        pos = self.owner.BLITPOS

        weaponBreathe = math.sin(self.owner.breatheTimer * math.pi)
        angle = - 30 - 3 * weaponBreathe
        tempim = self.rotatedImage

        self.BLITPOS = pos + self.holdingOut + v2(xA,yA + self.owner.breatheY + 50 - weaponBreathe*3)
        BP = self.app.convertPos(self.BLITPOS)
        self.app.screen.blit(tempim, BP - v2(tempim.get_size()) / 2)