"""
SmartSpace AI — Database Models & Data Access Layer
=====================================================
All persistent storage for the SmartSpace platform lives here.  The module
defines five SQLite tables and exposes pure-function helpers for every CRUD
operation used by the Flask routes, the recommendation engine, and the DQN
replay buffer warm-up.

Tables
------
- **FurnitureCatalog** — 10-category product catalog (bed, sofa, chair,
  table, wardrobe, desk, tv, cabinet, door, window) with real-world metric
  dimensions, clearance rules, style tags, and base costs in INR.
- **RoomPresetLayouts** — Curated ergonomic room layouts with normalised
  geometry, expert scores, and circulation ratios.  Used by the dual-engine
  recommender as starter templates.
- **ReplayBufferStore** — (state, action, reward, next_state, done)
  transitions for offline DQN training.  Keyed to presets and deduplicated
  by ``seed_key``.
- **Users** — Registered accounts with scrypt-hashed passwords.
- **ProjectHistory** — Per-user saved designs carrying the full 133-D MDP
  state vector and serialised layout JSON.

Design decisions
~~~~~~~~~~~~~~~~
* Python's built-in ``sqlite3`` is used intentionally — no ORM overhead,
  no extra dependency, and the WAL journal mode keeps reads non-blocking.
* All measurements are stored in **metres**; all prices in **Indian Rupees**.
* JSON columns (``*_json``) use compact ``separators=(',',':')`` encoding.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``routes/`` blueprints call the helpers here for auth, project history, and
preset queries.  ``engine/recommender.py`` queries the catalog and presets
when building recommendation bundles.  ``engine/seed_data.py`` populates the
tables at first startup.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SMARTSPACE_DB_PATH", PROJECT_ROOT / "data" / "smartspace.sqlite3"))


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS FurnitureCatalog (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('bed','sofa','chair','table','wardrobe','desk','tv','cabinet','door','window')),
    width REAL NOT NULL CHECK(width > 0),
    depth REAL NOT NULL CHECK(depth > 0),
    height REAL NOT NULL CHECK(height >= 0),
    clearance_front REAL NOT NULL DEFAULT 0,
    clearance_sides REAL NOT NULL DEFAULT 0,
    wall_placement_preference TEXT NOT NULL DEFAULT 'flexible'
        CHECK(wall_placement_preference IN ('essential','flexible','lateral','aperture')),
    base_cost_inr INTEGER NOT NULL DEFAULT 0,
    style_tag TEXT NOT NULL DEFAULT 'modern',
    asset_model_url TEXT,
    thumbnail_url TEXT,
    description TEXT NOT NULL DEFAULT '',
    source_benchmark TEXT NOT NULL DEFAULT 'project seed',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_furniture_category_style ON FurnitureCatalog(category, style_tag, active);
CREATE TABLE IF NOT EXISTS RoomPresetLayouts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    room_type TEXT NOT NULL,
    room_width_m REAL NOT NULL,
    room_length_m REAL NOT NULL,
    budget_inr INTEGER NOT NULL DEFAULT 0,
    style_tag TEXT NOT NULL,
    furniture_state_json TEXT NOT NULL,
    normalized_geometry_json TEXT NOT NULL,
    expert_ergonomic_score REAL NOT NULL DEFAULT 0,
    circulation_ratio REAL NOT NULL DEFAULT 0,
    estimated_cost_inr INTEGER NOT NULL DEFAULT 0,
    source_benchmark TEXT NOT NULL,
    thumbnail_url TEXT,
    description TEXT NOT NULL DEFAULT '',
    featured INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_presets_room_type ON RoomPresetLayouts(room_type, featured);
CREATE TABLE IF NOT EXISTS ReplayBufferStore (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_key TEXT UNIQUE,
    preset_id TEXT REFERENCES RoomPresetLayouts(id) ON DELETE CASCADE,
    state_133d_json TEXT NOT NULL,
    action_index INTEGER NOT NULL CHECK(action_index BETWEEN 0 AND 47),
    action_48d_json TEXT NOT NULL,
    reward REAL NOT NULL,
    next_state_133d_json TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'curated_ergonomic_perturbation',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_replay_created ON ReplayBufferStore(id);
CREATE TABLE IF NOT EXISTS Users (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ProjectHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    project_id TEXT,
    project_name TEXT NOT NULL,
    room_type TEXT NOT NULL DEFAULT 'Living Room',
    state_133d_json TEXT NOT NULL,
    layout_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_project_history_user_updated
    ON ProjectHistory(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_history_project
    ON ProjectHistory(user_id, project_id);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a configured SQLite connection and commit successful writes."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    """Create the current schema and indexes if they do not exist."""
    with connect() as conn:
        conn.executescript(SCHEMA)


def encode_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def decode_json(value: Optional[str], fallback: Any = None) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def insert_furniture(item: Dict[str, Any]) -> None:
    columns = (
        "id,name,category,width,depth,height,clearance_front,clearance_sides,"
        "wall_placement_preference,base_cost_inr,style_tag,asset_model_url,"
        "thumbnail_url,description,source_benchmark,active"
    )
    values = tuple(item.get(key) for key in columns.split(","))
    with connect() as conn:
        conn.execute(
            f"INSERT OR IGNORE INTO FurnitureCatalog ({columns}) VALUES ({','.join('?' for _ in values)})",
            values,
        )


def insert_preset(preset: Dict[str, Any]) -> None:
    columns = (
        "id,name,room_type,room_width_m,room_length_m,budget_inr,style_tag,"
        "furniture_state_json,normalized_geometry_json,expert_ergonomic_score,"
        "circulation_ratio,estimated_cost_inr,source_benchmark,thumbnail_url,"
        "description,featured"
    )
    values = tuple(preset.get(key) for key in columns.split(","))
    with connect() as conn:
        conn.execute(
            f"INSERT INTO RoomPresetLayouts ({columns}) VALUES ({','.join('?' for _ in values)}) "
            "ON CONFLICT(id) DO UPDATE SET "
            + ",".join(f"{column}=excluded.{column}" for column in columns.split(",") if column != "id"),
            values,
        )


def insert_transition(transition: Dict[str, Any]) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO ReplayBufferStore
               (seed_key,preset_id,state_133d_json,action_index,action_48d_json,reward,
                next_state_133d_json,done,source)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                transition.get("seed_key"),
                transition.get("preset_id"),
                encode_json(transition["state_133d"]),
                int(transition["action_index"]),
                encode_json(transition["action_48d"]),
                float(transition["reward"]),
                encode_json(transition["next_state_133d"]),
                int(bool(transition.get("done", False))),
                transition.get("source", "curated_ergonomic_perturbation"),
            ),
        )
        return cursor.rowcount == 1


def list_furniture(category: Optional[str] = None) -> list[Dict[str, Any]]:
    with connect() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM FurnitureCatalog WHERE active=1 AND category=? ORDER BY base_cost_inr, id",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM FurnitureCatalog WHERE active=1 ORDER BY category, base_cost_inr, id"
            ).fetchall()
    return [dict(row) for row in rows]


def list_presets(room_type: Optional[str] = None) -> list[Dict[str, Any]]:
    with connect() as conn:
        if room_type:
            rows = conn.execute(
                "SELECT * FROM RoomPresetLayouts WHERE room_type=? ORDER BY expert_ergonomic_score DESC, id",
                (room_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM RoomPresetLayouts ORDER BY featured DESC, room_type, id"
            ).fetchall()
    return [dict(row) for row in rows]


def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM RoomPresetLayouts WHERE id=?", (preset_id,)).fetchone()
    return dict(row) if row else None


def count_rows(table: str) -> int:
    if table not in {"FurnitureCatalog", "RoomPresetLayouts", "ReplayBufferStore"}:
        raise ValueError("Unknown SmartSpace table")
    with connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def recent_transitions(limit: int = 5000) -> list[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ReplayBufferStore ORDER BY id DESC LIMIT ?", (max(1, int(limit)),)
        ).fetchall()
    return [dict(row) for row in rows]


def clear_seed_tables() -> None:
    """Clear seeded rows for the explicit CLI --reset operation."""
    with connect() as conn:
        conn.execute("DELETE FROM ReplayBufferStore")
        conn.execute("DELETE FROM RoomPresetLayouts")
        conn.execute("DELETE FROM FurnitureCatalog")


def create_user(user_id: str, display_name: str, email: str, password_hash: str) -> Dict[str, Any]:
    """Create one account. Callers must pass a one-way password hash."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO Users (id,display_name,email,password_hash) VALUES (?,?,?,?)",
            (user_id, display_name.strip(), email.strip().lower(), password_hash),
        )
        row = conn.execute(
            "SELECT id,display_name,email,created_at FROM Users WHERE id=?", (user_id,)
        ).fetchone()
    return dict(row)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM Users WHERE email=? COLLATE NOCASE", (email.strip(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT id,display_name,email,created_at FROM Users WHERE id=?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def save_project_history(
    user_id: str,
    project_name: str,
    room_type: str,
    state_133d: list[float],
    layout: Dict[str, Any],
    project_id: Optional[str] = None,
    history_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Insert or update a user's saved design after validating its MDP vector."""
    if len(state_133d) != 133:
        raise ValueError("Saved layouts must contain a 133-value MDP state.")
    packed_layout = dict(layout)
    packed_layout["state_133d"] = state_133d
    # Annotated previews can be multi-megabyte data URLs; keep saved layouts compact.
    packed_layout.pop("annotated_image", None)
    layout_json = encode_json(packed_layout)
    state_json = encode_json(state_133d)
    clean_name = (project_name or "My SmartSpace design").strip()[:120]
    clean_room_type = (room_type or "Living Room").strip()[:80]

    with connect() as conn:
        row = None
        if history_id is not None:
            row = conn.execute(
                "SELECT id FROM ProjectHistory WHERE id=? AND user_id=?",
                (int(history_id), user_id),
            ).fetchone()
        if row is None and project_id:
            row = conn.execute(
                "SELECT id FROM ProjectHistory WHERE user_id=? AND project_id=? ORDER BY id DESC LIMIT 1",
                (user_id, project_id),
            ).fetchone()

        if row:
            saved_id = int(row["id"])
            conn.execute(
                """UPDATE ProjectHistory SET project_id=COALESCE(?,project_id), project_name=?,
                   room_type=?, state_133d_json=?, layout_json=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND user_id=?""",
                (project_id, clean_name, clean_room_type, state_json, layout_json, saved_id, user_id),
            )
        else:
            cursor = conn.execute(
                """INSERT INTO ProjectHistory
                   (user_id,project_id,project_name,room_type,state_133d_json,layout_json)
                   VALUES (?,?,?,?,?,?)""",
                (user_id, project_id, clean_name, clean_room_type, state_json, layout_json),
            )
            saved_id = int(cursor.lastrowid)

        saved = conn.execute(
            "SELECT * FROM ProjectHistory WHERE id=? AND user_id=?", (saved_id, user_id)
        ).fetchone()
    return dict(saved)


