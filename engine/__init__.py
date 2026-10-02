"""
SmartSpace AI — Optimization Engine Package
=============================================
Aggregates all spatial, planning, and reinforcement-learning modules that
power the layout optimization pipeline.

Modules
~~~~~~~
- ``sat_collision``   — Separating Axis Theorem (SAT) for OBB collision detection
- ``astar_planner``   — 15 cm grid A* walking-path search
- ``interior_env``    — 133-D Markov Decision Process (MDP) layout environment
- ``dqn_agent``       — Deep Q-Network model and trajectory search
- ``recommender``     — Dual-engine recommendation bundles (ML + rule-based)
- ``design_advisor``  — Rule-based room styling and finishing advice
- ``seed_data``       — Furniture catalog and preset seeder
- ``train_dqn``       — CLI training script for the DQN checkpoint

Legacy compatibility
~~~~~~~~~~~~~~~~~~~~
``engine.spatial_utils`` is a thin shim that re-exports everything from
``engine.sat_collision``, so older import paths still resolve.
"""
from engine.sat_collision import (
    get_rotated_corners, check_obb_collision, is_within_room,
    check_door_clearance, check_window_overlap
)
from engine.astar_planner import AStarPlanner
from engine.interior_env import InteriorEnv
from engine.dqn_agent import DQNAgent

__all__ = [
    "get_rotated_corners",
    "check_obb_collision",
    "is_within_room",
    "check_door_clearance",
    "check_window_overlap",
    "AStarPlanner",
    "InteriorEnv",
    "DQNAgent",
]
