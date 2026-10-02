"""
SmartSpace AI — Recommendation & AI Engine API Routes
======================================================
Exposes the core AI pipeline to the frontend via REST endpoints:

Endpoints
~~~~~~~~~
- ``POST /api/recommendations`` — Generate budgeted furniture bundles validated
  through SAT collision checks, A* circulation, and clearance rules.
  Uses the dual-engine approach: Primary (trained DQN) + Secondary
  (rule-based budget/clearance filters).
- ``POST /api/detect``          — Run YOLO 10-class interior object detection
  on an uploaded room photo or a built-in sample image.
- ``POST /api/optimize``        — Run the Deep Q-Network layout optimizer for
  up to N steps and return the full trajectory.
- ``POST /api/evaluate``        — Evaluate a custom layout and return metrics
  plus rule-based design advice.
- ``GET  /api/training-telemetry`` — Return DQN/YOLO training curves
  (only when real checkpoints exist).
- ``GET  /api/system-status``   — Report installed model state.
- ``POST /api/export-spec``     — Generate a downloadable text design spec.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is the primary integration point between the frontend studio and the
Python AI stack.  It delegates to:
- ``engine/recommender.py`` — dual-engine recommendation bundles
- ``engine/interior_env.py`` — 133-D MDP state and multi-objective reward
- ``engine/design_advisor.py`` — rule-based design advice
- ``engine/dqn_agent.py`` — DQN trajectory search
- ``vision/detector.py`` — YOLO detection pipeline
"""
import io
import json
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file, session
from werkzeug.exceptions import HTTPException

from engine.design_advisor import build_interior_recommendations
from engine.interior_env import InteriorEnv
from engine.recommender import recommend_designs
from routes.jobs import submit_work

PROJECT_ROOT = Path(__file__).resolve().parents[1]

recommendations_bp = Blueprint("recommendations", __name__)
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _uploaded_photo(payload):
    """Snapshot at most 10 MB of uploaded bytes; never pass FileStorage to a worker."""
    for field in ("roomPhoto", "file", "photo"):
        uploaded = request.files.get(field)
        if uploaded is not None and uploaded.filename:
            data = uploaded.read(MAX_PHOTO_BYTES + 1)
            if len(data) > MAX_PHOTO_BYTES:
                raise ValueError("Choose a room photo smaller than 10 MB.")
            return data
    encoded = payload.get("image_b64") or payload.get("photo")
    if encoded:
        if not isinstance(encoded, str) or len(encoded) > 14 * 1024 * 1024:
            raise ValueError("Choose a valid room photo smaller than 10 MB.")
        return encoded
    if payload.get("sample_id"):
        sample = PROJECT_ROOT / "data/samples/sample_room.jpg"
        return sample.read_bytes() if sample.is_file() else None
    return None


def _room_form(payload):
    """Accept the wizard's field names and the recommendation API's aliases."""
    form = dict(payload)
    for target, aliases in {
        "length": ("length_ft",), "width": ("width_ft",),
        "height": ("height_ft",), "budget": ("budget_inr",),
        "roomType": ("room_type",), "designStyle": ("style",),
    }.items():
        if target not in form:
            for alias in aliases:
                if alias in payload:
                    form[target] = payload[alias]
                    break
    form.setdefault("roomType", "Living Room")
    return form


def _prepare_photo_room(form, image_input, project_context, user_id, extractor, agent):
    """Decode via the vision service and reuse the real room/history/133-D pipeline."""
    from routes.projects import _prepare_room
    try:
        return _prepare_room(
            form, image_input, image_input is not None,
            project_context, user_id, extractor, agent,
        )
    except Exception:
        current_app.logger.exception("Photo room preparation failed; trying room template")
        try:
            return _prepare_room(form, None, False, project_context, user_id, extractor, agent)
        except Exception:
            current_app.logger.exception("Room template preparation failed")
            return jsonify(success=False, error="Could not prepare this room. Please retry."), 503


