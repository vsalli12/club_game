from pygame import Vector2 as v2
import pygame
class ScorePopup:
    def __init__(self, app):
        self.app = app
        self.score = 0
        self.display_score = 0.0
        self.label = ""
        self.labelRepeated = 0
        self.lifetime = 0.0
        self.max_lifetime = 2.5
        self.anim = 0.0       # 0→1 pop-in
        self.anim_speed = 8.0
        self.nudge = 0.0      # vertical nudge, decays
        self.alive = False

    def grant(self, amount, label):
        self.score += amount
        if label == self.label:
            self.labelRepeated += 1
        self.label = label
        self.lifetime = self.max_lifetime
        self.anim = 0.0
        self.nudge = -18.0    # nudge upward, decays to 0
        self.alive = True

    def tick(self):
        if not self.alive:
            return

        # count display_score toward score
        gap = self.score - self.display_score
        self.display_score += gap * min(1.0, 12.0 * self.app.dt)

        # pop-in animation
        self.anim = min(1.0, self.anim + self.anim_speed * self.app.dt)

        # nudge decay
        self.nudge *= max(0.0, 1.0 - 14.0 * self.app.dt)

        # lifetime
        self.lifetime -= self.app.dt
        if self.lifetime <= 0:
            self.alive = False
            self.score = 0
            self.display_score = 0.0
            self.labelRepeated = 0

    def render(self):
        if not self.alive:
            return

        t_ease = 1 - (1 - self.anim) ** 3

        # fade out in last 0.5s
        alpha = 255
        if self.lifetime < 0.5:
            alpha = int(255 * self.lifetime / 0.5)

        # pop scale
        scale = 1.0 + 0.3 * (1 - t_ease)

        app = self.app
        screen_pos = app.convertPos(app.player.pos)
        anchor = screen_pos + v2(80, -40 + self.nudge)

        # number
        num_surf = app.gunFont.render(f"+{round(self.display_score)}", True, (255, 255, 255)).convert_alpha()
        w = int(num_surf.get_width() * scale)
        h = int(num_surf.get_height() * scale)
        num_scaled = pygame.transform.scale(num_surf, (w, h))
        num_scaled.set_alpha(alpha)

        # label
        l = self.label
        if self.labelRepeated >= 2:
            l += f" x{self.labelRepeated}"
        label_surf = app.infoFont.render(l, True, (255, 255, 255)).convert_alpha()
        label_surf.set_alpha(alpha)

        # stack: number on top, label below
        num_rect = num_scaled.get_rect(topleft=anchor)
        label_rect = label_surf.get_rect(topleft=anchor + v2(0, num_rect.height + 2))

        app.screen.blit(num_scaled, num_rect)
        app.screen.blit(label_surf, label_rect)