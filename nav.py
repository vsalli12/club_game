"""
nav.py

Navigation network built at game startup from nav_nodes.json + wall_cache.json.

Integration:
    from nav import NavGraph, can_see
    import numpy as np, json

    with open("wall_cache.json") as f:
        los_walls = np.array(json.load(f), dtype=np.float64)

    nav = NavGraph.load("nav_nodes.json", los_walls)

    # per-frame LOS query (world pixel coords):
    visible = can_see(ax, ay, bx, by, los_walls)

    # when entity needs a path (world pixel coords in, world pixel v2 list out):
    path = nav.get_path(entity_pos, target_pos)
    # returns [v2(wp1), v2(wp2), ..., v2(target_pos)]
    # returns [target_pos] if no path found
"""

import json
import math
import os
import numpy as np
from numba import jit
from pygame import Vector2 as v2

TILESIZE = 100
INF      = np.inf


# ---------------------------------------------------------------------------
# JIT primitives
# ---------------------------------------------------------------------------

@jit(nopython=True)
def _ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)


@jit(nopython=True)
def _seg_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    return (_ccw(ax, ay, cx, cy, dx, dy) != _ccw(bx, by, cx, cy, dx, dy) and
            _ccw(ax, ay, bx, by, cx, cy) != _ccw(ax, ay, bx, by, dx, dy))


@jit(nopython=True)
def _can_see_jit(ax, ay, bx, by, walls):
    for i in range(walls.shape[0]):
        wx1, wy1 = walls[i, 0], walls[i, 1]
        wx2, wy2 = walls[i, 2], walls[i, 3]
        if (wx1 == ax and wy1 == ay) or (wx2 == ax and wy2 == ay):
            continue
        if (wx1 == bx and wy1 == by) or (wx2 == bx and wy2 == by):
            continue
        if _seg_intersect(ax, ay, bx, by, wx1, wy1, wx2, wy2):
            return False
    return True


@jit(nopython=True)
def _build_visibility(coords_world, walls):
    """coords_world: (n,2) float64 world pixels. Returns (n,n) uint8 vis matrix."""
    n = coords_world.shape[0]
    vis = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        for j in range(i + 1, n):
            if _can_see_jit(coords_world[i, 0], coords_world[i, 1],
                            coords_world[j, 0], coords_world[j, 1], walls):
                vis[i, j] = 1
                vis[j, i] = 1
    return vis


@jit(nopython=True)
def _floyd_warshall(dist, nxt):
    n = dist.shape[0]
    for k in range(n):
        for i in range(n):
            if dist[i, k] == np.inf:
                continue
            for j in range(n):
                nd = dist[i, k] + dist[k, j]
                if nd < dist[i, j]:
                    dist[i, j] = nd
                    nxt[i, j] = nxt[i, k]


@jit(nopython=True)
def _visible_from(px, py, coords_world, walls):
    """Returns array of node indices visible from world point (px,py)."""
    n = coords_world.shape[0]
    out = np.full(n, -1, dtype=np.int32)
    count = 0
    for i in range(n):
        if _can_see_jit(px, py, coords_world[i, 0], coords_world[i, 1], walls):
            out[count] = i
            count += 1
    return out[:count]


# ---------------------------------------------------------------------------
# Public LOS function (world pixel coords)
# ---------------------------------------------------------------------------

def can_see(ax, ay, bx, by, los_walls):
    """
    Returns True if world point (ax,ay) can see (bx,by) with no wall occlusion.
    los_walls: np.ndarray (N,4) float64, world pixel coords.
    """
    return bool(_can_see_jit(float(ax), float(ay), float(bx), float(by), los_walls))





# ---------------------------------------------------------------------------
# NavGraph
# ---------------------------------------------------------------------------

