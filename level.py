from dynamicBakedLight import Light
import json, os

from enum import Enum

class AreaType(Enum):
    OUTSIDE    = "OUTSIDE"
    DANCEFLOOR = "DANCEFLOOR"
    BAR        = "BAR"
    TOILET     = "TOILET"
    HALLWAY    = "HALLWAY"
    FORBIDDEN  = "FORBIDDEN"
    ENEMYSPAWN = "ENEMYSPAWN"
    REINFORCE = "REINFORCE"

AREA_COLORS = {
    AreaType.OUTSIDE:    (100, 180, 100),
    AreaType.DANCEFLOOR: (180,  80, 255),
    AreaType.BAR:        (255, 160,  40),
    AreaType.TOILET:     ( 80, 200, 220),
    AreaType.HALLWAY:    (200, 200, 200),
    AreaType.FORBIDDEN:  (220,  40,  40),
    AreaType.ENEMYSPAWN:  (40, 255, 40),
    AreaType.REINFORCE: (220,  40,  40),
}

AREA_TYPES = list(AreaType)  # auto-populated — add to enum, it appears in cycle

# ── Level class ───────────────────────────────────────────────────────────────

class Level:
    def __init__(self):
        self.walls: list = []        # list of [tx, ty, tw, th]
        self.nodes: list = []        # list of [tx, ty]
        self.lights: list[Light] = []
        self.areas: list = []

    def save(self, path="level.json"):
        data = {
            "walls": self.walls,
            "nodes": self.nodes,
            "lights": [l.to_dict() for l in self.lights],
            "areas": [[*a[:4], a[4].value] for a in self.areas],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(path="level.json") -> "Level":
        lv = Level()
        if not os.path.exists(path):
            return lv
        with open(path) as f:
            data = json.load(f)
        lv.walls  = [list(r) for r in data.get("walls", [])]
        lv.nodes  = [list(n) for n in data.get("nodes", [])]
        lv.lights = [Light.from_dict(d) for d in data.get("lights", [])]
        lv.areas = [[*a[:4], AreaType(a[4])] for a in data.get("areas", [])]
        return lv
