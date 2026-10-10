"""Usability checks and bounded joint placement search, without resizing items.

This is a heuristic search, not a proof of a globally optimal room arrangement.
The same report drives search, reward, API validation and user feedback.
"""
import copy
import math
import time

import numpy as np

from config import ERGONOMIC_RULES
from engine.furniture_orientation import get_forward_vector
from engine.layout_repair import corners, validate_geometry, _overlaps, WALL
from engine.sat_collision import check_obb_collision, check_door_clearance, get_rotated_corners


def _dot_to(item, target):
    dx, dy = target["x"] - item["x"], target["y"] - item["y"]
    distance = math.hypot(dx, dy)
    fx, fy = get_forward_vector(item["type"], item["rotation"])
    return (fx * dx + fy * dy) / max(distance, 1e-9), distance


def _zone(item, depth, side=0):
    fx, fy = get_forward_vector(item["type"], item["rotation"])
    if side:
        fx, fy = -fy * side, fx * side
    extent = item["width" if side else "depth"] / 2
    breadth = item["depth" if side else "width"]
    # Rectangle local +y is its depth axis.
    angle = math.degrees(math.atan2(fy, fx)) - 90
    return get_rotated_corners(item["x"] + fx * (extent + depth / 2 + .01),
                               item["y"] + fy * (extent + depth / 2 + .01),
                               breadth * .8, depth, angle)


def comfort_report(furniture, width, length, door):
    """Fast geometric checks. A* connectivity is added by InteriorEnv."""
    issues, checks = [], []
    penalty = 0.0
    boxes = {item["id"]: corners(item) for item in furniture}

    def issue(code, ids, message, weight):
        nonlocal penalty
        issues.append({"code": code, "item_ids": ids, "message": message})
        penalty += weight

    def zone_free(zone, own, allowed=()):
        if (zone[:, 0].min() < 0 or zone[:, 1].min() < 0 or
                zone[:, 0].max() > width or zone[:, 1].max() > length):
            return False
        return not any(check_obb_collision(zone, box) for key, box in boxes.items() if key != own and key not in allowed)

    tvs = [item for item in furniture if item["type"] == "tv"]
    desks = [item for item in furniture if item["type"] == "desk"]
    tables = [item for item in furniture if item["type"] == "table"]
    for item in furniture:
        kind, ident = item["type"], item["id"]
        if check_door_clearance(boxes[ident], door, width, length):
            issue("door_blocked", [ident], f"Move {kind} away from the entry door swing.", 60)
        if kind in ("sofa", "chair", "desk", "wardrobe", "cabinet"):
            depth = .25 if kind == "chair" else (.75 if kind == "wardrobe" else .60)
            # A correctly oriented work chair belongs in the desk's user zone;
            # it is reached from its side/back, not by walking through the desk.
            allowed = [other["id"] for other in furniture if kind == "desk" and other["type"] == "chair"
                       and _dot_to(item, other)[0] > .707 and _dot_to(other, item)[0] > .707
                       and _dot_to(item, other)[1] < 1.8]
            if not zone_free(_zone(item, depth), ident, allowed):
                issue("front_access", [ident], f"Leave {depth:.2f} m of usable space in front of the {kind}.", 35)
        if kind == "bed":
            if not any(zone_free(_zone(item, .75, side), ident) for side in (-1, 1)):
                issue("bed_access", [ident], "Leave a 0.75 m approach along at least one side of the bed.", 40)
            fx, fy = get_forward_vector(kind, item["rotation"])
            hx, hy = item["x"] - fx * item["depth"] / 2, item["y"] - fy * item["depth"] / 2
            # Check the wall behind the headboard, not whichever side wall is nearest.
            gaps = []
            if fx > .707: gaps.append(hx)
            if fx < -.707: gaps.append(width - hx)
            if fy > .707: gaps.append(hy)
            if fy < -.707: gaps.append(length - hy)
            if not gaps or min(gaps) > .30:
                issue("headboard", [ident], "Place the bed headboard against a wall.", 20)
        targets = tvs if kind == "sofa" else ((desks or tables) if kind == "chair" else [])
        if not targets:
            if kind in ("sofa", "chair"):
                centre = {"x": width / 2, "y": length / 2}
                inward, centre_distance = _dot_to(item, centre)
                if centre_distance > .4 and inward <= 0:
                    issue("outward_seating", [ident], f"Turn the {kind} toward the room's seating space instead of the wall.", 45)
            continue
        target = min(targets, key=lambda other: math.hypot(other["x"] - item["x"], other["y"] - item["y"]))
        alignment, distance = _dot_to(item, target)
        reverse, _ = _dot_to(target, item)
        minimum = math.cos(math.radians(30 if kind == "sofa" else 45))
        mutual = target["type"] in ("tv", "desk")
        facing = alignment >= minimum and (not mutual or reverse >= minimum)
        checks.append({"item_id": ident, "target_id": target["id"], "alignment": round(alignment, 3),
                       "target_alignment": round(reverse, 3), "distance_m": round(distance, 2), "facing": facing})
        if not facing:
            issue("viewing_direction" if kind == "sofa" else "chair_direction", [ident, target["id"]],
                  "Face the sofa and TV toward each other (within 30 degrees)." if kind == "sofa"
                  else "Face the chair toward the usable side of its desk or table.", 70)
        # Continuous alignment cost encourages the centre of the cone, not its edge.
        penalty += 8 * (1 - alignment) + (8 * (1 - reverse) if mutual else 0)
        if kind == "chair":
            direction = np.array([target["x"] - item["x"], target["y"] - item["y"]]) / max(distance, 1e-9)
            edge_gap = float((boxes[target["id"]] @ direction).min() - (boxes[ident] @ direction).max())
            if not .25 <= edge_gap <= .75:
                issue("chair_distance", [ident, target["id"]], "Keep the chair within 0.25–0.75 m of its desk or table edge.", 25)
        if kind == "sofa":
            low, high = ERGONOMIC_RULES["tv_min_viewing_distance"], ERGONOMIC_RULES["tv_max_viewing_distance"]
            if not low <= distance <= high:
                issue("viewing_distance", [ident, target["id"]], f"Keep sofa–TV viewing distance between {low:g} and {high:g} m.", 25)
            dx, dy = target["x"] - item["x"], target["y"] - item["y"]
            sightline = get_rotated_corners((item["x"] + target["x"]) / 2, (item["y"] + target["y"]) / 2,
                                            max(distance, .01), .12, math.degrees(math.atan2(dy, dx)))
            if any(other["id"] not in (ident, target["id"]) and other.get("height", 1) > .60
                   and check_obb_collision(sightline, boxes[other["id"]]) for other in furniture):
                issue("sightline_blocked", [ident, target["id"]], "Keep tall furniture out of the sofa–TV sightline.", 50)
    return {"valid": not issues, "issues": issues, "checks": checks, "penalty": penalty}


