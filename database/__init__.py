"""
SmartSpace AI — Database Package
=================================
Centralises all SQLite data access for the SmartSpace platform.

This package re-exports the public helpers from ``database.models`` so that
the rest of the codebase can write::

    from database.models import connect, list_presets, create_user, ...

The underlying storage uses Python's built-in ``sqlite3`` module (no ORM
dependency) for maximum portability and zero-config setup.
"""

from database.models import (  # noqa: F401 – re-exported public API
    connect,
    initialize_database,
    encode_json,
    decode_json,
    insert_furniture,
    insert_preset,
    insert_transition,
    list_furniture,
    list_presets,
    get_preset,
    count_rows,
    recent_transitions,
    clear_seed_tables,
    create_user,
    get_user_by_email,
    get_user_by_id,
    save_project_history,
    list_project_history,
    get_project_history,
)
