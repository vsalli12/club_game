import math
import pygame
def angle_diff(a, b):
    diff = (b - a + 180) % 360 - 180
    return diff

def angle_diff_radians(a,b):
    diff = (b - a + math.pi) % (2*math.pi) - math.pi
    return diff

def ease_in_out(t):
    return 3 * t**2 - 2 * t**3

def ease_out(x):
    return 1 - (1 - x)**3   # fast start, slows slightly

def ease_in(x):
    return x**3             # slow start, fast end

def reload_rotation(t):
    if t < 0.2:
        return ease_in_out(t / 0.2) * 90
    elif t < 0.35:
        return 90 - ease_in_out((t - 0.2) / 0.15) * (90 - 65)
    elif t < 0.5:
        return 65 + ease_in_out((t - 0.35) / 0.15) * (90 - 65)
    else:
        return 90 * (1 - ease_in_out((t - 0.5) / 0.5))
    
def melee_animation(t):
    if t < 0.15:
        k = ease_in_out(t / 0.15)
        x = -15 * k            # deeper wind-up
        y = 7 * k
        angle = -30 * k        # more backward rotation

    elif t < 0.5:
        k = ease_in_out((t - 0.15) / 0.35)
        x = -15 + 75 * k       # total +60 x from base
        y = 7 - 12 * k
        angle = -30 + 160 * k  # total +130° swing

    else:
        k = ease_in_out((t - 0.5) / 0.5)
        x = 60 * (1 - k)
        y = -5 * (1 - k)
        angle = 130 * (1 - k)

    return x, y, angle

def roll_angle(t):
    if t < 0.2:
        k = ease_out(t / 0.2)
        angle = 70 * k

    elif t < 0.6:
        k = ease_in((t - 0.2) / 0.4)
        angle = 70 + (110 - 70) * k

    else:
        k = ease_out((t - 0.6) / 0.4)
        angle = 110 + (360 - 110) * k

    return angle


        
def colorize(image, newColor):
    """
    Create a "colorized" copy of a surface (replaces RGB values with the given color, preserving the per-pixel alphas of
    original).
    :param image: Surface to create a colorized copy of
    :param newColor: RGB color to use (original alpha values are preserved)
    :return: New colorized Surface instance
    """
    image = image.copy()

    # zero out RGB values
    image.fill((0, 0, 0, 255), None, pygame.BLEND_RGBA_MULT)
    # add in new RGB values
    image.fill(newColor[0:3] + (0,), None, pygame.BLEND_RGBA_ADD)

    return image
