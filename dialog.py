

import math
import random

import pygame

class Dialog:
    def __init__(self, app, lines, left, right):
        self.app = app
        self.lines = lines
        self.currentLine = 0
        self.left = left.hudImage
        self.right = right.hudImage
        self.slideIn = 0
        self.fadingOut = False
        self.alive = True
        self.talkTimer = 0
        self.currentLine = ""
        self.targetLine = 0
        self.letterTimer = 0
        self.alreadyTalked = []
        self.done = False

        self.qte_active = False
        self.qte_angle = 0.0
        self.qte_speed = 2 * math.pi * 1.2  # rad/s (~1.2 rotations/sec)
        self.qte_target = 0.0               # center angle of success zone
        self.qte_width = math.radians(30)   # success window size
        self.qte_next_target = 0.0
        self.qte_word_index = 0
        self.qte_words = []
        self.qte_errors = 0


    def tick(self):

        if not self.fadingOut:
            self.slideIn = min(1, self.slideIn + self.app.dt)

            

        else:
            self.slideIn = max(0, self.slideIn - self.app.dt)
            if self.slideIn == 0:
                self.alive = False

        self.app.screen.blit(self.left, (50 - self.left.get_width() * 1.5 * (1 - self.slideIn)**2, self.app.res.y - self.left.get_height() - 400))
        self.app.screen.blit(self.right, (self.app.res.x - 50 - self.right.get_width() + self.right.get_width() * 1.5 * (1 - self.slideIn)**2, self.app.res.y - self.right.get_height() - 400))

        leftStart = 50 - self.left.get_width() * 1.5 * (1 - self.slideIn)**2 + self.left.get_width() + 20
        rightStart = self.app.res.x - 50 - self.right.get_width() + self.right.get_width() * 1.5 * (1 - self.slideIn)**2 - 20

        leftY = self.app.res.y - self.left.get_height() - 400 + 50
        rightY = self.app.res.y - self.right.get_height() - 400 + 50
        for i, x in enumerate(self.alreadyTalked + [self.currentLine]):

            onLeft = (i % 2) == 0

            text = self.app.font.render(x, True, (255,255,255))
            if onLeft:
                pos = (leftStart, leftY)
                leftY += text.get_height() + 20
            else:
                pos = (rightStart - text.get_width(), rightY)
                rightY += text.get_height() + 20

            self.app.screen.blit(text, pos)


        if self.slideIn == 1 and self.targetLine < len(self.lines):
            self.talkTimer += self.app.dt
            if self.done:
                if self.talkTimer > 1:
                    self.talkTimer = 0
                    self.targetLine += 1
                    self.alreadyTalked.append(self.currentLine)
                    self.currentLine = ""
                    self.done = False

            elif self.talkTimer > 1:
                if self.targetLine%2 == 1:
                    self.letterTimer += self.app.dt
                    if self.letterTimer > 0.08:
                        self.letterTimer = 0
                        self.currentLine += self.lines[self.targetLine][len(self.currentLine)]
                        self.app.playPositionalAudio(self.app.womanSound, self.app.player.pos, volume=0.5)
                        if self.currentLine == self.lines[self.targetLine]:
                            self.done = True

                else:
                    if not self.qte_active:
                        line = self.lines[self.targetLine]
                        self.qte_words = line.split(" ")
                        self.qte_word_index = 0
                        self.currentLine = ""
                        self.qte_active = True
                        self.qte_errors = 0
                        self._new_qte_target()
                    


        elif self.targetLine >= len(self.lines):
            self.fadingOut = True


        if self.qte_active:

            if not self.fadingOut:
                self.qte_angle = (self.qte_angle + self.qte_speed * self.app.dt) % (2*math.pi)

            if "mouse0" in self.app.keypress and not self.fadingOut:
                d = abs((self.qte_angle - self.qte_target + math.pi) % (2*math.pi) - math.pi)

                if d < self.qte_width * 0.5:

                    self.app.playPositionalAudio("audio/ORCHESTRAHIT.wav", self.app.player.pos, volume=0.8)

                    # success → append next word
                    word = self.qte_words[self.qte_word_index]
                    if self.currentLine:
                        self.currentLine += " "
                    self.currentLine += word

                    self.qte_word_index += 1

                    if self.qte_word_index >= len(self.qte_words):
                        self.qte_active = False
                        self.talkTimer = 0
                        self.done = True
                    else:
                        self._new_qte_target()
                else:
                    self.qte_errors += 1
                    self.app.playPositionalAudio("audio/fail.wav", self.app.player.pos, volume=0.8)
                    if self.qte_errors >= 3:
                        self.currentLine += " ööööö you aare sou beu bu beaut beu vITTU"
                        self.fadingOut = True
                    else:
                        self.currentLine += " UHM"

        if self.qte_active:
            self.draw_qte()

    def _new_qte_target(self):
        self.qte_target = self.qte_next_target
        self.qte_next_target = (self.qte_target + random.uniform(math.pi, 3*math.pi/2)) % (2*math.pi)
        self.qte_speed *= -1
        

        # Render the quick time wheel

    def draw_qte(self):
        center = (self.app.res.x // 2, self.app.res.y - 200)
        radius = 150

        # base circle
        pygame.draw.circle(self.app.screen, (80,80,80), center, radius, 3)

        def arc(color, angle_center, width, thickness=6):
            start = angle_center - width/2
            end = angle_center + width/2
            rect = pygame.Rect(center[0]-radius, center[1]-radius, radius*2, radius*2)
            pygame.draw.arc(self.app.screen, color, rect, start, end, thickness)

        # current success zone
        arc((255,255,255), self.qte_target, self.qte_width)

        # next zone (faded)
        arc((120,120,120), self.qte_next_target, self.qte_width)

        # rotating needle
        tip = (
            center[0] + math.cos(self.qte_angle) * radius,
            center[1] - math.sin(self.qte_angle) * radius
        )
        pygame.draw.line(self.app.screen, (255,0,0), center, tip, 3)