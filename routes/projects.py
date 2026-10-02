"""
SmartSpace AI — Project & Room State API Routes
=================================================
Handles all REST endpoints related to creating, saving, and retrieving
interior design projects and room configurations.

Endpoints
~~~~~~~~~
- ``POST /api/projects``                     — Create a new project session
- ``POST /api/rooms``                        — Save room specs, run YOLO, build 133-D state
- ``GET  /api/project-history``              — List user's saved designs
- ``GET  /api/project-history/<history_id>`` — Load one saved design
- ``POST /api/project-history``              — Upsert a saved design
- ``GET  /api/sample-rooms``                 — Return pre-configured demo rooms
- ``GET  /api/presets``                      — List DB-backed curated presets
- ``GET  /api/presets/<preset_id>``          — Load one preset into the studio

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``/api/rooms`` endpoint is the bridge between the frontend wizard and the
AI pipeline:  it accepts user-provided dimensions (feet → metres), runs YOLO
detection on the uploaded photo via ``vision.detector.VisionStateExtractor``,
maps detections into the ``InteriorEnv`` 133-D MDP state, and returns the
full room object ready for the studio canvas.

``database.models`` handles all persistence.
"""
import os
import math
import uuid
from functools import wraps
from pathlib import Path
from typing import Callable

from flask import Blueprint, current_app, jsonify, request, session

from config import FURNITURE_SPECS
from database.models import (
    decode_json,
    get_preset,
    get_project_history,
    get_user_by_id,
    list_presets,
    list_project_history,
    save_project_history,
)
from engine.interior_env import InteriorEnv
from engine.recommender import recommend_designs
from routes.jobs import submit_work

PROJECT_ROOT = Path(__file__).resolve().parents[1]

