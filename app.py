"""
SmartSpace AI — Flask Application Factory
===========================================
This file is the **sole entry-point** for the SmartSpace web server.  It
performs exactly three things and nothing else:

1. Creates the Flask application instance and configures sessions.
2. Initialises the two global AI service singletons
   (``VisionStateExtractor`` and ``DQN Agent``) and stores them in
   ``app.config`` so blueprints can access them via ``current_app``.
3. Registers the route blueprints and bounded background job queue.

**No algorithmic logic, no route handlers, no HTML rendering lives here.**

Architecture
~~~~~~~~~~~~
::

    app.py  (this file — init + wiring only)
      ├── routes/views.py             — HTML pages
      ├── routes/auth.py              — /api/auth/*
      ├── routes/projects.py          — /api/projects, /api/rooms, /api/project-history
      └── routes/recommendations.py   — /api/recommendations, /api/detect, /api/optimize, …

    engine/          — SAT, A*, MDP, DQN, recommender
    vision/          — YOLO loading and pixel→metric mapping
    database/        — SQLite models and helpers
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

import numpy as np
from flask import Flask

# Keep optional TensorFlow startup quiet before importing the model layer.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

from database.models import decode_json, recent_transitions
from engine.dqn_agent import DQNAgent
from engine.seed_data import ensure_catalog_and_presets
from routes import ALL_BLUEPRINTS
from routes.jobs import JobQueue
from vision.detector import VisionStateExtractor

PROJECT_ROOT = Path(__file__).resolve().parent


# ── Application Factory ───────────────────────────────────────────────────

def _session_secret() -> str:
    """Use a configured secret or keep a random local key stable across restarts."""
    configured = os.environ.get("SMARTSPACE_SECRET_KEY")
    if configured:
        return configured
    secret_path = PROJECT_ROOT / "data" / ".session_secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return secret_path.read_text(encoding="utf-8").strip()


def create_app() -> Flask:
    """Construct, configure, and return the SmartSpace Flask application."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

    app.secret_key = _session_secret()
    app.config.update(
        TEMPLATES_AUTO_RELOAD=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SMARTSPACE_COOKIE_SECURE", "").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    # ── AI Service Singletons ──────────────────────────────────────────────
    vision_extractor = VisionStateExtractor()
    dqn_agent = DQNAgent(state_dim=133, action_dim=48)

    app.config["VISION_EXTRACTOR"] = vision_extractor
    app.config["DQN_AGENT"] = dqn_agent
    # **Request isolation:** model/search work runs on a bounded worker queue.
    app.extensions["ai_jobs"] = JobQueue()

    # ── Database Seed & Replay Buffer Warm-Up ──────────────────────────────
    try:
        ensure_catalog_and_presets()
        for _transition in reversed(recent_transitions(limit=5000)):
            dqn_agent.memory.push(
                np.asarray(decode_json(_transition["state_133d_json"], []), dtype="float32"),
                int(_transition["action_index"]), float(_transition["reward"]),
                np.asarray(decode_json(_transition["next_state_133d_json"], []), dtype="float32"),
                bool(_transition["done"]),
            )
    except Exception as _db_error:
        app.logger.exception("SmartSpace database initialization failed: %s", _db_error)

    # ── Blueprint Registration ─────────────────────────────────────────────
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    return app


# ── Development Server ────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    print("\n" + "="*65)
    print("  [*] Starting SmartSpace AI Platform")
    print("  [*] Landing Page:   http://127.0.0.1:5000/")
    print("  [*] Create Project: http://127.0.0.1:5000/create-project")
    print("  [*] Room Details:   http://127.0.0.1:5000/room-details")
    print("  [*] AI Studio:      http://127.0.0.1:5000/studio")
    print("="*65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
