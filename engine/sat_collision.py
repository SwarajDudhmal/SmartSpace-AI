"""
SmartSpace AI — Separating Axis Theorem (SAT) Collision Detection
==================================================================
Implements all low-level 2D spatial mathematics required by the layout
optimisation pipeline.  Every function here operates on **Oriented Bounding
Boxes (OBBs)** — axis-aligned rectangles that have been rotated by an
arbitrary angle — because furniture can face any direction.

Core algorithms
~~~~~~~~~~~~~~~
1. **OBB corner computation** — ``get_rotated_corners()`` maps a
   (centre, width, depth, angle) tuple to four world-space vertices.
2. **Separating Axis Theorem (SAT)** — ``check_obb_collision()`` tests
   whether two convex polygons (our OBBs) overlap by projecting them onto
   every candidate separating axis.  If a gap is found on *any* axis the
   shapes are separated; otherwise they collide.
3. **Boundary containment** — ``is_within_room()`` checks that an OBB
   lies fully inside the ``[0, W] × [0, L]`` room rectangle.
4. **Interaction / clearance zones** — ``get_front_interaction_zone()``
   computes the OBB of the ergonomic area in front of a furniture piece
   (e.g. the pull-out zone in front of a wardrobe or desk chair).
5. **Wall / aperture clearance** — ``check_door_clearance()`` and
   ``check_window_overlap()`` test whether furniture intrudes into the
   swing arc of a door or blocks natural daylight.

How this module connects
~~~~~~~~~~~~~~~~~~~~~~~~
* ``engine/interior_env.py`` calls every function here when computing the
  multi-objective MDP reward (collision penalty, boundary penalty, clearance
  bonuses, etc.).
* ``engine/astar_planner.py`` uses ``get_rotated_corners`` to stamp
  furniture footprints into its 15 cm occupancy grid.
* ``engine/recommender.py`` invokes ``check_obb_collision`` and
  ``is_within_room`` to nudge recommended pieces away from overlaps.

Note
~~~~
``engine/spatial_utils.py`` still exists as a **thin compatibility shim**
that re-imports everything from this file, so legacy ``from
engine.spatial_utils import …`` statements continue to work during the
migration period.
"""
import math
from typing import List, Tuple, Dict, Any
import numpy as np

def get_rotated_corners(cx: float, cy: float, w: float, d: float, angle_deg: float) -> np.ndarray:
    """Return a (4, 2) array of world-space rectangle vertices.

    Args:
        cx, cy: Rectangle centre in metres.
        w, d: Width and depth along the unrotated local axes, in metres.
        angle_deg: Counter-clockwise rotation in degrees.

    Returns:
        Vertices in local bottom-left, bottom-right, top-right, top-left order.
    """
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    
    hw = w / 2.0
    hd = d / 2.0
    
    # Local unrotated offsets
    local_corners = np.array([
        [-hw, -hd],
        [ hw, -hd],
        [ hw,  hd],
        [-hw,  hd]
    ])
    
    # **Rotation:** x' = x*cos(theta) - y*sin(theta),
    # y' = x*sin(theta) + y*cos(theta); distances and angles are preserved.
    rotation_matrix = np.array([
        [cos_a, -sin_a],
        [sin_a,  cos_a]
    ])
    
    # **Row-vector convention:** transpose R because each vertex is a row.
    rotated_bounding_box = local_corners @ rotation_matrix.T
    # **Translation:** move the rotated local offsets to the room centre point.
    world_corners = rotated_bounding_box + np.array([cx, cy])
    return world_corners

def get_axes(corners: np.ndarray) -> List[np.ndarray]:
    """Return the two unit edge normals of four ordered rectangle corners.

    Opposite rectangle edges have parallel normals, so testing them again
    cannot reveal an additional separating axis. Degenerate edges are skipped.
    This function accepts rectangles, not arbitrary convex polygons.
    """
    axes = []
    for i in range(2):
        p1 = corners[i]
        p2 = corners[i + 1]
        edge = p2 - p1
        # Normal vector (-dy, dx)
        normal = np.array([-edge[1], edge[0]])
        norm = np.linalg.norm(normal)
        if norm > 1e-8:
            axes.append(normal / norm)
    return axes

def project_onto_axis(corners: np.ndarray, axis: np.ndarray) -> Tuple[float, float]:
    """Project (N, 2) vertices onto a unit axis; return its scalar interval."""
    dots = corners @ axis
    return float(np.min(dots)), float(np.max(dots))

def check_obb_collision(box_a_corners: np.ndarray, box_b_corners: np.ndarray, margin: float = 0.0) -> bool:
    """Return whether two ordered (4, 2) rectangle footprints overlap.

    ``margin`` expands projection intervals in metres. Touching counts as a
    collision. This is an axis-based clearance test, not Euclidean distance.
    """
    axes_a = get_axes(box_a_corners)
    axes_b = get_axes(box_b_corners)
    
    for axis in axes_a + axes_b:
        min_a, max_a = project_onto_axis(box_a_corners, axis)
        min_b, max_b = project_onto_axis(box_b_corners, axis)
        
        # **SAT early exit:** one gap proves separation; one overlap alone
        # cannot prove a collision. Both boxes' independent axes must overlap.
        if (max_a + margin < min_b) or (max_b + margin < min_a):
            return False
            
    return True