def _room_poses(item, furniture, width, length):
    """Room-wide anchors, all four orientations and original alignment axes."""
    poses = []
    for rotation in sorted({0, 90, 180, 270, item["rotation"]}):
        local = get_rotated_corners(0, 0, item["width"], item["depth"], rotation)
        hx, hy = local.max(axis=0)
        lx, ux, ly, uy = hx + WALL, width - hx - WALL, hy + WALL, length - hy - WALL
        if lx > ux or ly > uy:
            continue
        xs = set(np.linspace(lx, ux, 5)) | {min(ux, max(lx, f["x"])) for f in furniture}
        ys = set(np.linspace(ly, uy, 5)) | {min(uy, max(ly, f["y"])) for f in furniture}
        for x in sorted(xs):
            for y in sorted(ys):
                placed = {**item, "x": float(x), "y": float(y), "rotation": rotation}
                poses.append((placed, local + [x, y]))
    # Interleave headings so a bounded search never spends its entire budget
    # on rotation 0 before it reaches a valid reverse-facing arrangement.
    groups = {}
    for placed, box in poses:
        groups.setdefault(placed["rotation"], []).append((placed, box))
    for group in groups.values():
        group.sort(key=lambda entry: math.hypot(entry[0]["x"] - item["x"], entry[0]["y"] - item["y"]))
    return [group[i] for i in range(max((len(group) for group in groups.values()), default=0))
            for group in groups.values() if i < len(group)]


