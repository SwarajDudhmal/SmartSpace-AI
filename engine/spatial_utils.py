"""
SmartSpace AI — Spatial Utilities (Compatibility Shim)
======================================================
This module is a **backward-compatible re-export** layer.  All geometric and
collision logic has been moved to ``engine.sat_collision`` as part of the
modular refactoring.  Existing imports from ``engine.spatial_utils`` continue
to resolve correctly.

Canonical home:  ``engine/sat_collision.py``
"""
from engine.sat_collision import (  # noqa: F401 – re-exported public API
    get_rotated_corners,
    get_axes,
    project_onto_axis,
    check_obb_collision,
    is_within_room,
    get_front_interaction_zone,
    calculate_wall_distance,
    check_door_clearance,
    check_window_overlap,
)
