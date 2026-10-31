"""A* on the 1 m grid, 8-connected. Edge cost = step length * mean(cell costs). Hard cells are impassable.

Route stability (PlannerConfig): a re-plan that is not forced (goal unchanged, current route still clear) is
searched with a mild discount on the cells of the current route ('inertia') and is only adopted if its true,
undiscounted cost beats the remaining current route by 'switch_margin'. Ties in the open list are broken by the
lower heuristic and then by cell index, so identical inputs always give the identical route.
"""
from __future__ import annotations

import heapq
import time
from dataclasses import dataclass

import numpy as np

from autonomy.planning.rover_perception import cell_of, center_of

NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


@dataclass
class PlannerConfig:
    path_inertia: float = 1.0          # edge-cost multiplier on cells of the current route (<1 prefers keeping it)
    switch_margin: float = 0.0         # a non-forced re-plan switches only if >= this fraction cheaper
    min_replan_interval_s: float = 0.0 # minimum time between non-forced re-plans
    block_confirm: int = 1             # consecutive 'route blocked' checks (0.5 s apart) before re-planning
    tight_inflation_m: float | None = None   # fallback tier: if no route keeps the normal clearance, allow this one ...
    tight_speed: float = 0.5                 # ... and drive such a narrow-passage route at this fraction of cruise speed


def path_cost(cells: list, cost: np.ndarray) -> float:
    """True (undiscounted) cost of a cell route with the same edge model as the search."""
    tot = 0.0
    for a, b in zip(cells[:-1], cells[1:]):
        tot += float(np.hypot(b[0] - a[0], b[1] - a[1])) * 0.5 * (cost[a] + cost[b])
    return tot


def astar(cost: np.ndarray, hard: np.ndarray, start_xy, goal_xy, allow_start_blocked: bool = True,
          prefer_cells=None, inertia: float = 1.0, stable: bool = False,
          rocks: np.ndarray | None = None) -> dict:
    t0 = time.perf_counter()
    M = cost.shape[0]
    s, g = cell_of(*start_xy), cell_of(*goal_xy)
    hard = hard.copy()
    cost_true = cost
    if allow_start_blocked:
        # the rover may currently sit inside an inflated zone; let it leave - but never across a rock cell itself
        win = (slice(max(s[0] - 1, 0), s[0] + 2), slice(max(s[1] - 1, 0), s[1] + 2))
        hard[win] = False if rocks is None else rocks[win]
        hard[s] = False
    hard[g] = False
    if prefer_cells and inertia < 1.0:
        # mild discount on the current route: an equally good alternative never displaces it
        cost = cost.copy()
        pc = np.array(sorted(set(prefer_cells)))
        cost[pc[:, 0], pc[:, 1]] *= inertia
    open_ = [(0.0, 0.0, 0.0, s)]
    came = {s: None}
    gcost = {s: 0.0}
    cmin = float(cost[~hard].min()) if (~hard).any() else 1.0     # admissible: includes any discount
    expanded = 0
    while open_:
        _, _, gc, cur = heapq.heappop(open_)
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
                # stable: equal f broken by lower h (rounded so float noise cannot reorder), then by cell index
                key = (round(ng + h, 9), round(h, 9)) if stable else (ng + h, ng)
                heapq.heappush(open_, (*key, ng, (ni, nj)))
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
    return {"found": True, "path": pts, "cells": cells, "cost": path_cost(cells, cost_true),
            "length": length,
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