def list_project_history(user_id: str) -> list[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id,project_name,room_type,updated_at,created_at,layout_json,state_133d_json
               FROM ProjectHistory WHERE user_id=? ORDER BY updated_at DESC,id DESC""",
            (user_id,),
        ).fetchall()
    projects = []
    for row in rows:
        layout = decode_json(row["layout_json"], {})
        vector = decode_json(row["state_133d_json"], [])
        projects.append({
            "id": int(row["id"]),
            "project_name": row["project_name"],
            "room_type": row["room_type"],
            "updated_at": row["updated_at"],
            "created_at": row["created_at"],
            "budget": layout.get("budget", 0),
            "estimated_cost": (layout.get("metrics") or {}).get("total_cost")
                or sum(int(item.get("cost", 0) or 0) for item in layout.get("furniture", [])),
            "state_dimensions": len(vector),
        })
    return projects


def get_project_history(user_id: str, history_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ProjectHistory WHERE id=? AND user_id=?", (int(history_id), user_id)
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["layout"] = decode_json(result.pop("layout_json"), {})
    result["state_133d"] = decode_json(result.pop("state_133d_json"), [])
    if len(result["state_133d"]) != 133:
        return None
    result["layout"]["state_133d"] = result["state_133d"]
    result["layout"]["history_id"] = result["id"]
    result["layout"]["projectName"] = result["project_name"]
    return result