projects_bp = Blueprint("projects", __name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _current_user_id():
    user_id = session.get("user_id")
    if user_id and not get_user_by_id(user_id):
        # A restored cookie may refer to a user absent from the active database.
        session.pop("user_id", None)
        session.pop("user_name", None)
        return None
    return user_id


def _require_api_user(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not _current_user_id():
            return jsonify({"success": False, "error": "Sign in to access saved projects."}), 401
        return fn(*args, **kwargs)
    return wrapped


# ── Project CRUD ───────────────────────────────────────────────────────────

@projects_bp.route("/api/projects", methods=["POST"])
def create_project_api():
    """Creates a new interior design project session."""
    data = request.get_json() or {}
    project_id = str(uuid.uuid4())[:8]
    project = {
        "id": project_id,
        "name": data.get("name", "My Interior Project"),
        "roomType": data.get("roomType", "Living Room"),
        "description": data.get("description", "")
    }
    session["smartspace_project"] = project
    session.permanent = True
    return jsonify({"success": True, "project": project})


@projects_bp.route("/api/project-history", methods=["GET"])
@_require_api_user
def project_history_list_api():
    return jsonify({"success": True, "projects": list_project_history(_current_user_id())})


@projects_bp.route("/api/project-history/<int:history_id>", methods=["GET"])
@_require_api_user
def project_history_load_api(history_id):
    saved = get_project_history(_current_user_id(), history_id)
    if not saved:
        return jsonify({"success": False, "error": "Saved project not found."}), 404
    return jsonify({"success": True, "project": saved})


@projects_bp.route("/api/project-history", methods=["POST"])
@_require_api_user
def project_history_save_api():
    data = request.get_json(silent=True) or {}
    layout = data.get("layout")
    if not isinstance(layout, dict) or not isinstance(layout.get("furniture"), list):
        return jsonify({"success": False, "error": "A room layout is required to save a project."}), 400
    try:
        state = InteriorEnv(layout).get_state().tolist()
        project = save_project_history(
            _current_user_id(),
            str(data.get("project_name") or layout.get("projectName") or layout.get("name") or "My SmartSpace design"),
            str(layout.get("room_type") or layout.get("roomType") or "Living Room"),
            state,
            layout,
            project_id=str(data.get("project_id") or layout.get("projectId") or "") or None,
            history_id=data.get("history_id") or layout.get("history_id"),
        )
    except (TypeError, ValueError, KeyError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    return jsonify({
        "success": True,
        "project": {"id": project["id"], "project_name": project["project_name"], "updated_at": project["updated_at"]},
        "state_133d": state,
    })


# ── Room State (YOLO + MDP encoder) ───────────────────────────────────────

@projects_bp.route("/api/rooms", methods=["POST"])
def save_room_api():
    """Snapshot form/upload/session data and queue the room-to-Studio handoff."""
    uploaded_file = request.files.get("roomPhoto")
    photo_uploaded = bool(uploaded_file and uploaded_file.filename)
    image_bytes = uploaded_file.read(10 * 1024 * 1024 + 1) if photo_uploaded else None
    if image_bytes is not None and len(image_bytes) > 10 * 1024 * 1024:
        return jsonify(success=False, error="Room photos must be 10 MB or smaller."), 413
    return submit_work(
        _prepare_room, request.form.to_dict(), image_bytes, photo_uploaded,
        dict(session.get("smartspace_project") or {}), _current_user_id(),
        current_app.config["VISION_EXTRACTOR"], current_app.config.get("DQN_AGENT"),
    )


def _prepare_room(form, image_bytes, photo_uploaded, project_context, user_id, vision_extractor,
                  dqn_agent=None):
    """Return room JSON from detached inputs; vision failure uses room presets.

    The worker reads no request/session proxies. User and project identifiers
    are captured before submission; only a genuine user ID can save history.
    """
    try:
        # Form field extractions
        room_name = form.get("roomName", "Master Room")
        room_type = form.get("roomType", "Master Bedroom")

        # Dimensions in feet converted to meters
        length_ft = float(form.get("length", 12.0))
        width_ft = float(form.get("width", 10.0))
        height_ft = float(form.get("height", 10.0))

        length_m = round(length_ft * 0.3048, 2)
        width_m = round(width_ft * 0.3048, 2)
        height_m = round(height_ft * 0.3048, 2)

        num_doors = int(form.get("doors", 1))
        num_windows = int(form.get("windows", 1))
        budget_inr = float(form.get("budget", 20000.0))
        if not (6 <= length_ft <= 60 and 6 <= width_ft <= 60 and 7 <= height_ft <= 25):
            raise ValueError("Room width/length must be 6–60 feet and height 7–25 feet.")
        if not (1 <= num_doors <= 5 and 0 <= num_windows <= 6):
            raise ValueError("Choose 1–5 doors and 0–6 windows.")
        if not math.isfinite(budget_inr) or not 5000 <= budget_inr <= 100000000:
            raise ValueError("Choose a valid positive room budget.")

        design_style = form.get("designStyle", "Modern")
        primary_color = form.get("primaryColor", "White")
        secondary_color = form.get("secondaryColor", "Beige")
        material = form.get("preferredMaterial", "Wood")
        description = form.get("description", "")

        # Keep the user's aperture settings unless YOLO identifies openings in the photo.
        door_info = {"wall": "south", "offset": max(0.4, width_m * 0.2), "width": 0.9}
        windows = []
        for w_idx in range(num_windows):
            windows.append({
                "wall": "north",
                "offset": max(0.4, (width_m / (num_windows + 1)) * (w_idx + 1) - 0.6),
                "width": 1.4
            })

        # Check uploaded room photo for YOLO vision analysis
        annotated_img_b64 = None
        detected_furniture = None
        vision_result = None
        detector = getattr(vision_extractor, "detector", None)
        vision_available = bool(getattr(detector, "available", False))

        if photo_uploaded:
            try:
                if not vision_available:
                    raise FileNotFoundError("YOLO weights are unavailable.")
                vision_result = vision_extractor.process_room_image(
                    image_bytes, room_dimensions={"width": width_m, "length": length_m, "height": height_m}
                )
                annotated_img_b64 = vision_result.get("annotated_image")
                room_state = vision_result.get("room_state") or {}
                detected_furniture = room_state.get("initial_furniture")
                detected_classes = {item.get("class_name") for item in vision_result.get("detections", [])}
                if "door" in detected_classes:
                    door_info = room_state.get("door", door_info)
                if "window" in detected_classes:
                    windows = room_state.get("windows", windows)
            except Exception as error:
                current_app.logger.warning("YOLO skipped; using room template: %s", error)
                annotated_img_b64 = None
                detected_furniture = None
                vision_result = {"detected_count": 0, "fallback_used": True,
                                 "fallback_reason": "YOLO weights are unavailable." if not vision_available
                                 else "Photo detection failed. Starter furniture was used."}

        used_starter_furniture = not bool(detected_furniture)
        applied_bundle_id = None

        if used_starter_furniture:
            try:
                # **Fallback data flow:** reuse the catalogue/SAT/A* pipeline;
                # vision failure never fabricates furniture detections.
                recommendations = recommend_designs({
                    "room_type": room_type, "width_ft": width_ft,
                    "length_ft": length_ft, "budget_inr": budget_inr,
                    "style": design_style,
                })
                selected_id = form.get("variation_id", "")
                selected_bundle = next((bundle for bundle in recommendations["bundles"]
                                        if bundle["id"] == selected_id), None) if selected_id else None
                if selected_id and not selected_bundle:
                    raise ValueError("That bundle is unavailable. Refresh recommendations and select it again.")
                candidates = []
                for bundle in ([selected_bundle] if selected_bundle else recommendations["bundles"]):
                    furniture = bundle["layout"]["furniture"]
                    if not furniture:
                        continue
                    candidate_room = {
                        "dimensions": {"width": width_m, "length": length_m},
                        "budget": budget_inr, "door": door_info,
                        "windows": windows, "furniture": furniture,
                    }
                    metrics = InteriorEnv(candidate_room).evaluate_layout()
                    # Re-evaluate the catalogue layout against the user's openings.
                    # Geometric feasibility takes priority over ergonomic tie breaks.
                    rank = (
                        metrics.get("collision_count", 0),
                        metrics.get("boundary_violations", 0),
                        metrics.get("door_interferences", 0),
                        -metrics["total_reward"], bundle["total_cost_inr"],
                    )
                    candidates.append((rank, furniture))
                if candidates:
                    detected_furniture = min(candidates, key=lambda entry: entry[0])[1]
                    applied_bundle_id = selected_bundle["id"] if selected_bundle else None
            except Exception:
                current_app.logger.exception("Catalogue fallback unavailable; using basic room furniture")

        # Last-resort room-type furniture also works if the catalogue is unavailable.
        if not detected_furniture:
            if "bedroom" in room_type.lower():
                detected_furniture = [
                    {"id": "bed_1", "type": "bed", "x": width_m * 0.5, "y": length_m * 0.7, "width": 1.6, "depth": 2.0, "height": 0.8, "rotation": 0, "cost": 12000, "label": "Queen Bed"},
                    {"id": "wardrobe_1", "type": "wardrobe", "x": width_m * 0.8, "y": length_m * 0.3, "width": 1.5, "depth": 0.6, "height": 2.1, "rotation": 90, "cost": 8500, "label": "2-Door Wardrobe"},
                    {"id": "desk_1", "type": "desk", "x": width_m * 0.25, "y": length_m * 0.3, "width": 1.2, "depth": 0.6, "height": 0.75, "rotation": 0, "cost": 4200, "label": "Study Desk"},
                    {"id": "chair_1", "type": "chair", "x": width_m * 0.25, "y": length_m * 0.45, "width": 0.6, "depth": 0.6, "height": 0.85, "rotation": 0, "cost": 1500, "label": "Desk Chair"}
                ]
            elif "office" in room_type.lower():
                detected_furniture = [
                    {"id": "desk_1", "type": "desk", "x": width_m * 0.5, "y": length_m * 0.65, "rotation": 0, "cost": 4200, "label": "Study Desk"},
                    {"id": "chair_1", "type": "chair", "x": width_m * 0.5, "y": length_m * 0.4, "rotation": 0, "cost": 1500, "label": "Office Chair"},
                    {"id": "cabinet_1", "type": "cabinet", "x": width_m * 0.82, "y": length_m * 0.65, "rotation": 90, "cost": 3500, "label": "Storage Cabinet"}
                ]
            elif "dining" in room_type.lower():
                detected_furniture = [
                    {"id": "table_1", "type": "table", "x": width_m * 0.5, "y": length_m * 0.55, "rotation": 0, "cost": 3500, "label": "Dining Table"},
                    {"id": "chair_1", "type": "chair", "x": width_m * 0.5, "y": length_m * 0.22, "rotation": 0, "cost": 1500, "label": "Dining Chair"},
                    {"id": "chair_2", "type": "chair", "x": width_m * 0.5, "y": length_m * 0.84, "rotation": 180, "cost": 1500, "label": "Dining Chair"},
                    {"id": "cabinet_1", "type": "cabinet", "x": width_m * 0.82, "y": length_m * 0.55, "rotation": 90, "cost": 3500, "label": "Sideboard"}
                ]
            elif "kitchen" in room_type.lower():
                detected_furniture = [
                    {"id": "table_1", "type": "table", "x": width_m * 0.5, "y": length_m * 0.5, "rotation": 0, "cost": 3500, "label": "Kitchen Island"},
                    {"id": "cabinet_1", "type": "cabinet", "x": width_m * 0.82, "y": length_m * 0.5, "rotation": 90, "cost": 3500, "label": "Storage Cabinet"}
                ]
            elif "bathroom" in room_type.lower():
                detected_furniture = [
                    {"id": "cabinet_1", "type": "cabinet", "x": width_m * 0.75, "y": length_m * 0.55, "rotation": 90, "cost": 3500, "label": "Vanity Cabinet"}
                ]
            else:  # Living room / studio apartment
                detected_furniture = [
                    {"id": "sofa_1", "type": "sofa", "x": width_m * 0.5, "y": length_m * 0.3, "width": 2.1, "depth": 0.9, "height": 0.85, "rotation": 0, "cost": 14000, "label": "3-Seater Sofa"},
                    {"id": "table_1", "type": "table", "x": width_m * 0.5, "y": length_m * 0.55, "width": 1.2, "depth": 0.7, "height": 0.45, "rotation": 0, "cost": 3500, "label": "Coffee Table"},
                    {"id": "tv_1", "type": "tv", "x": width_m * 0.5, "y": length_m * 0.88, "width": 1.2, "depth": 0.15, "height": 0.7, "rotation": 180, "cost": 8000, "label": "55\" TV & Console"},
                    {"id": "chair_1", "type": "chair", "x": width_m * 0.2, "y": length_m * 0.55, "width": 0.7, "depth": 0.7, "height": 0.8, "rotation": 90, "cost": 2200, "label": "Lounge Chair"}
                ]

        for item in detected_furniture:
            specs = FURNITURE_SPECS.get(item.get("type", "chair"), FURNITURE_SPECS["chair"])
            item.setdefault("width", specs["width"])
            item.setdefault("depth", specs["depth"])
            item.setdefault("height", specs["height"])
            item.setdefault("cost", specs["base_cost"])
            item.setdefault("preferred_wall", specs.get("preferred_wall", False))

        room_id = str(uuid.uuid4())[:8]
        room_obj = {
            "id": room_id,
            "name": room_name,
            "room_type": room_type,
            "dimensions": {"width": width_m, "length": length_m, "height": height_m},
            "door": door_info,
            "windows": windows,
            "budget": budget_inr,
            "style": design_style,
            "primaryColor": primary_color,
            "secondaryColor": secondary_color,
            "material": material,
            "furniture": detected_furniture,
            "annotated_image": annotated_img_b64,
            "vision_model_available": vision_available,
            "vision_model_backend": getattr(detector, "engine_type", "unavailable"),
            "vision_detected_count": (vision_result or {}).get("detected_count", 0),
            "vision_detections": (vision_result or {}).get("detections", []),
            "vision_used_starter_furniture": used_starter_furniture,
            "vision_fallback_reason": (
                "No photo was uploaded." if not photo_uploaded else
                (vision_result or {}).get("fallback_reason") if (vision_result or {}).get("fallback_reason") else
                "YOLO weights are unavailable." if not vision_available else
                "No furniture objects were detected." if used_starter_furniture else None
            ),
        }
        if applied_bundle_id:
            room_obj["selected_bundle_id"] = applied_bundle_id

        if project_context:
            room_obj["projectId"] = project_context.get("id")
            room_obj["projectName"] = project_context.get("name") or room_name

        # The detected metric coordinates now enter the same 133-value encoder
        # used by the DQN, so the studio opens with the photo-derived room state.
        room_env = InteriorEnv(room_obj)
        if used_starter_furniture and dqn_agent is not None:
            try:
                # **Spatial refinement:** adjust the selected starter for the
                # user's door/window positions, with a cooperative demo budget.
                dqn_agent.optimize_layout_trajectory(room_env, max_steps=12, time_budget_seconds=2.0)
                room_obj["furniture"] = room_env.get_layout_dict()["furniture"]
            except Exception:
                current_app.logger.exception("Starter refinement failed; keeping catalogue placement")
                room_env = InteriorEnv(room_obj)
        room_obj["state_133d"] = room_env.get_state().tolist()
        room_obj["vision_state_object_count"] = min(len(room_env.furniture), room_env.max_items)
        room_obj["vision_state_dimensions"] = room_env.state_dim

        if user_id and get_user_by_id(user_id):
            history = save_project_history(
                user_id,
                room_obj.get("projectName") or room_name,
                room_type,
                room_obj["state_133d"],
                room_obj,
                project_id=room_obj.get("projectId"),
            )
            room_obj["history_id"] = int(history["id"])

        return jsonify({"success": True, "room": room_obj})

    except (TypeError, ValueError) as error:
        return jsonify(success=False, error=str(error)), 400


# ── Sample Rooms & Presets ─────────────────────────────────────────────────

@projects_bp.route("/api/sample-rooms", methods=["GET"])
def get_sample_rooms():
    """Returns available pre-configured sample rooms."""
    from config import SAMPLE_ROOMS
    return jsonify({"success": True, "rooms": SAMPLE_ROOMS})


@projects_bp.route("/api/presets", methods=["GET"])
def get_database_presets():
    """List curated DB-backed presets for the homepage/studio."""
    result = []
    for row in list_presets():
        packed = decode_json(row.get("furniture_state_json"), {})
        result.append({**row, "layout": packed.get("layout", {})})
    return jsonify({"success": True, "presets": result})


@projects_bp.route("/api/presets/<preset_id>", methods=["GET"])
def get_database_preset(preset_id):
    """Load one seeded or benchmark-imported room preset into the studio."""
    preset = get_preset(preset_id)
    if not preset:
        return jsonify({"success": False, "error": "Preset not found"}), 404
    packed = decode_json(preset.get("furniture_state_json"), {})
    layout = packed.get("layout")
    if not layout:
        return jsonify({"success": False, "error": "Preset layout is unavailable"}), 500
    layout.update({"id": preset["id"], "name": preset["name"], "style": preset["style_tag"]})
    return jsonify({"success": True, "preset": layout})
