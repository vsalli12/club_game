from pygame import Vector2 as v2
import pygame
from imageprocessing.imageProcessing import trim_surface, colorize_to_blood
import math
from animationHelper import *

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import App
    from parentActor import ParentActor


class Holdable:
    def __init__(self, app: "App", owner: "ParentActor", **kwargs):
        texture = kwargs.get("texture", None)
        sizeMult = kwargs.get("sizeMult", 1.0)
        holdoutPos = kwargs.get("holdoutPos", 0.0)

        self.kwargs = kwargs
        self.kwargs["texture"] = None

        self.app = app
        self.owner = owner

        if texture:
            self.processImage(texture, sizeMult)

        self.ROTATION = 0
        self.ROTATIONVEL = 0
        self.holdoutAmount = 0
        self.holdoutAmountDelta = 0
        self.holdingOut = v2(0, 0)
        self.holdoutPos = holdoutPos
        self.aimAt = v2(0, 0)
        self.FINALROTATION = 0

        if self.owner:
            self.BLITPOS = self.owner.pos.copy()

    def processImage(self, texture, sizeMult):
        self.path = texture
        self.image = pygame.image.load(self.path).convert_alpha()
        self.image = trim_surface(self.image)
        self.image = self.app.scaleTexture(self.image, desiredHeight=60 * sizeMult)
        self.imageR = pygame.transform.flip(self.image.copy(), True, False)
        self.hudImage = self.app.scaleTexture(self.image, desiredHeight=100)
        self.hudImage = colorize(self.hudImage, (255, 255, 255))
        self.hudImage.set_alpha(100)
        self.hudImageH = self.hudImage.copy()
        self.hudImageH.set_alpha(50)

    def duplicate(self, to: "ParentActor") -> "Holdable":
        h = self.__class__(self.app, to, **self.kwargs)
        h.path = self.path
        h.image = self.image
        h.imageR = self.imageR
        h.hudImage = self.hudImage
        h.hudImageH = self.hudImageH
        to.weapon = h
        return h

    def handleSprite(self):
        if 90 <= self.ROTATION <= 270:
            self.rotatedImage = pygame.transform.rotate(self.imageR, self.FINALROTATION + 180)
        else:
            self.rotatedImage = pygame.transform.rotate(self.image, self.FINALROTATION)

    # Override in subclasses.
    # Returns (r, xA, yA, rA) where r is the target rotation angle.
    # xA, yA are positional offsets, rA is an additive rotation offset.
    def getRotationTarget(self) -> tuple:
        if self.owner.facingRight:
            r = 45
        else:
            r = 135
        return r, 0, 0, 0

    def tick(self):
        ownerBreathe = math.cos(self.owner.breatheTimer * math.pi)
        weaponBreathe = math.sin(self.owner.breatheTimer * math.pi)

        self.holdoutAmount = self.app.smoothe(self.holdoutAmount, self.holdoutPos, 4)
        self.holdoutAmountDelta = self.app.smoothe(self.holdoutAmountDelta, self.holdoutAmount, 8)

        xA, yA, self.rA = 0, 0, 0
        rotationMod = ownerBreathe * 5 - self.owner.rotation * 0.5

        if not self.owner.holster:
            r, xA, yA, self.rA = self.getRotationTarget()

            if self.owner.runOffset > 0:
                RO = self.owner.runOffset
                yA -= self.owner.runOffset * 30 * RO
                if not self.owner.facingRight:
                    xA += self.owner.runOffset * 20 * RO
                else:
                    xA -= self.owner.runOffset * 20 * RO

            if self.owner.walking:
                si = (self.owner.stepI * 2) % 1
                yA -= math.sin(si * math.pi) * 7 * min(1, self.owner.walking)
                rotationMod += math.sin(si * math.pi) * 7 * min(1, self.owner.walking)

            rotation = -r + rotationMod
        else:
            rotation = -110 if self.owner.facingRight else -70
            yA = -50 - self.owner.yComponent

        if self.owner.isRolling() and not self.owner.ableToFire:
            rotation -= self.owner.rollAngle

        rotation = rotation % 360

        if self.owner.isRolling():
            RGAIN = 3000
        elif self.owner.holster:
            RGAIN = 2000
        else:
            RGAIN = 2500

        DIFF = angle_diff(self.ROTATION, rotation)

        rotation_factor = self.app.smoothRotationFactor(
            self.ROTATIONVEL,
            RGAIN,
            DIFF
        )

        self.ROTATIONVEL += rotation_factor * self.app.dt
        self.ROTATION += self.ROTATIONVEL * self.app.dt
        self.ROTATION = self.ROTATION % 360

        if 90 <= self.ROTATION <= 270:
            self.FINALROTATION = self.ROTATION - self.rA
            meleeOffset = v2(-xA, yA)
        else:
            self.FINALROTATION = self.ROTATION + self.rA
            meleeOffset = v2(xA, yA)

        self.holdingOut = v2(
            math.sin((90 - self.FINALROTATION) * math.pi / 180),
            -(math.cos((90 - self.FINALROTATION) * math.pi / 180))
        ) * (20 - 20 * self.holdoutAmountDelta)

        self.handleSprite()

        pos = self.owner.BLITPOS

        self.BLITPOS = pos + self.holdingOut + v2(xA, yA + self.owner.breatheY + 50 - weaponBreathe * 3)
        BP = self.app.convertPos(self.BLITPOS)
        self.app.screen.blit(self.rotatedImage, BP - v2(self.rotatedImage.get_size()) / 2)

    def fireTick(self):
        pass

    def hudTick(self):
        pass