import pygame
import sys
from pygame.math import Vector2 as v2
import numpy

def key_press_manager(obj):

    obj.mouse_pos = v2(pygame.mouse.get_pos())
    # obj.mouse_pos = pygame.mouse.get_pos()
    obj.events = pygame.event.get()
    obj.wheelI = 0
    if "wheelUp" in obj.keypress:
        obj.keypress.remove("wheelUp")

    if "wheelDown" in obj.keypress:
        obj.keypress.remove("wheelDown")


    for event in obj.events:
        if event.type == pygame.QUIT:
            sys.exit()

        elif event.type == pygame.MOUSEWHEEL:
            if event.y == 1:
                obj.keypress.append("wheelUp")
            elif event.y == -1:
                obj.keypress.append("wheelDown")

            obj.wheelI = event.y

    keys = pygame.key.get_pressed()

    for key, sign in [
        [pygame.K_w, "w"],
        [pygame.K_a, "a"],
        [pygame.K_s, "s"],
        [pygame.K_d, "d"],
        [pygame.K_x, "x"],
        [pygame.K_q, "q"],
        [pygame.K_c, "c"],
        [pygame.K_z, "z"],
        [pygame.K_r, "r"],
        [pygame.K_h, "h"],
        [pygame.K_e, "e"],
        [pygame.K_1, "1"],
        [pygame.K_2, "2"],
        [pygame.K_3, "3"],
        [pygame.K_4, "4"],
        [pygame.K_SPACE, "space"],
        [pygame.K_RETURN, "enter"],
        [pygame.K_BACKSPACE, "backspace"],
        [pygame.K_ESCAPE, "esc"],
        [pygame.K_DELETE, "del"],
        [pygame.K_t, "t"],
        [pygame.K_LSHIFT, "shift"],
        [pygame.K_LCTRL, "ctrl"],
        [pygame.K_F11, "f11"],
        [pygame.K_i, "i"]
    ]:
        if keys[key]:
            if sign in obj.keypress:
                obj.keypress.remove(sign)
            elif sign not in obj.keypress_held_down:
                obj.keypress.append(sign)

            if sign not in obj.keypress_held_down:
                obj.keypress_held_down.append(sign)
        else:
            if sign in obj.keypress:
                obj.keypress.remove(sign)
            if sign in obj.keypress_held_down:
                obj.keypress_held_down.remove(sign)

    for x in range(3):
        sign = "mouse" + str(x)
        if pygame.mouse.get_pressed()[x]:
            if sign in obj.keypress:
                obj.keypress.remove(sign)
            elif sign not in obj.keypress_held_down:
                obj.keypress.append(sign)

            if sign not in obj.keypress_held_down:
                obj.keypress_held_down.append(sign)
        else:
            if sign in obj.keypress:
                obj.keypress.remove(sign)
            if sign in obj.keypress_held_down:
                obj.keypress_held_down.remove(sign)
