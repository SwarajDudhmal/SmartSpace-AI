"""
SmartSpace AI - Global Configuration and Domain Constants
Defines YOLO 10-class taxonomy, furniture physical dimensions, ergonomic rules,
budget approximations, and room templates.
"""
from typing import Dict, List, Any

# 10 Target Classes for YOLO Interior Detection (as specified in project requirements)
TARGET_CLASSES = [
    "bed",       # 0
    "sofa",      # 1
    "chair",     # 2
    "table",     # 3
    "wardrobe",  # 4
    "desk",      # 5
    "tv",        # 6
    "cabinet",   # 7
    "door",      # 8
    "window"     # 9
]

CLASS_TO_IDX = {name: idx for idx, name in enumerate(TARGET_CLASSES)}
IDX_TO_CLASS = {idx: name for idx, name in enumerate(TARGET_CLASSES)}

# Palette for bounding boxes and 2D/3D visualization
CLASS_COLORS = {
    "bed": "#3b82f6",       # Blue
    "sofa": "#8b5cf6",      # Purple
    "chair": "#06b6d4",     # Cyan
    "table": "#10b981",     # Emerald
    "wardrobe": "#f59e0b",  # Amber
    "desk": "#6366f1",      # Indigo
    "tv": "#ec4899",        # Pink
    "cabinet": "#f97316",   # Orange
    "door": "#ef4444",      # Red
    "window": "#14b8a6"     # Teal
}

# Standard real-world physical furniture specifications (Width x Depth x Height in meters)
# and estimated retail cost (in Indian rupees)
FURNITURE_SPECS: Dict[str, Dict[str, Any]] = {
    "bed": {
        "width": 1.6, "depth": 2.0, "height": 0.8,
        "base_cost": 12000, "clearance_front": 0.8, "clearance_sides": 0.6,
        "category": "furniture", "preferred_wall": True, "label": "Queen Bed"
    },
    "sofa": {
        "width": 2.1, "depth": 0.9, "height": 0.85,
        "base_cost": 14000, "clearance_front": 0.9, "clearance_sides": 0.3,
        "category": "furniture", "preferred_wall": False, "label": "3-Seater Sofa"
    },
    "chair": {
        "width": 0.6, "depth": 0.6, "height": 0.85,
        "base_cost": 1500, "clearance_front": 0.5, "clearance_sides": 0.2,
        "category": "furniture", "preferred_wall": False, "label": "Accent / Dining Chair"
    },
    "table": {
        "width": 1.4, "depth": 0.8, "height": 0.75,
        "base_cost": 3500, "clearance_front": 0.7, "clearance_sides": 0.7,
        "category": "furniture", "preferred_wall": False, "label": "Dining / Coffee Table"
    },
    "wardrobe": {
        "width": 1.5, "depth": 0.6, "height": 2.1,
        "base_cost": 8500, "clearance_front": 0.9, "clearance_sides": 0.2,
        "category": "furniture", "preferred_wall": True, "label": "2-Door Wardrobe"
    },
    "desk": {
        "width": 1.3, "depth": 0.65, "height": 0.75,
        "base_cost": 4200, "clearance_front": 0.8, "clearance_sides": 0.3,
        "category": "furniture", "preferred_wall": True, "label": "Study / Work Desk"
    },
    "tv": {
        "width": 1.2, "depth": 0.15, "height": 0.7,
        "base_cost": 8000, "clearance_front": 1.8, "clearance_sides": 0.2,
        "category": "electronics", "preferred_wall": True, "label": "55\" Wall / Console TV"
    },
    "cabinet": {
        "width": 1.0, "depth": 0.45, "height": 0.9,
        "base_cost": 3500, "clearance_front": 0.7, "clearance_sides": 0.2,
        "category": "furniture", "preferred_wall": True, "label": "Side Storage Cabinet"
    },
    "door": {
        "width": 0.9, "depth": 0.15, "height": 2.1,
        "base_cost": 0, "clearance_front": 1.0, "clearance_sides": 0.2,
        "category": "architectural", "preferred_wall": True, "label": "Entry Door"
    },
    "window": {
        "width": 1.4, "depth": 0.15, "height": 1.2,
        "base_cost": 0, "clearance_front": 0.6, "clearance_sides": 0.2,
        "category": "architectural", "preferred_wall": True, "label": "Window (Natural Light)"
    }
}

