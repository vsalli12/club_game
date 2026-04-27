import pygame
from pygame import Vector2 as v2
class MuzzleFlash:
    def __init__(self, app, weapon):
        self.app = app
        self.weapon = weapon
        self.lifetime = 0.0
        self.app.muzzleFlashes.append(self)
        self.maxLife = 0.15

    def tick(self):
        self.lifetime += self.app.dt
        if self.lifetime >= self.maxLife:
            self.app.muzzleFlashes.remove(self)

    def renderTo(self, surf):

        pos = self.weapon.bulletSpawnPoint()
        angle_deg = -self.weapon.FINALROTATION

        FRAME = int((self.lifetime / 0.25) * (len(self.app.MUZZLE_FLASH_FRAMES) - 1))
        im, (ox, oy) = self.app.MUZZLE_FLASH_FRAMES[FRAME]
        r = int(300 * (1.0 - (self.lifetime / 0.25) * 0.7) * self.app.RENDER_SCALE)
        full_size = 128
        scale = (r * 2) / full_size
        scaled = pygame.transform.smoothscale(im, (int(im.get_width() * scale), int(im.get_height() * scale)))
        rotated = pygame.transform.rotate(scaled, -angle_deg)
        center = self.app.convertPos(pos)

        # offset of cropped surface center from full surface center, in pre-rotation space
        cropped_cx = ox + im.get_width()  / 2
        cropped_cy = oy + im.get_height() / 2
        full_cx = full_size / 2
        full_cy = full_size / 2
        off = v2(cropped_cx - full_cx, cropped_cy - full_cy) * scale

        # rotate that offset by the same angle
        off = off.rotate(angle_deg)

        surf.blit(rotated, center + off - v2(rotated.get_size()) / 2, special_flags=pygame.BLEND_RGB_ADD)