# SmartSpace AI: Viva walkthrough and refinement record

## Repository cleanup

The user approved this list before any deletion:

- `templates/room_details.html`: obsolete form; `/room-details` redirects to the React wizard.
- `static/samples/sample_room.jpg`: unused copy; the active sample is under `data/samples/`.
- 36 tracked Python bytecode files: removed from the Git index; local runtime caches remain ignored.

The shared CSS, vanilla Studio scripts, furniture SVGs, Vite output and interior photos are active dependencies. They were retained. Ignore checks cover Python caches, Node dependencies, both original virtual environments, the new local validation environment, OS files, NumPy/Keras checkpoints, checkpoint directories and SQLite runtime files.

The checkout already contained substantial uncommitted changes. These were preserved; no unrelated files were staged or committed. Only the approved bytecode removals are staged.

## Explain the real architecture

This checkout uses **Flask with Python's `sqlite3`**, not SQLAlchemy. React/Vite renders the wizard and several UI islands. The CAD Studio still uses the vanilla JavaScript canvas/Three.js code. Removing that code would break the application.

```text
React wizard: room dimensions (feet), budget (INR), optional photo
  -> POST /api/rooms -> HTTP 202 + private status URL
  -> bounded background worker
     -> metres = feet * 0.3048
     -> decode photo -> YOLO -> pixel boxes -> approximate metric furniture
     -> failed/missing/empty vision: catalogue starter layouts
     -> SAT + A* validation and bounded spatial refinement
     -> InteriorEnv.get_state(): 133 float32 values
  -> poll GET /api/jobs/<id> -> room JSON
  -> sessionStorage pending room -> /studio -> CAD canvas
```

Photo-to-floor coordinates are a heuristic projection, not calibrated 3-D reconstruction. No detections are invented when weights are absent.

## Phase 2: mathematical walkthrough

### `engine/sat_collision.py`

Each furniture item is a rectangle centred at `(cx, cy)` in metres. Rotate its local offsets and then translate them:

```python
# **Rotation:** x' = x*cos(theta) - y*sin(theta),
# y' = x*sin(theta) + y*cos(theta).
rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
# **Row-vector convention:** vertex rows multiply R.T.
rotated_bounding_box = local_corners @ rotation_matrix.T
world_corners = rotated_bounding_box + np.array([cx, cy])
```

SAT needs two independent edge normals per rectangle. Opposite edges repeat an axis. One separating axis proves **no collision**; overlapping on only one axis does **not** prove collision. Touching counts as collision. Boolean queries over obstacles stop at the first confirmed collision; reward evaluation still counts all pairs.

### `engine/astar_planner.py`

```python
# **A*:** f(n) = g(n) + h(n), with both costs measured in metres.
row_distance = nr - goal_rc[0]
column_distance = nc - goal_rc[1]
remaining_distance = math.hypot(row_distance, column_distance) * self.res
estimated_total_cost = tentative_g + remaining_distance
```

Straight-line distance is an admissible lower bound with axial cost `resolution` and diagonal cost `sqrt(2) * resolution`. Diagonal steps require both adjacent orthogonal cells to be free. Occupied cells skip further SAT checks. Occupied endpoints snap to a nearby free cell; reachability is a grid approximation.

### `engine/interior_env.py`

**State concatenation:** `5 + 8 * (5 + 10 + 1) = 133`.

| Indices | Meaning | Scaling |
|---|---|---|
| 0–1 | Room width, length | metres / 10 |
| 2 | Budget | INR / 10000 |
| 3–4 | Door entry x, y | position / room extent |
| Each 16-value object block: 0–4 | x, y, width, depth, angle | room-relative x/y; sizes / 3; angle / 360 |
| Object block: 5–14 | Ten class indicators | one-hot |
| Object block: 15 | Presence | 1 when present |

Unused slots are zero-padded. Existing feature order/scales remain unchanged. Normalization does not imply every value lies in `[0, 1]`. Eight objects times six actions gives 48 action indices. After a move or rotation, oriented corners are clamped inside the room; impossible orientations leave the item unchanged.

### `engine/dqn_agent.py`

```python
# **Bellman target:** terminal transitions contribute no future return.
nonterminal_mask = (~dones).astype(np.float32)
discounted_future_rewards = self.gamma * best_next_values * nonterminal_mask
bellman_targets = rewards + discounted_future_rewards
targets[np.arange(self.batch_size), actions] = bellman_targets
```

