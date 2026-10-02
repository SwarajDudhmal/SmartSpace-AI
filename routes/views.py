"""
SmartSpace AI — HTML View Routes
=================================
Handles all server-rendered Jinja2 page endpoints.  This blueprint serves
the multi-page design flow:

- ``/``                — Landing page with curated showcase presets
- ``/create-project``  — React four-step project creation wizard
- ``/room-details``    — Redirect into wizard step 2 (legacy bookmark)
- ``/login``           — Authentication page (login mode)
- ``/register``        — Authentication page (register mode)
- ``/projects``        — Saved project dashboard (auth-gated)
- ``/studio``          — Interactive 2D / 3D WebGL layout studio
- ``/report.pdf``      — Downloadable academic project report
- ``/data/samples/*``  — Static sample image server

No algorithmic or business logic lives here — this module only calls
``render_template`` and returns HTTP redirects.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Templates in ``templates/`` reference ``static/css/style.css``,
``static/js/*.js``, and ``static/assets/furniture/*.svg``.
The landing page queries ``database.models.list_presets`` via the
``ensure_catalog_and_presets`` startup hook.
"""
from pathlib import Path

from flask import Blueprint, redirect, render_template, request, send_file, send_from_directory, session, url_for

from config import TARGET_CLASSES, CLASS_COLORS, FURNITURE_SPECS, SAMPLE_ROOMS
from database.models import decode_json, list_presets

PROJECT_ROOT = Path(__file__).resolve().parents[1]

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def landing_page():
    """Renders the SmartSpace overview page."""
    showcases = []
    for row in list_presets():
        if not row.get("featured"):
            continue
        packed = decode_json(row.get("furniture_state_json"), {})
        layout = packed.get("layout", {})
        showcases.append({
            "id": row["id"], "name": row["name"], "room_type": row["room_type"],
            "style": row["style_tag"], "width_m": row["room_width_m"],
            "length_m": row["room_length_m"], "budget": row["budget_inr"],
            "score": row["expert_ergonomic_score"],
            "circulation": row["circulation_ratio"],
            "collision_count": layout.get("metrics", {}).get("collision_count", 0),
            "estimated_cost": row["estimated_cost_inr"],
            "layout_metrics": layout.get("metrics", {}),
            "thumbnail": row["thumbnail_url"], "description": row["description"],
            "layout": layout,
        })
    order = {"living_room": 0, "bedroom": 1, "home_office": 2, "dining_room": 3}
    showcases.sort(key=lambda preset: order.get(preset["room_type"], 10))
    return render_template("landing.html", page_key="home", showcase_presets=showcases)


@views_bp.route("/create-project")
def create_project_page():
    """Renders the React four-step project wizard."""
    initial_step = request.args.get("step", "1")
    if initial_step not in {"1", "2", "3", "4"}:
        initial_step = "1"
    return render_template("create_project.html", page_key="project", initial_step=initial_step)


@views_bp.route("/room-details")
def room_details_page():
    """Keep old bookmarks pointed at the room details step in the new wizard."""
    return redirect(url_for("views.create_project_page", step=2))


@views_bp.route("/login")
def login_page():
    return render_template("auth.html", page_key="auth", mode="login")


@views_bp.route("/register")
def register_page():
    return render_template("auth.html", page_key="auth", mode="register")


@views_bp.route("/projects")
def projects_page():
    if not session.get("user_id"):
        return redirect(url_for("views.login_page", next="/projects"))
    return render_template("projects.html", page_key="projects")


@views_bp.route("/auth/logout", methods=["POST"])
def logout_page():
    session.clear()
    return redirect(url_for("views.landing_page"))


@views_bp.route("/studio")
def studio_page():
    """Renders Interactive 2D/3D Studio with DQN Layout AI."""
    return render_template(
        "studio.html",
        classes=TARGET_CLASSES,
        colors=CLASS_COLORS,
        specs=FURNITURE_SPECS,
        sample_rooms=SAMPLE_ROOMS,
        page_key="studio"
    )


@views_bp.route("/data/samples/<path:filename>")
def serve_sample_file(filename):
    return send_from_directory(PROJECT_ROOT / "data" / "samples", filename)


@views_bp.route("/report.pdf")
@views_bp.route("/download-report")
def serve_pdf_report():
    """Serves the generated academic and presentation PDF report."""
    pdf_path = PROJECT_ROOT / "SmartSpace_AI_Project_Report.pdf"
    if pdf_path.exists():
        return send_file(pdf_path, mimetype="application/pdf", as_attachment=False, download_name="SmartSpace_AI_Project_Report.pdf")
    from flask import jsonify
    return jsonify({"error": "Report PDF not found"}), 404


@views_bp.app_errorhandler(404)
def page_not_found(_error):
    return render_template("404.html", page_key="not-found"), 404
