import random

import pygame
from pygame import Vector2 as v2

class MPHE:
    def __init__(self, app, ownerObj, options = None, animation = False):
        self.app = app
        self.ownerObj = ownerObj
        self.options = options 
        self.animation = animation
        if self.animation:
            self.animation.parent = self
        self.animTick = 0.0
        self.app.active_widget = self


    def tickOptions(self):
        for key in self.options:
            if key in self.app.keypress:
                # store a lambda function in the options.
                self.options[key][1]()
                self.kill()

        
    def tickDistance(self):
        if (self.ownerObj.pos - self.app.player.pos).length() > 230:
            self.kill()

        

    def tick(self):
        speed = 6.0
        self.animTick = min(1.0, self.animTick + speed * self.app.dt)
        if self.animation:
            if getattr(self.animation, 'done', False):
                self.kill()
                return
            self.animation(self.app)
        if self.options:
            self.tickOptions()
            self.tickDistance()

    def kill(self):
        if self == self.app.active_widget:
            self.app.active_widget = None

    def render(self):
        if self.options:
            self.renderOptions()
        # animation draws itself inside tick so timing is frame-accurate




    def renderOptions(self):
        t = 1 - (1 - self.animTick) ** 3
        alpha = int(255 * t)

        defpos = self.app.convertPos(self.ownerObj.pos.copy())
        defpos.y -= 80  # lift above door

        bar_color  = (80, 80, 80)
        bar_w      = 2
        bar_margin = 8

        for key, (label, _) in self.options.items():
            text     = f"{key.upper()}  {label}"
            key_surf = self.app.gunFont.render(key.upper(), True, (255, 255, 255)).convert_alpha()
            lbl_surf = self.app.infoFont.render(label, True, (160, 160, 160)).convert_alpha()

            key_surf.set_alpha(alpha)
            lbl_surf.set_alpha(alpha)

            total_h  = max(key_surf.get_height(), lbl_surf.get_height())
            baseline = defpos.y + total_h // 2

            # accent bar
            bar_x = int(defpos.x) - bar_margin - bar_w
            bar_surf = pygame.Surface((bar_w, total_h), pygame.SRCALPHA)
            bar_surf.fill((*bar_color, alpha))
            self.app.screen.blit(bar_surf, (bar_x, int(defpos.y)))

            # key in gunFont, label in infoFont, baseline aligned
            kx = int(defpos.x)
            ky = int(baseline - key_surf.get_height() // 2)
            lx = kx + key_surf.get_width() + 10
            ly = int(baseline - lbl_surf.get_height() // 2)

            self.app.screen.blit(key_surf, (kx, ky))
            self.app.screen.blit(lbl_surf, (lx, ly))

            defpos.y += total_h + 10



class CodeInputAnimation:
    def __init__(self, code, on_complete, success=True):
        self.code = code          # e.g. "4719"
        self.success = success    # True = green, False = red
        self.on_complete = on_complete  # called when animation finishes
        self.revealed = 0         # how many digits shown so far
        self.timer = 0.0
        self.interval = 0.2
        self.glitch_timers = [0.0] * len(code)  # per-digit glitch decay
        self.done = False
        self.result_timer = 0.0   # how long to show final green/red state
        self.result_duration = 0.6
        self.parent = None

    def __call__(self, app):
        if self.done:
            return

        self.timer += app.dt
        # advance reveal
        if self.revealed < len(self.code) and self.timer >= self.interval:
            self.timer -= self.interval
            self.glitch_timers[self.revealed] = 0.3  # glitch for 0.3s on reveal
            self.revealed += 1

        # tick glitch timers
        for i in range(len(self.glitch_timers)):
            self.glitch_timers[i] = max(0.0, self.glitch_timers[i] - app.dt)

        all_revealed = self.revealed >= len(self.code)

        if all_revealed:
            self.result_timer += app.dt
            if self.result_timer >= self.result_duration:
                self.done = True
                if self.on_complete:
                    self.on_complete()

        # --- render ---
        color_final = (80, 255, 80) if self.success else (255, 60, 60)
        color_digit = color_final if all_revealed else (255, 255, 255)
        color_mask  = (80, 80, 80)

        center = v2(app.res.x // 2, app.res.y // 2)

        chars = []
        for i, ch in enumerate(self.code):
            if i < self.revealed:
                chars.append((ch, color_digit, self.glitch_timers[i] > 0))
            else:
                chars.append(("*", color_mask, False))

        # render each char individually so we can glitch per-digit
        total_w = 0
        surfs = []
        for ch, col, glitching in chars:
            s = app.gunFont.render(ch, True, col).convert_alpha()
            surfs.append((s, glitching))
            total_w += s.get_width() + 12

        if self.parent:
            xy = self.parent.app.convertPos(self.parent.ownerObj.pos)
            x = xy.x - total_w // 2
            y = xy.y - surfs[0][0].get_height() // 2
        else:
            x = center.x - total_w // 2
            y = center.y - surfs[0][0].get_height() // 2

        for s, glitching in surfs:
            pos = (int(x), int(y))
            if glitching:
                blit_glitch(app.screen, s, pos, glitch=6, diagonal=True, black_bar_chance=4)
            else:
                app.screen.blit(s, pos)
            x += s.get_width() + 12


def blit_glitch(screen, image, pos, glitch = 2, diagonal = False, black_bar_chance = 15, black_bar_color = (0,0,0)):
    upper_pos = 0
    lower_pos = random.randint(2, 5)
    image_size = image.get_size()
    while 1:
        if random.randint(1, black_bar_chance) != 1:
            screen.blit(
                image,
                [pos[0] + random.randint(-glitch, glitch), pos[1] + upper_pos + (0 if not diagonal else random.randint(-glitch, glitch))],
                area=[0, upper_pos, image_size[0], lower_pos-upper_pos],
            )
        if lower_pos == image_size[1]:
            break
        upper_pos = lower_pos
        lower_pos += random.randint(2, 5)
        if lower_pos >= image_size[1]:
            lower_pos = image_size[1]