def improve_comfort(env, deadline):
    """Search complete arrangements together so one blocked rotation cannot trap search."""
    original = copy.deepcopy(env.furniture)
    if not original or time.monotonic() >= deadline:
        return
    best = original
    best_metrics = env.evaluate_layout()

    def rank(metrics):
        report = metrics["comfort"]
        return (len(report["issues"]),
                report["penalty"] + 100 * (1 - metrics.get("circulation_ratio", 1)),
                -metrics["total_reward"])

    best_rank = rank(best_metrics)
    pools = [_room_poses(item, original, env.room_w, env.room_l) for item in original]
    # Try direct rotations/repositioning first, including 180 degrees in one
    # step. This also supplies a complete solution if beam search times out.
    local_end = time.monotonic() + max(0, deadline - time.monotonic()) * .2
    for index in sorted(range(len(original)), key=lambda i: original[i]["type"] != "sofa"):
        proposals = []
        base = copy.deepcopy(best)
        other_boxes = [corners(item) for i, item in enumerate(base) if i != index]
        item_end = time.monotonic() + max(0, local_end - time.monotonic()) / max(1, len(original))
        for item, box in pools[index]:
            if time.monotonic() >= item_end:
                break
            if any(_overlaps(box, other) for other in other_boxes):
                continue
            candidate = [item if i == index else other for i, other in enumerate(base)]
            report = comfort_report(candidate, env.room_w, env.room_l, env.door)
            proposals.append((len(report["issues"]), report["penalty"], candidate))
        proposals.sort(key=lambda proposal: proposal[:2])
        for _, _, candidate in proposals[:3]:
            if time.monotonic() >= local_end:
                break
            env.furniture = candidate
            metrics = env.evaluate_layout()
            if rank(metrics) < best_rank:
                best, best_rank = copy.deepcopy(candidate), rank(metrics)
    orders = [sorted(range(len(original)), key=lambda i: ({"bed": 0, "sofa": 1, "tv": 2}.get(original[i]["type"], 3),
                                                         -original[i]["width"] * original[i]["depth"])),
              sorted(range(len(original)), key=lambda i: ({"sofa": 0, "tv": 1, "bed": 2}.get(original[i]["type"], 3),
                                                         -original[i]["width"] * original[i]["depth"]))]
    # Each ordering gets its own budget; reserve the last part for actual A* checks.
    start = time.monotonic()
    for order_number, order in enumerate(orders):
        order_end = start + (deadline - start) * ((order_number + 1) / len(orders))
        search_end = time.monotonic() + max(0, order_end - time.monotonic()) * .8
        beam = [({}, {}, 0.0)]
        for depth, index in enumerate(order):
            depth_end = time.monotonic() + max(0, search_end - time.monotonic()) / (len(order) - depth)
            expanded = []
            for beam_index, (placed, boxes, _) in enumerate(beam):
                branch_end = time.monotonic() + max(0, depth_end - time.monotonic()) / (len(beam) - beam_index)
                for item, box in pools[index]:
                    if time.monotonic() >= branch_end:
                        break
                    if check_door_clearance(box, env.door, env.room_w, env.room_l) or any(_overlaps(box, b) for b in boxes.values()):
                        continue
                    updated = {**placed, index: item}
                    report = comfort_report(list(updated.values()), env.room_w, env.room_l, env.door)
                    movement = sum(math.hypot(value["x"] - original[i]["x"], value["y"] - original[i]["y"])
                                   for i, value in updated.items())
                    expanded.append((updated, {**boxes, index: box}, report["penalty"] + movement * .05))
                if time.monotonic() >= depth_end:
                    break
            if not expanded:
                beam = []
                break
            # Keep distinct orientations/room zones; tiny position variants must
            # not crowd all alternatives out before another piece is placed.
            expanded.sort(key=lambda entry: entry[2])
            beam, seen = [], set()
            for entry in expanded:
                signature = tuple((i, value["rotation"], round(value["x"] / .6), round(value["y"] / .6))
                                  for i, value in sorted(entry[0].items()))
                if signature not in seen:
                    beam.append(entry)
                    seen.add(signature)
                if len(beam) == 12:
                    break
        for placed, _, _ in beam:
            if len(placed) != len(original) or time.monotonic() >= order_end:
                continue
            candidate = [placed[i] for i in range(len(original))]
            if not validate_geometry(candidate, env.room_w, env.room_l)["valid"]:
                continue
            env.furniture = candidate
            metrics = env.evaluate_layout()
            candidate_rank = rank(metrics)
            if candidate_rank < best_rank:
                best, best_rank = copy.deepcopy(candidate), candidate_rank
    env.furniture = best
