"""A* on the 1 m grid, 8-connected. Edge cost = step length * mean(cell costs). Hard cells are impassable."""
from __future__ import annotations

import heapq
import time

import numpy as np

from autonomy.planning.rover_perception import cell_of, center_of

NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def astar(cost: np.ndarray, hard: np.ndarray, start_xy, goal_xy, allow_start_blocked: bool = True) -> dict:
    t0 = time.perf_counter()
    M = cost.shape[0]
    s, g = cell_of(*start_xy), cell_of(*goal_xy)
    hard = hard.copy()
    if allow_start_blocked:
        # the rover may currently sit inside an inflated zone; let it leave
        hard[max(s[0] - 1, 0):s[0] + 2, max(s[1] - 1, 0):s[1] + 2] = False
    hard[g] = False
    open_ = [(0.0, 0.0, s)]
    came = {s: None}
    gcost = {s: 0.0}
    cmin = float(cost[~hard].min()) if (~hard).any() else 1.0
    expanded = 0
    while open_:
        _, gc, cur = heapq.heappop(open_)
        if cur == g:
            break
        if gc > gcost.get(cur, np.inf):
            continue
        expanded += 1
        ci, cj = cur
        for di, dj, d in NB:
            ni, nj = ci + di, cj + dj
            if not (0 <= ni < M and 0 <= nj < M) or hard[ni, nj]:
                continue
            if di and dj and (hard[ci + di, cj] or hard[ci, cj + dj]):
                continue        # no corner cutting
            ng = gc + d * 0.5 * (cost[ci, cj] + cost[ni, nj])
            if ng < gcost.get((ni, nj), np.inf):
                gcost[(ni, nj)] = ng
                came[(ni, nj)] = cur
                h = cmin * np.hypot(g[0] - ni, g[1] - nj)
                heapq.heappush(open_, (ng + h, ng, (ni, nj)))
    ms = 1000 * (time.perf_counter() - t0)
    if g not in came:
        return {"found": False, "path": [], "cost": None, "expanded": expanded, "time_ms": ms}
    cells = []
    c = g
    while c is not None:
        cells.append(c); c = came[c]
    cells.reverse()
    cells = smooth(cells, cost, hard)
    pts = [center_of(*c) for c in cells]
    pts[-1] = tuple(goal_xy)
    length = float(sum(np.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) for k in range(len(pts) - 1)))
    return {"found": True, "path": pts, "cells": cells, "cost": float(gcost[g]), "length": length,
            "expanded": expanded, "time_ms": ms}


def path_blocked(path_cells: list, hard: np.ndarray, from_index: int = 0, rover_cell=None, ignore_radius: int = 1) -> bool:
    """True if any remaining path cell (excluding the rover's own neighbourhood) is a hard cell."""
    for c in path_cells[from_index + 1:-1]:
        if rover_cell is not None and max(abs(c[0] - rover_cell[0]), abs(c[1] - rover_cell[1])) <= ignore_radius:
            continue
        if hard[c]:
            return True
    return False


def _line(a, b):
    """Grid cells on the segment a-b (Bresenham)."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    out = []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def _corridor_clear(ln, hard) -> bool:
    M = hard.shape[0]
    for (i, j) in ln[1:-1]:
        for di, dj in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < M and 0 <= b < M and hard[a, b]:
                return False
    return True


def smooth(cells: list, cost: np.ndarray, hard: np.ndarray, cost_tol: float = 1.15) -> list:
    """Line-of-sight shortcutting ('string pulling'). A shortcut is accepted only if every cell on it
    is non-hard and its worst cell cost is within cost_tol of the worst cost on the replaced segment.
    The result is re-densified to unit steps so path-blocked checks still see every traversed cell."""
    if len(cells) < 3:
        return cells
    out = [cells[0]]
    i = 0
    while i < len(cells) - 1:
        j = len(cells) - 1
        while j > i + 1:
            ln = _line(cells[i], cells[j])
            seg_max = max(cost[c] for c in cells[i:j + 1])
            if _corridor_clear(ln, hard) and max(cost[c] for c in ln) <= cost_tol * seg_max:
                break
            j -= 1
        out.extend(_line(cells[i], cells[j])[1:])
        i = j
    return out
