"""
SmartSpace AI — Routes Package (Flask Blueprints)
==================================================
Splits the monolithic ``app.py`` route handlers into focused blueprint modules:

- ``routes.views``            — HTML page rendering (landing, studio, auth pages)
- ``routes.auth``             — ``/api/auth/*`` user authentication endpoints
- ``routes.projects``         — ``/api/projects``, ``/api/rooms``, ``/api/project-history``
- ``routes.recommendations``  — ``/api/recommendations``, ``/api/detect``,
                                ``/api/optimize``, ``/api/evaluate``, system status
- ``routes.jobs``             — bounded worker queue and ``/api/jobs/<id>`` polling

Each blueprint is registered by the slim ``app.py`` application factory.
"""

from routes.views import views_bp
from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.recommendations import recommendations_bp
from routes.jobs import jobs_bp

ALL_BLUEPRINTS = [views_bp, auth_bp, projects_bp, recommendations_bp, jobs_bp]