def is_within_room(cx: float, cy: float, w: float, d: float, angle_deg: float, 
                   room_w: float, room_l: float, wall_margin: float = 0.05) -> Tuple[bool, float]:
    """Return (inside, summed wall penetration in metres) for a rectangle.

    Inputs describe its centre, dimensions, rotation in degrees, room size in
    metres, and the required clearance ``wall_margin`` from every wall.
    """
    corners = get_rotated_corners(cx, cy, w, d, angle_deg)
    min_x, max_x = np.min(corners[:, 0]), np.max(corners[:, 0])
    min_y, max_y = np.min(corners[:, 1]), np.max(corners[:, 1])
    
    violation = 0.0
    if min_x < wall_margin:
        violation += (wall_margin - min_x)
    if max_x > room_w - wall_margin:
        violation += (max_x - (room_w - wall_margin))
    if min_y < wall_margin:
        violation += (wall_margin - min_y)
    if max_y > room_l - wall_margin:
        violation += (max_y - (room_l - wall_margin))
        
    return (violation <= 1e-4, violation)

def get_front_interaction_zone(cx: float, cy: float, w: float, d: float, angle_deg: float,
                               front_depth: float = 0.8) -> np.ndarray:
    """Return (4, 2) corners of the front clearance rectangle in metres.

    Inputs describe the item's centre, size and rotation in degrees;
    ``front_depth`` extends the zone along local +y before rotation.
    """
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    
    # **Rotated front:** R @ [0, offset] = [-sin(theta)*offset, cos(theta)*offset].
    offset_dist = (d / 2.0) + (front_depth / 2.0)
    front_cx = cx - offset_dist * sin_a
    front_cy = cy + offset_dist * cos_a
    
    return get_rotated_corners(front_cx, front_cy, w, front_depth, angle_deg)

def calculate_wall_distance(cx: float, cy: float, w: float, d: float, angle_deg: float,
                            room_w: float, room_l: float) -> Tuple[float, str]:
    """Return (nonnegative edge-to-wall distance, nearest wall name).

    Inputs are the rectangle centre, size, angle in degrees and room size in
    metres. The nearest footprint edge is used; it need not be the back edge.
    """
    corners = get_rotated_corners(cx, cy, w, d, angle_deg)
    min_x, max_x = np.min(corners[:, 0]), np.max(corners[:, 0])
    min_y, max_y = np.min(corners[:, 1]), np.max(corners[:, 1])
    
    dists = {
        "west": min_x,
        "east": room_w - max_x,
        "south": min_y,
        "north": room_l - max_y
    }
    
    closest_wall = min(dists, key=dists.get)
    return max(0.0, dists[closest_wall]), closest_wall

def check_door_clearance(furniture_corners: np.ndarray, door_info: Dict[str, Any],
                         room_w: float, room_l: float, swing_radius: float = 1.0) -> bool:
    """Return whether (4, 2) furniture corners overlap a door clearance box.

    ``door_info`` supplies wall, offset and width in metres; room dimensions
    locate that wall. ``swing_radius`` is the inward depth of a conservative
    rectangle approximation, not an exact circular swing arc.
    """
    wall = door_info.get("wall", "south")
    offset = door_info.get("offset", 0.5)
    dw = door_info.get("width", 0.9)
    
    # Calculate door clearance rectangle in world coordinates
    if wall == "south":
        door_box = np.array([
            [offset, 0.0],
            [offset + dw, 0.0],
            [offset + dw, swing_radius],
            [offset, swing_radius]
        ])
    elif wall == "north":
        door_box = np.array([
            [offset, room_l - swing_radius],
            [offset + dw, room_l - swing_radius],
            [offset + dw, room_l],
            [offset, room_l]
        ])
    elif wall == "west":
        door_box = np.array([
            [0.0, offset],
            [swing_radius, offset],
            [swing_radius, offset + dw],
            [0.0, offset + dw]
        ])
    else: # east
        door_box = np.array([
            [room_w - swing_radius, offset],
            [room_w, offset],
            [room_w, offset + dw],
            [room_w - swing_radius, offset + dw]
        ])
        
    return check_obb_collision(furniture_corners, door_box)

def check_window_overlap(furniture_corners: np.ndarray, windows: List[Dict[str, Any]],
                         room_w: float, room_l: float, clearance_depth: float = 0.5) -> bool:
    """Return True at the first window clearance box touched by furniture.

    Inputs are (4, 2) furniture corners, window wall/offset/width dictionaries,
    room size and inward daylight clearance depth, all in metres.
    """
    for win in windows:
        wall = win.get("wall", "north")
        offset = win.get("offset", 1.0)
        ww = win.get("width", 1.2)
        
        if wall == "north":
            win_box = np.array([
                [offset, room_l - clearance_depth],
                [offset + ww, room_l - clearance_depth],
                [offset + ww, room_l],
                [offset, room_l]
            ])
        elif wall == "south":
            win_box = np.array([
                [offset, 0.0],
                [offset + ww, 0.0],
                [offset + ww, clearance_depth],
                [offset, clearance_depth]
            ])
        elif wall == "west":
            win_box = np.array([
                [0.0, offset],
                [clearance_depth, offset],
                [clearance_depth, offset + ww],
                [0.0, offset + ww]
            ])
        else: # east
            win_box = np.array([
                [room_w - clearance_depth, offset],
                [room_w, offset],
                [room_w, offset + ww],
                [room_w - clearance_depth, offset + ww]
            ])
            
        if check_obb_collision(furniture_corners, win_box):
            return True
            
    return False
