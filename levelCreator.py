import json
import os
import numpy as np
import pygame
from pygame import Vector2 as v2
from dynamicBakedLight import (Light, StaticLight, StrobeLight, PulseLight,
                    RotatingLight, ColorCycleLight)

pygame.init()
from level import Level
LEVEL_FILE = "level.json"
CACHE_FILE = "wall_cache.json"

RES = v2(1920, 1080)
screen = pygame.display.set_mode(RES)
clock  = pygame.time.Clock()
pygame.display.set_caption("Level Creator")

TILESIZE = 100
TILE     = 100.0
TILE_MIN = 20.0
TILE_MAX = 300.0

cam  = v2(0, 0)
font = pygame.font.SysFont("monospace", 16)

editor_mode = "walls"   # "walls" | "nodes" | "lights"



level = Level.load()


# ── coordinate helpers ────────────────────────────────────────────────────────

def world_to_screen(wx, wy):
    return v2((wx - cam.x) * TILE / TILESIZE,
              (wy - cam.y) * TILE / TILESIZE)

def screen_to_world(sx, sy):
    return v2(sx * TILESIZE / TILE + cam.x,
              sy * TILESIZE / TILE + cam.y)

def world_to_tile_f(wx, wy):
    return round(wx / TILESIZE * 2) / 2, round(wy / TILESIZE * 2) / 2

def tile_to_world(tx, ty):
    return tx * TILESIZE, ty * TILESIZE