def _recommend_with_photo(payload, image_input, extractor, agent):
    """Keep photo detections and encoded state alongside the six suggested bundles."""
    result = recommend_designs(payload, agent=agent)
    response = current_app.make_response(
        _prepare_photo_room(_room_form(payload), image_input, {}, None, extractor, agent)
    )
    if response.status_code != 200:
        return response
    room = response.get_json()["room"]
    result["room"] = room
    result["state_133d"] = room["state_133d"]
    result["vision"] = {
        "detected_count": room["vision_detected_count"],
        "detections": room.get("vision_detections", []),
        "fallback_used": room["vision_used_starter_furniture"],
        "fallback_reason": room["vision_fallback_reason"],
    }
    return result


@recommendations_bp.route("/api/recommendations", methods=["POST"])
def get_design_recommendations():
    """Queue JSON/form room preferences; return a 202 status URL for bundles."""
    dqn_agent = current_app.config["DQN_AGENT"]
    vision_extractor = current_app.config.get("VISION_EXTRACTOR")
    try:
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        if not isinstance(payload, dict):
            return jsonify(success=False, error="Room preferences must be a JSON object."), 400

        image_input = _uploaded_photo(payload)
        if image_input is not None:
            return submit_work(_recommend_with_photo, payload, image_input, vision_extractor, dqn_agent)

        return submit_work(recommend_designs, payload, agent=dqn_agent)
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except HTTPException as error:
        return jsonify(success=False, error=error.description), error.code
    except Exception as error:
        current_app.logger.exception("Recommendation generation failed")
        return jsonify({"success": False, "error": "Could not build recommendations for this room."}), 500


@recommendations_bp.route("/api/detect", methods=["POST"])
def detect_room():
    """Prepare the wizard photo as a Studio room with a 133-value state."""
    from routes.projects import _current_user_id
    vision_extractor = current_app.config.get("VISION_EXTRACTOR")
    dqn_agent = current_app.config.get("DQN_AGENT")
    try:
        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        if not isinstance(payload, dict):
            return jsonify(success=False, error="Room inputs must be a JSON object."), 400
        image_input = _uploaded_photo(payload)
        return submit_work(
            _prepare_photo_room, _room_form(payload), image_input,
            dict(session.get("smartspace_project") or {}), _current_user_id(),
            vision_extractor, dqn_agent,
        )
    except ValueError as error:
        return jsonify(success=False, error=str(error)), 400
    except HTTPException as error:
        return jsonify(success=False, error=error.description), error.code
    except Exception:
        current_app.logger.exception("Photo upload could not be queued")
        return jsonify(success=False, error="Photo processing is unavailable. Please retry."), 503


@recommendations_bp.route("/api/optimize", methods=["POST"])
def optimize_layout():
    """Queue a metric room layout; return 202 while DQN spatial search runs."""
    dqn_agent = current_app.config["DQN_AGENT"]
    try:
        room_data = request.get_json(silent=True)
        if not isinstance(room_data, dict):
            return jsonify(success=False, error="Room layout must be a JSON object."), 400
        return submit_work(_optimize_room, room_data, dqn_agent)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _optimize_room(room_data, dqn_agent):
    """Return trajectory JSON from detached room input on the model worker."""
    max_steps = max(0, min(100, int(room_data.get("max_steps", 25))))
    env = InteriorEnv(room_data)
    trajectory = dqn_agent.optimize_layout_trajectory(env, max_steps=max_steps)
    return {
        "success": True, "trajectory": trajectory,
        "final_layout": env.get_layout_dict(), "step_count": len(trajectory),
        "optimizer_trained": dqn_agent.is_trained, "optimizer_backend": dqn_agent.backend,
    }


