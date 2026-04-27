import random
import subprocess, sys
import threading
from dialog import Dialog
import pygame
import keypress, os
from pygame import Vector2 as v2
from player import Player
import math
from audioPlayer.audioMixer import AudioMixer, AudioSource
from particles.particle import ParticleSystem
from bullet import Bullet
import time
from core.render_los_image_jit import draw as DRAWLOS
import numpy as np
from weapon import Weapon
from objects.speaker import Speaker
from wall import Wall
import json
from floorSolver import solve
from concurrent.futures import ThreadPoolExecutor
import threading
from los.los_walls import build_and_cache
from los.los_draw import draw as los_draw
from objects.pill import Pill
from enemies.enemy import Enemy
from level import Level, AreaType
from nav import NavGraph
from light import StaticLight, make_muzzle_flash_frames
from scorepopup import ScorePopup
def blit_glitch(screen, image, pos, glitch = 2, diagonal = False, black_bar_chance = 15, black_bar_color = (0,0,0)):
    upper_pos = 0
    lower_pos = random.randint(2, 5)
    image_size = image.get_size()
    while 1:
        if random.randint(1, black_bar_chance) != 1:
            screen.blit(
                image,
                [pos[0] + random.randint(-glitch, glitch), pos[1] + upper_pos + (0 if not diagonal else random.randint(-glitch, glitch))],
                area=[0, upper_pos, image_size[0], lower_pos-upper_pos],
            )
        if lower_pos == image_size[1]:
            break
        upper_pos = lower_pos
        lower_pos += random.randint(2, 5)
        if lower_pos >= image_size[1]:
            lower_pos = image_size[1]

