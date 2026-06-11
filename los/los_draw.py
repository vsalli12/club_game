import math
import numpy as np
import pygame

import los.los_jit as los_jit


def draw(surface, player_pos, camera_pos, walls, look_angle=None, fov=None, debug=False):
    """
    Renders a black/white LOS surface.
      White = visible (lit polygon)
      Black = unlit fog

    Args:
        surface     : pygame.Surface to draw on (colorkey set to white by caller)
        player_pos  : (x, y) world pixel coords
        camera_pos  : (x, y) world pixel coords of viewport top-left
        walls       : np.ndarray shape (N,4) int32 — world pixel coords, no camera offset
        look_angle  : float, radians [0, tau) — centre of FOV cone. None = 360 degrees
        fov         : float, radians — full cone width. None = 360 degrees
        debug       : if True, draws ray lines over the surface
    """
    screen_size = surface.get_size()
    w, h = screen_size
    size = np.array(screen_size, dtype=np.int32)
    cam  = np.array(camera_pos,  dtype=np.int32)
    pos  = np.array(player_pos,  dtype=np.float64)
    pos_screen = pos - cam
    px, py = pos_screen[0], pos_screen[1]

    use_fov = look_angle is not None and fov is not None

    walls_view = los_jit.filter_walls_in_view(walls, cam, size)

    if walls_view.shape[0] > 0:
        n = walls_view.shape[0]
        angle_array = np.zeros((n, 8), dtype=np.float64)
        angle_array = los_jit.get_wall_angles(pos_screen, walls_view, angle_array)
        los_jit.filter_occluded_walls(angle_array)
        angle_array = angle_array[angle_array[:, 7] != 0]
    else:
        angle_array = np.zeros((0, 8), dtype=np.float64)

    if angle_array.shape[0] > 0:
        points = los_jit.build_points(angle_array)
    else:
        points = np.zeros((0, 4), dtype=np.float64)

    if use_fov:
        # FOV boundary rays — clipped to nearest wall or screen edge
        fov_corners = los_jit.get_fov_corners(px, py, look_angle, fov, angle_array, w, h) \
            if angle_array.shape[0] > 0 \
            else _fov_corners_no_walls(px, py, look_angle, fov, w, h)
        if points.shape[0] > 0:
            points = los_jit.filter_points_in_fov(points, look_angle, fov)
        points = np.vstack((points, fov_corners)) if points.shape[0] > 0 else fov_corners
    else:
        # Full 360 — add screen corners so the polygon fills without walls
        corner_rows = np.zeros((4, 4), dtype=np.float64)
        for i, (cx, cy) in enumerate(((0, 0), (w, 0), (w, h), (0, h))):
            a = math.atan2(cy - py, cx - px)
            if a < 0.0: a += math.tau
            corner_rows[i] = (a, cx, cy, 1.0)
        points = np.vstack((points, corner_rows)) if points.shape[0] > 0 else corner_rows

    points = los_jit.check_visible_points(pos_screen, points, angle_array) \
        if angle_array.shape[0] > 0 else points
    points = points[points[:, 3] != 0]

    _, idx = np.unique(points[:, 0], return_index=True)
    points = points[idx]
    points = points[np.argsort(points[:, 0])]

    if len(points) < 2:
        return None
    

    triangle_array = los_jit.build_triangle_array(points)
    triangle_array = los_jit.calc_triangles(pos_screen, triangle_array, angle_array) \
        if angle_array.shape[0] > 0 else triangle_array

    poly = los_jit.collect_polygon_points(triangle_array)

    if use_fov: # Only use player position as apex if we're doing a cone — otherwise it can cause weird artifacts when it coincides with a wall endpoint
        poly[-1] = [px, py]

    pygame.draw.polygon(surface, (255, 255, 255), poly.tolist())

    if debug:
        for p in points:
            pygame.draw.line(surface, (255, 0, 0), (int(px), int(py)), (int(p[1]), int(p[2])), 1)

    return poly


def _fov_corners_no_walls(px, py, look_angle, fov, screen_w, screen_h):
    """Fallback when no walls are present: FOV boundary rays clipped to screen edge."""
    half = fov * 0.5
    out = np.zeros((2, 4), dtype=np.float64)
    for i, angle in enumerate((look_angle - half, look_angle + half)):
        angle %= math.tau
        # March to screen boundary
        RAY_LEN = 4000.0
        rx = math.cos(angle) * RAY_LEN + px
        ry = math.sin(angle) * RAY_LEN + py
        rx = min(max(rx, 0.0), float(screen_w))
        ry = min(max(ry, 0.0), float(screen_h))
        out[i] = (angle, rx, ry, 1.0)
    return out