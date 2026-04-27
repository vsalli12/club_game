from light import Light
import json, os

# ── Level class ───────────────────────────────────────────────────────────────

class Level:
    def __init__(self):
        self.walls: list = []        # list of [tx, ty, tw, th]
        self.nodes: list = []        # list of [tx, ty]
        self.lights: list[Light] = []

    def save(self, path="level.json"):
        data = {
            "walls": self.walls,
            "nodes": self.nodes,
            "lights": [l.to_dict() for l in self.lights],
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
        return lv
