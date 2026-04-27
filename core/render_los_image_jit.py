import pygame
import numpy as np
import math
import time
import pygame.gfxdraw
import sys

import core.jit_tools as jit_tools
from pygame import Vector2 as v2


def draw(screen, phase, camera_pos, player_pos, walls, size, quick_render=False, background=None):

    cam = np.array(camera_pos, dtype=np.int32)
    pos = np.array(player_pos, dtype=np.int32)

    walls_filtered = jit_tools.filter_walls_jit(
        walls,
        np.empty((0, 4), dtype=np.int32),
        cam,
        size
    )

    if not quick_render:
        screen.fill((0, 0, 0))

    if background is not None:
        screen.blit(
            background,
            (0, 0),
            area=(camera_pos[0], camera_pos[1], size[0], size[1])
        )

    angle_array = np.zeros((walls_filtered.shape[0] + 4, 8), dtype=float)
    angle_array = jit_tools.get_wall_angles(pos, walls_filtered, angle_array)

    jit_tools.filter_out_non_visible_walls(angle_array)

    angle_array = angle_array[angle_array[:, -1] != 0]

    points = np.zeros((angle_array.shape[0] * 2 + 4, 4), dtype=float)
    points = jit_tools.re_arrange(points, angle_array)

    for i, corner in enumerate([(0, 0), (size[0], 0), (size[0], size[1]), (0, size[1])]):
        a = math.atan2(corner[1] - pos[1], corner[0] - pos[0])
        if a < 0:
            a += math.tau

        points[-(i + 1), 0] = a
        points[-(i + 1), 1:3] = corner
        points[-(i + 1), 3] = 1

    points = jit_tools.check_visible_points(pos, points, angle_array)

    points = points[points[:, -1] != 0]

    unique_angles = set()
    filtered = []

    for p in points:
        if p[0] not in unique_angles:
            unique_angles.add(p[0])
            filtered.append(p)

    points = np.array(filtered)
    points = points[np.argsort(points[:, 0])]

    triangles = np.zeros((len(points), 8), dtype=float)

    for i in range(len(points)):
        prev = len(points) - 1 if i == 0 else i - 1
        triangles[i, 0] = points[i, 0] + 1e-4
        triangles[prev, 4] = points[i, 0] - 1e-4

    start = time.perf_counter()
    triangles = jit_tools.calc_triangles(pos, triangles, points, angle_array)
    dt = time.perf_counter() - start

    render(screen, pos, triangles, points, angle_array, phase)

    return screen, triangles, dt


def render(screen, pos, triangles, points, angle_array, phase):

    for p in points:
        if p[-1] == 0:
            continue
        pygame.draw.line(screen, (255, 255, 255), pos, p[1:3], 3)

    for t in triangles:
        try:
            x1, y1 = pos
            x2, y2 = int(t[1]), int(t[2])
            x3, y3 = int(t[5]), int(t[6])

            pygame.gfxdraw.filled_trigon(
                screen, x1, y1, x2, y2, x3, y3, (255, 255, 255)
            )
        except:
            pass

    if phase == 1:
        for p in points:
            if p[-1]:
                pygame.draw.line(screen, (255, 0, 0), pos, p[1:3])
    elif phase == 2:
        for a in angle_array:
            if a[-1]:
                pygame.draw.line(screen, (255, 0, 255), a[0:2], a[3:5])

    return screen


def testLOS():

    pygame.init()

    player_pos = v2(-58.2, -314.7)
    camera_pos = v2(100, 200)

    walls = np.array([
         [ 356,   67,  356,    0],
         [ 356,    0,  445 ,   0],
         [ 445,   67,  356  , 67],
         [ 445,    0,  445   ,67],
         [ 799,   66,  799,    0],
         [ 799,    0,  889 ,   0],
         [ 889,    0,  889  , 66],
         [ 889,   66,  799   ,66],
         [ 800,  200,  800,  532],
         [ 800,  200,  889 , 200],
         [ 889,  200,  889  ,266],
         [ 889,  266, 1066,  266],
         [1066,  266, 1066 , 334],
         [1245,  328, 1245  ,266],
         [1245,  266, 1422,  266],
         [1422,  266, 1422,  328],
         [1422,  328, 1245,  328],
         [ 355,  333,  355,  267],
         [ 355,  267,  443,  267],
         [ 443,  267,  443,  666],
         [ 266,  333,  355,  333],
         [ 266,  466,  266,  333],
         [ 266,  466,  355,  466],
         [   0,  466,    0,  334],
         [   0,  334,   88,  334],
         [  88,  334,   88,  466],
         [  88,  466,    0,  466],
         [ 889,  334, 1066,  334],
         [ 889,  334,  889,  532],
         [ 889,  532,  800,  532],
         [ 355,  666,  355,  466],
         [ 443,  666,  355,  666],
         [ 800,  868,  800,  734],
         [ 800,  734,  888,  734],
         [ 888,  734,  888,  868],
         [ 976,  868,  888,  868],
         [ 357,  868,  357,  801],
         [ 357,  801,  444,  801],
         [ 444,  801,  444,  868],
         [ 800,  868,  444,  868],
         [ 179,  934,  179,  868],
         [ 179,  868,  357,  868],
         [ 976,  868,  976,  934],
         [ 976,  934,  179,  934],
         [1156,  934, 1156,  868],
         [1156,  868, 1422,  868],
         [1422,  868, 1422,  934],
         [1422,  934, 1156,  934]], dtype=np.int32)
    

    size = np.array((2560, 1440))

    screen = pygame.display.set_mode(size.tolist())
    clock = pygame.time.Clock()

    while True:

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill((0, 0, 0))

        player_pos = pygame.mouse.get_pos()

        _, triangles, dt = draw(
            screen,
            1,
            camera_pos,
            player_pos,
            walls,
            size
        )

        print(dt)

        for w in walls:
            pygame.draw.line(
                screen,
                (255, 255, 0),
                v2(w[0], w[1]) - camera_pos,
                v2(w[2], w[3]) - camera_pos,
                3
            )

        pygame.display.flip()
        clock.tick(144)

        
