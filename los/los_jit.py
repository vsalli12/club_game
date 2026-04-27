import math
import numpy as np
from numba import jit


@jit(nopython=True)
def filter_walls_in_view(walls, cam, size):
    n = walls.shape[0]
    out = np.empty((n, 4), dtype=np.float64)
    count = 0
    sw, sh = float(size[0]), float(size[1])
    for i in range(n):
        x1 = walls[i, 0] - cam[0]
        y1 = walls[i, 1] - cam[1]
        x2 = walls[i, 2] - cam[0]
        y2 = walls[i, 3] - cam[1]
        cx = (x1 + x2) * 0.5
        cy = (y1 + y2) * 0.5
        if ((0.0 < x1 < sw and 0.0 < y1 < sh) or
            (0.0 < x2 < sw and 0.0 < y2 < sh) or
            (0.0 < cx < sw and 0.0 < cy < sh)):
            out[count, 0] = x1
            out[count, 1] = y1
            out[count, 2] = x2
            out[count, 3] = y2
            count += 1
    return out[:count]


@jit(nopython=True)
def get_wall_angles(pos, walls, out):
    px, py = pos[0], pos[1]
    for i in range(walls.shape[0]):
        x1, y1 = walls[i, 0], walls[i, 1]
        x2, y2 = walls[i, 2], walls[i, 3]
        a1 = math.atan2(y1 - py, x1 - px)
        a2 = math.atan2(y2 - py, x2 - px)
        if a1 < 0.0: a1 += math.tau
        if a2 < 0.0: a2 += math.tau
        cx, cy = (x1 + x2) * 0.5, (y1 + y2) * 0.5
        dist = math.sqrt((cx - px)**2 + (cy - py)**2)
        out[i, 0] = x1;  out[i, 1] = y1;  out[i, 2] = a1
        out[i, 3] = x2;  out[i, 4] = y2;  out[i, 5] = a2
        out[i, 6] = dist; out[i, 7] = 1.0
    return out


@jit(nopython=True)
def _wall_span(a1, a2):
    # Returns (start, span): start is the CCW-earlier endpoint,
    # span is the shorter angular width. Always < pi for a normal wall.
    fwd = (a2 - a1) % math.tau   # CCW arc from a1 to a2
    bwd = (a1 - a2) % math.tau   # CCW arc from a2 to a1
    if fwd <= bwd:
        return a1, fwd
    else:
        return a2, bwd


@jit(nopython=True)
def _in_span(a, start, span):
    # True if angle a is within [start, start+span) mod tau
    return (a - start) % math.tau <= span


@jit(nopython=True)
def filter_occluded_walls(angle_array):
    n = angle_array.shape[0]

    # insertion sort indices by ascending distance
    order = np.arange(n)
    for i in range(1, n):
        key = order[i]
        j = i - 1
        while j >= 0 and angle_array[order[j], 6] > angle_array[key, 6]:
            order[j + 1] = order[j]
            j -= 1
        order[j + 1] = key

    for oi in range(n):
        i = order[oi]
        if angle_array[i, 7] == 0:
            continue
        start_i, span_i = _wall_span(angle_array[i, 2], angle_array[i, 5])

        for oj in range(oi + 1, n):
            j = order[oj]
            if angle_array[j, 7] == 0:
                continue
            a3 = angle_array[j, 2]
            a4 = angle_array[j, 5]
            if _in_span(a3, start_i, span_i) and _in_span(a4, start_i, span_i):
                angle_array[j, 7] = 0


@jit(nopython=True)
def _ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)


@jit(nopython=True)
def _segments_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    return (_ccw(ax, ay, cx, cy, dx, dy) != _ccw(bx, by, cx, cy, dx, dy) and
            _ccw(ax, ay, bx, by, cx, cy) != _ccw(ax, ay, bx, by, dx, dy))


