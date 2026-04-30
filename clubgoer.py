import pygame
from pygame import Vector2 as v2
import random
import math
from parentActor import ParentActor
from level import AreaType

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from main import App


AREA_WEIGHTS = {
    AreaType.DANCEFLOOR: 0.5,
    AreaType.BAR:        0.25,
    AreaType.TOILET:     0.15,
    AreaType.HALLWAY:    0.10,
}

AREA_DWELL_TIME = {
    AreaType.DANCEFLOOR: (60.0, 120.0),
    AreaType.BAR:        (20.0, 40.0),
    AreaType.TOILET:     (30.0, 50.0),
    AreaType.HALLWAY:    (30.0,  60.0),
}

BEAT_JUMP_THRESHOLD = 0.08  # seconds: snap to beat if within this window


class ClubGoer(ParentActor):

    def __init__(self, app: "App", pos, path="texture/clubgoer.png"):
        super().__init__(app, pos, path)
        self.player  = False
        self.speed   = 300

        self.route       = None
        self.walkTo      = None
        self.dwellTimer  = 0.0
        self.currentArea = None

        self.jumpHeight   = 0.0   # current visual offset (pixels, positive = up)
        self.jumpVel      = 0.0
        self.onBeat       = False
        self._lastBeatPhase = 0.0
        self.beatJumpDelay = random.uniform(-0.05, 0.05)

    # ------------------------------------------------------------------
    def tick(self):
        self.mandatoryTick()
        self._updateArea()
        self._roamTick()
        if self.currentArea == AreaType.DANCEFLOOR:
            self._danceTick()
        self._gravityTick()
        if self.app.onScreen(self.pos):
            self.render()

    # ------------------------------------------------------------------
    def duplicate(self, atPos=v2(0, 0)):
        p = ClubGoer(self.app, atPos, path="")
        p.image    = self.image
        p.imageBat = self.imageBat
        p.hudImage = self.hudImage
        return p

    # ------------------------------------------------------------------
    def _updateArea(self):
        self.currentArea = self.app.checkPositionArea(self.pos)

    # ------------------------------------------------------------------
    def _roamTick(self):
        if self.dwellTimer > 0:
            self.dwellTimer -= self.app.dt
            self.vel = v2(0, 0)
            return

        if not self.walkTo and self.route:
            self.walkTo = self.route.pop(0)

        if self.walkTo:
            diff = v2(self.walkTo) - v2(self.pos)
            if diff.length() < 12:
                self.walkTo = None
                if not self.route:
                    lo, hi = AREA_DWELL_TIME.get(self.currentArea, (2.0, 6.0))
                    self.dwellTimer = random.uniform(lo, hi)
                    self.vel = v2(0, 0)
                    return
            if diff.length() > 0:
                self.vel = diff.normalize()

            for x in self.app.interactables:
                if x.collides(self.hitBox):
                    x.openFor(1.5)

            if self.touchingWall > 0.3:
                self.walkTo = None
                self.route   = None
                self.touchingWall = 0

        if not self.route and not self.walkTo:
            target = self._pickDestination()
            if target:
                self.route = self.app.nav.get_path(self.pos, target)

    def _pickDestination(self):
        areas   = list(AREA_WEIGHTS.keys())
        weights = list(AREA_WEIGHTS.values())
        chosen  = random.choices(areas, weights=weights, k=1)[0]

        candidates = [
            r
            for r, a_t in self.app.mapAreas
            if a_t == chosen
        ]
        if not candidates:
            return None

        randomArea = random.choice(candidates)
        # jitter so goers don't stack on the same pixel
        return v2(random.randint(randomArea.left + 45, randomArea.right - 45), random.randint(randomArea.top + 45, randomArea.bottom - 45))

    # ------------------------------------------------------------------
    def _danceTick(self):
        bpm   = getattr(self.app, "songBPM", 155)
        beat  = 60.0 / bpm
        phase = ((getattr(self.app, "songTime", 0.0) + self.beatJumpDelay) % beat) / beat  # 0..1

        crossed = self._lastBeatPhase > 0.8 and phase < 0.2
        self._lastBeatPhase = phase

        if crossed:
            self.jumpVel = 280.0
            self.jumpHeight = 0.0

    def _gravityTick(self):
        if self.jumpVel != 0.0 or self.jumpHeight != 0.0:
            self.jumpVel    -= 1200.0 * self.app.dt   # gravity
            self.jumpHeight += self.jumpVel * self.app.dt
            if self.jumpHeight <= 0.0:
                self.jumpHeight = 0.0
                self.jumpVel    = 0.0

        

    # 