Training uses epsilon-greedy exploration, replay and a target network. NumPy uses a 64-unit hidden layer and MSE/SGD. Optional TensorFlow uses 128/128/64 hidden units and Huber/Adam. Weights and metadata are stored in `data/models/dqn_policy.npz`.

The displayed trajectory is **greedy spatial search over improving actions**, with learned Q-values breaking reward ties when a trained checkpoint exists. It is not an epsilon-greedy policy rollout. Untrained Q-values are not used. Search has a cooperative time budget checked between candidate evaluations; one native inference cannot be forcibly interrupted by this timer.

### `vision/yolo_model.py`

```python
# **Input normalization:** [0,255] pixel values become [0,1] floats.
normalized_pixels = np.asarray(canvas, dtype=np.float32) / 255.0
# **Tensor axes:** HWC -> CHW -> batch x channels x height x width.
channels_first = np.transpose(normalized_pixels, (2, 0, 1))
tensor = channels_first[None, ...]
```

ONNX inference uses letterboxing. To recover pixels, subtract padding and divide by the scale. Class-wise nonmaximum suppression keeps the stronger box when intersection-over-union exceeds the threshold. Shared inference is locked because the model predictor can be mutable.

## Phase 3: backend resilience

`routes/recommendations.py` queues recommendations, detection and optimization. `routes/projects.py` snapshots upload bytes and session identifiers before queuing room creation. Workers never read a live request stream or request/session proxy.

`routes/jobs.py` uses one worker, up to four unfinished jobs, at most 32 retained results and five-minute result retention. Excess work receives JSON `503`; malformed JSON receives `400`. Job failures become JSON errors without a traceback in the response. Poll URLs are random bearer capabilities and must be kept private.

All four heavy POST endpoints now return **202**, so custom clients must poll the returned `status_url`. `static/js/api.js` implements this once for both React and Studio, with a two-minute client timeout and abortable polling. A browser abort stops waiting; it does not kill already-running server work.

`vision/detector.py` catches image decode and inference errors and returns explicit fallback metadata. Missing weights and empty detections also select starter furniture. `routes/projects.py` reuses catalogue recommendations, evaluates them against the user's openings, then refines them. Basic room furniture remains a last resort if the catalogue is unavailable.

The job store is **single-process and in-memory**. Restarting loses jobs; a multi-process deployment needs a shared task queue/result store. A Python thread keeps the HTTP handler available but does not provide hard isolation from native-library crashes.

Flask reference: [Async and background tasks](https://flask.palletsprojects.com/en/stable/async-await/). An `async def` view alone still occupies a WSGI worker.

## Phase 4: UI walkthrough

- `frontend/src/components/DesignLoading.tsx`: Framer Motion spinner with status announcements and reduced-motion support.
- `ProjectWizard.tsx`: abort stale recommendations, clear outdated bundles, restore keyboard focus after transitions, show loading during requests and Studio preparation, and label layouts needing manual adjustment.
- `frontend/src/api.ts` / `static/js/api.js`: shared polling, cancellation and timeout handling.
- `PresetLayoutGrid.tsx`: show available validated layouts even when fewer than five pass.
- `ExpandableLayoutCard.tsx` and Studio scripts: consume the new background API contract.
- Studio handoff writes the new room to `smartspace_pending_layout`, which takes precedence over old drafts. If browser storage is unavailable, the wizard shows an actionable error instead of silently opening the wrong room.

Lists already have stable keys. TypeScript's `noUnusedLocals` and `noUnusedParameters` checks pass. The browser walkthrough captured no console warnings or errors.

## Verification and local demo

The original `.venv` and `venv` point to Python installations on another computer. An ignored `.venv-viva` was created locally with the declared requirements.

Run from the repository root in PowerShell:

```powershell
.venv-viva\Scripts\python.exe -m unittest discover -s tests -v
.venv-viva\Scripts\python.exe app.py
```

Run from `frontend/`:

```powershell
pnpm run typecheck
pnpm run build
```

Observed checks: wizard progression, loading announcements, six recommendation results, named-room handoff, Studio optimization and clean console. Live recommendation submission returned 202 in about 31 ms while `/api/system-status` remained responsive. The final default 12 x 10 ft fallback evaluated with zero collisions, boundary violations, door interference and window blockage, plus 100% A* reachability.

**Model limitation:** no trained YOLO or DQN checkpoints are installed in this checkout. Real learned inference accuracy is therefore unverified. The verified demo uses explicit catalogue/spatial fallbacks; mocked vision cases test contracts, not detector accuracy.
