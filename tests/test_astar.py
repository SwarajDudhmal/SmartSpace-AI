"""
Unit Tests for SmartSpace AI A* Pathfinding and Circulation
"""
import unittest
from engine.astar_planner import AStarPlanner

class TestAStarPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = AStarPlanner(room_width=4.0, room_length=4.0, grid_res=0.2)

    def test_open_room_path(self):
        # In an empty room, path from (0.5, 0.5) to (3.5, 3.5) must succeed
        path = self.planner.plan_path((0.5, 0.5), (3.5, 3.5))
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 0)

    def test_circulation_evaluation(self):
        furniture = [
            {"id": "bed_1", "type": "bed", "x": 2.0, "y": 2.0, "width": 1.4, "depth": 1.8, "rotation": 0}
        ]
        self.planner.build_occupancy_grid(furniture)
        eval_res = self.planner.evaluate_circulation((0.5, 0.5), furniture)
        self.assertIn("circulation_score", eval_res)
        self.assertGreaterEqual(eval_res["circulation_score"], 0.0)

if __name__ == '__main__':
    unittest.main()
