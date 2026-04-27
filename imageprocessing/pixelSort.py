import pygame
import numpy as np
from imageprocessing.imageProcessing import set_image_hue_rgba
def pixel_sort_surface(surface, lower=50, upper=200):
    rgb_arr = pygame.surfarray.array3d(surface).astype(np.uint8)  # shape: (w, h, 3)
    alpha_arr = pygame.surfarray.array_alpha(surface)             # shape: (w, h)

    rgb_arr = np.transpose(rgb_arr, (1, 0, 2))  # (h, w, 3)
    alpha_arr = alpha_arr.T                    # (h, w)

    luminance = (0.2126 * rgb_arr[:, :, 0] +
                 0.7152 * rgb_arr[:, :, 1] +
                 0.0722 * rgb_arr[:, :, 2]).astype(np.uint8)

    mask = (luminance >= lower) & (luminance <= upper)

    h, w = luminance.shape
    for y in range(h):
        row_mask = mask[y]
        row_rgb = rgb_arr[y]
        row_alpha = alpha_arr[y]

        start = None
        for x in range(w):
            if row_mask[x]:
                if start is None:
                    start = x
            else:
                if start is not None:
                    segment = slice(start, x)
                    lum_segment = luminance[y, segment]
                    indices = np.argsort(lum_segment)
                    rgb_arr[y, segment] = row_rgb[segment][indices]
                    alpha_arr[y, segment] = row_alpha[segment][indices]
                    start = None
        if start is not None:
            segment = slice(start, w)
            lum_segment = luminance[y, segment]
            indices = np.argsort(lum_segment)
            rgb_arr[y, segment] = row_rgb[segment][indices]
            alpha_arr[y, segment] = row_alpha[segment][indices]

    rgb_arr = np.transpose(rgb_arr, (1, 0, 2))  # back to (w, h, 3)
    alpha_arr = alpha_arr.T                    # back to (w, h)

    result = pygame.Surface(surface.get_size(), flags=pygame.SRCALPHA, depth=32)
    pygame.surfarray.blit_array(result, rgb_arr)
    result.lock()
    result.set_alpha(None)  # ensure per-pixel alpha
    pygame.surfarray.pixels_alpha(result)[:, :] = alpha_arr
    result.unlock()

    return result


import time
if __name__ == "__main__":

    
    s = pygame.display.set_mode((1000,1000))
    image = pygame.image.load("players/kalevi.jpg").convert_alpha()
    image = pygame.transform.scale(image, (1000,1000))
    print("Setting hue")
    #image = set_image_hue_rgba(image, 30)
    print("Hue set")
    image = pixel_sort_surface(image, lower=50, upper=155)
    print("Sorted")
    while True:
        s.blit(image, (0,0))
        pygame.display.update()
        time.sleep(0.01)


