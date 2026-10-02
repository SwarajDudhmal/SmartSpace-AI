"""
Unit Tests for SmartSpace AI Spatial Utilities & Collision Detection
"""
import unittest
import numpy as np

from engine.spatial_utils import (
    get_rotated_corners,
    check_obb_collision,
    is_within_room,
    calculate_wall_distance
)

class TestSpatialUtils(unittest.TestCase):
    def test_rotated_corners(self):
        corners = get_rotated_corners(2.0, 2.0, 1.0, 2.0, 0)
        self.assertEqual(corners.shape, (4, 2))
        # Center should be (2, 2)
        center = np.mean(corners, axis=0)
        self.assertAlmostEqual(center[0], 2.0)
        self.assertAlmostEqual(center[1], 2.0)

    def test_obb_collision_true(self):
        # Two overlapping boxes
        box_a = get_rotated_corners(2.0, 2.0, 1.0, 1.0, 0)
        box_b = get_rotated_corners(2.2, 2.2, 1.0, 1.0, 0)
        self.assertTrue(check_obb_collision(box_a, box_b))

    def test_obb_collision_false(self):
        # Two separated boxes
        box_a = get_rotated_corners(1.0, 1.0, 1.0, 1.0, 0)
        box_b = get_rotated_corners(3.5, 3.5, 1.0, 1.0, 0)
        self.assertFalse(check_obb_collision(box_a, box_b))

    def test_within_room(self):
        # Center inside 5x5 room
        inside, viol = is_within_room(2.5, 2.5, 1.0, 1.0, 0, 5.0, 5.0)
        self.assertTrue(inside)
        self.assertEqual(viol, 0.0)

        # Protruding outside
        inside_out, viol_out = is_within_room(4.8, 2.5, 1.0, 1.0, 0, 5.0, 5.0)
        self.assertFalse(inside_out)
        self.assertGreater(viol_out, 0.0)

if __name__ == '__main__':
    unittest.main()
