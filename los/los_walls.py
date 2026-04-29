"""
los_walls.py

Builds the LOS wall segment array from the level's wall JSON.
Call build_and_cache() once at game startup; it reads walls.json,
computes the contour segments, and caches them to los_walls.json.
Subsequent runs load from cache unless force_rebuild=True.

Integration in app:
    from los_walls import build_and_cache
    import numpy as np

    self.los_walls = build_and_cache()   # np.ndarray shape (N,4) int32, pixel coords

Then each frame:
    from los_draw import draw
    los_surf = draw(self.screen.get_size(), self.player.pos, self.camPD, self.los_walls)
    # blit los_surf onto screen with colorkey or blend mode
"""

import json
import os
import numpy as np
from collections import defaultdict, deque

WALLS_FILE   = "walls.json"
CACHE_FILE   = "los_walls.json"
TILESIZE     = 100


# ---------------------------------------------------------------------------
# Interior fill  (your existing solve() logic, inlined)
# ---------------------------------------------------------------------------

def _build_grid(walls):
    xs = [x for x,_,w,_ in walls] + [x+w for x,_,w,_ in walls]
    ys = [y for _,y,_,h in walls] + [y+h for _,y,_,h in walls]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    W, H = xmax - xmin, ymax - ymin
    grid = np.zeros((H, W), dtype=np.uint8)
    for x, y, w, h in walls:
        grid[y-ymin:y-ymin+h, x-xmin:x-xmin+w] = 1
    return grid, xmin, ymin


def _flood_outside(grid):
    H, W = grid.shape
    outside = np.zeros_like(grid, dtype=np.uint8)
    q = deque()
    for x in range(W):
        if grid[0,   x] == 0: q.append((0,   x))
        if grid[H-1, x] == 0: q.append((H-1, x))
    for y in range(H):
        if grid[y,   0] == 0: q.append((y, 0))
        if grid[y, W-1] == 0: q.append((y, W-1))
    while q:
        y, x = q.popleft()
        if outside[y, x]: continue
        outside[y, x] = 1
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny, nx = y+dy, x+dx
            if 0 <= ny < H and 0 <= nx < W and grid[ny,nx] == 0 and not outside[ny,nx]:
                q.append((ny, nx))
    return ((grid == 0) & (outside == 0)).astype(np.uint8)


def _extract_interior_rects(interior):
    """Greedy rectangle cover of interior cells (tile coords relative to grid origin)."""
    H, W = interior.shape
    used = np.zeros_like(interior)
    rects = []
    for y in range(H):
        for x in range(W):
            if interior[y, x] and not used[y, x]:
                w = 0
                while x+w < W and interior[y, x+w] and not used[y, x+w]:
                    w += 1
                h = 1
                while y+h < H:
                    if all(interior[y+h, x+dx] and not used[y+h, x+dx] for dx in range(w)):
                        h += 1
                    else:
                        break
                used[y:y+h, x:x+w] = 1
                rects.append((x, y, w, h))
    return rects


def _contour_segments(interior_rects):
    """
    Return axis-aligned segments (tile coords) that form the contour of the
    interior region — i.e. edges of interior rects not shared with another
    interior rect.  Each segment is (x1,y1,x2,y2) in tile coords.
    """
    # Count each edge: shared edges appear twice and cancel
    edge_count = defaultdict(int)

    for x, y, w, h in interior_rects:
        # top edge: y, left-to-right
        for dx in range(w):
            edge_count[('H', y,   x+dx)] += 1
        # bottom edge: y+h
        for dx in range(w):
            edge_count[('H', y+h, x+dx)] += 1
        # left edge: x, top-to-bottom
        for dy in range(h):
            edge_count[('V', x,   y+dy)] += 1
        # right edge: x+w
        for dy in range(h):
            edge_count[('V', x+w, y+dy)] += 1

    # Keep only edges with count == 1 (not shared)
    h_edges = set()  # (row, col) unit horizontal edges on contour
    v_edges = set()  # (col, row) unit vertical edges on contour

    for key, count in edge_count.items():
        if count == 1:
            if key[0] == 'H':
                _, row, col = key
                h_edges.add((row, col))
            else:
                _, col, row = key
                v_edges.add((col, row))

    return h_edges, v_edges


def _merge_h_edges(h_edges):
    """Merge unit horizontal edge cells into maximal horizontal segments."""
    # Group by row
    by_row = defaultdict(list)
    for row, col in h_edges:
        by_row[row].append(col)

    segments = []
    for row, cols in by_row.items():
        cols = sorted(cols)
        start = cols[0]
        prev  = cols[0]
        for col in cols[1:]:
            if col == prev + 1:
                prev = col
            else:
                segments.append((start, row, prev+1, row))
                start = col
                prev  = col
        segments.append((start, row, prev+1, row))
    return segments


def _merge_v_edges(v_edges):
    """Merge unit vertical edge cells into maximal vertical segments."""
    by_col = defaultdict(list)
    for col, row in v_edges:
        by_col[col].append(row)

    segments = []
    for col, rows in by_col.items():
        rows = sorted(rows)
        start = rows[0]
        prev  = rows[0]
        for row in rows[1:]:
            if row == prev + 1:
                prev = row
            else:
                segments.append((col, start, col, prev+1))
                start = row
                prev  = row
        segments.append((col, start, col, prev+1))
    return segments


def _to_pixels(segments, render_scale):
    """Convert tile-coord segments to pixel coords."""
    return [(x1*TILESIZE*render_scale, y1*TILESIZE*render_scale, x2*TILESIZE*render_scale, y2*TILESIZE*render_scale)
            for x1, y1, x2, y2 in segments]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_los_walls(walls_tile, render_scale):
    """
    walls_tile : list of [tx, ty, tw, th]  (tile coords, as stored in walls.json)
    Returns np.ndarray shape (N,4) int32 in pixel coords: [x1,y1,x2,y2]
    """
    grid, ox, oy = _build_grid(walls_tile)
    interior      = _flood_outside(grid)
    int_rects     = _extract_interior_rects(interior)
    # shift back to level tile coords
    int_rects_abs = [(x+ox, y+oy, w, h) for x, y, w, h in int_rects]

    h_edges, v_edges = _contour_segments(int_rects_abs)
    segs = _merge_h_edges(h_edges) + _merge_v_edges(v_edges)
    px   = _to_pixels(segs, render_scale)

    return np.array(px, dtype=np.int32)


def build_and_cache(level_file=WALLS_FILE, cache_file=CACHE_FILE, force_rebuild=False, render_scale = 1.0):
    """
    Load walls.json, compute LOS wall segments, cache to los_walls.json.
    On subsequent calls loads from cache unless force_rebuild=True.

    Returns np.ndarray shape (N,4) int32, pixel coords.
    """
    if not force_rebuild and os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
        return np.array(data, dtype=np.int32)

    if os.path.exists(level_file):
        with open(level_file) as f:
            walls_tile = json.load(f)["walls"]

    arr = build_los_walls(walls_tile, render_scale)

    with open(cache_file, "w") as f:
        json.dump(arr.tolist(), f)

    return arr
