"""
SmartSpace AI — Interior Layout MDP Environment
=================================================
Formulates furniture layout optimisation as a **Markov Decision Process**
directly referencing the project's research-paper specifications.

133-D State Vector
~~~~~~~~~~~~~~~~~~
The state encodes the full room configuration as a flat ``float32[133]``
vector:

- **Dims [0–2]:**   Room width, length, height (metres)
- **Dims [3–12]:**  Per-item slot occupied flags (10 slots × 1 flag)
- **Dims [13–132]:** For each of the 10 furniture slots — normalised
  (x, y, width, depth, rotation, class one-hot[10], cost)  →  12 dims/slot

Action Space (48 discrete actions)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Each action encodes *(item_index, Δx, Δy, Δrotation)* combinations across
the 10 slots, giving 48 unique transforms per step.

Multi-Objective Reward
~~~~~~~~~~~~~~~~~~~~~~
The reward ``r(s, a)`` sums:

- **Collision penalty** — ``−15 × collision_count`` (SAT overlap)
- **Boundary penalty** — ``−20 × boundary_violation_distance``
- **Door swing penalty** — per blocked door
- **Window daylight penalty** — per blocked window
- **A* circulation bonus** — ``+10 × (reachable_ratio − 0.5)``
- **Ergonomic bonuses** — bed-to-wall adherence, sofa↔TV viewing range,
  desk natural-light proximity, wardrobe wall backing
- **Budget adherence** — mild penalty when total cost exceeds budget

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Instantiated by ``routes/projects.py`` (room setup), ``routes/recommendations.py``
(layout evaluation), and ``engine/recommender.py`` (bundle building).
``engine/dqn_agent.py`` calls ``step()`` and ``get_state()`` during rollouts.
"""
import copy
import math
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from config import TARGET_CLASSES, CLASS_TO_IDX, FURNITURE_SPECS, ERGONOMIC_RULES
from engine.spatial_utils import (
    get_rotated_corners,
    check_obb_collision,
    is_within_room,
    get_front_interaction_zone,
    calculate_wall_distance,
    check_door_clearance,
    check_window_overlap
)
from engine.astar_planner import AStarPlanner


# Furniture artwork is drawn in screen coordinates (positive y points down),
# while the room model uses world coordinates (positive y points north/up).
# These headings describe the visible forward side of each bundled SVG at 0°.
# The resulting world vector is [cos(theta), sin(theta)], with theta equal to
# item rotation plus its intrinsic asset heading.
FORWARD_AXIS_OFFSETS_DEG = {
    "sofa": 270.0,   # Upholstered seat/front is the lower edge of sofa.svg.
    "tv": 90.0,      # Screen faces into the room from a south-wall placement.
    "chair": 270.0,  # Chair seat/front is the lower edge of chair.svg.
    "desk": 270.0,   # User-facing edge points outward from the desk toward the chair.
    "bed": 270.0,    # Foot points down the bed; the headboard is the opposite vector.
}


def get_forward_vector(item_type: str, rotation_deg: float) -> Tuple[float, float]:
    """Return a unit forward vector in room-world coordinates for an item.

    ``rotation_deg`` uses the same positive counter-clockwise convention as
    SAT corners and the Canvas renderer. The class offset aligns that angle
    with the visible front/foot/seat side of its default 0° top-down asset.
    """
    theta = math.radians(float(rotation_deg) + FORWARD_AXIS_OFFSETS_DEG.get(item_type, 90.0))
    return (math.cos(theta), math.sin(theta))


def _unit_direction(source: Dict[str, Any], target: Dict[str, Any]) -> Tuple[float, float]:
    """Return the unit vector between x/y item centres, or zero if coincident."""
    dx = float(target["x"]) - float(source["x"])
    dy = float(target["y"]) - float(source["y"])
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _dot(left: Tuple[float, float], right: Tuple[float, float]) -> float:
    """Return the scalar dot product of two 2-D vectors (alignment if unit)."""
    return left[0] * right[0] + left[1] * right[1]