# Ergonomic & Architectural Layout Rules (referenced from Interior Design literature & paper)
ERGONOMIC_RULES = {
    "min_walkway_width": 0.75,         # Minimum clearance aisle between any objects (meters)
    "optimal_walkway_width": 0.90,     # Desired main circulation path width
    "door_swing_clearance": 0.95,      # Radius in front of door that must remain 100% unobstructed
    "window_light_clearance": 0.60,    # Clearance depth in front of windows to prevent daylight blockage
    "tv_min_viewing_distance": 1.50,   # Minimum distance between sofa/bed and TV
    "tv_max_viewing_distance": 3.80,   # Maximum comfortable viewing distance
    "desk_window_light_bonus": 1.5,    # Ergonomic bonus for placing desk with lateral or front natural daylight
    "bed_wall_adherence_bonus": 2.0,   # Bonus for headboard firmly placed along a wall
    "wardrobe_wall_adherence_bonus": 2.0, # Wardrobes must back against a wall
    "collision_penalty_scale": -15.0,  # Heavy negative reward for physical intersections
    "boundary_penalty_scale": -20.0,   # Heavy penalty for placing items outside room perimeter
    "connectivity_reward_scale": 10.0  # Reward when all furniture interaction zones are reachable via A*
}

# Pre-configured sample room profiles for rapid demonstration & verification
SAMPLE_ROOMS = {
    "master_bedroom": {
        "id": "master_bedroom",
        "name": "Contemporary Master Bedroom",
        "room_type": "bedroom",
        "dimensions": {"width": 4.8, "length": 4.0, "height": 2.8},
        "budget": 35000,
        "door": {"wall": "south", "offset": 0.8, "width": 0.9},
        "windows": [{"wall": "north", "offset": 1.8, "width": 1.6}],
        "initial_furniture": [
            {"id": "bed_1", "type": "bed", "x": 1.2, "y": 1.5, "rotation": 0},
            {"id": "wardrobe_1", "type": "wardrobe", "x": 3.6, "y": 0.8, "rotation": 90},
            {"id": "desk_1", "type": "desk", "x": 0.9, "y": 3.2, "rotation": 180},
            {"id": "chair_1", "type": "chair", "x": 0.9, "y": 2.5, "rotation": 0},
            {"id": "cabinet_1", "type": "cabinet", "x": 3.8, "y": 3.0, "rotation": 270}
        ]
    },
    "studio_living": {
        "id": "studio_living",
        "name": "Urban Studio Living Room",
        "room_type": "living_room",
        "dimensions": {"width": 5.4, "length": 4.5, "height": 2.8},
        "budget": 42000,
        "door": {"wall": "west", "offset": 0.6, "width": 0.9},
        "windows": [{"wall": "east", "offset": 1.5, "width": 2.0}],
        "initial_furniture": [
            {"id": "sofa_1", "type": "sofa", "x": 2.5, "y": 1.2, "rotation": 0},
            {"id": "table_1", "type": "table", "x": 2.5, "y": 2.2, "rotation": 0},
            {"id": "tv_1", "type": "tv", "x": 2.5, "y": 3.8, "rotation": 180},
            {"id": "chair_1", "type": "chair", "x": 1.2, "y": 2.0, "rotation": 90},
            {"id": "chair_2", "type": "chair", "x": 3.8, "y": 2.0, "rotation": 270},
            {"id": "cabinet_1", "type": "cabinet", "x": 4.5, "y": 1.0, "rotation": 90}
        ]
    },
    "executive_office": {
        "id": "executive_office",
        "name": "Minimalist Executive Office",
        "room_type": "office",
        "dimensions": {"width": 4.2, "length": 3.6, "height": 2.7},
        "budget": 28000,
        "door": {"wall": "south", "offset": 0.5, "width": 0.9},
        "windows": [{"wall": "west", "offset": 1.0, "width": 1.5}],
        "initial_furniture": [
            {"id": "desk_1", "type": "desk", "x": 2.1, "y": 1.8, "rotation": 0},
            {"id": "chair_1", "type": "chair", "x": 2.1, "y": 1.1, "rotation": 0},
            {"id": "cabinet_1", "type": "cabinet", "x": 3.4, "y": 0.8, "rotation": 90},
            {"id": "chair_2", "type": "chair", "x": 1.4, "y": 2.5, "rotation": 180},
            {"id": "chair_3", "type": "chair", "x": 2.8, "y": 2.5, "rotation": 180}
        ]
    }
}