@recommendations_bp.route("/api/evaluate", methods=["POST"])
def evaluate_custom_layout():
    """Evaluates the layout and returns room-specific design advice."""
    try:
        room_data = request.get_json() or {}
        env = InteriorEnv(room_data)
        metrics = env.evaluate_layout()
        design_advice = build_interior_recommendations(room_data, metrics)
        return jsonify({
            "success": True,
            "metrics": metrics,
            "design_advice": design_advice,
            "state_133d": env.get_state().tolist(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@recommendations_bp.route("/api/training-telemetry", methods=["GET"])
def get_training_telemetry():
    """Return only training curves accompanied by real installed checkpoints."""
    dqn_agent = current_app.config["DQN_AGENT"]
    vision_extractor = current_app.config["VISION_EXTRACTOR"]
    models_dir = PROJECT_ROOT / "data" / "models"
    dqn_file = models_dir / "dqn_training_history.json"
    yolo_file = PROJECT_ROOT / "runs" / "interior_yolo" / "yolo_training_telemetry.json"
    dqn_data = None
    yolo_data = None
    if dqn_agent.is_trained and dqn_file.is_file():
        try:
            candidate = json.loads(dqn_file.read_text(encoding="utf-8"))
            if candidate.get("real_training") is True:
                dqn_data = candidate
        except (OSError, ValueError):
            pass
    if vision_extractor.detector.available and yolo_file.is_file():
        try:
            candidate = json.loads(yolo_file.read_text(encoding="utf-8"))
            if candidate.get("real_training") is True:
                yolo_data = candidate
        except (OSError, ValueError):
            pass
    return jsonify({"success": True, "dqn": dqn_data, "yolo": yolo_data})


@recommendations_bp.route("/api/system-status", methods=["GET"])
def get_system_status():
    """Report the actual installed model state for the studio UI."""
    dqn_agent = current_app.config["DQN_AGENT"]
    vision_extractor = current_app.config["VISION_EXTRACTOR"]
    detector = vision_extractor.detector
    return jsonify({
        "success": True,
        "vision": {
            "available": detector.available,
            "backend": detector.engine_type,
            "model": detector.model_path.name if detector.available else None,
        },
        "optimizer": {
            "available": True,
            "trained": dqn_agent.is_trained,
            "backend": dqn_agent.backend,
            "mode": "trained DQN with spatial search" if dqn_agent.is_trained else "spatial search (checkpoint not trained)",
        },
    })


@recommendations_bp.route("/api/export-spec", methods=["POST"])
def export_spec():
    """Generates a downloadable design spec sheet."""
    try:
        data = request.get_json() or {}
        layout = data.get("layout", {})
        furniture = layout.get("furniture", [])
        metrics = layout.get("metrics", {})

        spec_text = []
        spec_text.append("=" * 60)
        spec_text.append("           SMARTSPACE AI · INTERIOR DESIGN SPECIFICATION")
        spec_text.append("=" * 60)
        spec_text.append(f"Room Dimensions : {layout.get('room_width', 4.8)}m x {layout.get('room_length', 4.0)}m")
        spec_text.append(f"Ergonomics Score: {metrics.get('ergonomics_score', 0)}%")
        spec_text.append(f"Circulation     : {metrics.get('circulation_ratio', 0)*100:.0f}% Reachable")
        spec_text.append(f"Collisions      : {metrics.get('collision_count', 0)} Detected")
        spec_text.append(f"Total Cost      : ₹{metrics.get('total_cost', 0):,}")
        spec_text.append(f"Budget Limit    : ₹{layout.get('budget', 0):,}")
        spec_text.append("-" * 60)
        spec_text.append("FURNITURE SCHEDULE:")
        for idx, item in enumerate(furniture, 1):
            spec_text.append(
                f"  {idx}. {item.get('label', item['type']).upper():<24} | "
                f"Pos: ({item['x']:.2f}m, {item['y']:.2f}m) | "
                f"Rot: {item.get('rotation', 0):>3} deg | "
                f"Size: {item['width']:.2f}x{item['depth']:.2f}m | "
                f"₹{item.get('cost', 0):,}"
            )
        design_advice = layout.get("design_advice", {})
        recommendations = design_advice.get("recommendations", [])
        if recommendations:
            spec_text.append("-" * 60)
            spec_text.append("INTERIOR DESIGN RECOMMENDATIONS:")
            spec_text.append(f"  Palette direction: {design_advice.get('palette_summary', 'Use the selected room palette')}")
            for item in recommendations:
                spec_text.append(f"  {item.get('category', 'Design')}: {item.get('title', 'Suggestion')}")
                spec_text.append(f"    {item.get('detail', '')}")
        spec_text.append("=" * 60)
        spec_text.append("Generated with SmartSpace AI · Interior Design Studio")

        buffer = io.BytesIO()
        buffer.write("\n".join(spec_text).encode("utf-8"))
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="smartspace_design_specification.txt",
            mimetype="text/plain"
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
