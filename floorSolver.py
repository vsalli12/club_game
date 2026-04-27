import numpy as np
import os, json
def build_grid(walls):
    xs = [x for x,_,w,_ in walls] + [x+w for x,_,w,_ in walls]
    ys = [y for _,y,_,h in walls] + [y+h for _,y,_,h in walls]

    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    W = xmax - xmin
    H = ymax - ymin

    grid = np.zeros((H, W), dtype=np.uint8)

    for x,y,w,h in walls:
        grid[y-ymin:y-ymin+h, x-xmin:x-xmin+w] = 1

    return grid, xmin, ymin

def extract_rectangles(grid):
    H, W = grid.shape
    used = np.zeros_like(grid)
    rects = []

    for y in range(H):
        for x in range(W):
            if grid[y,x] == 1 and not used[y,x]:
                
                w = 0
                while x+w < W and grid[y,x+w] == 1 and not used[y,x+w]:
                    w += 1

                h = 1
                while y+h < H:
                    ok = True
                    for dx in range(w):
                        if grid[y+h,x+dx] != 1 or used[y+h,x+dx]:
                            ok = False
                            break
                    if not ok:
                        break
                    h += 1

                used[y:y+h, x:x+w] = 1
                rects.append((x,y,w,h))

    return rects

from collections import deque

def remove_leaks(grid):
    H, W = grid.shape
    outside = np.zeros_like(grid, dtype=np.uint8)

    q = deque()

    # enqueue all boundary empty cells
    for x in range(W):
        if grid[0, x] == 0:
            q.append((0, x))
        if grid[H-1, x] == 0:
            q.append((H-1, x))
    for y in range(H):
        if grid[y, 0] == 0:
            q.append((y, 0))
        if grid[y, W-1] == 0:
            q.append((y, W-1))

    # flood fill
    while q:
        y, x = q.popleft()
        if outside[y, x]:
            continue
        outside[y, x] = 1

        for dy, dx in [(1,0),(-1,0),(0,1),(0,-1)]:
            ny, nx = y+dy, x+dx
            if 0 <= ny < H and 0 <= nx < W:
                if grid[ny, nx] == 0 and not outside[ny, nx]:
                    q.append((ny, nx))

    # interior = empty AND not outside
    interior = (grid == 0) & (outside == 0)
    return interior.astype(np.uint8)

def solve(walls):
    grid, ox, oy = build_grid(walls)

    interior = remove_leaks(grid)

    rects = extract_rectangles(interior)

    return [(x+ox, y+oy, w, h) for x,y,w,h in rects]

if __name__ == "__main__":
    SAVE_FILE = "walls.json"

    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE) as f:
            l = [list(r) for r in json.load(f)]
