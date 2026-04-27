import pygame
import numpy as np
import math
from pygame import Vector2 as v2

import hashlib
import os 
import json


KERNEL_SIZE = 128  # fixed resolution for all lights


pygame.init()


def _make_radial_gradient(color, falloff=2.0):
    size = KERNEL_SIZE
    radius = size // 2
    surf = pygame.Surface((size, size))  # no SRCALPHA
    x, y = np.ogrid[:size, :size]
    dist = np.sqrt((x - radius)**2 + (y - radius)**2)
    t = (np.clip(1.0 - dist / radius, 0, 1) ** falloff)  # 0.0–1.0 falloff

    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    rgb[:, :, 0] = (color[0] * t).astype(np.uint8)
    rgb[:, :, 1] = (color[1] * t).astype(np.uint8)
    rgb[:, :, 2] = (color[2] * t).astype(np.uint8)

    pygame.surfarray.blit_array(surf, rgb)
    return surf


def _make_cone_gradient(angle_deg: float, spread_deg: float,
                        color: tuple, falloff: float = 2.0) -> pygame.Surface:
    radius = KERNEL_SIZE // 2
    size = KERNEL_SIZE

    surf = pygame.Surface((size, size))  # no SRCALPHA
    cx = cy = radius
    x, y = np.ogrid[:size, :size]  # x: (size,1), y: (1,size) — surfarray axis order
    dx = x - cx
    dy = y - cy
    dist = np.sqrt(dx ** 2 + dy ** 2)
    pixel_angle = np.degrees(np.arctan2(dy, dx))
    diff = (pixel_angle - angle_deg + 180) % 360 - 180
    half_spread = spread_deg / 2.0
    angle_t = np.clip(1.0 - np.abs(diff) / half_spread, 0, 1)
    dist_t = np.clip(1.0 - dist / radius, 0, 1) ** falloff
    t = angle_t * dist_t  # 0.0–1.0

    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    rgb[:, :, 0] = (color[0] * t).astype(np.uint8)
    rgb[:, :, 1] = (color[1] * t).astype(np.uint8)
    rgb[:, :, 2] = (color[2] * t).astype(np.uint8)

    pygame.surfarray.blit_array(surf, rgb)
    return surf


FRAMES = 60


class Light:
    """
    Base light. Subclass and override _build_frames().

    pos        : world-space position (v2)
    radius     : light radius in world pixels
    color      : (R, G, B) base color
    intensity  : 0.0–1.0 master brightness multiplier
    """

    def __init__(self, pos: v2, radius: int, color: tuple = (255, 220, 150),
                 intensity: float = 1.0):
        self.pos = v2(pos)
        self.radius = radius
        self.color = color
        self.intensity = intensity
        self.frames: list[pygame.Surface] = []
        self.scaled_frames: list[pygame.Surface | None] = [None] * FRAMES
        if not load_light_frames(self):
            self._build_frames()
            save_light_frames(self)

    def _scaled_color(self, t: float = 1.0) -> tuple:
        s = self.intensity * t
        return (int(self.color[0] * s), int(self.color[1] * s), int(self.color[2] * s))

    def _build_frames(self):
        base = _make_radial_gradient(self._scaled_color())
        self.frames = [base] * FRAMES

    def render(self, frame: int) -> pygame.Surface:
        """Return the raw light surface (SRCALPHA) for this frame index."""
        return self.frames[frame % FRAMES]

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "pos": [self.pos.x, self.pos.y],
            "radius": self.radius,
            "color": list(self.color),
            "intensity": self.intensity,
        }

    @staticmethod
    def from_dict(d: dict) -> "Light":
        cls_map = {
            "Light": Light,
            "StaticLight": StaticLight,
            "StrobeLight": StrobeLight,
            "PulseLight": PulseLight,
            "RotatingLight": RotatingLight,
            "ColorCycleLight": ColorCycleLight,
        }
        cls = cls_map.get(d["type"], Light)
        kwargs = {k: v for k, v in d.items() if k not in ("type", "pos")}
        kwargs["pos"] = v2(d["pos"])
        kwargs["color"] = tuple(d["color"])
        return cls(**kwargs)


class StaticLight(Light):
    """Single unchanging radial gradient. One surface reused across all frames."""

    def __init__(self, pos, radius, color=(255, 220, 150), intensity=1.0,
                 falloff: float = 2.0):
        self.falloff = falloff
        super().__init__(pos, radius, color, intensity)

    def _build_frames(self):
        base = _make_radial_gradient(self._scaled_color(), self.falloff)
        self.frames = [base] * FRAMES

    def to_dict(self):
        d = super().to_dict()
        d["falloff"] = self.falloff
        return d


