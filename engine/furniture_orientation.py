"""Asset-aligned world headings and usable approach sides (metres)."""
import math

FORWARD_AXIS_OFFSETS_DEG = {
    "sofa": 270.0, "tv": 90.0, "chair": 270.0, "desk": 270.0,
    "bed": 270.0, "wardrobe": 270.0, "cabinet": 270.0,
}


def get_forward_vector(item_type, rotation_deg):
    # SVG y points down; world y points north. Canvas rotates by -rotation.
    theta = math.radians(float(rotation_deg) + FORWARD_AXIS_OFFSETS_DEG.get(item_type, 90.0))
    return math.cos(theta), math.sin(theta)


def approach_points(item, furniture=(), clearance=0.525):
    """Targets outside the footprint, on a usable side, never its centre."""
    forward = get_forward_vector(item["type"], item["rotation"])
    side = (-forward[1], forward[0])
    sides = [(forward, item["depth"] / 2)]
    if item["type"] == "desk":
        chairs = [other for other in furniture if other["type"] == "chair"
                  and math.hypot(item["x"] - other["x"], item["y"] - other["y"]) < 1.8]
        if chairs:
            chair = min(chairs, key=lambda other: math.hypot(item["x"] - other["x"], item["y"] - other["y"]))
            return approach_points(chair, clearance=clearance)
    if item["type"] in ("bed", "chair"):
        sides = [(side, item["width"] / 2), ((-side[0], -side[1]), item["width"] / 2)]
        if item["type"] == "chair":
            sides.append(((-forward[0], -forward[1]), item["depth"] / 2))
    elif item["type"] == "table":
        sides += [((-forward[0], -forward[1]), item["depth"] / 2),
                  (side, item["width"] / 2), ((-side[0], -side[1]), item["width"] / 2)]
    return [(item["x"] + dx * (extent + clearance), item["y"] + dy * (extent + clearance))
            for (dx, dy), extent in sides]