class App:
    
    def __init__(self):
        self.res = v2(1920,1080)
        self.RENDER_SCALE = self.res.x / 2560
        self.screen = pygame.display.set_mode((self.res.x, self.res.y), pygame.SCALED | pygame.FULLSCREEN) #
        self.clock = pygame.time.Clock()
        self.keypress = []
        self.keypress_held_down = []
        pygame.font.init()
        pygame.mixer.init()
        self.font = pygame.Font("texture/agencyb.ttf", int(30*self.RENDER_SCALE))
        self.fontSmaller = pygame.Font("texture/agencyb.ttf", int(20*self.RENDER_SCALE))
        self.titleFont = pygame.Font("texture/agencyb.ttf", int(20*self.RENDER_SCALE))
        self.loading = True
        self.loadPoint = 0
        self.maxLoad = 10
        self.currLoad = ""

        t = threading.Thread(target=self.load)
        t.daemon = True
        t.start()





    def load(self):

        self.currLoad = "Initializing"
        self.losScreen = pygame.Surface(self.res)
        self.losScreen.set_colorkey((255,255,255))

        self.gunFont = pygame.font.Font("texture/terminal.ttf", int(60*self.RENDER_SCALE))
        self.infoFont = pygame.font.Font("texture/terminal.ttf", int(30*self.RENDER_SCALE))

        self.font40 = pygame.font.Font("texture/terminal.ttf", int(40*self.RENDER_SCALE))
        self.timerFont = pygame.Font("texture/d7.ttf", int(70*self.RENDER_SCALE))
        
        self.entityTypes = ["misc", "players", "bullets"]
        self.entities = {x: [] for x in self.entityTypes}
        print(self.entities)
        self.particle_list = []
        self.trails = []
        self.debugI = 0

        self.pillTextures = []
        for x in range(4):
            s = pygame.image.load(f"texture/pills/pill{x+1}.png").convert_alpha()
            s = self.scaleTexture(s, desiredWidth=20)
            self.pillTextures.append(s)

        

        self.pillHUD = pygame.image.load("texture/pills/pillHUD.png").convert_alpha()
        self.pillHUD = self.scaleTexture(self.pillHUD, desiredWidth=50)

        

        self.introMusic = pygame.Sound("audio/music/intro.wav")
        self.HEAT = 0
        self.introPlayed = False
        self.music = self.loadSound("audio/music/bar", volume = 1.0, asPygame=True)
        self.hitSounds = self.loadSound("audio/hit")
        self.deathSounds = self.loadSound("audio/death")
        self.musicChannel = pygame.Channel(0)
        self.Player = Player

        tileTexture = pygame.image.load("texture/tile2.jpg").convert()
        self.tileTexture = self.scaleTextureSmooth(tileTexture, desiredHeight=100)

        tileTexture2 = pygame.image.load("texture/tile1.jpg").convert()
        self.tileTexture2 = self.scaleTextureSmooth(tileTexture2, desiredHeight=100)

        tileTexture3 = pygame.image.load("texture/tile3.jpg").convert()
        self.tileTexture3 = self.scaleTextureSmooth(tileTexture3, desiredHeight=100)

        self.enemiesSpottedPlayer = False
        self.sightToPlayer = False
        self.enemiesSeePlayer = 0
        self.alertIndex = -1

        Speaker(self, [200,-400])
        Speaker(self, [-200,-400])

        self.bulletSprite = pygame.image.load("texture/bullet.png").convert_alpha()
        self.bulletSprite = pygame.transform.scale(self.bulletSprite, [200, 5])
        
        self.glitch = 0
        self.AUDIOVOLUME = 0.5
        self.TOTAL_TIME_ADJUSTMENT = 1.0

        
        self.PARTICLESYSTEM = ParticleSystem(self)
        self.camPD = v2(0,0)
        self.camPD_f = v2(0,0)
        self.cacheLock = threading.Lock()
        self.player = Player(self, v2(0,0), "texture/crack.png", True, True)
        self.bouncerTemp = Player(self, v2(0,0), "texture/bouncer.png", aiType="pistol")

        self.enemyTemp = Enemy(self, v2(0,0))

        self.WEAPON_USPS = Weapon(self, None, texture = "texture/pistol.png", name = "USP-S", 
                                  sizeMult=0.5, holdoutPos = -2.0, shotSound="audio/silenced2.wav", 
                                  rps = 10, magCap = 12, damage = 5)

        self.lastSec = -1
        self.addEntity(self.player)
        
        self.timeStarted = time.time()

        self.fade = []
        s = pygame.Surface(self.res)
        s.fill((0,0,0))
        for x in range(10):
            s2 = s.copy()
            s2.set_alpha(int(x*255/9))
            self.fade.append(s2)

        self.fadeTimer = 0
        self.maxFade = 0.25
        self.fadePhase = 2
        self.pillAmount = 0

        self.SCORE_POPUP = ScorePopup(self)
        self.totalScore = 0


        self.dt = 0.016
        self.fps = 180
        self.interactingWith = None
        self.dialog = None

        
        #self.loop.cutoff = None
        self.prevSpotted = False
        self.stateAnim = 0

        self.level = Level.load()

        #self.mapAreas = level.areas
        TILESIZE = 100
        self.mapAreas = [(pygame.Rect(a[0] * TILESIZE, a[1] * TILESIZE, a[2] * TILESIZE, a[3] * TILESIZE), a[4]) for a in self.level.areas]

        self.defDialog = dialogue = [
                "HELLO. I HAVE IDENTIFIED YOU AS A POTENTIAL MATING PARTNER.",
                "Uh… hi?",
                "MY HEART RATE HAS INCREASED BY 23 PERCENT IN YOUR PRESENCE.",
                "That's… specific.",
                "I HAVE PREPARED THREE TOPICS: WEATHER, NUTRITION, AND YOU.",
                "You can just talk normally, you know.",
                "AFFIRMATIVE. NORMAL MODE ENGAGED. YOU LOOK… STATISTICALLY PLEASING.",
                "I think you mean 'nice', but thanks.",
                "CORRECTION ACCEPTED. YOU LOOK NICE. I AM EXPERIENCING CONFUSION.",
                "About what?",
                "I DO NOT KNOW WHERE TO PLACE MY HANDS.",
                "Anywhere but hovering like that would be a good start.",
                "ACKNOWLEDGED. HANDS RETURNED TO NEUTRAL POSITIONS.",
                "Much better.",
                "WOULD YOU LIKE TO EXCHANGE CONTACT INFORMATION FOR FUTURE INTERACTIONS?",
                "You mean like… numbers?",
                "YES. NUMBERS WOULD BE OPTIMAL.",
                "§ure, I guess that works.",
                "SUCCESS. THIS INTERACTION EXCEEDED EXPECTATIONS.",
                "I'm glad one of us knows what just happened."
            ]
        
        self.currLoad = "Loading walls"
        self.loadWalls()

        self.los_walls = build_and_cache("level.json", "wall_cache.json", True, self.RENDER_SCALE)

        self.DOLIGHTS = True

        if self.DOLIGHTS:
            self.currLoad = "Making muzzle flashes"
            self.MUZZLE_FLASH_FRAMES = make_muzzle_flash_frames()
            self.generateLights("level.json")
        self.muzzleFlashes = []
        self.currLoad = "Lights done"

        tHid = self.gunFont.render("HIDDEN", True, [255,255,255])
        tSpot = self.gunFont.render("SPOTTED", True, [0,0,0])
        x = max(tHid.get_width(), tSpot.get_width())
        y = max(tHid.get_height(), tSpot.get_height())
        self.hidspot_surf = pygame.Surface((x,y))
        self.hidspot_surf.set_colorkey((0,0,0))

        print(self.los_walls.shape)

        self.los_surf = pygame.Surface(self.res)
        self.los_surf.set_colorkey((255, 255, 255))

        self.currLoad = "Loading navgraph"
        self.nav = NavGraph.load("level.json", self.los_walls, self.RENDER_SCALE)

        self.currLoad = "Initting audio engine"
        self.AUDIOMIXER = AudioMixer(self, chunk_size=1024)
        self.AUDIOMIXER.start_stream()

        self.warmupSound = self.playPositionalAudio("audio/waddle1.wav", v2(0,0), volume=0.1)
        while self.warmupSound.active:
            time.sleep(0.25)

        self.loop = self.playPositionalAudio("audio/klbutekno.wav", v2(0,0), loop = True, volume=1.0)
        self.loop.pitch = 1

        self.loading = False

        #self.dialog = ["Moi", "Moikka, mikä sun nimi on?", "Ei se sulle kuulu", ]


    def scaleTexture(self, image, desiredHeight = None, desiredWidth = None):
        return pygame.transform.scale_by(image, desiredHeight*self.RENDER_SCALE / image.get_height() if desiredHeight else desiredWidth*self.RENDER_SCALE / image.get_width())
    
    def scaleTextureSmooth(self, image, desiredHeight = None, desiredWidth = None):
        return pygame.transform.smoothscale_by(image, desiredHeight*self.RENDER_SCALE / image.get_height() if desiredHeight else desiredWidth*self.RENDER_SCALE / image.get_width())

    def renderLights(self):
        self.light_frame_time += self.dt
        self.light_frame_time %= 1

        lightframe = int(self.light_frame_time * (len(self.light_frames) - 1))

        screen_rect = self.screen.get_rect()
        # camPD is in world space; convert to render space for the offset
        cam_render = self.camPD * self.RENDER_SCALE - self.res / 2

        for surf, r in self.light_static:
            screen_pos = v2(r.topleft) - cam_render
            screen_pos = (int(screen_pos.x), int(screen_pos.y))
            if not screen_rect.colliderect((screen_pos, surf.get_size())):
                continue
            self.screen.blit(surf, screen_pos, special_flags=pygame.BLEND_RGB_MULT)

        for surf, r in self.light_frames[lightframe]:
            screen_pos = v2(r.topleft) - cam_render
            screen_pos = (int(screen_pos.x), int(screen_pos.y))
            if not screen_rect.colliderect((screen_pos, surf.get_size())):
                continue
            self.screen.blit(surf, screen_pos, special_flags=pygame.BLEND_RGB_MULT)

        for MF in self.muzzleFlashes:
            MF.renderTo(self.screen)
            MF.tick()

    def generateLights(self, level_file):
        print("Generating lights.")
        
        t = time.time()
        

        self.currLoad = "Generating lights"
        
        self.loadPoint = 0

        self.maxLoad = len(self.level.lights) + len(self.floorRects)

        self.mapCorner = v2(
            min(w.rect.left for w in self.walls),
            min(w.rect.top  for w in self.walls)
        )

        for i, LIGHT in enumerate(self.level.lights):
            self.loadPoint += 1
            print(f"Light {i}: Making wall mask")
            r = int(LIGHT.radius * self.RENDER_SCALE)
            LIGHT.los_surf = pygame.Surface((r * 2, r * 2))
            LIGHT.los_surf.fill((0, 0, 0))
            # Camera = render-space top-left of this light's bounding box
            light_cam = LIGHT.pos * self.RENDER_SCALE - v2(r, r)
            los_draw(LIGHT.los_surf, LIGHT.pos * self.RENDER_SCALE, light_cam, self.los_walls, debug=False)
            LIGHT.is_static = isinstance(LIGHT, StaticLight)

        def light_touches_rect(light, r):
            closest_x = max(r.left, min(light.pos.x, r.right))
            closest_y = max(r.top,  min(light.pos.y, r.bottom))
            return v2(closest_x, closest_y).distance_to(light.pos) < light.radius

        rect_lights  = {}
        rect_dynamic = {}
        for i, r in enumerate(self.floorRects):
            touching = [L for L in self.level.lights if light_touches_rect(L, r)]
            rect_lights[i]  = touching
            rect_dynamic[i] = any(not L.is_static for L in touching)

        def bake_rect(i, r, x):
            rect_surf = pygame.Surface((r.width, r.height)).convert()
            rect_surf.fill((40, 40, 40))
            for LIGHT in rect_lights[i]:
                radius = int(LIGHT.radius * self.RENDER_SCALE)

                if not LIGHT.scaled_frames[x]:

                    QUALITY = 5
                    smR = int(radius * 2 / QUALITY)

                    scaled = pygame.transform.smoothscale(LIGHT.frames[x], (smR, smR))
                    if QUALITY > 1:
                        scaled = pygame.transform.scale(scaled, (radius * 2, radius * 2))
                    # Apply the LOS mask: black out areas the light can't reach
                    scaled.blit(LIGHT.los_surf, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                    LIGHT.scaled_frames[x] = scaled
                else:
                    scaled = LIGHT.scaled_frames[x]

                blit_pos = LIGHT.pos * self.RENDER_SCALE - v2(radius) - v2(r.topleft)
                rect_surf.blit(scaled, blit_pos, special_flags=pygame.BLEND_RGB_ADD)
            return rect_surf

        NUM_FRAMES = len(self.level.lights[0].frames) if self.level.lights else 1

        self.light_static = []
        self.light_frames = [[] for _ in range(NUM_FRAMES)]

        for i, r in enumerate(self.floorRects):
            self.loadPoint += 1
            print(f"Rect: {i}/{len(self.floorRects)}")

            rectConverted = r.copy()
            rectConverted.x = int(r.x * self.RENDER_SCALE)
            rectConverted.y = int(r.y * self.RENDER_SCALE)
            rectConverted.width = int(r.width * self.RENDER_SCALE)
            rectConverted.height = int(r.height * self.RENDER_SCALE)
           

            if not rect_dynamic[i]:
                self.light_static.append((bake_rect(i, rectConverted, 0), rectConverted))
            else:
                for x in range(NUM_FRAMES):
                    self.light_frames[x].append((bake_rect(i, rectConverted, x), rectConverted))

        self.light_frame_time = 0
        print(f"Lights drawn. Elapsed time: {time.time() - t:.1f}s")
        
    def checkPositionArea(self, pos):
        for rect, a_t in self.mapAreas:
            if rect.collidepoint(pos):
                return a_t
        else:
            return None
        



    def incrementSight(self):

        self.enemiesSeePlayer += self.dt
        self.enemiesSeePlayer = min(1, self.enemiesSeePlayer)

        if not self.enemiesSpottedPlayer:
            index = self.enemiesSeePlayer // 0.125
            if index != self.alertIndex:
                audio = self.playPositionalAudio("audio/sightalert.wav", self.player.pos, volume=1.2)
                scale = [0, 2, 4, 5, 7, 9, 11, 12, 14]
                audio.pitch = 2 ** (scale[int(index % len(scale))] / 12)
            self.alertIndex = index

            if self.enemiesSeePlayer >= 1:
                self.enemiesSpottedPlayer = True
                self.playPositionalAudio("audio/spotted.wav", self.player.pos, volume=1.2)




    def loadWalls(self):

        
        SAVE_FILE = "level.json"

        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE) as f:
                l = [list(r) for r in json.load(f)["walls"]]

        fr = solve(l)

        TILESIZE = 100

        self.floorRects = []
        self.floorSurfs = []
        self.maxLoad = len(fr)
        self.loadPoint = 0
        for x,y,w,h in fr:
            r = pygame.Rect(v2(x,y) * TILESIZE, v2(w,h) * TILESIZE)
            self.floorRects.append(r)

            s = pygame.Surface(v2(r.size) * self.RENDER_SCALE)
            self.paintFloor(s, r.topleft)
            
            self.floorSurfs.append((s, r.topleft))
            self.loadPoint += 1

            
        self.walls = []
        for x,y,w,h in l:
            self.walls.append(Wall(self, (x,y), (w,h)))

    def paintFloor(self, s, topleft):
        x = 0
        while x < s.get_width():
            y = 0
            while y < s.get_height():

                pos = v2(x,y) / self.RENDER_SCALE + topleft + [50,50]

                t = self.checkPositionArea(pos)
                if t == AreaType.DANCEFLOOR:
                    texture = self.tileTexture
                elif t == AreaType.OUTSIDE:
                    texture = self.tileTexture3
                else:
                    texture = self.tileTexture2

                s.blit(texture, (x,y))
                y += self.tileTexture.get_height()
            x += self.tileTexture.get_width()




    def addEntity(self, ent):
        if isinstance(ent, (Player, Enemy)):
            self.entities["players"].append(ent)

        elif isinstance(ent, Bullet):
            self.entities["bullets"].append(ent)

        else:
            self.entities["misc"].append(ent)

    def removeEntity(self, ent):
        for x in self.entities:
            if ent in self.entities[x]:
                self.entities[x].remove(ent)

    def loadSound(self, fileHint, startIndex = 1, suffix=".wav", volume = 0.3, asPygame = False):
        l = []
        while True:
            f = fileHint + str(startIndex) + suffix
            if os.path.exists(f):
                if asPygame:
                    l.append(pygame.mixer.Sound(f))
                    l[-1].set_volume(volume)
                else:
                    l.append(f)
                startIndex += 1

            else:
                return l
            

    def spawnEnemies(self):

        if len(self.entities["players"]) > 8:
            return

        a = random.uniform(0, math.pi*2)
        pos = v2(random.choice(self.floorRects).center)

        if self.nav.can_see(pos, self.player.pos):
            return

        bouncer = self.enemyTemp.duplicate(pos)
        self.WEAPON_USPS.duplicate(bouncer)
        self.addEntity(bouncer)

            

    def handleMusic(self):
        if not self.musicChannel.get_sound():

            if not self.introPlayed:
                self.musicChannel.play(self.introMusic)
                self.introPlayed = True
                self.timeStarted = time.time()
                return
            
            
            self.HEAT += random.randint(0,1)
            self.HEAT = self.HEAT % 4
            self.musicChannel.play(self.music[self.HEAT])
            

    def drawTimer(self):

        timeRemaining = self.timeStarted + 5*60+16 - time.time()
        minutes = int(timeRemaining / 60)
        seconds = int(timeRemaining % 60)

        if seconds != self.lastSec:
            self.glitch = 0.4
        self.lastSec = seconds
        t = self.timerFont.render(f"{minutes:02}:{seconds:02}", True, [255, 239, 92])
        pos = (self.res.x/2 - t.get_width()/2, 10)
        if self.glitch > 0:
            
            blit_glitch(self.screen, t, pos, glitch=int(10 * (self.HEAT + 1) * self.glitch))
            self.glitch -= self.dt
        else:
            self.screen.blit(t, pos)
            

    def tickTrails(self):
        toremove = []
        for i, trail in enumerate(self.trails):
            if trail:
                trail.pop(0)
            if not trail:
                toremove.append(i)

        for i in reversed(toremove):
            self.trails.pop(i)

    def renderTrails(self):
        for trail in self.trails:
            if len(trail) < 2:
                continue
            Bullet.renderTrail(self, trail)
            

    def drawHud(self):
        if self.player.weapon:

            WEAPON = self.player.weapon

            p = v2(20, 20) * self.RENDER_SCALE
            self.screen.blit(WEAPON.hudImage if not self.player.holster else WEAPON.hudImageH, p)
            text = self.gunFont.render(WEAPON.name, True, (255,255,255))
            self.screen.blit(text, p)

            if self.player.holster:
                text = self.infoFont.render("HOLSTERED", True, (255,255,255))
                self.screen.blit(text, p + v2(0, 65) * self.RENDER_SCALE)

            if WEAPON.reloadTimer > 0:
                text = self.infoFont.render(f"RELOADING: {(WEAPON.reloadTime - WEAPON.reloadTimer)*100/WEAPON.reloadTime:.0f}%", True, (255,255,255))
                self.screen.blit(text, p + v2(0, 100) * self.RENDER_SCALE)
            else:
                text = self.infoFont.render(f"MAG: {WEAPON.mag}/{WEAPON.magCap}", True, (255,255,255))
                self.screen.blit(text, p + v2(0, 100) * self.RENDER_SCALE)

            text = self.gunFont.render(self.player.weapon.name, True, (255,255,255))

        self.screen.blit(self.pillHUD, p + v2(0, 140) * self.RENDER_SCALE)
        text = self.font40.render(f":{self.pillAmount}", True, (255,255,255))
        self.screen.blit(text, p + v2(self.pillHUD.get_width(), 140 * self.RENDER_SCALE))
        

        health = self.player.health
        bars = int(health // 10)
        if bars > 0:
            for x in range(bars):
                r = pygame.Rect((20 + x * 40) * self.RENDER_SCALE, self.res.y - 60 * self.RENDER_SCALE, 36 * self.RENDER_SCALE, 40 * self.RENDER_SCALE)
                pygame.draw.rect(self.screen, [255,255,255], r)

        pygame.draw.rect(self.screen, [255,255,255], (16 * self.RENDER_SCALE, self.res.y - 64 * self.RENDER_SCALE, 404 * self.RENDER_SCALE, 48 * self.RENDER_SCALE), width = 1)
        text = self.gunFont.render("HEALTH", True, (255,255,255))

        self.screen.blit(text, (16, self.res.y - 66 * self.RENDER_SCALE - text.get_height()))

            

    def logParticleEffect(self, fn, args, kwargs):

        tick = self.demoTick
        ticks = self.DEMO.setdefault("ticks", {})

        tick_data = ticks.setdefault(tick, {})
        creates = tick_data.setdefault("create", [])

        creates.append((fn, args, kwargs))
        
    def debugText(self, text):
        t = self.fontSmaller.render(str(text), True, [255,255,255])
        self.screen.blit(t, [self.res[0] - 20 - t.get_size()[0], max(self.res[1] - 700, 0) + self.debugI * 22])
        self.debugI += 1

    def getAngleFrom(self, fromPoint, toPoint):
        return math.radians(v2([0,0]).angle_to(v2(toPoint) - v2(fromPoint))) 
    
    def playPositionalAudio(self, audio, pos = None, volume = 0.5, loop = False):

        if isinstance(audio, list):
            audio = random.choice(audio)


        return self.AUDIOMIXER.playPositionalAudio(audio, pos, volume=volume, loop = loop)
    
    def drawHiddenHud(self):
        prog = self.enemiesSeePlayer  # [0,1]
        state = self.enemiesSpottedPlayer

        # --- detect state change ---
        if state != self.prevSpotted:
            self.stateAnim = 0.0
            self.prevSpotted = state

        # --- advance animation ---
        speed = 6.0  # 1/s → ~0.17s
        self.stateAnim = min(1.0, self.stateAnim + speed * self.dt)

        # ease-out (critical for not looking cheap)
        t = 1 - (1 - self.stateAnim)**3

        # --- text selection ---
        label = "SPOTTED" if state else "HIDDEN"
        color = (255, 80, 80) if state else (255, 255, 255)

        base = self.gunFont.render(label, True, color).convert_alpha()

        # --- scale "pop" animation ---
        # starts slightly larger, settles to 1.0
        scale = 1.0 + 0.25 * (1 - t)
        w = int(base.get_width() * scale)
        h = int(base.get_height() * scale)
        surf = pygame.transform.smoothscale(base, (w, h))

        # optional fade-in on change
        surf.set_alpha(int(255 * t))

        center = (self.res.x // 2, int(self.res.y / 5))
        rect = surf.get_rect(center=center)

        self.screen.blit(surf, rect.topleft)

        # --- centered progress bar ---
        bar_w = max(base.get_width(), 120)
        bar_h = 6

        bx_center = center[0]
        by = rect.bottom + 6

        filled = int(bar_w * prog)

        # center-expand: split left/right
        left = bx_center - filled // 2

        pygame.draw.rect(self.screen, (60, 60, 60),
                        (bx_center - bar_w // 2, by, bar_w, bar_h))

        pygame.draw.rect(self.screen, (255, 80, 80),
                        (left, by, filled, bar_h))
                

    
    def smoothRotationFactor(self, angleVel, gainFactor, diff):
        dir = 1 if diff > 0 else -1
        gainFactor *= min(1, abs(diff) * 3)
        gainFactor = max(0.1, gainFactor)

        # Your original calculation - time needed to decelerate to zero
        if abs(angleVel) < 1e-6:  # Avoid division by zero
            decelarationTicks = 0
        else:
            try:
                decelarationTicks = abs(angleVel / gainFactor)
            except:
                print("VITUN OUTO BUGI")
                print(angleVel, gainFactor)
                decelarationTicks = 0
        # Your original calculation - distance covered while decelerating
        distanceDecelerating = angleVel * decelarationTicks - 0.5 * dir * gainFactor * decelarationTicks**2
        
        acceleratingMod = 1 if distanceDecelerating < diff else -1
        
        return acceleratingMod * gainFactor

    def smoothe(self, value, target, k):
        alpha = 1.0 - math.exp(-k * self.dt)
        return value * (1 - alpha) + target * alpha
        
    def convertPos(self, pos, heightDiff=1.0, skipRenderScale = False):
        screen_center = self.res * 0.5
        if skipRenderScale:
            return (pos - self.camPD) * heightDiff + screen_center
        return (pos - self.camPD) * self.RENDER_SCALE * heightDiff + screen_center
    
    def inverseConvertPos(self, screen_pos, heightDiff=1.0):
        return (screen_pos - self.res * 0.5) / (self.RENDER_SCALE * heightDiff) + self.camPD
    
    def initiateFade(self):
        self.fadePhase = 0
        self.fadeTimer = 0

    def loadRender(self):
        if hasattr(self, "gunFont"):
            t = self.gunFont.render("LOADING", True, [255,255,255])
            self.screen.blit(t, self.res/2 - v2(t.get_size())/2)

        if hasattr(self, "infoFont"):
            t = self.infoFont.render(self.currLoad, True, [255,255,255])
            self.screen.blit(t, self.res/2 - v2(t.get_size())/2 + [0, 65])

        loadRect = pygame.Rect(self.res.x/2 - 100, self.res.y/2 + 100, 200, 8)
        bar = loadRect.copy()
        bar.inflate_ip(4,4)
        pygame.draw.rect(self.screen, [255,255,255], bar, width=1)

        loadRect.width = 200 * self.loadPoint / self.maxLoad

        pygame.draw.rect(self.screen, [255,255,255], loadRect)

        pygame.display.flip()
        self.dt = self.clock.tick(30) / 1000.0

    def grantScore(self, amount, label=""):
        self.totalScore += amount
        self.SCORE_POPUP.grant(amount, label)


    def run(self):
        while True:
            self.debugI = 0
            keypress.key_press_manager(self)
            #mouseoffset = (self.mouse_pos - self.res/2)*0.35
            
        
            self.screen.fill((0,0,0))
            

            if self.loading:
                self.loadRender()
                continue

            self.los_surf.fill((0,0,0))

            self.cameraPos = self.player.pos.copy()
            if self.interactingWith:
                self.cameraPos = (self.player.pos + self.interactingWith.pos)/2 - self.res/2
                self.cameraPos.y += self.res.y * 0.35
            #if self.player.ableToFire:
            mouseoffset = (self.mouse_pos - self.res * 0.5) / self.RENDER_SCALE * 0.35
            self.cameraPos += mouseoffset
            k = 5.0  # tune this (e.g. 5–20)
            alpha = 1.0 - math.exp(-k * self.dt)

            self.camPD_f = self.camPD_f * (1 - alpha) + self.cameraPos * alpha
            self.camPD = v2(int(self.camPD_f.x), int(self.camPD_f.y))
            
            #self.handleMusic()

            self.spawnEnemies()

            

            for r2 in self.floorRects:

                r = r2.copy()

                r.topleft = self.convertPos(r2.topleft)
                r.size = v2(r2.size) * self.RENDER_SCALE

                #pygame.draw.rect(self.screen, (50,50,50), r)
                pygame.draw.rect(self.los_surf, (20,20,20), r)

            for surf, topleft in self.floorSurfs:
                pos = self.convertPos(topleft)
                self.screen.blit(surf, pos)

            

            self.player.tickPlayerHealth()
            self.sightToPlayer = False
            for key in self.entityTypes:
                for x in self.entities[key]:
                    if x == self.player:
                        continue
                    x.tick()

            self.player.tick()

            if self.sightToPlayer:
                self.incrementSight()
            else:
                if self.enemiesSpottedPlayer:
                    self.enemiesSeePlayer -= self.dt*0.25
                else:
                    self.enemiesSeePlayer -= self.dt

                self.enemiesSeePlayer = max(0, self.enemiesSeePlayer)
                if self.enemiesSeePlayer > 0:
                    self.alertIndex = self.enemiesSeePlayer // 0.125
                else:
                    if self.enemiesSpottedPlayer:
                        self.enemiesSpottedPlayer = False
                        self.alertIndex = -1

                

            self.tickTrails()
            self.renderTrails()

            #self.light_layer.fill((255, 50, 50))

            t = time.perf_counter()


            for x in self.particle_list:
                x.tick()
                x.render(self.screen)

            poly = los_draw(
                self.los_surf,     # shape: self.res
                self.player.pos * self.RENDER_SCALE,   # world space
                self.camPD * self.RENDER_SCALE - self.res/2,        # world camera
                self.los_walls,    # Converted to render scale
                debug=False
            )

            if self.DOLIGHTS:
                self.renderLights()
            
            lostime = 1000 * (time.perf_counter() - t)
            #self.screen.blit(los, (0,0))

            # each frame, after drawing the scene:

            

            

            

            self.screen.blit(self.los_surf, (0, 0))


            for x in self.walls:
                x.render()

            if False: # DEBUG PATH
                debugPath = self.nav.get_path(self.player.pos, v2(0,0))
                lp = self.player.pos
                for x in debugPath + [v2(0,0)]:
                    pygame.draw.line(self.screen, [255,0,0], self.convertPos(lp), self.convertPos(x))
                    lp = x
        
            if self.fadePhase < 2:

                self.fadeTimer += self.dt

                len_fade = len(self.fade) - 1
                FRAME = int(min(len_fade, len_fade * self.fadeTimer / self.maxFade))
                print(FRAME)
                if self.fadePhase == 0:
                    self.screen.blit(self.fade[FRAME], (0,0))

                elif self.fadePhase == 1:
                    self.screen.blit(self.fade[len_fade - FRAME], (0,0))

                if self.fadeTimer > self.maxFade:
                    self.fadeTimer = 0
                    self.fadePhase += 1


            if not self.interactingWith and False:
                closest = self.player._playerDetectInteraction()
                if closest:
                    text = self.font.render(f"Press E to interact with {closest.name}", True, (255,255,255))
                    pos = closest.pos - v2(0, 100) - v2(text.get_size()) / 2 - self.camPD
                    self.screen.blit(text, pos)

                    if "e" in self.keypress:
                        self.interactingWith = closest
                        self.keypress.remove("e")
                        self.dialog = Dialog(self, self.defDialog, self.player, closest)

            if self.interactingWith:
                if self.player.pos.distance_to(self.interactingWith.pos) > 300 or "esc" in self.keypress:
                    self.interactingWith = None
                    if self.dialog:
                        self.dialog.fadingOut = True

            if self.dialog:
                self.dialog.tick()
                if not self.dialog.alive:
                    self.dialog = None
                    self.interactingWith = None 


            if self.player.ableToFire:
                self.player.weapon.hudTick()


            if pygame.mouse.get_visible() == self.player.ableToFire:
                pygame.mouse.set_visible(not self.player.ableToFire)

            self.debugText(f"AUDIO: {len(self.AUDIOMIXER.audio_sources)}")

            ent = [len(self.entities[x]) for x in self.entities]

            self.debugText(f"ENT: {ent}")
            self.debugText(f"SIGHT: {self.enemiesSeePlayer:.1f}")

            self.drawHud()
            self.drawHiddenHud()

            self.SCORE_POPUP.tick()
            self.SCORE_POPUP.render()

            self.drawTimer()

            #pygame.draw.circle(self.screen, (255,0,0), self.inverseConvertPos(v2(0,0)), 4)
            #pygame.draw.circle(self.screen, (0,255,0), self.convertPos(self.player.pos), 10)
            self.debugText(self.inverseConvertPos(v2(0,0)))

            self.debugText(f"FPS: {self.fps:.0f}")
            self.debugText(f"TIME ON LOS: {lostime:.1f}ms")
            #if self.DOLIGHTS:
            #    self.debugText(f"LIGHTFRAME: {lightframe}")
            pygame.display.flip()
            self.dt = self.clock.tick(180) / 1000.0
            self.dt = min(0.1, self.dt)

            self.fps = self.clock.get_fps() * 0.01 + self.fps * 0.99
            
def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside

if __name__ == "__main__":
    app = App()
    app.run()