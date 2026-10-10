"""Bounded furniture placement using the same oriented SAT boxes as the MDP.

Feasibility is a hard constraint, separate from the ergonomic reward. Search
failure means no solution was found within this grid/time budget, not that the
room is mathematically impossible to furnish. Dimensions and IDs never change.
"""
import copy
import math
import time

import numpy as np

from engine.sat_collision import (
    check_door_clearance, check_obb_collision, get_rotated_corners, is_within_room,
)

GAP = 0.05
WALL = 0.0501  # Numerical slack beyond the environment's 5 cm wall margin.


def corners(item):
    return get_rotated_corners(item["x"], item["y"], item["width"], item["depth"], item.get("rotation", 0))


def validate_geometry(furniture, width, length):
    """Return exact SAT pairs and out-of-room IDs (do not use rounded metrics)."""
    boxes = []
    outside = []
    for item in furniture:
        if not all(math.isfinite(float(item[key])) for key in ("x", "y", "width", "depth", "rotation")):
            raise ValueError("Furniture geometry must contain finite numbers.")
        if item["width"] <= 0 or item["depth"] <= 0:
            raise ValueError("Furniture width and depth must be positive.")
        boxes.append(corners(item))
        if not is_within_room(item["x"], item["y"], item["width"], item["depth"], item["rotation"], width, length)[0]:
            outside.append(item["id"])
    pairs = [[furniture[i]["id"], furniture[j]["id"]]
             for i in range(len(boxes)) for j in range(i + 1, len(boxes))
             if check_obb_collision(boxes[i], boxes[j], margin=GAP)]
    return {"valid": not pairs and not outside, "collision_pairs": pairs, "outside_room": outside}


def _overlaps(box, other):
    # Cheap broad-phase rejection; intersecting candidates still use exact SAT.
    if np.any(box.max(axis=0) + GAP < other.min(axis=0)) or np.any(other.max(axis=0) + GAP < box.min(axis=0)):
        return False
    return check_obb_collision(box, other, margin=GAP)


def _poses(item, furniture, width, length):
    """Propose nearby centres, wall/edge anchors and a bounded room-wide grid."""
    candidates = []
    step = max(0.15, max(width, length) / 45)
    for turn in range(4):
        rotation = (item["rotation"] + 90 * turn) % 360
        local = get_rotated_corners(0, 0, item["width"], item["depth"], rotation)
        half_x, half_y = local.max(axis=0)
        low_x, high_x = half_x + WALL, width - half_x - WALL
        low_y, high_y = half_y + WALL, length - half_y - WALL
        if high_x < low_x or high_y < low_y:
            continue
        xs = {low_x, high_x, min(high_x, max(low_x, item["x"]))}
        ys = {low_y, high_y, min(high_y, max(low_y, item["y"]))}
        xs.update(np.arange(low_x, high_x, step).tolist())
        ys.update(np.arange(low_y, high_y, step).tolist())
        for other in furniture:
            if other is item:
                continue
            box = corners(other)
            minimum, maximum = box.min(axis=0), box.max(axis=0)
            xs.update(x for x in (minimum[0] - half_x - GAP - .001, maximum[0] + half_x + GAP + .001) if low_x <= x <= high_x)
            ys.update(y for y in (minimum[1] - half_y - GAP - .001, maximum[1] + half_y + GAP + .001) if low_y <= y <= high_y)
        for x in sorted(xs):
            for y in sorted(ys):
                distance = (x - item["x"]) ** 2 + (y - item["y"]) ** 2 + (0.02 if turn else 0)
                candidates.append((distance, float(x), float(y), rotation, local))
    candidates.sort(key=lambda pose: (pose[0], pose[3], pose[1], pose[2]))
    return candidates


def repair_layout(env, deadline):
    """Commit a complete valid arrangement, or leave the environment unchanged."""
    original = copy.deepcopy(env.furniture)
    report = validate_geometry(original, env.room_w, env.room_l)
    if report["valid"]:
        return True
    pools = {}

    def poses(index):
        if index not in pools:
            pools[index] = _poses(original[index], original, env.room_w, env.room_l)
        return pools[index]

    def candidate(index, pose):
        _, x, y, rotation, local = pose
        return {**original[index], "x": x, "y": y, "rotation": rotation}, local + np.array([x, y])

    def door_clear(box):
        return not check_door_clearance(box, env.door, env.room_w, env.room_l)

    # First preserve the existing composition: relocate only affected items.
    working = copy.deepcopy(original)
    local_deadline = time.monotonic() + max(0, deadline - time.monotonic()) * .4
    for _ in range(len(working) * 2):
        report = validate_geometry(working, env.room_w, env.room_l)
        if report["valid"]:
            env.furniture = working
            return True
        affected = set(report["outside_room"])
        affected.update(item_id for pair in report["collision_pairs"] for item_id in pair)
        indices = sorted((i for i, item in enumerate(working) if item["id"] in affected),
                         key=lambda i: working[i]["width"] * working[i]["depth"])
        moved = False
        for index in indices:
            if time.monotonic() >= local_deadline:
                break
            other_boxes = [corners(item) for i, item in enumerate(working) if i != index]
            for pose in poses(index):
                if time.monotonic() >= local_deadline:
                    break
                item, box = candidate(index, pose)
                if door_clear(box) and not any(_overlaps(box, other) for other in other_boxes):
                    working[index] = item
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break

    # A local move may be impossible until another item moves. Repack all items
    # with backtracking, largest first; retain their original list order/IDs.
    order = sorted(range(len(original)), key=lambda i: -original[i]["width"] * original[i]["depth"])
    placed = {}
    nodes = 0

    def search(depth):
        nonlocal nodes
        if time.monotonic() >= deadline or nodes >= 30000:
            return False
        if depth == len(order):
            return True
        index = order[depth]
        for pose in poses(index):
            nodes += 1
            if nodes >= 30000 or time.monotonic() >= deadline:
                return False
            item, box = candidate(index, pose)
            if not door_clear(box) or any(_overlaps(box, other[1]) for other in placed.values()):
                continue
            placed[index] = (item, box)
            if search(depth + 1):
                return True
            del placed[index]
        return False

    if search(0):
        result = [placed[i][0] for i in range(len(original))]
        if validate_geometry(result, env.room_w, env.room_l)["valid"]:
            env.furniture = result
            return True
    return False
