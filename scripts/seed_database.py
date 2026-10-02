#!/usr/bin/env python
"""Create the SmartSpace SQLite catalog, room presets and DQN replay rows.

The bundled records are explicitly identified as ergonomic-rule seeds. To
ingest benchmark-derived records, provide a JSON export that you are permitted
to use, normalized to metric dimensions and the documented catalog fields.
The original 3D-FRONT/3D-FUTURE asset archives are not bundled or redistributed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.seed_data import ensure_catalog_and_presets, import_catalog_json, seed_replay_buffer
from config import TARGET_CLASSES
from database.models import clear_seed_tables, count_rows, initialize_database, list_furniture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete current catalog, presets and replay rows first")
    parser.add_argument("--skip-replay", action="store_true", help="do not generate offline DQN perturbation transitions")
    parser.add_argument("--transitions-per-preset", type=int, default=12,
                        help="number of perturbation transitions to store for each preset (default: 12)")
    parser.add_argument("--import-catalog", type=Path, help="import a rights-cleared catalog JSON file")
    args = parser.parse_args()

    initialize_database()
    if args.reset:
        clear_seed_tables()
    ensure_catalog_and_presets()
    catalog = list_furniture()
    catalog_by_class = {category: sum(row["category"] == category for row in catalog) for category in TARGET_CLASSES}
    if len(catalog) < 50 or any(count < 5 for count in catalog_by_class.values()):
        raise RuntimeError("Catalog seeding must provide at least five named items in each of the ten core classes.")
    imported = import_catalog_json(args.import_catalog) if args.import_catalog else 0
    added_transitions = 0 if args.skip_replay else seed_replay_buffer(args.transitions_per_preset)

    print("SmartSpace SQLite seed completed")
    print(f"FurnitureCatalog: {count_rows('FurnitureCatalog')} rows ({imported} imported this run)")
    print("Catalog items by class: " + ", ".join(f"{category}={count}" for category, count in catalog_by_class.items()))
    print(f"RoomPresetLayouts: {count_rows('RoomPresetLayouts')} rows")
    print(f"ReplayBufferStore: {count_rows('ReplayBufferStore')} rows ({added_transitions} added this run)")
    print("Built-in records are curated ergonomic-rule examples, not imported benchmark data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
