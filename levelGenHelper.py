import time, pygame
from los.los_draw import draw as los_draw
from dynamicBakedLight import StaticLight
from pygame.math import Vector2 as v2
def generateLights(self, level_file):
    print("Generating lights.")
    
    t = time.time()
    

    self.currLoad = "Generating lights"
    
    self.loadPoint = 0

    self.maxLoad = len(self.level.lights) + len(self.floorRects) * 2

    self.mapCorner = v2(
        min(w.rect.left for w in self.walls),
        min(w.rect.top  for w in self.walls)
    )

    for i, LIGHT in enumerate(self.level.lights):
        self.loadPoint += 1
        self.currLoad = f"Light {i}: Making wall mask"
        r = int(LIGHT.radius * self.RENDER_SCALE)
        LIGHT.los_surf = pygame.Surface((r * 2, r * 2))
        LIGHT.los_surf.fill((0, 0, 0))
        # Camera = render-space top-left of this light's bounding box
        light_cam = LIGHT.pos * self.RENDER_SCALE - v2(r, r)
        los_draw(LIGHT.los_surf, LIGHT.pos * self.RENDER_SCALE, light_cam, self.los_walls, debug=False)
        LIGHT.is_static = isinstance(LIGHT, StaticLight)

    def light_touches_rect(light, r):
        closest_x = max(r.left, min(light.pos.x, r.right))
        closest_y = max(r.top,  min(light.pos.y, r.bottom))
        return v2(closest_x, closest_y).distance_to(light.pos) < light.radius
    
    def light_reaches_rect(light, r):
        radius = int(light.radius * self.RENDER_SCALE)
        # r is already in render space at this point (rectConverted)
        lx = int(r.left - light.pos.x * self.RENDER_SCALE + radius)
        ly = int(r.top  - light.pos.y * self.RENDER_SCALE + radius)

        x0 = max(0, lx);            y0 = max(0, ly)
        x1 = min(radius*2, lx+r.width); y1 = min(radius*2, ly+r.height)

        if x0 >= x1 or y0 >= y1:
            return False

        arr = pygame.surfarray.array3d(light.los_surf)
        return bool(arr[x0:x1, y0:y1].max() > 0)

    rect_lights  = {}
    rect_dynamic = {}
    for i, r in enumerate(self.floorRects):
        self.loadPoint += 1
        self.currLoad = f"Floor {i}: Checking light reachability"
        touching = [L for L in self.level.lights if light_reaches_rect(L, r)]
        rect_lights[i]  = touching
        rect_dynamic[i] = any(not L.is_static for L in touching)


    NUM_FRAMES = max(len(L.frames) for L in self.level.lights)
    print("FRAMES:", NUM_FRAMES)

    self.light_static = []
    self.light_frames = [[] for _ in range(NUM_FRAMES)]

    # Pre-build rect surfaces (ambient base)
    rect_surfs_static = {}
    rect_surfs_dynamic = [{} for _ in range(NUM_FRAMES)]

    for i, r in enumerate(self.floorRects):
        rectConverted = pygame.Rect(
            int(r.x * self.RENDER_SCALE),
            int(r.y * self.RENDER_SCALE),
            int(r.width * self.RENDER_SCALE),
            int(r.height * self.RENDER_SCALE),
        )
        if not rect_dynamic[i]:
            s = pygame.Surface((rectConverted.width, rectConverted.height)).convert()
            s.fill((40, 40, 40))
            rect_surfs_static[i] = (s, rectConverted)
        else:
            for x in range(NUM_FRAMES):
                s = pygame.Surface((rectConverted.width, rectConverted.height)).convert()
                s.fill((40, 40, 40))
                rect_surfs_dynamic[x][i] = (s, rectConverted)

    # Process one light at a time
    for LIGHT in self.level.lights:
        radius = int(LIGHT.radius * self.RENDER_SCALE)

        frames_needed = range(NUM_FRAMES) if not LIGHT.is_static else [0]
        scaled_cache = {}

        for x in frames_needed:
            QUALITY = 5
            smR = int(radius * 2 / QUALITY)
            scaled = pygame.transform.smoothscale(LIGHT.frames[x], (smR, smR))
            if QUALITY > 1:
                scaled = pygame.transform.scale(scaled, (radius * 2, radius * 2))
            scaled.blit(LIGHT.los_surf, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            scaled_cache[x] = scaled

        for i, r in enumerate(self.floorRects):
            if LIGHT not in rect_lights[i]:
                continue

            rectConverted = pygame.Rect(
                int(r.x * self.RENDER_SCALE),
                int(r.y * self.RENDER_SCALE),
                int(r.width * self.RENDER_SCALE),
                int(r.height * self.RENDER_SCALE),
            )
            blit_pos = LIGHT.pos * self.RENDER_SCALE - v2(radius) - v2(rectConverted.topleft)

            if not rect_dynamic[i]:
                rect_surfs_static[i][0].blit(scaled_cache[0], blit_pos, special_flags=pygame.BLEND_RGB_ADD)
            else:
                for x in range(NUM_FRAMES):
                    rect_surfs_dynamic[x][i][0].blit(scaled_cache[x if not LIGHT.is_static else 0], blit_pos, special_flags=pygame.BLEND_RGB_ADD)

        # Drop this light's data immediately
        del scaled_cache
        del LIGHT.los_surf
        del LIGHT.frames

    self.light_static = list(rect_surfs_static.values())
    for x in range(NUM_FRAMES):
        self.light_frames[x] = list(rect_surfs_dynamic[x].values())

    self.light_frame_time = 0
    print(f"Lights drawn. Elapsed time: {time.time() - t:.1f}s")
    del self.level.lights