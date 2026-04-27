from animationHelper import *
from imageprocessing.imageProcessing import gaussian_blur, trim_surface, remove_background, remove_background_bytes, generate_corpse_sprite, set_image_hue_rgba, colorize_to_blood, get_or_remove_background, brighten_surface, outline_surface
from PIL import Image
import io
from pygame import Vector2 as v2
import random
from imageprocessing.faceMorph import getFaceLandMarks, processFaceMorph, get_or_load_landmarks
import numpy as np
from particles.bloodSplatter import BloodSplatter
from objects.pill import Pill

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import App
class ParentActor:
    def __init__(self, app: "App", pos, path):
        

        self.app = app
        self.pos = pos
        self.BLITPOS = pos.copy()
        self.dvel = v2(0,0)
        self.vel = v2(0,0)
        self.speed = 500

        if path:
            self.processImage(path)

        self.facingRight = True
        self.walking = 0
        self.stepI = 0
        self.walkingSpeedMult = 1
        self.runOffset = 0
        self.running = False
        self.blink = 1
        self.holster = False
        self.killed = None
        self.hitBox = pygame.Rect((0,0), (100,100))
        self.rolling = 0.0
        self.rollTime = 0.75
        self.rollDir = v2(0,0)
        self.rollingRight = True
        self.rollAngle = 0
        self.landed = False
        self.health = 100
        self.targetPos = v2(0,0)
        self.outOfCombat = 0.0
        self.aimTimer = 0
        self.shooting = False
        self.breatheTimer = 0
        self.weapon = None


    def mandatoryTick(self):
        speedMod = 0.85
        if not self.holster:
            speedMod = 0.75

        if self.rolling > 0:
            self.rolling -= self.app.dt
            VELOCITY = self.rollDir * self.speed * self.app.dt * (self.rolling/self.rollTime + 0.5) * 2.7 * speedMod

        else:
            VELOCITY = self.dvel * self.speed * self.app.dt * speedMod
        self.pos += VELOCITY

        self.hitBox.center = self.pos

        moved = False
        for x in self.app.walls:
            hb = self.hitBox.copy()
            if x.resolve_collision(hb):
                self.hitBox.center = hb.center
                moved = True

        if moved:
            self.pos = v2(self.hitBox.center)

        if self.vel.length() > self.walking:
            self.walking += self.app.dt * 4
            self.walking = min(self.walking, self.vel.length())

        else:
            self.walking -= self.app.dt * 4

        self.walking = max(0, self.walking)

        self.breatheTimer += self.app.dt
        
        self.blink -= self.app.dt
        if self.blink <= 0:
            self.blink = random.uniform(0.2, 1.0)
        
        self.dvel = self.vel * 0.1 + self.dvel * 0.9


    def takeDamage(self, damage, bloodAngle = None):

        self.app.playPositionalAudio(self.app.hitSounds, self.pos, volume = 0.5)
        self.outOfCombat = 2.0

        if bloodAngle:
            for x in range(random.randint(int(damage/2),int(damage))):
                BloodSplatter(self.app, self.pos.copy() + [random.uniform(-10,10), random.uniform(-10,10)], bloodAngle)
        
        self.health -= damage
        if self.health <= 0:
            self.die()

    def die(self):
        self.app.removeEntity(self)
        self.app.playPositionalAudio(self.app.deathSounds, self.pos)
        for i in range(1, 3):
            self.app.addEntity(Pill(self.app, self.pos.copy()))

        if not self.player:
            if not self.app.enemiesSpottedPlayer:
                self.app.grantScore(50, "STEALTH KILL")
            else:
                self.app.grantScore(20, "LOUD KILL")


    
    def morph(self, image, eye_vert = 1.0):
        rgb = pygame.surfarray.array3d(image).swapaxes(0, 1)
        alpha = pygame.surfarray.array_alpha(image)

        landMarks = get_or_load_landmarks(self.app, rgb, "cache/landmarks_cache.json")
        if landMarks.dtype == object and landMarks.size == 1 and landMarks[()] is None:
            self.morphed = False
            return image
        
        # Left eye (landmarks 36-41)
        left_eye_points = landMarks[36:42]
        left_eye_center = left_eye_points.mean(axis=0)
        self.left_eye_center = v2(left_eye_center[0], left_eye_center[1]) / 400
        # Right eye (landmarks 42-47)  
        right_eye_points = landMarks[42:48]
        right_eye_center = right_eye_points.mean(axis=0)
        self.right_eye_center = v2(right_eye_center[0], right_eye_center[1]) / 400
        self.eyeMirror = v2(image.get_width()/image.get_height(), 0)

        result = processFaceMorph(rgb, landMarks, smileIntensity=8, eyeScale=2, eye_vert=eye_vert)
        surface_array = result.swapaxes(0, 1).astype(np.uint8)

        # Ensure alpha matches dimensions
        if alpha.shape != surface_array.shape[:2]:
            alpha = np.resize(alpha, surface_array.shape[:2])

        alpha = alpha.astype(np.uint8)

        # Create surface with alpha support
        surface_out = pygame.Surface(surface_array.shape[:2], flags=pygame.SRCALPHA, depth=32)

        # Blit the RGB data first (only 3 channels)
        pygame.surfarray.blit_array(surface_out, surface_array)

        # Then apply the alpha channel separately
        alpha_array = pygame.surfarray.pixels_alpha(surface_out)
        alpha_array[:] = alpha  # Note the transpose - pygame uses (width, height) while numpy uses (height, width)
        del alpha_array  # Release the pixel array lock
        self.morphed = True
        IMAGE = surface_out.convert_alpha()
        return IMAGE


    def processImage(self, path):
        with open(path, "rb") as f:
            imageRaw = f.read()

        image = get_or_remove_background(self.app, imageRaw, "cache/background_cache.json")
        # convert to pygame.Surface
        img = Image.open(io.BytesIO(image)).convert("RGBA")
        mode = img.mode
        size = img.size
        data = img.tobytes()
        image = pygame.image.frombuffer(data, size, mode).convert_alpha()
        image = trim_surface(image)
        image = self.morph(image, eye_vert = 1.2)
        imageBat = self.morph(image, eye_vert = 0.1)
        #self.image = pygame.transform.scale_by(image, 100 / image.get_height())
        self.image = self.app.scaleTexture(image, desiredHeight = 100)
        #self.hudImage = pygame.transform.scale_by(image, 500 / image.get_height())
        self.hudImage = self.app.scaleTexture(image, desiredHeight = 500)
        self.image = outline_surface(self.image, int(5 * self.app.RENDER_SCALE))
        #self.imageBat = pygame.transform.scale_by(imageBat, 100 / imageBat.get_height())
        self.imageBat = self.app.scaleTexture(imageBat, desiredHeight = 100)
        self.imageBat = outline_surface(self.imageBat, int(5 * self.app.RENDER_SCALE))

    def AIWeaponPointingAtPlayer(self):
        spawnpoint = self.weapon.bulletSpawnPoint()
        mp = self.app.player.pos
        baseRot = math.degrees(math.atan2(mp.y - spawnpoint.y, mp.x - spawnpoint.x)) - 270 # 

        baseRot2 = 90 - self.weapon.FINALROTATION

        return abs(angle_diff(baseRot, baseRot2)) < 5

    def isRunning(self):
        return self.runOffset > 0
    
    def isRolling(self):
        return self.rolling > 0
        #return (self.rollTime - self.rolling)/self.rollTime < 0.5


    def render(self):
        shadowPos = (self.hitBox.centerx, self.hitBox.bottom)
        r = pygame.Rect((0,0), (80, 40))
        r.center = self.app.convertPos(shadowPos)
        pygame.draw.ellipse(self.app.screen, (20,20,20), r)

        breathingMod = 1
        im = self.image if self.blink > 0.1 else self.imageBat
        if self.facingRight:
            im = pygame.transform.flip(im, True, False)
        self.breatheY = 2.5*math.sin(self.breatheTimer * 2 * math.pi) * breathingMod
        
        self.yComponent = 0
        self.xComponent = 0
        self.rotation = 0
        yAdd = 0
        Addrotation = 0


        if self.walking > 0 and not self.isRolling():
            s = self.stepI // 0.5

            self.stepI += self.app.dt * self.walking * 1.5

            if s != self.stepI // 0.5:
                self.app.playPositionalAudio("audio/waddle1.wav", self.pos, volume=0.5)


            # The player should be swinging from side to side when walking
            self.yComponent = abs(math.sin(self.stepI * 2 * math.pi)) * 15 * min(1, self.walking)
            # The player should move left and right when walking
            self.xComponent = math.cos(self.stepI * 2 * math.pi) * 15 * min(1, self.walking)
            self.rotation = math.cos(self.stepI * 2 * math.pi) * 7 * min(1, self.walking)
            Addrotation = 0
            if self.facingRight:
                Addrotation -= self.runOffset * 15 * min(1, self.walking) * abs(self.dvel.x)
            else:
                Addrotation += self.runOffset * 15 * min(1, self.walking) * abs(self.dvel.x)
            
            yAdd -= self.runOffset * 15

        rollReachScale = 0 

        if self.rolling > 0:
            self.facingRight = self.rollingRight

            t = (self.rollTime - self.rolling) / self.rollTime  # 0 → 1

            p = roll_angle(t)

            rollReachScale = max(0, math.sin((1/self.rollTime)*t*math.pi))

            yAdd += rollReachScale * 100 * self.rollTime

            if t > 0.5 and not self.landed:
                self.landed = True
                self.app.playPositionalAudio("audio/land.wav", self.pos, volume = 0.5)
            
            if self.rollingRight:
                self.rollAngle = p
            else:
                self.rollAngle = -p
            Addrotation += self.rollAngle

        elif self.running:
            self.facingRight = self.dvel.x > 0

        elif not self.holster and self.weapon and self.player:
            self.facingRight = not 90 <= self.weapon.ROTATION <= 270
        else:
            self.facingRight = self.dvel.x > 0

        if self.stepI > 1:
            self.stepI = 0
            
        tempIm = pygame.transform.scale_by(im, [1 + 0.05 * math.sin(self.breatheTimer * 2 * math.pi) * breathingMod, (1+rollReachScale*0.25) + 0.05 * math.cos(self.breatheTimer * 2 * math.pi) * breathingMod])
        tempIm = pygame.transform.rotate(tempIm, self.rotation - Addrotation)

        holdout = v2(0,0) if not self.weapon else self.weapon.holdingOut

        self.BLITPOS = self.pos + holdout*0.4 + v2(-self.xComponent, -self.yComponent + self.breatheY - yAdd)
        BP = self.app.convertPos(self.BLITPOS)

        self.app.screen.blit(tempIm, BP - v2(tempIm.get_size()) / 2)