class StrobeLight(Light):
    """
    oscillations : how many full on/off cycles in 60 frames
                   e.g. 2 → on 15f, off 15f, on 15f, off 15f
    duty         : fraction of cycle that is ON (0.0–1.0), default 0.5
    """

    def __init__(self, pos, radius, color=(255, 255, 255), intensity=1.0,
                 oscillations: int = 2, duty: float = 0.5):
        self.oscillations = oscillations
        self.duty = duty
        super().__init__(pos, radius, color, intensity)

    def _build_frames(self):
        on_surf = _make_radial_gradient(self._scaled_color())
        off_surf = pygame.Surface((KERNEL_SIZE, KERNEL_SIZE), pygame.SRCALPHA)
        cycle_len = FRAMES / self.oscillations
        on_frames = int(cycle_len * self.duty)
        self.frames = []
        for i in range(FRAMES):
            phase = i % cycle_len
            self.frames.append(on_surf if phase < on_frames else off_surf)

    def to_dict(self):
        d = super().to_dict()
        d["oscillations"] = self.oscillations
        d["duty"] = self.duty
        return d


class PulseLight(Light):
    """
    Smoothly oscillates intensity via sine wave.
    oscillations : full cycles in 60 frames
    min_intensity: floor brightness (0.0–1.0)
    """

    def __init__(self, pos, radius, color=(255, 150, 50), intensity=1.0,
                 oscillations: float = 1.0, min_intensity: float = 0.1,
                 falloff: float = 2.0):
        self.oscillations = oscillations
        self.min_intensity = min_intensity
        self.falloff = falloff
        super().__init__(pos, radius, color, intensity)

    def _build_frames(self):
        self.frames = []
        for i in range(FRAMES):
            t = i / FRAMES
            s = self.min_intensity + (1.0 - self.min_intensity) * (
                0.5 + 0.5 * math.sin(2 * math.pi * self.oscillations * t))
            c = tuple(int(ch * self.intensity * s) for ch in self.color)
            self.frames.append(_make_radial_gradient(c, self.falloff))

    def to_dict(self):
        d = super().to_dict()
        d["oscillations"] = self.oscillations
        d["min_intensity"] = self.min_intensity
        d["falloff"] = self.falloff
        return d


class RotatingLight(Light):
    """
    A cone of light that rotates around pos.
    spread_deg   : angular width of the cone in degrees
    rotations    : full rotations in 60 frames (can be fractional)
    clockwise    : direction of rotation
    """

    def __init__(self, pos, radius, color=(200, 50, 255), intensity=1.0,
                 spread_deg: float = 45.0, rotations: float = 1.0,
                 clockwise: bool = True, falloff: float = 1.5):
        self.spread_deg = spread_deg
        self.rotations = rotations
        self.clockwise = clockwise
        self.falloff = falloff
        super().__init__(pos, radius, color, intensity)

    def _build_frames(self):
        self.frames = []
        direction = 1 if self.clockwise else -1
        for i in range(FRAMES):
            angle = (i / FRAMES) * 360 * self.rotations * direction
            c = self._scaled_color()
            self.frames.append(
                _make_cone_gradient(angle, self.spread_deg, c, self.falloff)
            )

    def to_dict(self):
        d = super().to_dict()
        d["spread_deg"] = self.spread_deg
        d["rotations"] = self.rotations
        d["clockwise"] = self.clockwise
        d["falloff"] = self.falloff
        return d


class ColorCycleLight(Light):
    """
    Cycles through a list of colors over 60 frames.
    colors       : list of (R,G,B) tuples to interpolate between
    """

    def __init__(self, pos, radius, color=(255, 0, 0), intensity=1.0,
                 colors: list = None, falloff: float = 2.0):
        self.colors = colors or [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        self.falloff = falloff
        super().__init__(pos, radius, color, intensity)

    def _build_frames(self):
        self.frames = []
        n = len(self.colors)
        for i in range(FRAMES):
            t = (i / FRAMES) * n
            idx = int(t) % n
            frac = t - int(t)
            c0 = self.colors[idx]
            c1 = self.colors[(idx + 1) % n]
            blended = tuple(int(c0[j] + (c1[j] - c0[j]) * frac) for j in range(3))
            scaled = tuple(int(ch * self.intensity) for ch in blended)
            self.frames.append(_make_radial_gradient(scaled, self.falloff))

    def to_dict(self):
        d = super().to_dict()
        d["colors"] = [list(c) for c in self.colors]
        d["falloff"] = self.falloff
        return d
    


def _light_cache_path(light: Light) -> str:
    os.makedirs("cache/lights", exist_ok=True)
    d = json.dumps(light.to_dict(), sort_keys=True)
    h = hashlib.md5(d.encode()).hexdigest()[:12]
    return f"cache/lights/{h}.npy"

def save_light_frames(light: Light):
    path = _light_cache_path(light)
    # stack all frames into (60, W, H, 4) using surfarray
    arrays = []
    for surf in light.frames:
        rgb = pygame.surfarray.array3d(surf)        # (W, H, 3)
          # (W, H, 4)
        arrays.append(rgb)
    np.save(path, np.stack(arrays))                 # (60, W, H, 4)

def load_light_frames(light: Light) -> bool:
    path = _light_cache_path(light)
    if not os.path.exists(path):
        return False
    stack = np.load(path)                           # (60, W, H, 4)
    light.frames = []
    for i in range(stack.shape[0]):
        rgba = stack[i]                             # (W, H, 4)
        surf = pygame.Surface((rgba.shape[0], rgba.shape[1]), pygame.SRCALPHA)
        pygame.surfarray.blit_array(surf, rgba[:, :, :3])
        light.frames.append(surf)
    return True