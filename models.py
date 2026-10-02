"""
SmartSpace AI — Legacy Models Re-Export (Compatibility Shim)
=============================================================
The canonical database layer has moved to ``database/models.py``.
This shim re-exports the full public API so that any stray imports
from ``models`` continue to resolve during the migration period.

Canonical home:  ``database/models.py``
"""
from database.models import *  # noqa: F401,F403 – re-export entire public API