class InteriorEnv:
    """Expose room dictionaries as a 133-value state and 48-action MDP.

    Actions translate, rotate or align furniture; rewards combine spatial
    feasibility, circulation, orientation and budget terms.
    """
    def __init__(self, room_config: Optional[Dict[str, Any]] = None):
        """Initialize metric room geometry, furniture and fixed encoder sizes."""
        self.room_config = room_config or {}
        dims = self.room_config.get("dimensions", {})
        self.room_w = float(dims.get("width", self.room_config.get("room_width", 4.8)))
        self.room_l = float(dims.get("length", self.room_config.get("room_length", 4.0)))
        self.budget = float(self.room_config.get("budget", 40000.0))
        if not all(math.isfinite(value) and 0 < value <= 30 for value in (self.room_w, self.room_l)):
            raise ValueError("Room dimensions must be positive finite values up to 30 metres.")
        if not math.isfinite(self.budget) or self.budget < 0:
            raise ValueError("Budget must be a finite nonnegative number.")
        self.door = self.room_config.get("door", {"wall": "south", "offset": 0.8, "width": 0.9})
        self.windows = self.room_config.get("windows", [{"wall": "north", "offset": 1.5, "width": 1.5}])
        
        # Door world-space entry coordinates
        self.door_pos = self._compute_door_entry_coords()
        
        # Max number of furniture items handled in state vector
        self.max_items = 8
        self.furniture: List[Dict[str, Any]] = []
        self.planner = AStarPlanner(self.room_w, self.room_l, grid_res=0.15)
        
        # Action space definition:
        # For each furniture item:
        # 0: Shift +X (+0.25m)
        # 1: Shift -X (-0.25m)
        # 2: Shift +Y (+0.25m)
        # 3: Shift -Y (-0.25m)
        # 4: Rotate +90 deg
        # 5: Snap to closest wall
        self.actions_per_item = 6
        self.action_dim = self.max_items * self.actions_per_item
        
        # State vector: [room_w, room_l, budget_ratio, door_x, door_y,
        #                for each item: [norm_x, norm_y, norm_w, norm_d, norm_rot, class_onehot(10), placed]]
        # Dimension = 5 + max_items * (5 + 10 + 1) = 5 + 8 * 16 = 133
        self.item_feature_dim = 16
        self.state_dim = 5 + self.max_items * self.item_feature_dim
        
        self.step_count = 0
        self.max_steps = 50
        self.current_reward = 0.0
        
        items = self.room_config.get("furniture") or self.room_config.get("initial_furniture")
        if items:
            self.load_furniture(items)
            
    def _compute_door_entry_coords(self) -> Tuple[float, float]:
        """Return the door-centred (x, y) entry point 0.4 metres into the room."""
        wall = self.door.get("wall", "south")
        offset = self.door.get("offset", 0.8)
        dw = self.door.get("width", 0.9)
        cx = offset + dw / 2.0
        
        if wall == "south":
            return (cx, 0.4)
        elif wall == "north":
            return (cx, self.room_l - 0.4)
        elif wall == "west":
            return (0.4, offset + dw / 2.0)
        else: # east
            return (self.room_w - 0.4, offset + dw / 2.0)

    def load_furniture(self, furniture_list: List[Dict[str, Any]]):
        """Copy at most eight item dictionaries, filling missing catalogue sizes."""
        self.furniture = []
        for i, item in enumerate(furniture_list[:self.max_items]):
            f_type = item.get("type", "chair").lower()
            specs = FURNITURE_SPECS.get(f_type, FURNITURE_SPECS["chair"])
            
            f_item = {
                "id": item.get("id", f"{f_type}_{i+1}"),
                "type": f_type,
                "x": float(item.get("x", self.room_w / 2.0)),
                "y": float(item.get("y", self.room_l / 2.0)),
                "width": float(item.get("width", specs["width"])),
                "depth": float(item.get("depth", specs["depth"])),
                "height": float(item.get("height", specs["height"])),
                "rotation": int(item.get("rotation", 0)) % 360,
                "cost": float(item.get("cost", specs["base_cost"])),
                "preferred_wall": specs.get("preferred_wall", False)
            }
            self.furniture.append(f_item)

    def reset(self) -> np.ndarray:
        """Reset actions and configured furniture; return a float32 state vector."""
        self.step_count = 0
        items = self.room_config.get("furniture") or self.room_config.get("initial_furniture")
        if items:
            self.load_furniture(items)
        return self.get_state()

    def get_state(self) -> np.ndarray:
        """Return the current room as a (133,) float32 DQN input vector.

        No arguments are required. Five room features precede eight 16-value
        object slots: five geometry values, ten one-hot classes and one presence
        flag. Empty slots remain zero. Scaling matches existing checkpoints;
        values such as the budget feature are not necessarily bounded to [0, 1].
        """
        state = np.zeros(self.state_dim, dtype=np.float32)
        
        # **State concatenation:** s = [room(5), item_0(16), ..., item_7(16)].
        # Slices implement concatenation in a preallocated array: 5 + 8*16 = 133.
        # **Room scaling:** metres / 10; rupees / 10000; door / room extent.
        state[0] = self.room_w / 10.0
        state[1] = self.room_l / 10.0
        state[2] = self.budget / 10000.0
        state[3] = self.door_pos[0] / max(1.0, self.room_w)
        state[4] = self.door_pos[1] / max(1.0, self.room_l)
        
        offset = 5
        for i in range(self.max_items):
            if i < len(self.furniture):
                item = self.furniture[i]
                c_idx = CLASS_TO_IDX.get(item["type"], 2)
                
                # **Geometry block:** relative x/y, width/depth scaled by 3 m,
                # and counter-clockwise angle represented as a fraction of 360°.
                state[offset + 0] = item["x"] / max(1.0, self.room_w)
                state[offset + 1] = item["y"] / max(1.0, self.room_l)
                state[offset + 2] = item["width"] / 3.0
                state[offset + 3] = item["depth"] / 3.0
                state[offset + 4] = (item["rotation"] % 360) / 360.0
                
                # **Class block:** exactly one of ten slots is 1 for this class.
                state[offset + 5 + c_idx] = 1.0
                # **Presence flag:** distinguish a placed item from a zero-padded slot.
                state[offset + 15] = 1.0
            offset += self.item_feature_dim
            
        return state

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Executes one discrete action chosen by the DQN agent.
        Returns: (next_state, reward, done, info)
        """
        self.step_count += 1
        num_items = len(self.furniture)
        
        if num_items == 0:
            return self.get_state(), 0.0, True, {"msg": "No furniture to place"}
            
        item_idx = (action // self.actions_per_item) % num_items
        act_type = action % self.actions_per_item
        
        target = self.furniture[item_idx]
        original_item = target.copy()
        delta_dist = 0.25 # 25cm movements
        
        # Apply action
        if act_type == 0:   # +X
            target["x"] = min(self.room_w - target["width"]/2, target["x"] + delta_dist)
        elif act_type == 1: # -X
            target["x"] = max(target["width"]/2, target["x"] - delta_dist)
        elif act_type == 2: # +Y
            target["y"] = min(self.room_l - target["depth"]/2, target["y"] + delta_dist)
        elif act_type == 3: # -Y
            target["y"] = max(target["depth"]/2, target["y"] - delta_dist)
        elif act_type == 4: # Rotate +90 deg
            target["rotation"] = (target["rotation"] + 90) % 360
        elif act_type == 5: # Snap to closest wall
            dist, wall = calculate_wall_distance(
                target["x"], target["y"], target["width"], target["depth"],
                target["rotation"], self.room_w, self.room_l
            )
            hw = target["width"] / 2.0
            hd = target["depth"] / 2.0
            if wall == "south":
                target["y"] = hd + 0.05
            elif wall == "north":
                target["y"] = self.room_l - hd - 0.05
            elif wall == "west":
                target["x"] = hw + 0.05
            elif wall == "east":
                target["x"] = self.room_w - hw - 0.05
                
        # **Oriented containment:** a 90-degree turn swaps the effective width
        # and depth. Clamp the rotated corners, not the unrotated item size.
        rotated_bounding_box = get_rotated_corners(
            target["x"], target["y"], target["width"], target["depth"], target["rotation"]
        )
        minimum_corner = rotated_bounding_box.min(axis=0)
        maximum_corner = rotated_bounding_box.max(axis=0)
        rotated_size = maximum_corner - minimum_corner
        wall_margin = 0.05
        if rotated_size[0] > self.room_w - 2 * wall_margin or rotated_size[1] > self.room_l - 2 * wall_margin:
            # This orientation cannot fit at any centre; leave the item unchanged.
            target.update(original_item)
        else:
            correction_x = max(0.0, wall_margin - minimum_corner[0])
            correction_x += min(0.0, self.room_w - wall_margin - maximum_corner[0])
            correction_y = max(0.0, wall_margin - minimum_corner[1])
            correction_y += min(0.0, self.room_l - wall_margin - maximum_corner[1])
            target["x"] += float(correction_x)
            target["y"] += float(correction_y)

        # Evaluate layout reward
        eval_metrics = self.evaluate_layout()
        reward = eval_metrics["total_reward"]
        
        done = self.step_count >= self.max_steps
        info = {
            "step": self.step_count,
            "metrics": eval_metrics,
            "modified_item": target["id"],
            "action_type": act_type
        }
        
        return self.get_state(), reward, done, info

    def evaluate_layout(self) -> Dict[str, Any]:
        """
        Computes the research paper's multi-objective reward formulation:
        - Collision Penalty (Inter-furniture SAT collisions)
        - Boundary Containment Penalty
        - Door Swing Interference Penalty
        - Window Daylight Clearance Penalty
        - Wall Alignment Reward (Bed, Wardrobe, Desk against walls)
        - TV-to-Sofa viewing distance and directional sightline rewards
        - Bed headboard-to-nearest-wall and chair-to-desk orientation checks
        - A* Circulation Path Reachability Reward
        - Budget Adherence
        """
        num_items = len(self.furniture)
        if num_items == 0:
            return {"total_reward": 0.0, "ergonomics_score": 100}
            
        collision_count = 0
        boundary_violations = 0.0
        door_interferences = 0
        window_blockages = 0
        wall_alignment_score = 0.0
        ergonomic_bonuses = 0.0
        directional_bonuses = 0.0
        orientation_penalties = 0
        orientation_checks: List[Dict[str, Any]] = []
        
        corners_list = []
        for item in self.furniture:
            corners = get_rotated_corners(
                item["x"], item["y"], item["width"], item["depth"], item["rotation"]
            )
            corners_list.append(corners)
            
            # 1. Boundary check
            inside, dist_out = is_within_room(
                item["x"], item["y"], item["width"], item["depth"], item["rotation"],
                self.room_w, self.room_l
            )
            if not inside:
                boundary_violations += dist_out
                
            # 2. Door swing interference
            if check_door_clearance(corners, self.door, self.room_w, self.room_l):
                door_interferences += 1
                
            # 3. Window daylight blockage (for tall items: wardrobe, high cabinet)
            if item["type"] in ["wardrobe", "cabinet"] and check_window_overlap(corners, self.windows, self.room_w, self.room_l):
                window_blockages += 1
                
            # 4. Wall alignment for items that prefer backing a wall
            if item.get("preferred_wall", False):
                min_dist, _ = calculate_wall_distance(
                    item["x"], item["y"], item["width"], item["depth"],
                    item["rotation"], self.room_w, self.room_l
                )
                if min_dist < 0.20:
                    wall_alignment_score += 1.0
                else:
                    wall_alignment_score -= (min_dist * 0.5)

        # 5. Pairwise inter-furniture collision check via SAT
        for i in range(num_items):
            for j in range(i + 1, num_items):
                if check_obb_collision(corners_list[i], corners_list[j], margin=0.05):
                    collision_count += 1

        # 6. Directional ergonomics (headboards, sightlines and seating sides).
        sofa_items = [it for it in self.furniture if it["type"] == "sofa"]
        tv_items = [it for it in self.furniture if it["type"] == "tv"]
        for s in sofa_items:
            for t in tv_items:
                dist = math.hypot(s["x"] - t["x"], s["y"] - t["y"])
                if ERGONOMIC_RULES["tv_min_viewing_distance"] <= dist <= ERGONOMIC_RULES["tv_max_viewing_distance"]:
                    ergonomic_bonuses += 2.0
                else:
                    ergonomic_bonuses -= 1.0

                sofa_alignment = _dot(
                    get_forward_vector("sofa", s["rotation"]), _unit_direction(s, t)
                )
                tv_alignment = _dot(
                    get_forward_vector("tv", t["rotation"]), _unit_direction(t, s)
                )
                if sofa_alignment > 0.707:
                    directional_bonuses += 1.0
                elif sofa_alignment <= 0.0:
                    orientation_penalties += 1
                if tv_alignment > 0.707:
                    directional_bonuses += 1.0
                elif tv_alignment <= 0.0:
                    orientation_penalties += 1
                orientation_checks.append({
                    "kind": "sofa_tv_sightline",
                    "sofa_id": s["id"], "tv_id": t["id"],
                    "sofa_alignment": round(float(sofa_alignment), 3),
                    "tv_alignment": round(float(tv_alignment), 3),
                    "distance_m": round(float(dist), 3),
                    "sofa_in_forward_cone": sofa_alignment > 0.707,
                    "tv_faces_sofa": tv_alignment > 0.707,
                })

        # Bed forward points toward the foot. Its headboard points in the
        # opposite direction and should face the nearest room boundary.
        wall_vectors = {
            "west": (-1.0, 0.0), "east": (1.0, 0.0),
            "south": (0.0, -1.0), "north": (0.0, 1.0),
        }
        for bed in (it for it in self.furniture if it["type"] == "bed"):
            _, closest_wall = calculate_wall_distance(
                bed["x"], bed["y"], bed["width"], bed["depth"], bed["rotation"],
                self.room_w, self.room_l,
            )
            foot_vector = get_forward_vector("bed", bed["rotation"])
            headboard_vector = (-foot_vector[0], -foot_vector[1])
            wall_alignment = _dot(headboard_vector, wall_vectors[closest_wall])
            if wall_alignment > 0.707:
                directional_bonuses += 1.0
            elif wall_alignment <= 0.0:
                orientation_penalties += 1
            orientation_checks.append({
                "kind": "bed_headboard_wall",
                "item_id": bed["id"], "closest_wall": closest_wall,
                "alignment": round(float(wall_alignment), 3),
                "headboard_faces_wall": wall_alignment > 0.707,
            })

        # Check each chair against its nearest desk (or, when no desk exists,
        # the nearest table). The chair looks toward the work/eating surface;
        # the desk's outward-facing user side points back toward that chair.
        chairs = [it for it in self.furniture if it["type"] == "chair"]
        desks = [it for it in self.furniture if it["type"] == "desk"]
        interaction_surfaces = desks or [it for it in self.furniture if it["type"] == "table"]
        for chair in chairs:
            if not interaction_surfaces:
                break
            surface = min(
                interaction_surfaces,
                key=lambda it: math.hypot(chair["x"] - it["x"], chair["y"] - it["y"]),
            )
            chair_alignment = _dot(
                get_forward_vector("chair", chair["rotation"]), _unit_direction(chair, surface)
            )
            surface_alignment = (
                _dot(get_forward_vector("desk", surface["rotation"]), _unit_direction(surface, chair))
                if surface["type"] == "desk" else None
            )
            if chair_alignment > 0.707:
                directional_bonuses += 1.0
            elif chair_alignment <= 0.0:
                orientation_penalties += 1
            if surface_alignment is not None and surface_alignment > 0.707:
                directional_bonuses += 1.0
            elif surface_alignment is not None and surface_alignment <= 0.0:
                orientation_penalties += 1
            orientation_checks.append({
                "kind": "chair_interaction_surface",
                "chair_id": chair["id"], "surface_id": surface["id"],
                "surface_type": surface["type"],
                "chair_alignment": round(float(chair_alignment), 3),
                "surface_alignment": round(float(surface_alignment), 3) if surface_alignment is not None else None,
                "chair_faces_surface": chair_alignment > 0.707,
                "surface_faces_chair": surface_alignment > 0.707 if surface_alignment is not None else None,
            })

        # 7. A* Circulation evaluation
        self.planner.build_occupancy_grid(self.furniture, inflation_margin=0.08)
        circ_eval = self.planner.evaluate_circulation(self.door_pos, self.furniture)
        circulation_ratio = circ_eval["circulation_score"]
        
        # 8. Budget evaluation
        total_cost = sum(item.get("cost", 0.0) for item in self.furniture)
        budget_penalty = max(0.0, (total_cost - self.budget) / 1000.0)
        
        # **Weighted reward:** each confirmed pair collision contributes -15.
        # Keep counting all pairs here: unlike a boolean query, reward needs totals.
        collision_penalty = -15.0 * collision_count
        r_boundary = -20.0 * boundary_violations
        r_door = -25.0 * door_interferences
        r_window = -10.0 * window_blockages
        r_wall = 2.0 * wall_alignment_score
        r_ergo = 1.5 * ergonomic_bonuses
        r_directional = 1.5 * directional_bonuses
        # A backwards/away-facing directional object gets an immediate -15.
        r_orientation = -15.0 * orientation_penalties
        r_circ = 12.0 * circulation_ratio
        r_budget = -5.0 * budget_penalty
        
        total_reward = (
            collision_penalty + r_boundary + r_door + r_window +
            r_wall + r_ergo + r_directional + r_orientation + r_circ + r_budget
        )
        
        # Overall Ergonomic & Quality Score (0 to 100%)
        # Deduct for collisions, door blocks, and unreachable items
        score = 100.0
        score -= min(50.0, collision_count * 25.0)
        score -= min(30.0, door_interferences * 30.0)
        score -= min(20.0, boundary_violations * 20.0)
        score -= min(30.0, orientation_penalties * 15.0)
        score -= (1.0 - circulation_ratio) * 20.0
        score = max(0.0, min(100.0, score + (wall_alignment_score * 3.0)))
        
        return {
            "total_reward": round(float(total_reward), 2),
            "ergonomics_score": round(float(score), 1),
            "collision_count": collision_count,
            "door_interferences": door_interferences,
            "window_blockages": window_blockages,
            "orientation_bonus_count": int(directional_bonuses),
            "orientation_penalties": orientation_penalties,
            "orientation_checks": orientation_checks,
            "boundary_violations": round(float(boundary_violations), 2),
            "circulation_ratio": round(float(circulation_ratio), 2),
            "unreachable_count": len(circ_eval["unreachable_items"]),
            "paths": circ_eval["paths"],
            "total_cost": total_cost,
            "budget": self.budget
        }

    def get_layout_dict(self, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return a copied layout with metrics for rendering or a trajectory.

        Pass ``metrics`` only when already evaluated for this exact state;
        otherwise they are recomputed using SAT and A*.
        """
        eval_metrics = metrics if metrics is not None else self.evaluate_layout()
        return {
            "room_width": self.room_w,
            "room_length": self.room_l,
            "door": self.door,
            "door_pos": self.door_pos,
            "windows": self.windows,
            "budget": self.budget,
            "furniture": copy.deepcopy(self.furniture),
            "metrics": eval_metrics
        }