class NavGraph:
    def __init__(self, nodes_tile, coords_world, edges, dist, next_hop, los_walls, app = None, render_scale = 1.0):
        """
        nodes_tile  : list of [tx, ty] tile coords (may be 0.5 increments)
        coords_world: np.ndarray (n,2) float64 world pixels
        edges       : list of (i,j) visible pairs
        dist        : np.ndarray (n,n) float64 all-pairs shortest distances
        next_hop    : np.ndarray (n,n) int32   next-hop table
        los_walls   : np.ndarray (N,4) float64 world pixel wall segments
        """
        self.nodes_tile   = nodes_tile
        self.coords       = coords_world
        self.edges        = edges
        self.dist         = dist
        self.next_hop     = next_hop
        self.walls        = los_walls
        self.render_scale = render_scale
        self.app = app

    # --- public query -------------------------------------------------------

    def can_see(self, start: v2, end: v2) -> bool:
        rs = self.render_scale
        if self.app:
            w = self.app.effective_los_walls
        else:
            w = self.walls
        return bool(_can_see_jit(
            float(start.x) * rs, float(start.y) * rs,
            float(end.x)   * rs, float(end.y)   * rs,
            w))

    def get_path(self, start: v2, end: v2) -> list:
        n = len(self.nodes_tile)
        if n == 0:
            return [v2(end)]

        rs = self.render_scale
        sx, sy = float(start.x) * rs, float(start.y) * rs
        ex, ey = float(end.x)   * rs, float(end.y)   * rs

        vis_s = _visible_from(sx, sy, self.coords, self.walls)
        vis_e = _visible_from(ex, ey, self.coords, self.walls)

        if vis_s.shape[0] == 0 or vis_e.shape[0] == 0:
            return [v2(end)]

        best_cost = INF
        best_s = best_e = -1

        for si in range(vis_s.shape[0]):
            s  = int(vis_s[si])
            ds = math.dist((sx, sy), self.coords[s])
            for ei in range(vis_e.shape[0]):
                e  = int(vis_e[ei])
                de = math.dist((ex, ey), self.coords[e])
                mid = float(self.dist[s, e]) if s != e else 0.0
                cost = ds + mid + de
                if cost < best_cost:
                    best_cost, best_s, best_e = cost, s, e

        if best_s == -1 or best_cost == INF:
            return [v2(end)]

        path_nodes = []
        cur = best_s
        visited = set()
        while cur != best_e:
            if cur == -1 or cur in visited:
                return [v2(end)]
            visited.add(cur)
            path_nodes.append(cur)
            cur = int(self.next_hop[cur, best_e])
        path_nodes.append(best_e)

        # coords are render space; convert back to world space for callers
        result = [v2(self.coords[i, 0] / rs, self.coords[i, 1] / rs) for i in path_nodes]
        result.append(v2(end))
        return result

    # --- build --------------------------------------------------------------

    @staticmethod
    def build(app, nodes_tile):
        n = len(nodes_tile)
        los_walls = app.los_walls
        render_scale = app.RENDER_SCALE
        empty = NavGraph([], np.zeros((0, 2), dtype=np.float64), [],
                        np.zeros((0, 0)), np.zeros((0, 0), dtype=np.int32),
                        los_walls, render_scale)
        if n == 0:
            return empty

        # Store coords in render space to match los_walls
        coords_render = np.array(
            [[t[0] * TILESIZE * render_scale, t[1] * TILESIZE * render_scale] for t in nodes_tile],
            dtype=np.float64)

        vis = _build_visibility(coords_render, los_walls)

        edges = [(i, j) for i in range(n) for j in range(i+1, n) if vis[i, j]]

        direct = np.full((n, n), INF, dtype=np.float64)
        np.fill_diagonal(direct, 0.0)
        next_hop = np.full((n, n), -1, dtype=np.int32)
        for i in range(n):
            next_hop[i, i] = i
        for i, j in edges:
            d = math.dist(coords_render[i], coords_render[j])
            direct[i, j] = d
            direct[j, i] = d
            next_hop[i, j] = j
            next_hop[j, i] = i

        dist = direct.copy()
        _floyd_warshall(dist, next_hop)

        return NavGraph(nodes_tile, coords_render, edges, dist, next_hop, los_walls, app, render_scale)

    @staticmethod
    def load(app, levelFile):
        """Load nav_nodes.json and build the graph."""
        nodes_tile = []
        if os.path.exists(levelFile):
            with open(levelFile) as f:
                nodes_tile = json.load(f)["nodes"]
        return NavGraph.build(app, nodes_tile)