# Database and recommendation pipeline

SmartSpace uses built-in `sqlite3`; no ORM or external DB package is required.
The database defaults to `data/smartspace.sqlite3`. Set
`SMARTSPACE_DB_PATH` to use a different SQLite file.

## Local setup and seeding

```powershell
python scripts/seed_database.py
```

The command idempotently creates 50 furniture catalog variants (five styles
for each of the 10 detector classes), six curated room presets, and twelve
replay transitions per preset. `--reset` clears the three seed tables first;
`--skip-replay` skips transition generation. `--transitions-per-preset N`
changes the replay rows generated per room. The same seed keys prevent repeated
CLI runs from duplicating those transitions.

The bundled prices are approximate INR examples based on the application's
existing `FURNITURE_SPECS`; they are not live retail quotes. The bundled room
layouts are curated from the application's clearance and ergonomic rules. They
are not claimed to be extracted from 3D-FRONT or 3D-FUTURE.

To import an authorized/rights-cleared catalog export, normalize dimensions to
metres and map the ten target classes, then pass a JSON array or an object with
an `items` array:

```json
{
  "items": [
    {
      "id": "source-object-001",
      "name": "Example sofa",
      "category": "sofa",
      "width": 2.1,
      "depth": 0.9,
      "height": 0.85,
      "base_cost_inr": 14000,
      "style_tag": "modern",
      "source_benchmark": "3D-FUTURE-derived, locally priced estimate"
    }
  ]
}
```

```powershell
python scripts/seed_database.py --import-catalog path\to\normalized-catalog.json
```

The importer does not download benchmark assets, map their license, or infer
Indian prices. 3D-FRONT/3D-FUTURE require following their dataset terms; model
weights trained on those data are not included in this checkout.

## Schema and state contract

- `FurnitureCatalog`: metric width/depth/height, front/side clearance, wall
  placement, estimated INR cost, style, thumbnail/model asset URL and source.
- `RoomPresetLayouts`: room size, serialized 133-value `InteriorEnv` state,
  normalized furniture geometry, SAT/A* scores and source statement.
- `ReplayBufferStore`: 133-value before/after states, DQN action index (0–47),
  its 48-way one-hot representation, reward, terminal flag and seed provenance.

Replay rows are loaded into DQN memory at app startup and again by
`engine/train_dqn.py`. Seeding a replay buffer does not mark the DQN as trained.
Run the existing training CLI to train and save a compatible checkpoint:

```powershell
python engine/train_dqn.py --episodes 50 --steps 30
```

## Recommendation engine and API

`POST /api/recommendations` accepts `room_type`, `width_ft`, `length_ft`,
`budget_inr`, and `style`. It returns value/style bundles under a 90% furniture
budget cap. Per-item floor area is limited to 35% of the room. It selects the
closest room preset by aspect-ratio distance, transfers normalized furniture
positions, then evaluates the result with the current SAT and A* implementation,
door swing, daylight, and living-room TV-to-sofa distance checks.

The primary learned path is the project's existing DQN action policy. It is
only active when a compatible trained checkpoint is installed. With no
checkpoint, the preset/rule generator supplies candidates and the same spatial
checks remain authoritative. The `/studio` and `/room-details` recommendation
interfaces label this state instead of implying a trained generative model is
present.

## Homepage

The landing gallery reads featured presets from SQLite. The metrics on each
card are saved room dimensions, budget, ergonomic score, and the actual A*
circulation ratio. The What-If room diagram is drawn from the saved furniture
coordinates in Canvas; the lighting preview filters a local interior photo.

