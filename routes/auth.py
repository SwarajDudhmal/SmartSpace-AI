"""
SmartSpace AI — Authentication API Routes
==========================================
Handles user registration, login, logout, and session identity via the
``/api/auth/*`` REST endpoints.

Endpoints
~~~~~~~~~
- ``POST /api/auth/register`` — Create a new account (scrypt-hashed password)
- ``POST /api/auth/login``    — Verify credentials and create a session
- ``POST /api/auth/logout``   — Clear the Flask session
- ``GET  /api/auth/me``       — Return the currently signed-in user (if any)

All authentication state is stored in Flask's signed-cookie session.
Passwords are hashed with Werkzeug's ``scrypt`` hasher before storage.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``database.models.create_user`` / ``get_user_by_email`` / ``get_user_by_id``
handle the actual database writes.  The ``user_id`` stashed in ``session``
is consumed by ``routes.projects`` to gate project-history endpoints.
"""
import re
import sqlite3
import uuid

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database.models import create_user, get_user_by_email, get_user_by_id

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/me", methods=["GET"])
def auth_me_api():
    user_id = session.get("user_id")
    user = get_user_by_id(user_id) if user_id else None
    if user_id and not user:
        session.clear()
    return jsonify({"success": True, "user": user})


@auth_bp.route("/api/auth/register", methods=["POST"])
def auth_register_api():
    data = request.get_json(silent=True) or {}
    display_name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if len(display_name) < 2 or len(display_name) > 80:
        return jsonify({"success": False, "error": "Enter a name between 2 and 80 characters."}), 400
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify({"success": False, "error": "Enter a valid email address."}), 400
    if len(password) < 8 or len(password) > 256:
        return jsonify({"success": False, "error": "Use a password between 8 and 256 characters."}), 400
    try:
        user = create_user(str(uuid.uuid4()), display_name, email, generate_password_hash(password, method="scrypt"))
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "An account with this email already exists."}), 409
    current_project = session.get("smartspace_project")
    session.clear()
    if current_project:
        session["smartspace_project"] = current_project
    session["user_id"] = user["id"]
    session["user_name"] = user["display_name"]
    session.permanent = True
    return jsonify({"success": True, "user": user}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def auth_login_api():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user_record = get_user_by_email(email) if email else None
    if not user_record or not check_password_hash(user_record["password_hash"], password):
        return jsonify({"success": False, "error": "Email or password is incorrect."}), 401
    user = {key: user_record[key] for key in ("id", "display_name", "email", "created_at")}
    current_project = session.get("smartspace_project")
    session.clear()
    if current_project:
        session["smartspace_project"] = current_project
    session["user_id"] = user["id"]
    session["user_name"] = user["display_name"]
    session.permanent = True
    return jsonify({"success": True, "user": user})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout_api():
    session.clear()
    return jsonify({"success": True})
