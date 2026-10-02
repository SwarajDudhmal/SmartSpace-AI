"""
SmartSpace AI — Rule-Based Interior Design Advisor
====================================================
Generates practical, room-specific design recommendations covering layout
priorities, colour palette direction, lighting layers, and finishing/budget
advice.

This module does **not** use machine learning.  It reads the layout metrics
produced by ``engine/interior_env.py`` (collision count, circulation ratio,
door/window blockages, boundary violations) and the user's style preferences
(primary/secondary colour, material, design style) to assemble four
actionable suggestion cards:

1. **Layout** — Prioritised fix list (e.g. "separate 2 overlapping pairs",
   "clear the door swing area").
2. **Colour & materials** — Palette guide based on the chosen style.
3. **Lighting** — Room-type-specific lighting layer advice.
4. **Finishing & budget** — Soft-furnishing tips and remaining-budget note.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Called by ``routes/recommendations.py`` (``/api/evaluate`` endpoint) after
``InteriorEnv.evaluate_layout()`` has produced the raw metrics dict.
"""
from typing import Any, Dict, List


STYLE_ACCENTS = {
    "modern": "matte black or brushed brass",
    "minimalist": "one muted accent such as sage green",
    "scandinavian": "muted sage and pale natural wood",
    "industrial": "rust, cognac, or matte black",
    "contemporary": "muted teal or deep green",
}

ROOM_LIGHTING = {
    "bedroom": "Use warm ambient light with separate bedside reading lights, so the whole room does not need to be brightly lit at night.",
    "living": "Layer soft ambient light with a floor or table lamp near seating; use a dimmable source near the TV to reduce screen glare.",
    "dining": "Center a warm pendant over the dining table and add softer ambient light around the room.",
    "office": "Combine daylight with an adjustable task lamp, and place the screen so the window is to its side rather than directly in front or behind it.",
    "kitchen": "Combine general ceiling light with focused task lighting over counters and food-preparation areas.",
    "bathroom": "Use even mirror lighting together with general room lighting, and choose fixtures rated for the room's moisture conditions.",
    "default": "Layer general ambient lighting with one focused task light and a softer accent light.",
}

ROOM_FINISHES = {
    "bedroom": "Add a soft rug beside or partly under the bed, and use layered curtains to balance privacy with daylight.",
    "living": "Use a rug to visually connect the sofa and table; keep the main route from the door clear around its edges.",
    "dining": "Choose a rug large enough that dining chairs stay on it when pulled back, or leave the floor clear for easier movement.",
    "office": "Use a small rug or curtains to soften sound, and keep cables grouped along one wall for a calmer workspace.",
    "kitchen": "Repeat one or two hardware finishes and keep countertop accessories grouped to make the room feel coordinated.",
    "bathroom": "Use moisture-resistant storage and repeat the same metal finish across taps, handles, and towel hooks.",
    "default": "Repeat one accent color in two small details, such as cushions and artwork, to make the room feel intentional.",
}


def _room_key(room_type: str) -> str:
    value = (room_type or "").strip().lower()
    if "bed" in value:
        return "bedroom"
    if "living" in value or "studio" in value:
        return "living"
    if "dining" in value:
        return "dining"
    if "office" in value or "work" in value:
        return "office"
    if "kitchen" in value:
        return "kitchen"
    if "bath" in value:
        return "bathroom"
    return "default"


def build_interior_recommendations(
    room: Dict[str, Any], metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Create practical layout, palette, lighting, and finishing suggestions."""
    room_type = str(room.get("room_type") or room.get("roomType") or "Living Room")
    room_key = _room_key(room_type)
    style = str(room.get("style") or room.get("designStyle") or "Modern").strip()
    if not style:
        style = "Modern"
    style_key = style.lower()
    accent = STYLE_ACCENTS.get(style_key, STYLE_ACCENTS["modern"])
    primary = str(room.get("primaryColor") or "warm white").strip()
    secondary = str(room.get("secondaryColor") or "soft neutral").strip()
    material = str(room.get("material") or room.get("preferredMaterial") or "natural wood").strip()

    issues: List[str] = []
    collisions = int(metrics.get("collision_count", 0) or 0)
    door_blocks = int(metrics.get("door_interferences", 0) or 0)
    window_blocks = int(metrics.get("window_blockages", 0) or 0)
    boundary_violations = float(metrics.get("boundary_violations", 0) or 0)
    circulation = float(metrics.get("circulation_ratio", 1.0) or 0)
    unreachable = int(metrics.get("unreachable_count", 0) or 0)
    if collisions:
        issues.append(f"separate the {collisions} overlapping furniture pair(s)")
    if door_blocks:
        issues.append("clear the door opening and swing area")
    if window_blocks:
        issues.append(f"move tall storage away from {window_blocks} blocked window area(s)")
    if boundary_violations > 0:
        issues.append("move furniture fully inside the room boundary")
    if circulation < 0.999:
        count_text = f"; {unreachable} item(s) are unreachable from the entry" if unreachable else ""
        issues.append(f"open a clearer walking route from the entry{count_text}")

    if issues:
        if circulation < 0.999:
            layout_title = "Open a clear walking route"
        elif collisions:
            layout_title = "Resolve furniture overlaps"
        elif door_blocks:
            layout_title = "Protect the doorway"
        elif window_blocks:
            layout_title = "Keep window light clear"
        else:
            layout_title = "Keep furniture inside the room"
        layout_detail = "Start with this priority: " + "; ".join(issues) + ". Recheck the green A* route after moving items."
    else:
        layout_title = "Keep the current clearances"
        layout_detail = "The current plan passes its collision, room-boundary, door, and route checks. Preserve the entry path as you add decor."

    budget = float(room.get("budget", metrics.get("budget", 0)) or 0)
    total_cost = float(metrics.get("total_cost", 0) or 0)
    remaining = budget - total_cost
    if budget and remaining < 0:
        budget_detail = f"Furniture is estimated at INR {total_cost:,.0f}, which is INR {abs(remaining):,.0f} above budget. Adjust the furniture list before adding decor."
    elif budget:
        budget_detail = f"About INR {remaining:,.0f} remains after the current furniture estimate. Reserve part of it for lighting and soft furnishings."
    else:
        budget_detail = f"Current furniture is estimated at INR {total_cost:,.0f}. Keep a separate allowance for lighting and soft furnishings."

    recommendations = [
        {
            "category": "Layout",
            "title": layout_title,
            "detail": layout_detail,
        },
        {
            "category": "Color and materials",
            "title": f"Build a {style} palette",
            "detail": f"Use {primary} on larger surfaces and {secondary} in textiles. Add {accent} in small accents, and repeat {material} in one or two details for cohesion.",
        },
        {
            "category": "Lighting",
            "title": "Layer the room lighting",
            "detail": ROOM_LIGHTING.get(room_key, ROOM_LIGHTING["default"]),
        },
        {
            "category": "Finishing and budget",
            "title": "Add the finishing layer",
            "detail": f"{ROOM_FINISHES.get(room_key, ROOM_FINISHES['default'])} {budget_detail}",
        },
    ]
    return {
        "style": style,
        "palette_summary": f"{primary} + {secondary} + {accent}",
        "recommendations": recommendations,
        "source": "Rule-based advice from room preferences, layout metrics, and budget",
    }
