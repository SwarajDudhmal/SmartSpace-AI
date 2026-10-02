"""Curated local furniture catalog and ergonomic starter-room seed data.

This file does not redistribute 3D-FRONT/3D-FUTURE records. The built-in seed
uses this application's furniture dimensions and design rules. The CLI also
accepts a user-downloaded, rights-cleared JSON catalog for benchmark ingestion.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from config import FURNITURE_SPECS, TARGET_CLASSES
from engine.interior_env import InteriorEnv
from database.models import (
    count_rows,
    encode_json,
    initialize_database,
    insert_furniture,
    insert_preset,
    insert_transition,
    list_presets,
)


STYLE_TAGS = ["modern", "minimalist", "scandinavian", "industrial", "contemporary"]
PHOTO_BY_STYLE = {
    "modern": "/static/images/interior-modern.jpg",
    "minimalist": "/static/images/interior-minimal-bedroom.jpg",
    "scandinavian": "/static/images/interior-scandinavian.jpg",
    "industrial": "/static/images/interior-luxury.jpg",
    "contemporary": "/static/images/interior-hero.jpg",
}

def _catalog_rows() -> Iterable[Dict[str, Any]]:
    """Yield named retail-scale variants with explicit dimensions and fit zones.

    Dimensions and INR prices below are curated estimates for the demo catalog,
    not claims of vendor quotes or records copied from 3D-FRONT/3D-FUTURE.
    Each tuple is (id, name, class, W, D, H, front clearance, side clearance,
    INR cost, style, wall preference, practical description).
    """
    variants = [
        ("bed-king", "King Size Bed", "bed", 1.93, 2.03, 0.82, 0.85, 0.65, 32000, "modern", "essential", "King platform bed with upholstered headboard and two bedside approach zones."),
        ("bed-queen", "Queen Size Bed", "bed", 1.60, 2.00, 0.78, 0.80, 0.60, 22000, "minimalist", "essential", "Queen bed sized for two sleepers with a clear foot path and side access."),
        ("bed-single", "Single Bed", "bed", 1.00, 1.90, 0.68, 0.75, 0.45, 11000, "scandinavian", "essential", "Single bed for a compact bedroom, child room or guest room."),
        ("bed-bunk", "Bunk Bed", "bed", 1.00, 2.00, 1.70, 0.80, 0.55, 26500, "industrial", "essential", "Stacked twin bunks; footprint is the floor-level collision envelope."),
        ("bed-floor-minimal", "Minimalist Floor Bed", "bed", 1.60, 2.00, 0.28, 0.75, 0.55, 12500, "contemporary", "essential", "Low-profile floor bed with a thin timber platform."),

        ("sofa-modular-3", "Modular 3-Seater Sofa", "sofa", 2.10, 0.90, 0.85, 0.90, 0.30, 36000, "contemporary", "flexible", "Three-seat modular sofa with a deep seat and separate cushion modules."),
        ("sofa-loveseat-2", "2-Seater Loveseat", "sofa", 1.55, 0.85, 0.82, 0.85, 0.25, 23500, "modern", "flexible", "Compact two-seat upholstered sofa for apartments and small lounges."),
        ("sofa-l-shape", "L-Shape Sectional", "sofa", 2.60, 1.80, 0.88, 0.95, 0.35, 62000, "contemporary", "flexible", "L-shaped corner sectional; dimensions describe its enclosing floor footprint."),
        ("sofa-recliner", "Recliner Sofa", "sofa", 1.00, 0.98, 1.02, 1.20, 0.35, 42000, "industrial", "flexible", "Single powered-recliner seat; front zone reserves space for the footrest."),
        ("sofa-futon", "Futon / Sofa-bed", "sofa", 1.90, 0.92, 0.78, 1.30, 0.30, 28500, "minimalist", "flexible", "Convertible futon with added front clearance for its unfolded sleep surface."),

        ("chair-lounge", "Lounge Chair", "chair", 0.82, 0.88, 0.90, 0.65, 0.25, 12500, "contemporary", "flexible", "Low lounge chair with a broad upholstered seat and armrests."),
        ("chair-ergonomic-desk", "Ergonomic Desk Chair", "chair", 0.60, 0.60, 1.15, 0.70, 0.15, 7800, "modern", "flexible", "Adjustable task chair with a five-star base; footprint includes the base."),
        ("chair-dining", "Dining Chair", "chair", 0.45, 0.50, 0.88, 0.65, 0.12, 3200, "scandinavian", "flexible", "Armless dining chair with a compact timber frame."),
        ("chair-accent-armchair", "Accent / Armchair", "chair", 0.80, 0.82, 0.92, 0.65, 0.25, 11200, "industrial", "flexible", "Occasional armchair with side arms and a firm back."),
        ("chair-gaming", "Gaming Chair", "chair", 0.70, 0.70, 1.28, 0.80, 0.18, 14800, "modern", "flexible", "High-back gaming chair with adjustable arms and caster base."),

        ("table-central-coffee", "Central Coffee Table", "table", 1.00, 0.60, 0.43, 0.45, 0.40, 6800, "modern", "flexible", "Low central table with rounded corners and a clear sofa-side approach."),
        ("table-dining-6", "6-Seater Dining Table", "table", 1.40, 0.80, 0.76, 0.80, 0.75, 18500, "contemporary", "flexible", "Six-place rectangular dining table; apron and legs are included in the footprint."),
        ("table-side", "Side Table", "table", 0.50, 0.50, 0.55, 0.35, 0.20, 3900, "scandinavian", "flexible", "Small occasional table sized to sit beside a sofa or lounge chair."),
        ("table-entry-console", "Entryway Console Table", "table", 1.10, 0.35, 0.82, 0.65, 0.18, 9200, "industrial", "lateral", "Shallow console for an entry wall with space to pass in front."),
        ("table-extendable-dining", "Extendable Dining Table", "table", 1.60, 0.90, 0.76, 0.90, 0.80, 26800, "minimalist", "flexible", "Extendable family dining table; clearance supports chairs on each long side."),

        ("wardrobe-sliding-2", "2-Door Sliding Wardrobe", "wardrobe", 1.50, 0.60, 2.10, 0.75, 0.20, 28500, "modern", "essential", "Two-panel sliding wardrobe; front zone is for standing and drawer access."),
        ("wardrobe-almirah-3", "3-Door Almirah", "wardrobe", 1.50, 0.60, 2.10, 0.90, 0.20, 32500, "industrial", "essential", "Three-door steel or timber almirah with full-height hanging and shelf storage."),
        ("wardrobe-compact", "Compact 2-Door Wardrobe", "wardrobe", 1.00, 0.55, 2.00, 0.85, 0.18, 19800, "minimalist", "essential", "Compact full-height wardrobe for a single bedroom or guest room."),
        ("wardrobe-corner", "Corner Wardrobe Unit", "wardrobe", 1.25, 1.05, 2.15, 0.85, 0.20, 39800, "contemporary", "essential", "L-corner wardrobe footprint that makes use of two adjoining walls."),
        ("wardrobe-tall-wood", "Tall Solid-Wood Wardrobe", "wardrobe", 1.20, 0.62, 2.20, 0.95, 0.22, 46500, "scandinavian", "essential", "Full-height oak-finish wardrobe with hinged doors and a top shelf."),

        ("desk-standard-study", "Standard Study Desk", "desk", 1.30, 0.65, 0.75, 0.80, 0.30, 9200, "scandinavian", "lateral", "Study desk with a 1.3 m worktop, cable gap and room for a chair."),
        ("desk-executive", "Executive Office Desk", "desk", 1.60, 0.80, 0.76, 0.95, 0.35, 28500, "modern", "lateral", "Wide office desk with modesty panel and front task-chair clearance."),
        ("desk-l-corner", "L-Shaped Corner Desk", "desk", 1.50, 1.20, 0.75, 0.85, 0.30, 24800, "industrial", "lateral", "Corner workstation with an L-shaped enclosing footprint."),
        ("desk-standing", "Electric Standing Desk", "desk", 1.20, 0.70, 1.15, 0.85, 0.28, 22500, "contemporary", "lateral", "Height-adjustable work desk shown at standing height."),
        ("desk-writing", "Compact Writing Desk", "desk", 1.00, 0.50, 0.74, 0.72, 0.22, 7500, "minimalist", "lateral", "Slim writing table for a bedroom or small home-office nook."),

        ("tv-wall-55", "55\" Wall-Mounted TV", "tv", 1.23, 0.08, 0.71, 1.80, 0.18, 36900, "modern", "essential", "55-inch television with a low-profile wall mount and specified viewing zone."),
        ("tv-65", "65\" TV", "tv", 1.45, 0.09, 0.84, 2.10, 0.20, 58900, "contemporary", "essential", "65-inch television; depth includes the stand and cable bend allowance."),
        ("tv-wide-console", "Wide Media Console", "tv", 1.20, 0.15, 0.48, 1.80, 0.22, 14800, "scandinavian", "essential", "Shallow 1.2 m media console with a rear cable chase."),
        ("tv-low-media-unit", "Low Media Console", "tv", 1.80, 0.42, 0.52, 1.80, 0.25, 22500, "industrial", "essential", "Long low cabinet for a television, streaming devices and media storage."),
        ("tv-swivel-unit", "Swivel-Mount TV Unit", "tv", 1.23, 0.16, 0.72, 1.80, 0.25, 42800, "minimalist", "essential", "55-inch display with articulated bracket; keep its viewing arc clear."),

        ("cabinet-tall-display", "Tall Display Cabinet", "cabinet", 0.90, 0.42, 2.00, 0.65, 0.18, 21800, "contemporary", "essential", "Full-height glass-front display cabinet with a narrow wall-side footprint."),
        ("cabinet-low-sideboard", "Low Sideboard", "cabinet", 1.40, 0.45, 0.82, 0.70, 0.20, 18900, "scandinavian", "essential", "Low dining-room sideboard with drawers and concealed storage."),
        ("cabinet-bedside", "Bedside Cabinet", "cabinet", 0.45, 0.40, 0.55, 0.40, 0.15, 5600, "minimalist", "flexible", "One-drawer bedside cabinet sized to sit beside a queen bed."),
        ("cabinet-glass-book", "Glass-Front Book Cabinet", "cabinet", 0.80, 0.38, 1.80, 0.60, 0.16, 16400, "modern", "essential", "Narrow book and display cabinet with glazed upper doors."),
        ("cabinet-modular-storage", "Modular Storage Cabinet", "cabinet", 1.00, 0.45, 1.20, 0.65, 0.18, 13200, "industrial", "essential", "Stackable closed cabinet for office, living-room or utility storage."),

        ("door-solid-core-entry", "Solid-Core Entry Door", "door", 0.90, 0.12, 2.10, 0.95, 0.10, 15800, "modern", "aperture", "Solid-core hinged door; the front clearance reserves the swing and entry."),
        ("door-shaker-panel", "Shaker-Panel Interior Door", "door", 0.80, 0.10, 2.10, 0.90, 0.08, 11200, "scandinavian", "aperture", "Painted panel door for bedrooms and internal passageways."),
        ("door-pocket-slide", "Pocket Sliding Door", "door", 0.90, 0.08, 2.10, 0.35, 0.08, 24800, "minimalist", "aperture", "Pocket slider with reduced swing area but a clear opening approach."),
        ("door-french-double", "French Double Door", "door", 1.50, 0.10, 2.10, 1.05, 0.12, 32500, "contemporary", "aperture", "Pair of glazed leaves with the wider approach needed for both swings."),
        ("door-glazed-patio", "Glazed Patio Door", "door", 1.80, 0.10, 2.10, 0.45, 0.10, 39800, "industrial", "aperture", "Sliding glazed exterior door with clear access to its full opening."),

        ("window-aluminum-casement", "Aluminum Casement Window", "window", 1.20, 0.12, 1.20, 0.60, 0.12, 14800, "modern", "aperture", "Single casement glazing with a daylight clearance strip in front."),
        ("window-sliding", "Sliding Window", "window", 1.50, 0.12, 1.20, 0.60, 0.12, 17900, "scandinavian", "aperture", "Two-track sliding window with aluminum frame and sill."),
        ("window-double-glazed", "Double-Glazed Picture Window", "window", 1.80, 0.15, 1.35, 0.75, 0.15, 28600, "contemporary", "aperture", "Wide insulated glazing; preserve the front zone for daylight."),
        ("window-awning-bath", "Bathroom Awning Window", "window", 0.60, 0.12, 0.60, 0.45, 0.10, 8200, "minimalist", "aperture", "Small top-hinged privacy window with a modest light clearance zone."),
        ("window-bay", "Bay Window Assembly", "window", 2.40, 0.20, 1.50, 0.85, 0.18, 46500, "industrial", "aperture", "Three-panel bay glazing with a deeper projecting frame."),
    ]

    for (item_id, name, category, width, depth, height, clearance_front, clearance_sides,
         cost, style, preference, description) in variants:
        if category not in TARGET_CLASSES or style not in STYLE_TAGS:
            raise ValueError(f"Invalid seeded furniture catalog row: {item_id}")
        yield {
            "id": item_id,
            "name": name,
            "category": category,
            "width": width,
            "depth": depth,
            "height": height,
            "clearance_front": clearance_front,
            "clearance_sides": clearance_sides,
            "wall_placement_preference": preference,
            "base_cost_inr": cost,
            "style_tag": style,
            "asset_model_url": f"/static/assets/furniture/{category}.svg",
            "thumbnail_url": PHOTO_BY_STYLE[style],
            "description": description,
            "source_benchmark": "Curated metric furniture specification and indicative Indian retail estimate",
            "active": 1,
        }


def _preset_specs() -> list[Dict[str, Any]]:
    return [
        {
            "id": "showcase-living-modern", "name": "Modern Living Room", "room_type": "living_room",
            "width": 5.4, "length": 4.8, "budget": 85000, "style": "modern",
            "door": {"wall": "south", "offset": 0.25, "width": 0.9},
            "windows": [{"wall": "north", "offset": 1.7, "width": 1.5}],
            "thumbnail": PHOTO_BY_STYLE["modern"],
            "description": "Sofa-to-TV sightline, compact coffee table, and an open entry route.",
            "furniture": [
                {"id": "sofa_1", "type": "sofa", "label": "3-Seater Sofa", "x": 3.35, "y": 3.88, "width": 2.1, "depth": 0.9, "height": 0.85, "rotation": 0, "cost": 14000},
                {"id": "table_1", "type": "table", "label": "Coffee Table", "x": 3.35, "y": 2.55, "width": 1.0, "depth": 0.6, "height": 0.45, "rotation": 0, "cost": 3500},
                {"id": "tv_1", "type": "tv", "label": "TV Console", "x": 3.35, "y": 0.45, "width": 1.2, "depth": 0.15, "height": 0.7, "rotation": 0, "cost": 8000},
                {"id": "chair_1", "type": "chair", "label": "Accent Chair", "x": 1.35, "y": 2.65, "width": 0.6, "depth": 0.6, "height": 0.85, "rotation": 0, "cost": 2200},
            ],
        },
        {
            "id": "showcase-bedroom-minimal", "name": "Minimal Bedroom", "room_type": "bedroom",
            "width": 4.8, "length": 4.4, "budget": 65000, "style": "minimalist",
            "door": {"wall": "south", "offset": 0.25, "width": 0.9},
            "windows": [{"wall": "north", "offset": 1.65, "width": 1.5}],
            "thumbnail": PHOTO_BY_STYLE["minimalist"],
            "description": "A wall-backed bed, side storage, and a separate desk corner.",
            "furniture": [
                {"id": "bed_1", "type": "bed", "label": "Queen Bed", "x": 2.35, "y": 2.85, "width": 1.6, "depth": 2.0, "height": 0.8, "rotation": 0, "cost": 12000},
                {"id": "wardrobe_1", "type": "wardrobe", "label": "2-Door Wardrobe", "x": 0.55, "y": 2.7, "width": 1.5, "depth": 0.6, "height": 2.1, "rotation": 90, "cost": 8500},
                {"id": "desk_1", "type": "desk", "label": "Study Desk", "x": 4.0, "y": 3.15, "width": 1.2, "depth": 0.6, "height": 0.75, "rotation": 0, "cost": 4200},
                {"id": "chair_1", "type": "chair", "label": "Desk Chair", "x": 4.0, "y": 2.35, "width": 0.55, "depth": 0.55, "height": 0.85, "rotation": 180, "cost": 1500},
            ],
        },
        {
            "id": "showcase-home-office-scandi", "name": "Scandinavian Home Office", "room_type": "home_office",
            "width": 4.2, "length": 3.8, "budget": 42000, "style": "scandinavian",
            "door": {"wall": "south", "offset": 0.25, "width": 0.9},
            "windows": [{"wall": "north", "offset": 1.1, "width": 1.4}],
            "thumbnail": PHOTO_BY_STYLE["scandinavian"],
            "description": "A daylight-aware desk, accessible chair, and wall-side storage.",
            "furniture": [
                {"id": "desk_1", "type": "desk", "label": "Work Desk", "x": 2.7, "y": 3.0, "width": 1.3, "depth": 0.65, "height": 0.75, "rotation": 0, "cost": 6000},
                {"id": "chair_1", "type": "chair", "label": "Ergonomic Chair", "x": 2.7, "y": 2.05, "width": 0.6, "depth": 0.6, "height": 0.85, "rotation": 180, "cost": 4500},
                {"id": "cabinet_1", "type": "cabinet", "label": "Storage Cabinet", "x": 0.48, "y": 2.55, "width": 1.0, "depth": 0.45, "height": 1.0, "rotation": 90, "cost": 3500},
            ],
        },
        {
            "id": "showcase-dining-contemporary", "name": "Contemporary Dining Room", "room_type": "dining_room",
            "width": 4.8, "length": 4.3, "budget": 55000, "style": "contemporary",
            "door": {"wall": "south", "offset": 0.25, "width": 0.9},
            "windows": [{"wall": "north", "offset": 1.4, "width": 1.5}],
            "thumbnail": PHOTO_BY_STYLE["contemporary"],
            "description": "A compact dining set with space around the table and a sideboard.",
            "furniture": [
                {"id": "table_1", "type": "table", "label": "Dining Table", "x": 2.65, "y": 2.45, "width": 1.4, "depth": 0.8, "height": 0.75, "rotation": 0, "cost": 7500},
                {"id": "chair_1", "type": "chair", "label": "Dining Chair", "x": 1.4, "y": 2.45, "width": 0.45, "depth": 0.45, "height": 0.85, "rotation": 90, "cost": 2200},
                {"id": "chair_2", "type": "chair", "label": "Dining Chair", "x": 3.9, "y": 2.45, "width": 0.45, "depth": 0.45, "height": 0.85, "rotation": 270, "cost": 2200},
                {"id": "cabinet_1", "type": "cabinet", "label": "Sideboard", "x": 4.3, "y": 3.55, "width": 1.0, "depth": 0.45, "height": 0.9, "rotation": 90, "cost": 5500},
            ],
        },
        {
            "id": "showcase-kitchen-modern", "name": "Modern Kitchen", "room_type": "kitchen",
            "width": 4.2, "length": 3.8, "budget": 60000, "style": "modern",
            "door": {"wall": "south", "offset": 0.25, "width": 0.9},
            "windows": [{"wall": "north", "offset": 1.3, "width": 1.4}],
            "thumbnail": PHOTO_BY_STYLE["modern"],
            "description": "A wall-side work surface and storage with a clear route through the room.",
            "furniture": [
                {"id": "cabinet_1", "type": "cabinet", "label": "Base Cabinet", "x": 0.5, "y": 2.4, "width": 1.2, "depth": 0.55, "height": 0.9, "rotation": 90, "cost": 6000},
                {"id": "cabinet_2", "type": "cabinet", "label": "Tall Cabinet", "x": 3.65, "y": 2.55, "width": 0.65, "depth": 0.55, "height": 2.0, "rotation": 90, "cost": 9000},
                {"id": "table_1", "type": "table", "label": "Prep Table", "x": 2.2, "y": 2.0, "width": 1.0, "depth": 0.6, "height": 0.9, "rotation": 0, "cost": 4500},
            ],
        },
        {
            "id": "showcase-bath-minimal", "name": "Minimal Bathroom", "room_type": "bathroom",
            "width": 3.2, "length": 2.8, "budget": 28000, "style": "minimalist",
            "door": {"wall": "south", "offset": 0.25, "width": 0.8},
            "windows": [{"wall": "north", "offset": 1.0, "width": 1.0}],
            "thumbnail": PHOTO_BY_STYLE["minimalist"],
            "description": "Compact vanity storage with a clear doorway and daylight area.",
            "furniture": [
                {"id": "cabinet_1", "type": "cabinet", "label": "Vanity Cabinet", "x": 0.45, "y": 1.95, "width": 0.9, "depth": 0.45, "height": 0.85, "rotation": 90, "cost": 6500},
                {"id": "cabinet_2", "type": "cabinet", "label": "Wall Storage", "x": 2.75, "y": 1.95, "width": 0.7, "depth": 0.35, "height": 0.65, "rotation": 90, "cost": 4200},
            ],
        },
    ]


def ensure_catalog_and_presets() -> None:
    """Idempotently create the local catalog and curated showcase layouts."""
    initialize_database()
    for item in _catalog_rows():
        insert_furniture(item)
    for spec in _preset_specs():
        room = {
            "dimensions": {"width": spec["width"], "length": spec["length"]},
            "budget": spec["budget"], "door": spec["door"], "windows": spec["windows"],
            "furniture": spec["furniture"],
        }
        env = InteriorEnv(room)
        state = env.get_state().tolist()
        metrics = env.evaluate_layout()
        layout = {
            "id": spec["id"], "name": spec["name"], "room_type": spec["room_type"],
            "room_width": spec["width"], "room_length": spec["length"],
            "budget": spec["budget"], "style": spec["style"], "door": spec["door"],
            "windows": spec["windows"], "furniture": spec["furniture"], "metrics": metrics,
        }
        normalized = [
            {
                "id": item["id"], "type": item["type"],
                "x": round(item["x"] / spec["width"], 6),
                "y": round(item["y"] / spec["length"], 6),
                "width": round(item["width"] / spec["width"], 6),
                "depth": round(item["depth"] / spec["length"], 6),
                "rotation": item.get("rotation", 0),
            }
            for item in spec["furniture"]
        ]
        insert_preset({
            "id": spec["id"], "name": spec["name"], "room_type": spec["room_type"],
            "room_width_m": spec["width"], "room_length_m": spec["length"],
            "budget_inr": spec["budget"], "style_tag": spec["style"],
            "furniture_state_json": encode_json({"state_133d": state, "layout": layout}),
            "normalized_geometry_json": encode_json(normalized),
            "expert_ergonomic_score": metrics["ergonomics_score"],
            "circulation_ratio": metrics["circulation_ratio"],
            "estimated_cost_inr": int(metrics["total_cost"]),
            "source_benchmark": "Curated ergonomic-rule seed; not imported from 3D-FRONT/3D-FUTURE",
            "thumbnail_url": spec["thumbnail"], "description": spec["description"],
            "featured": int(spec["id"].startswith("showcase-") and spec["room_type"] in {
                "living_room", "bedroom", "home_office", "dining_room"
            }),
        })


def seed_replay_buffer(transitions_per_preset: int = 12) -> int:
    """Persist small state/action perturbation trajectories for DQN replay.

    This seeds replay memory, it does not claim to train a policy. The action
    index stays an integer for DQNAgent; the 48-value one-hot form is retained
    as an auditable representation in SQLite.
    """
    from models import get_preset, insert_transition

    count = 0
    for preset in list_presets():
        packed = json.loads(preset["furniture_state_json"])
        layout = packed["layout"]
        env = InteriorEnv({
            "dimensions": {"width": preset["room_width_m"], "length": preset["room_length_m"]},
            "budget": preset["budget_inr"], "door": layout["door"],
            "windows": layout["windows"], "furniture": layout["furniture"],
        })
        max_count = max(0, int(transitions_per_preset))
        for step in range(max_count):
            item_index = step % max(1, len(env.furniture))
            direction = 0 if step % 2 == 0 else 1
            action = item_index * env.actions_per_item + direction
            state = env.get_state().copy()
            next_state, reward, done, _ = env.step(action)
            one_hot = [0] * 48
            one_hot[action] = 1
            inserted = insert_transition({
                "seed_key": f"{preset['id']}:curated-perturbation:{step}",
                "preset_id": preset["id"], "state_133d": state.tolist(),
                "action_index": action, "action_48d": one_hot,
                "reward": reward, "next_state_133d": next_state.tolist(),
                "done": done, "source": "curated_ergonomic_perturbation",
            })
            count += int(inserted)
    return count


def import_catalog_json(path: str | Path) -> int:
    """Import rights-cleared catalog JSON records with metric dimensions.

    Expected format: a JSON list or an object with ``items``. Accepted fields
    match FurnitureCatalog (category/class and depth/d aliases are supported).
    The user must obtain and use source data under its own dataset terms.
    """
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("items", [])
    inserted = 0
    for index, source in enumerate(rows):
        category = str(source.get("category") or source.get("class") or "").lower()
        if category not in TARGET_CLASSES:
            continue
        width = float(source.get("width", source.get("w", 0)))
        depth = float(source.get("depth", source.get("d", 0)))
        height = float(source.get("height", source.get("h", 0)))
        if min(width, depth) <= 0:
            continue
        item = {
            "id": str(source.get("id") or f"external-{source_path.stem}-{index}"),
            "name": str(source.get("name") or f"{category.title()} {index + 1}"),
            "category": category, "width": width, "depth": depth, "height": height,
            "clearance_front": float(source.get("clearance_front", 0.0)),
            "clearance_sides": float(source.get("clearance_sides", 0.0)),
            "wall_placement_preference": source.get("wall_placement_preference", "flexible"),
            "base_cost_inr": int(source.get("base_cost_inr", source.get("price_inr", 0))),
            "style_tag": str(source.get("style_tag") or "modern").lower(),
            "asset_model_url": source.get("asset_model_url") or source.get("model_url"),
            "thumbnail_url": source.get("thumbnail_url"),
            "description": str(source.get("description") or "Imported from user-provided dataset file."),
            "source_benchmark": str(source.get("source_benchmark") or "User-provided, rights-cleared catalog import"),
            "active": 1,
        }
        insert_furniture(item)
        inserted += 1
    return inserted
