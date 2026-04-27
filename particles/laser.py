import pygame
import math
import random

class ThickLaser:
    def __init__(self, app, width=25):
        self.width = width
        self.active = False
        self.app = app

        self.soundStart = pygame.mixer.Sound("audio/minigun1.wav")
        self.soundEnd = pygame.mixer.Sound("audio/minigun2.wav")
        self.soundStart.set_volume(0.3)
        self.soundEnd.set_volume(0.3)
        
        # Random variation seed (changes each laser activation)
        self.color_seed = 0
        
    def activate(self):
        """Activate the laser (continuous beam)"""
        self.active = True
        self.soundEnd.stop()
        self.soundStart.play(loops=-1)
        
    def deactivate(self):
        """Deactivate the laser"""
        self.active = False
        self.soundEnd.play()
        self.soundStart.stop()
    
    def draw(self, screen, start_pos, end_pos, color, sizeMod=5):
        """Draw the thick multi-line laser beam"""

        start_pos = self.app.convertPos(start_pos)
        end_pos = self.app.convertPos(end_pos)
        
        # Create temporary surface for all laser lines
        #temp_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        
        # Calculate perpendicular offset for multiple lines
        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        length = math.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
        
        linesDrawn = 0
            
        # Normalize perpendicular vector
        perp_x = -dy / length
        perp_y = dx / length
        
        # Draw multiple layers for thickness
        layers = [
            {"count": int(20), "thickness": 4, "spacing": 1},
            {"count": int(10), "thickness": 4, "spacing": 2.2},
            {"count": int(10), "thickness": 5, "spacing": 3.5}
        ]
        
        
        for layer_idx, layer in enumerate(layers):
            for i in range(layer["count"]):
                # Calculate offset from center
                offset = (i - layer["count"] // 2) * layer["spacing"] * self.app.RENDER_SCALE
                
                # Calculate line positions
                line_start = (
                    start_pos[0] + perp_x * offset + perp_y * abs(offset),
                    start_pos[1] + perp_y * offset - perp_x * abs(offset)
                )
                line_end = (
                    end_pos[0] + perp_x * offset - perp_y * abs(offset),
                    end_pos[1] + perp_y * offset + perp_x * abs(offset)
                )
                
                # Distance from center affects color
                # Distance from center affects color
                center_distance = abs(i - layer["count"] // 2)
                max_distance = layer["count"] // 2
                if max_distance > 0:
                    center_factor = 1 - (center_distance / max_distance)
                else:
                    center_factor = 1

                # Interpolate between white (core) and chosen color (edges)
                r_core, g_core, b_core = (255, 255, 255)
                r_edge, g_edge, b_edge = color

                red   = int(r_edge + (r_core - r_edge) * center_factor)
                green = int(g_edge + (g_core - g_edge) * center_factor)
                blue  = int(b_edge + (b_core - b_edge) * center_factor)

                # Add intensity variation
                intensity_var = random.uniform(0.9, 1.0)
                final_color = (
                    int(red * intensity_var),
                    int(green * intensity_var),
                    int(blue * intensity_var)
                )
                
                # Draw the line with varying thickness
                line_thickness = layer["thickness"] + random.randint(-1, 1)
                line_thickness = max(1, int(line_thickness * self.app.RENDER_SCALE))
                
                if length > 2:  # Only draw if line is long enough
                    pygame.draw.line(screen, final_color, line_start, line_end, line_thickness)
                    linesDrawn += 1
        
        # Add more electrical arcs that protrude from the laser
        if random.random() < 0.7:  # 70% chance for multiple arcs
            num_arcs = random.randint(2, 5)  # Multiple arcs
            
            for _ in range(num_arcs):
                arc_start_t = random.random()
                arc_end_t = random.random()
                
                arc_start = (
                    start_pos[0] + dx * arc_start_t,
                    start_pos[1] + dy * arc_start_t
                )
                arc_end = (
                    start_pos[0] + dx * arc_end_t,
                    start_pos[1] + dy * arc_end_t
                )
                
                # Add perpendicular offset to create arc effect
                arc_offset = random.uniform(-self.width * 0.8, self.width * 0.8)
                arc_mid = (
                    (arc_start[0] + arc_end[0]) / 2 + perp_x * arc_offset,
                    (arc_start[1] + arc_end[1]) / 2 + perp_y * arc_offset
                )
                
                arc_color = (random.randint(200, 255), 255, 255)
                
                # Draw arc as two line segments
                pygame.draw.line(screen, arc_color, arc_start, arc_mid, 2)
                pygame.draw.line(screen, arc_color, arc_mid, arc_end, 2)
        




import time
# Demo application
class ThickLaserDemo:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1200, 800))
        pygame.display.set_caption("Thick Continuous Laser Demo - Hold mouse to fire")
        self.clock = pygame.time.Clock()
        
        # Create laser
        self.laser = ThickLaser(None, width=20)
        
        # Laser positioning
        self.weapon_pos = (100, 400)
        self.target_pos = (600, 400)
        
        # Demo state
        self.mouse_pressed = False
        
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self.mouse_pressed = True
                    self.laser.activate()
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.mouse_pressed = False
                    self.laser.deactivate()
            elif event.type == pygame.MOUSEMOTION:
                self.target_pos = event.pos
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if self.laser.active:
                        self.laser.deactivate()
                    else:
                        self.laser.activate()
        
        return True
    
    def draw(self):
        # Clear screen with dark background
        self.screen.fill((5, 5, 15))  # Very dark blue
        
        # Draw weapon position
        pygame.draw.circle(self.screen, (80, 80, 100), self.weapon_pos, 12)
        pygame.draw.circle(self.screen, (120, 120, 150), self.weapon_pos, 8)
        pygame.draw.circle(self.screen, (200, 200, 220), self.weapon_pos, 4)
        
        # Draw target crosshair
        cross_size = 10
        pygame.draw.line(self.screen, (100, 255, 100), 
                        (self.target_pos[0] - cross_size, self.target_pos[1]), 
                        (self.target_pos[0] + cross_size, self.target_pos[1]), 2)
        pygame.draw.line(self.screen, (100, 255, 100), 
                        (self.target_pos[0], self.target_pos[1] - cross_size), 
                        (self.target_pos[0], self.target_pos[1] + cross_size), 2)
        
        # Draw aiming line when not firing
        if not self.laser.active:
            pygame.draw.line(self.screen, (40, 40, 50), self.weapon_pos, self.target_pos, 1)
        
        # Draw laser
        t = time.time()
        self.laser.draw(self.screen, self.weapon_pos, self.target_pos, [0,255,0])
        pygame.display.set_caption(str(time.time()- t))
        # Draw instructions
        font = pygame.font.Font(None, 36)
        instructions = [
            "Move mouse to aim",
            "Hold left mouse button to fire continuous beam",
            "Space bar to toggle laser on/off"
        ]
        
        for i, text in enumerate(instructions):
            surface = font.render(text, True, (200, 200, 200))
            self.screen.blit(surface, (20, 20 + i * 35))
        
        # Show laser status
        status_text = "LASER: ON" if self.laser.active else "LASER: OFF"
        status_color = (255, 100, 100) if self.laser.active else (100, 100, 100)
        status_surface = font.render(status_text, True, status_color)
        self.screen.blit(status_surface, (20, 150))
        
        pygame.display.flip()
    
    def run(self):
        running = True
        
        while running:
            running = self.handle_events()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()

# Run the demo
if __name__ == "__main__":
    demo = ThickLaserDemo()
    demo.run()