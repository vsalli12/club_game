import math
import numpy as np
import pygame

import los.los_jit as los_jit


def draw(surface, player_pos, camera_pos, walls, debug=False):
    """
    Renders a black/white LOS surface.
      White = visible (lit polygon)
      Black = unlit fog

    Args:
        surface     : pygame.Surface to draw on (pre-created, colorkey set to white by caller)
        player_pos  : (x, y) world pixel coords  (app.player.pos)
        camera_pos  : (x, y) world pixel coords of viewport top-left  (app.camPD)
        walls       : np.ndarray shape (N,4) int32 — world pixel coords, no camera offset
        debug       : if True, draws ray lines over the surface
    """
    screen_size = surface.get_size()
    size = np.array(screen_size, dtype=np.int32)
    cam  = np.array(camera_pos,  dtype=np.int32)
    pos  = np.array(player_pos,  dtype=np.float64)
    pos_screen = pos - cam

    

    walls_view = los_jit.filter_walls_in_view(walls, cam, size)
    if walls_view.shape[0] == 0:
        return

    n = walls_view.shape[0]
    angle_array = np.zeros((n, 8), dtype=np.float64)
    angle_array = los_jit.get_wall_angles(pos_screen, walls_view, angle_array)

    los_jit.filter_occluded_walls(angle_array)
    angle_array = angle_array[angle_array[:, 7] != 0]

    if angle_array.shape[0] == 0:
        return

    points = los_jit.build_points(angle_array)

    # screen corners
    w, h = screen_size
    corner_rows = np.zeros((4, 4), dtype=np.float64)
    for i, (cx, cy) in enumerate(((0, 0), (w, 0), (w, h), (0, h))):
        a = math.atan2(cy - pos_screen[1], cx - pos_screen[0])
        if a < 0.0: a += math.tau
        corner_rows[i] = (a, cx, cy, 1.0)
    points = np.vstack((points, corner_rows))

    points = los_jit.check_visible_points(pos_screen, points, angle_array)
    points = points[points[:, 3] != 0]

    # vectorised dedup by angle
    _, idx = np.unique(points[:, 0], return_index=True)
    points = points[idx]
    points = points[np.argsort(points[:, 0])]

    if len(points) < 2:
        return

    triangle_array = los_jit.build_triangle_array(points)
    triangle_array = los_jit.calc_triangles(pos_screen, triangle_array, angle_array)

    poly = los_jit.collect_polygon_points(triangle_array)
    pygame.draw.polygon(surface, (255, 255, 255), poly.tolist())

    if debug:
        px, py = int(pos_screen[0]), int(pos_screen[1])
        for p in points:
            pygame.draw.line(surface, (255, 0, 0), (px, py), (int(p[1]), int(p[2])), 1)

    return poly