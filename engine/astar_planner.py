"""
SmartSpace AI — A* Pathfinding & Circulation Planner
=====================================================
Discretises the room floor into a **15 cm occupancy grid** and runs an A*
graph-search algorithm to find the shortest walking path from the entry door
to each furniture item's interaction zone.

Algorithm
~~~~~~~~~
1. **Grid construction** — The room ``[0, W] × [0, L]`` is divided into
   cells of ``grid_res`` metres (default 0.15 m ≈ 15 cm).
2. **Obstacle stamping** — Each furniture OBB is rasterised onto the grid
   by iterating over cells that fall inside the rotated corners returned by
   ``engine.sat_collision.get_rotated_corners``.
3. **A* search** — For every furniture piece the planner finds the lowest-
   cost path from the door cell to the nearest free cell adjacent to the
   item's bounding box, using Chebyshev (8-connected) neighbours and an
   octile heuristic.
4. **Circulation ratio** — ``reachable / total`` gives a 0–1 score used as
   a reward term by the MDP environment and a validation gate by the
   recommendation engine.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``engine/interior_env.py`` instantiates ``AStarPlanner`` inside
``evaluate_layout()`` to compute the circulation ratio and identify
unreachable items.  The A* waypoints are also serialised into the layout
JSON so the frontend studio can render the green walking path.
"""
import heapq
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from engine.spatial_utils import get_rotated_corners, check_obb_collision