def screen_to_tile_int(sx, sy):
    wx, wy = screen_to_world(sx, sy)
    return int(wx // TILESIZE), int(wy // TILESIZE)


from level import AreaType, AREA_COLORS, AREA_TYPES
from los.los_walls import build_and_cache
# ── area state (mirrors wall state) ──────────────────────────────────────────
area_type_idx  = 0
area_state     = "idle"
area_drag_start = None
area_preview   = None
sel_area       = None
area_move_off  = None

if not hasattr(level, "areas"):
    level.areas = []


# ── wall helpers ──────────────────────────────────────────────────────────────

wall_state   = "idle"
drag_start   = None
preview_rect = None
selected_idx = None
move_offset  = None

def rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx+bw and ax+aw > bx and ay < by+bh and ay+ah > by

def any_overlap_excluding(nx, ny, nw, nh, exclude=None):
    for i, r in enumerate(level.walls):
        if i == exclude:
            continue
        if rects_overlap(nx, ny, nw, nh, r[0], r[1], r[2], r[3]):
            return True
    return False

def normalize_rect(ax, ay, bx, by):
    x = min(ax, bx); y = min(ay, by)
    return x, y, abs(bx-ax)+1, abs(by-ay)+1

def point_in_rect(tx, ty, r):
    return r[0] <= tx < r[0]+r[2] and r[1] <= ty < r[1]+r[3]

def rect_at_tile(tx, ty):
    for i, r in enumerate(level.walls):
        if point_in_rect(tx, ty, r):
            return i
    return None


# ── nav helpers ───────────────────────────────────────────────────────────────

nav_edges    = []
sel_node     = None
node_move_off= None

def load_cache():
    return build_and_cache("level.json", "wall_cache.json", True, 1.0)

los_walls_np = load_cache()

def node_world(i):
    return v2(level.nodes[i][0] * TILESIZE, level.nodes[i][1] * TILESIZE)

def node_screen(i):
    wx, wy = level.nodes[i][0] * TILESIZE, level.nodes[i][1] * TILESIZE
    return world_to_screen(wx, wy)

def node_screen_radius():
    return max(4, 12 * TILE / TILESIZE)

def _ccw(ax, ay, bx, by, cx, cy):
    return (cy-ay)*(bx-ax) > (by-ay)*(cx-ax)

def _seg_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    return (_ccw(ax,ay,cx,cy,dx,dy) != _ccw(bx,by,cx,cy,dx,dy) and
            _ccw(ax,ay,bx,by,cx,cy) != _ccw(ax,ay,bx,by,dx,dy))

def can_see(ax, ay, bx, by):
    if los_walls_np.shape[0] == 0:
        return True
    for i in range(los_walls_np.shape[0]):
        wx1,wy1 = los_walls_np[i,0], los_walls_np[i,1]
        wx2,wy2 = los_walls_np[i,2], los_walls_np[i,3]
        if (wx1==ax and wy1==ay) or (wx2==ax and wy2==ay): continue
        if (wx1==bx and wy1==by) or (wx2==bx and wy2==by): continue
        if _seg_intersect(ax,ay,bx,by,wx1,wy1,wx2,wy2):
            return False
    return True

def rebuild_edges():
    global nav_edges
    nav_edges = []
    n = len(level.nodes)
    for i in range(n):
        for j in range(i+1, n):
            ax,ay = level.nodes[i][0]*TILESIZE, level.nodes[i][1]*TILESIZE
            bx,by = level.nodes[j][0]*TILESIZE, level.nodes[j][1]*TILESIZE
            if can_see(ax, ay, bx, by):
                nav_edges.append((i, j))

def node_at_world(world_pos):
    for i in range(len(level.nodes)):
        if node_world(i).distance_to(world_pos) <= 12:
            return i
    return None

rebuild_edges()


# ── light helpers ─────────────────────────────────────────────────────────────

sel_light    = None
light_frame  = 0
frame_timer  = 0.0

LIGHT_TYPES = ["StaticLight", "StrobeLight", "PulseLight", "RotatingLight", "ColorCycleLight"]
light_type_idx = 0

LIGHT_DEFAULTS = {
    "StaticLight":    dict(radius=1000, color=(255, 220, 150), intensity=1.0),
    "StrobeLight":    dict(radius=1000, color=(255, 255, 255), intensity=1.0, oscillations=4, duty=0.5),
    "PulseLight":     dict(radius=1000, color=(255, 100,  50), intensity=1.0, oscillations=2.0, min_intensity=0.1),
    "RotatingLight":  dict(radius=1000, color=(200,  50, 255), intensity=1.0, spread_deg=45.0, rotations=1.0),
    "ColorCycleLight":dict(radius=1000, color=(255,   0,   0), intensity=1.0,
                           colors=[[255,0,0],[0,255,0],[0,0,255]]),
}

LIGHT_CLS = {
    "StaticLight": StaticLight,
    "StrobeLight": StrobeLight,
    "PulseLight":  PulseLight,
    "RotatingLight": RotatingLight,
    "ColorCycleLight": ColorCycleLight,
}

def light_screen_pos(light: Light):
    return world_to_screen(light.pos.x, light.pos.y)

def light_at_world(world_pos: v2):
    HIT = 20
    for i, l in enumerate(level.lights):
        if l.pos.distance_to(world_pos) <= HIT:
            return i
    return None

light_move_off = None


# ── drawing ───────────────────────────────────────────────────────────────────

def draw_grid():
    offset_x = (-cam.x * TILE / TILESIZE) % TILE
    offset_y = (-cam.y * TILE / TILESIZE) % TILE
    x = offset_x
    while x <= RES.x:
        pygame.draw.line(screen, (60,60,60), (int(x),0), (int(x),int(RES.y)))
        x += TILE
    y = offset_y
    while y <= RES.y:
        pygame.draw.line(screen, (60,60,60), (0,int(y)), (int(RES.x),int(y)))
        y += TILE

def draw_rect_world(tx, ty, tw, th, color, alpha=255):
    sp = world_to_screen(tx*TILESIZE, ty*TILESIZE)
    pw = tw * TILE; ph = th * TILE
    surf = pygame.Surface((max(1,int(pw)), max(1,int(ph))), pygame.SRCALPHA)
    surf.fill((*color, alpha))
    screen.blit(surf, sp)

def draw_rect_outline(tx, ty, tw, th, color, width=1):
    sp = world_to_screen(tx*TILESIZE, ty*TILESIZE)
    pw = tw * TILE; ph = th * TILE
    pygame.draw.rect(screen, color, (*sp, pw, ph), width)

def draw_walls():
    for i, r in enumerate(level.walls):
        draw_rect_world(r[0],r[1],r[2],r[3], (0,0,0))
        col = (255,200,0) if i==selected_idx else (80,80,80)
        w   = 2 if i==selected_idx else 1
        draw_rect_outline(r[0],r[1],r[2],r[3], col, w)

def draw_nodes():
    r = int(node_screen_radius())
    for i, j in nav_edges:
        a = node_screen(i); b = node_screen(j)
        pygame.draw.line(screen, (0,180,255), (int(a.x),int(a.y)), (int(b.x),int(b.y)), 1)
    for i in range(len(level.nodes)):
        sp  = node_screen(i)
        col = (255,200,0) if i==sel_node else (0,220,255)
        pygame.draw.circle(screen, col,    (int(sp.x),int(sp.y)), r)
        pygame.draw.circle(screen, (0,0,0),(int(sp.x),int(sp.y)), r, 2)

def draw_node_preview():
    mworld = screen_to_world(*pygame.mouse.get_pos())
    tx, ty = world_to_tile_f(mworld.x, mworld.y)
    wx, wy = tile_to_world(tx, ty)
    sp = world_to_screen(wx, wy)
    r  = int(node_screen_radius())
    pygame.draw.circle(screen, (0,220,255), (int(sp.x),int(sp.y)), r, 2)
    for nd in level.nodes:
        nx, ny = nd[0]*TILESIZE, nd[1]*TILESIZE
        if can_see(wx, wy, nx, ny):
            nsp = world_to_screen(nx, ny)
            pygame.draw.line(screen, (0,255,100),
                             (int(sp.x),int(sp.y)), (int(nsp.x),int(nsp.y)), 1)

def draw_lights():
    for i, light in enumerate(level.lights):
        # scale the light surface to screen space
        world_r = light.radius
        screen_r = int(world_r * TILE / TILESIZE)
        if screen_r < 2:
            continue
        
        sp = light_screen_pos(light)
        pygame.draw.circle(screen, light.color, sp, screen_r, 1)
        #screen.blit(scaled, (sp.x - screen_r, sp.y - screen_r), special_flags=pygame.BLEND_RGB_ADD)
        # icon dot
        col = (255, 255, 0) if i == sel_light else (200, 200, 200)
        pygame.draw.circle(screen, col, (int(sp.x), int(sp.y)), 6)
        pygame.draw.circle(screen, (0,0,0), (int(sp.x), int(sp.y)), 6, 1)
        lbl = font.render(light.__class__.__name__[:-5], True, col)
        screen.blit(lbl, (int(sp.x) + 8, int(sp.y) - 8))

def draw_areas():
    area_font = pygame.font.SysFont("monospace", 12)
    for i, a in enumerate(level.areas):
        tx, ty, tw, th, atype = a
        color = AREA_COLORS[atype]
        draw_rect_world(tx, ty, tw, th, color, alpha=60)
        col = (255, 255, 0) if i == sel_area else color
        draw_rect_outline(tx, ty, tw, th, col, 2 if i == sel_area else 1)

        # label in inner top-left
        sp = world_to_screen(tx * TILESIZE, ty * TILESIZE)
        lbl = area_font.render(atype.value, True, col)
        screen.blit(lbl, (int(sp.x) + 4, int(sp.y) + 4))

    # preview while dragging
    if area_state == "drawing" and area_preview:
        tx, ty, tw, th = area_preview
        color = AREA_COLORS[AREA_TYPES[area_type_idx]]
        draw_rect_world(tx, ty, tw, th, color, alpha=40)
        draw_rect_outline(tx, ty, tw, th, color, 2)

def draw_light_preview():
    mworld = screen_to_world(*pygame.mouse.get_pos())
    sp = world_to_screen(mworld.x, mworld.y)
    pygame.draw.circle(screen, (255, 255, 100), (int(sp.x), int(sp.y)), 6, 2)
    lbl = font.render(f"[{LIGHT_TYPES[light_type_idx][:-5]}]", True, (255, 255, 100))
    screen.blit(lbl, (int(sp.x) + 10, int(sp.y) - 10))

def draw_ui():
    cam_cx = (cam.x + RES.x/2*TILESIZE/TILE) / TILESIZE
    cam_cy = (cam.y + RES.y/2*TILESIZE/TILE) / TILESIZE
    mworld_x, mworld_y = screen_to_world(*pygame.mouse.get_pos())
    mode_str = {"walls":"WALLS","nodes":"NODES","lights":"LIGHTS", "areas":"AREAS"}[editor_mode]

    if editor_mode == "walls":
        hint  = "[LMB drag] Place  [RMB] Select/Move  [DEL] Delete  [Wheel] Zoom  [C] Clear"
        extra = f"State: {wall_state}{'  Sel: '+str(selected_idx) if selected_idx is not None else ''}"
    elif editor_mode == "nodes":
        hint  = "[LMB] Place  [RMB] Select/Move  [DEL] Delete  [C] Clear"
        extra = f"Nodes: {len(level.nodes)}  Edges: {len(nav_edges)}"
    elif editor_mode == "areas":
        hint  = "[LMB drag] Place  [RMB] Select/Move  [DEL] Delete  [Q/E] Type  [C] Clear"
        extra = f"Type: {AREA_TYPES[area_type_idx].value}  Areas: {len(level.areas)}"
    else:
        hint  = "[LMB] Place  [RMB] Select/Move  [DEL] Delete  [Q/E] Type  [C] Clear"
        extra = f"Type: {LIGHT_TYPES[light_type_idx]}  Lights: {len(level.lights)}"

    lines = [
        f"Mouse: ({mworld_x / TILESIZE:.1f},{mworld_y / TILESIZE:.1f})  Zoom: {TILE:.0f}  [TAB] Mode: {mode_str}",
        extra, hint,
    ]
    if editor_mode == "walls" and preview_rect:
        pr = preview_rect
        lines.insert(1, f"Preview: ({pr[0]},{pr[1]}) {pr[2]}x{pr[3]}")

    y = 8
    for line in lines:
        screen.blit(font.render(line, True, (220,220,220)), (8, y))
        y += 20


# ── main loop ─────────────────────────────────────────────────────────────────

running = True
while running:
    dt = clock.tick(144) / 1000

    # animate light preview
    frame_timer += dt
    if frame_timer >= 1/60:
        frame_timer -= 1/60
        light_frame = (light_frame + 1) % 60

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        # zoom
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (4, 5):
            ms  = v2(pygame.mouse.get_pos())
            old = TILE
            TILE = min(TILE_MAX, TILE+10) if e.button==4 else max(TILE_MIN, TILE-10)
            s   = TILE / old
            cam.x = (ms.x * TILESIZE/old + cam.x) * s - ms.x * TILESIZE/TILE
            cam.y = (ms.y * TILESIZE/old + cam.y) * s - ms.y * TILESIZE/TILE

        # TAB toggle
        if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
            modes = ["walls", "nodes", "lights", "areas"]
            editor_mode = modes[(modes.index(editor_mode)+1) % len(modes)]
            selected_idx = sel_node = sel_light = None
            wall_state = "idle"

        # ══ WALL MODE ════════════════════════════════════════════════════
        if editor_mode == "walls":
            if e.type == pygame.MOUSEBUTTONDOWN:
                sx, sy = pygame.mouse.get_pos()
                tile = screen_to_tile_int(sx, sy)
                if e.button == 1 and wall_state == "idle":
                    selected_idx = None
                    wall_state   = "drawing"
                    drag_start   = tile
                    preview_rect = (*tile, 1, 1)
                elif e.button == 3 and wall_state == "idle":
                    idx = rect_at_tile(*tile)
                    if idx is not None:
                        if idx == selected_idx:
                            selected_idx = None; level.save()
                        else:
                            selected_idx = idx
                            r = level.walls[idx]
                            move_offset  = (tile[0]-r[0], tile[1]-r[1])
                            wall_state   = "moving"
                    else:
                        if selected_idx is not None:
                            selected_idx = None; level.save()

            if e.type == pygame.MOUSEBUTTONUP:
                sx, sy = pygame.mouse.get_pos()
                tile = screen_to_tile_int(sx, sy)
                if e.button == 1 and wall_state == "drawing":
                    if drag_start:
                        nx,ny,nw,nh = normalize_rect(*drag_start, *tile)
                        if not any_overlap_excluding(nx,ny,nw,nh):
                            level.walls.append([nx,ny,nw,nh]); level.save()
                    wall_state = "idle"; drag_start = None; preview_rect = None
                elif e.button == 3 and wall_state == "moving":
                    wall_state = "idle"; level.save(); move_offset = None

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_DELETE and selected_idx is not None and wall_state == "idle":
                    level.walls.pop(selected_idx); selected_idx = None; level.save()
                if e.key == pygame.K_c and wall_state == "idle":
                    level.walls.clear(); selected_idx = None; level.save()

        # ══ NODE MODE ════════════════════════════════════════════════════
        elif editor_mode == "nodes":
            if e.type == pygame.MOUSEBUTTONDOWN:
                mworld = screen_to_world(*pygame.mouse.get_pos())
                if e.button == 1:
                    tx, ty = world_to_tile_f(mworld.x, mworld.y)
                    level.nodes.append([tx, ty])
                    rebuild_edges(); level.save()
                elif e.button == 3:
                    idx = node_at_world(mworld)
                    if idx is not None:
                        if idx == sel_node:
                            sel_node = None; level.save()
                        else:
                            sel_node = idx
                            node_move_off = node_world(idx) - mworld
                    else:
                        if sel_node is not None:
                            sel_node = None; level.save()

            if e.type == pygame.MOUSEBUTTONUP:
                if e.button == 3 and sel_node is not None:
                    rebuild_edges(); level.save(); node_move_off = None

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_DELETE and sel_node is not None:
                    level.nodes.pop(sel_node); sel_node = None; rebuild_edges(); level.save()
                if e.key == pygame.K_c:
                    level.nodes.clear(); sel_node = None; nav_edges.clear(); level.save()

        # ══ LIGHT MODE ═══════════════════════════════════════════════════
        elif editor_mode == "lights":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_q:
                    light_type_idx = (light_type_idx - 1) % len(LIGHT_TYPES)
                if e.key == pygame.K_e:
                    light_type_idx = (light_type_idx + 1) % len(LIGHT_TYPES)
                if e.key == pygame.K_DELETE and sel_light is not None:
                    level.lights.pop(sel_light); sel_light = None; level.save()
                if e.key == pygame.K_c:
                    level.lights.clear(); sel_light = None; level.save()

            if e.type == pygame.MOUSEBUTTONDOWN:
                mworld = screen_to_world(*pygame.mouse.get_pos())
                if e.button == 1:
                    cls_name = LIGHT_TYPES[light_type_idx]
                    cls      = LIGHT_CLS[cls_name]
                    kwargs   = dict(LIGHT_DEFAULTS[cls_name])
                    kwargs["pos"] = mworld
                    light = cls(**kwargs)
                    level.lights.append(light)
                    level.save()

                elif e.button == 3:
                    idx = light_at_world(mworld)
                    if idx is not None:
                        if idx == sel_light:
                            sel_light = None; level.save()
                        else:
                            sel_light = idx
                            light_move_off = level.lights[idx].pos - mworld
                    else:
                        if sel_light is not None:
                            sel_light = None; level.save()

            if e.type == pygame.MOUSEBUTTONUP:
                if e.button == 3 and sel_light is not None:
                    level.save(); light_move_off = None

        elif editor_mode == "areas":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_q:
                    area_type_idx = (area_type_idx - 1) % len(AREA_TYPES)
                if e.key == pygame.K_e:
                    area_type_idx = (area_type_idx + 1) % len(AREA_TYPES)
                if e.key == pygame.K_DELETE and sel_area is not None:
                    level.areas.pop(sel_area); sel_area = None; level.save()
                if e.key == pygame.K_c:
                    level.areas.clear(); sel_area = None; level.save()

            if e.type == pygame.MOUSEBUTTONDOWN:
                sx, sy = pygame.mouse.get_pos()
                tile = screen_to_tile_int(sx, sy)
                if e.button == 1 and area_state == "idle":
                    sel_area = None
                    area_state = "drawing"
                    area_drag_start = tile
                    area_preview = (*tile, 1, 1)
                elif e.button == 3 and area_state == "idle":
                    # find topmost area containing tile
                    hit = None
                    for i, a in enumerate(level.areas):
                        if point_in_rect(tile[0], tile[1], a[:4]):
                            hit = i
                    if hit is not None:
                        if hit == sel_area:
                            sel_area = None; level.save()
                        else:
                            sel_area = hit
                            r = level.areas[hit]
                            area_move_off = (tile[0] - r[0], tile[1] - r[1])
                            area_state = "moving"
                    else:
                        if sel_area is not None:
                            sel_area = None; level.save()

            if e.type == pygame.MOUSEBUTTONUP:
                sx, sy = pygame.mouse.get_pos()
                tile = screen_to_tile_int(sx, sy)
                if e.button == 1 and area_state == "drawing":
                    if area_drag_start:
                        nx, ny, nw, nh = normalize_rect(*area_drag_start, *tile)
                        level.areas.append([nx, ny, nw, nh, AREA_TYPES[area_type_idx]])
                        level.save()
                    area_state = "idle"; area_drag_start = None; area_preview = None
                elif e.button == 3 and area_state == "moving":
                    area_state = "idle"; level.save(); area_move_off = None

        

    # ── per-frame updates ─────────────────────────────────────────────────
    if editor_mode == "walls":
        if wall_state == "drawing" and drag_start:
            sx, sy = pygame.mouse.get_pos()
            preview_rect = normalize_rect(*drag_start, *screen_to_tile_int(sx, sy))
        if wall_state == "moving" and selected_idx is not None:
            sx, sy = pygame.mouse.get_pos()
            tile = screen_to_tile_int(sx, sy)
            r  = level.walls[selected_idx]
            nx = tile[0] - move_offset[0]
            ny = tile[1] - move_offset[1]
            if not any_overlap_excluding(nx,ny,r[2],r[3], exclude=selected_idx):
                level.walls[selected_idx][0] = nx
                level.walls[selected_idx][1] = ny

    elif editor_mode == "nodes":
        if sel_node is not None and node_move_off is not None:
            mworld = screen_to_world(*pygame.mouse.get_pos())
            tx, ty = world_to_tile_f((mworld + node_move_off).x, (mworld + node_move_off).y)
            level.nodes[sel_node] = [tx, ty]

    elif editor_mode == "lights":
        if sel_light is not None and light_move_off is not None:
            mworld = screen_to_world(*pygame.mouse.get_pos())
            level.lights[sel_light].pos = mworld + light_move_off

    elif editor_mode == "areas":
        if area_state == "drawing" and area_drag_start:
            sx, sy = pygame.mouse.get_pos()
            area_preview = normalize_rect(*area_drag_start, *screen_to_tile_int(sx, sy))
        if area_state == "moving" and sel_area is not None:
            sx, sy = pygame.mouse.get_pos()
            tile = screen_to_tile_int(sx, sy)
            a = level.areas[sel_area]
            level.areas[sel_area][0] = tile[0] - area_move_off[0]
            level.areas[sel_area][1] = tile[1] - area_move_off[1]

    # ── camera ────────────────────────────────────────────────────────────
    keys  = pygame.key.get_pressed()
    speed = 500 * dt
    if keys[pygame.K_a]: cam.x -= speed
    if keys[pygame.K_d]: cam.x += speed
    if keys[pygame.K_w]: cam.y -= speed
    if keys[pygame.K_s] and wall_state == "idle": cam.y += speed

    # ── render ────────────────────────────────────────────────────────────
    screen.fill((30,30,30))
    draw_grid()
    draw_walls()

    if editor_mode in ("nodes", "walls"):
        draw_nodes()
        if editor_mode == "nodes" and sel_node is None:
            draw_node_preview()

    if editor_mode == "walls" and wall_state == "drawing" and preview_rect:
        pr    = preview_rect
        valid = not any_overlap_excluding(pr[0],pr[1],pr[2],pr[3])
        col   = (0,180,0) if valid else (180,0,0)
        draw_rect_world(pr[0],pr[1],pr[2],pr[3], col, alpha=120)
        draw_rect_outline(pr[0],pr[1],pr[2],pr[3], col, 2)

    draw_lights()
    draw_areas()
    if editor_mode == "lights" and sel_light is None:
        draw_light_preview()

    draw_ui()

    pygame.draw.circle(screen, (255,0,0), world_to_screen(0,0), 6)

    pygame.display.flip()

pygame.quit()