@jit(nopython=True)
def _line_intersection(ax, ay, bx, by, cx, cy, dx, dy):
    denom = (ax - bx) * (cy - dy) - (ay - by) * (cx - dx)
    if denom == 0.0:
        return False, 0.0, 0.0
    t = ((ax - cx) * (cy - dy) - (ay - cy) * (cx - dx)) / denom
    return True, ax + t * (bx - ax), ay + t * (by - ay)


@jit(nopython=True)
def build_points(angle_array):
    n = angle_array.shape[0]
    out = np.zeros((n * 2, 4), dtype=np.float64)
    for i in range(n):
        a1 = angle_array[i, 2]
        a2 = angle_array[i, 5]
        if a1 < 0.0: a1 += math.tau
        if a2 < 0.0: a2 += math.tau
        out[i*2,     0] = a1;  out[i*2,     1] = angle_array[i, 0];  out[i*2,     2] = angle_array[i, 1];  out[i*2,     3] = 1.0
        out[i*2 + 1, 0] = a2;  out[i*2 + 1, 1] = angle_array[i, 3];  out[i*2 + 1, 2] = angle_array[i, 4];  out[i*2 + 1, 3] = 1.0
    return out


@jit(nopython=True)
def check_visible_points(pos, points, angle_array):
    px, py = pos[0], pos[1]
    nw = angle_array.shape[0]
    for i in range(points.shape[0]):
        a  = points[i, 0]
        x  = points[i, 1]
        y  = points[i, 2]
        xn = x - math.cos(a) * 5.0
        yn = y - math.sin(a) * 5.0
        for j in range(nw):
            if angle_array[j, 7] == 0:
                continue
            wx1, wy1 = angle_array[j, 0], angle_array[j, 1]
            wx2, wy2 = angle_array[j, 3], angle_array[j, 4]
            if (wx1 == xn and wy1 == yn) or (wx2 == xn and wy2 == yn):
                continue
            if _segments_intersect(px, py, xn, yn, wx1, wy1, wx2, wy2):
                points[i, 3] = 0.0
                break
    return points


@jit(nopython=True)
def build_triangle_array(points):
    n = points.shape[0]
    out = np.zeros((n, 8), dtype=np.float64)
    for i in range(n):
        prev = n - 1 if i == 0 else i - 1
        out[i,    0] = points[i, 0] + 1e-4
        out[prev, 4] = points[i, 0] - 1e-4
    return out


@jit(nopython=True)
def calc_triangles(pos, triangle_array, angle_array):
    RAY_LEN = 4000.0
    px, py = pos[0], pos[1]
    nw = angle_array.shape[0]
    for i in range(triangle_array.shape[0]):
        for slot in range(2):
            n = slot * 4
            angle = triangle_array[i, n]
            rx = math.cos(angle) * RAY_LEN + px
            ry = math.sin(angle) * RAY_LEN + py
            best_x, best_y = rx, ry
            best_d = RAY_LEN * RAY_LEN + 1.0
            for j in range(nw):
                if angle_array[j, 7] == 0:
                    continue
                wx1, wy1 = angle_array[j, 0], angle_array[j, 1]
                wx2, wy2 = angle_array[j, 3], angle_array[j, 4]
                if _segments_intersect(px, py, rx, ry, wx1, wy1, wx2, wy2):
                    ok, ix, iy = _line_intersection(px, py, rx, ry, wx1, wy1, wx2, wy2)
                    if ok:
                        d = (ix - px)**2 + (iy - py)**2
                        if d < best_d:
                            best_d = d
                            best_x, best_y = ix, iy
            triangle_array[i, n + 1] = best_x
            triangle_array[i, n + 2] = best_y
    return triangle_array


@jit(nopython=True)
def collect_polygon_points(triangle_array):
    n = triangle_array.shape[0]
    out = np.zeros((n * 2, 2), dtype=np.float64)
    for i in range(n):
        out[i * 2,     0] = triangle_array[i, 1]
        out[i * 2,     1] = triangle_array[i, 2]
        out[i * 2 + 1, 0] = triangle_array[i, 5]
        out[i * 2 + 1, 1] = triangle_array[i, 6]
    return out