class AStarPlanner:
    """Map metric furniture footprints to a grid and return walkable paths.

    Room dimensions and cell resolution are metres. The binary occupancy grid
    uses (row, column) indices; public paths use room-world (x, y) coordinates.
    """

    def __init__(self, room_width: float, room_length: float, grid_res: float = 0.15):
        """Initialize an empty grid from positive, finite metre dimensions."""
        if not all(math.isfinite(value) and value > 0 for value in (room_width, room_length, grid_res)):
            raise ValueError("Room dimensions and grid resolution must be positive finite numbers.")
        self.room_w = room_width
        self.room_l = room_length
        self.res = grid_res
        self.cols = max(2, int(math.ceil(room_width / grid_res)))
        self.rows = max(2, int(math.ceil(room_length / grid_res)))
        self.grid = np.zeros((self.rows, self.cols), dtype=np.uint8) # 0 = free, 1 = obstacle
        
    def world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """Return clamped (row, column) indices for a world point in metres."""
        c = int(np.clip(x / self.res, 0, self.cols - 1))
        r = int(np.clip(y / self.res, 0, self.rows - 1))
        return (r, c)
        
    def grid_to_world(self, r: int, c: int) -> Tuple[float, float]:
        """Return the cell-centre (x, y) in metres, clipped to room bounds."""
        x = (c + 0.5) * self.res
        y = (r + 0.5) * self.res
        return (min(x, self.room_w), min(y, self.room_l))

    def build_occupancy_grid(self, furniture_list: List[Dict[str, Any]], 
                             inflation_margin: float = 0.10) -> np.ndarray:
        """Rasterize furniture dictionaries and return the binary occupancy grid.

        Each item supplies x/y, width/depth in metres and rotation in degrees.
        ``inflation_margin`` increases the full width/depth, providing half
        that extra clearance on each side of the rectangle.
        """
        self.grid.fill(0)
        
        for item in furniture_list:
            cx = item["x"]
            cy = item["y"]
            w = item.get("width", 1.0)
            d = item.get("depth", 1.0)
            rot = item.get("rotation", 0)
            
            # Get corners of the item plus inflation
            corners = get_rotated_corners(cx, cy, w + inflation_margin, d + inflation_margin, rot)
            min_x = max(0.0, np.min(corners[:, 0]))
            max_x = min(self.room_w, np.max(corners[:, 0]))
            min_y = max(0.0, np.min(corners[:, 1]))
            max_y = min(self.room_l, np.max(corners[:, 1]))
            
            r_start, c_start = self.world_to_grid(min_x, min_y)
            r_end, c_end = self.world_to_grid(max_x, max_y)
            
            for r in range(r_start, r_end + 1):
                for c in range(c_start, c_end + 1):
                    # **Boolean early exit:** an occupied cell needs no more
                    # SAT tests against additional furniture footprints.
                    if self.grid[r, c]:
                        continue
                    wx, wy = self.grid_to_world(r, c)
                    cell_box = np.array([
                        [wx - self.res/2, wy - self.res/2],
                        [wx + self.res/2, wy - self.res/2],
                        [wx + self.res/2, wy + self.res/2],
                        [wx - self.res/2, wy + self.res/2]
                    ])
                    if check_obb_collision(corners, cell_box):
                        self.grid[r, c] = 1
                        
        return self.grid

    def plan_path(self, start_pos: Tuple[float, float], goal_pos: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
        """Return a shortest grid path between metre coordinates, or None.

        Occupied endpoints snap to a nearby free cell. Returned coordinates
        are cell centres; diagonals cannot pass between touching obstacles.
        """
        start_rc = self.world_to_grid(start_pos[0], start_pos[1])
        goal_rc = self.world_to_grid(goal_pos[0], goal_pos[1])
        
        # If start or goal is inside obstacle, look for nearest free neighbor
        if self.grid[start_rc[0], start_rc[1]] == 1:
            start_rc = self._find_nearest_free(start_rc)
        if self.grid[goal_rc[0], goal_rc[1]] == 1:
            goal_rc = self._find_nearest_free(goal_rc)
            
        if not start_rc or not goal_rc:
            return None
            
        # Priority queue for A*: (f_score, cost, r, c)
        open_set = []
        heapq.heappush(open_set, (0.0, 0.0, start_rc[0], start_rc[1]))
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score = {start_rc: 0.0}
        
        # 8-connectivity with diagonal movement cost
        diagonal_cost = math.sqrt(2.0)
        neighbors = [
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, diagonal_cost), (-1, 1, diagonal_cost),
            (1, -1, diagonal_cost), (1, 1, diagonal_cost)
        ]
        
        while open_set:
            _, current_g, r, c = heapq.heappop(open_set)
            curr = (r, c)
            
            if curr == goal_rc:
                # Reconstruct path
                path_rc = [curr]
                while curr in came_from:
                    curr = came_from[curr]
                    path_rc.append(curr)
                path_rc.reverse()
                return [self.grid_to_world(pr, pc) for pr, pc in path_rc]
                
            if current_g > g_score.get(curr, float('inf')):
                continue
                
            for dr, dc, weight in neighbors:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    if self.grid[nr, nc] == 1:
                        continue
                    # **No corner cutting:** both adjacent orthogonal cells
                    # must be free before taking a diagonal step.
                    if dr != 0 and dc != 0 and (self.grid[r, nc] or self.grid[nr, c]):
                        continue
                    tentative_g = current_g + (weight * self.res)
                    if tentative_g < g_score.get((nr, nc), float('inf')):
                        came_from[(nr, nc)] = curr
                        g_score[(nr, nc)] = tentative_g
                        # **A* heuristic:** straight-line distance cannot exceed
                        # a walkable route with axial cost 1 and diagonal sqrt(2).
                        # Multiply grid distance by resolution to match g's metres.
                        row_distance = nr - goal_rc[0]
                        column_distance = nc - goal_rc[1]
                        remaining_distance = math.hypot(row_distance, column_distance) * self.res
                        estimated_total_cost = tentative_g + remaining_distance  # f = g + h
                        heapq.heappush(open_set, (estimated_total_cost, tentative_g, nr, nc))
                        
        return None # No path found

    def _find_nearest_free(self, rc: Tuple[int, int], search_radius: int = 4) -> Optional[Tuple[int, int]]:
        """Return the nearest free (row, column) in a cell-radius square, or None."""
        r, c = rc
        best_dist = float('inf')
        best_rc = None
        for dr in range(-search_radius, search_radius + 1):
            for dc in range(-search_radius, search_radius + 1):
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    if self.grid[nr, nc] == 0:
                        dist = dr*dr + dc*dc
                        if dist < best_dist:
                            best_dist = dist
                            best_rc = (nr, nc)
        return best_rc

    def evaluate_circulation(self, door_pos: Tuple[float, float], 
                             furniture_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Measure door-to-furniture connectivity using metre coordinates.

        Furniture dictionaries provide IDs, types and x/y target positions.
        Returns:
            - circulation_score: float (0.0 to 1.0)
            - paths: Dict[item_id, list_of_coords]
            - unreachable_items: list of IDs
        """
        paths = {}
        unreachable = []
        reachable_count = 0
        total_eval = 0
        
        for item in furniture_items:
            item_type = item.get("type", "")
            if item_type in ["door", "window"]:
                continue
                
            total_eval += 1
            item_id = item.get("id", f"{item_type}_{total_eval}")
            
            # Target is the center or front interaction zone
            fx, fy = item["x"], item["y"]
            path = self.plan_path(door_pos, (fx, fy))
            
            if path is not None and len(path) > 0:
                paths[item_id] = path
                reachable_count += 1
            else:
                unreachable.append(item_id)
                
        score = (reachable_count / max(1, total_eval)) if total_eval > 0 else 1.0
        return {
            "circulation_score": score,
            "reachable_count": reachable_count,
            "total_items": total_eval,
            "unreachable_items": unreachable,
            "paths": paths
        }
