# SmartSpace AI — Architectural Specification & Viva Defense Reference Guide

> **Single Source of Truth** for technical architecture, algorithmic formulations, state vector mathematics, and viva defense Q&A.

---

## 1. System Architecture & End-to-End Execution Flow

SmartSpace AI is an intelligent spatial planning and ergonomic interior layout assistant. It combines computer vision (YOLO), geometric algorithms (SAT collision detection), graph search (A* reachability), and reinforcement learning (Deep Q-Networks) over a lightweight, responsive web stack.

### 1.1 Technical Stack
- **Backend**: Python 3.10+ / Flask, native `sqlite3` (no ORM overhead), bounded thread pool background queue (`routes/jobs.py`).
- **Frontend**:
  - **Wizard & UI Islands**: React 19, TypeScript, Tailwind CSS v4, Framer Motion (compiled via Vite to `static/dist/`).
  - **CAD Studio**: Native HTML5 Canvas 2D spatial renderer, Three.js WebGL 3D preview, OrbitControls.
- **Machine Learning & Spatial Engine**: NumPy, SciPy, PIL, Ultralytics YOLO / ONNX Runtime (optional), TensorFlow / NumPy DQN.

### 1.2 End-to-End Workflow Diagram
```text
[User Input: Wizard / Photo]
             │
             ▼
   POST /api/rooms (or /api/recommendations)
             │
             ▼
    [Bounded JobQueue] ──(Returns HTTP 202 + status_url)──> [Client Polls]
             │
      ┌──────┴───────────────────────────────────┐
      │ Background Worker Thread                  │
      ├───────────────────────────────────────────┤
      │ 1. Imperial -> Metric Conversion          │
      │ 2. Photo Decoding & YOLO Vision Pipeline  │
      │    └─ Missing weights? -> Graceful fallback│
      │ 3. Spatial Validation (SAT + A* Paths)    │
      │ 4. 133-D MDP State Vector Encoding        │
      │ 5. DQN Spatial Trajectory Search          │
      └───────────────────────────────────────────┘
             │
             ▼ (HTTP 200 via Polling)
   [SessionStorage Handoff]
             │
             ▼
  [/studio CAD Canvas] ──(Interactive Drag, Rotate, Snap, DQN Optimize)
```

---

## 2. Core Mathematical & Algorithmic Formulations

### 2.1 Separating Axis Theorem (SAT) Collision Detection (`engine/sat_collision.py`)

Each furniture item is modeled as an Oriented Bounding Box (OBB) in 2D metric space, specified by center $(c_x, c_y)$, width $w$, depth $d$, and rotation angle $\theta$.

#### Bounding Box Transformation
1. Local unrotated corners centered at origin:
   $$\text{corners}_{\text{local}} = \begin{bmatrix} -w/2 & -d/2 \\ w/2 & -d/2 \\ w/2 & d/2 \\ -w/2 & d/2 \end{bmatrix}$$
2. 2D rotation matrix:
   $$R(\theta) = \begin{bmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{bmatrix}$$
3. World coordinate transformation (using row-vector convention $V_{\text{world}} = V_{\text{local}} R^T + C$):
   $$\begin{bmatrix} x_i' \\ y_i' \end{bmatrix} = \begin{bmatrix} x_i \cos\theta - y_i \sin\theta + c_x \\ x_i \sin\theta + y_i \cos\theta + c_y \end{bmatrix}$$

#### SAT Theorem & Separation Testing
For any two convex polygons $A$ and $B$, they are disjoint if and only if there exists a line (axis) onto which their projections do not overlap.
- For two rectangles, there are at most **4 candidate separating axes** (the perpendicular normal vectors to each rectangle's unique edges).
- Normal vector for an edge vector $(dx, dy)$ is given by:
  $$\mathbf{n} = \frac{(-dy, dx)}{\sqrt{dx^2 + dy^2}}$$
- The scalar projection of polygon vertices $V$ onto axis $\mathbf{n}$ is:
  $$p_i = V_i \cdot \mathbf{n}$$
  $$[\min_A, \max_A] = \left[ \min_{i} (A_i \cdot \mathbf{n}), \max_{i} (A_i \cdot \mathbf{n}) \right]$$
- If $\max_A < \min_B$ or $\max_B < \min_A$ for **any single axis**, the shapes do not collide (early exit).
- A collision is confirmed only if their projections overlap across **all 4 axes**.

---

### 2.2 A* Circulation & Accessibility Pathfinding (`engine/astar_planner.py`)

SmartSpace calculates human circulation routes from the entry door to each furniture interaction zone across a discretized occupancy grid (default resolution: $0.1\,\text{m} = 10\,\text{cm}$ per cell).

#### Cost Function
$$f(n) = g(n) + h(n)$$
- $g(n)$: Exact path cost accumulated from the start node to current node $n$.
- $h(n)$: Admissible heuristic estimate from node $n$ to goal $(r_g, c_g)$.

#### Heuristic & Movement Costs
- Straight-line Euclidean distance heuristic (admissible, guarantees optimal path):
  $$h(n) = \sqrt{(r - r_g)^2 + (c - c_g)^2} \times \text{resolution}$$
- Movement step costs on an 8-connected grid:
  - Orthogonal transition: $\Delta g = \text{resolution}$ ($0.1\,\text{m}$)
  - Diagonal transition: $\Delta g = \sqrt{2} \times \text{resolution} \approx 0.1414\,\text{m}$

#### Corner-Cutting Prevention
To ensure a person can realistically walk diagonally, diagonal movement from $(r, c)$ to $(r \pm 1, c \pm 1)$ is permitted **only if both orthogonal adjacent neighbors** $(r \pm 1, c)$ and $(r, c \pm 1)$ are completely free of obstacles.

#### Ergonomic Circulation Ratio
$$\text{Circulation Ratio} = \frac{\text{Count of Reachable Target Furniture Interaction Zones}}{\text{Total Essential Target Zones}}$$
A candidate layout is considered circulation-valid if $\text{Circulation Ratio} \ge 0.75$ ($75\%$).

---

### 2.3 133-Dimensional MDP State Representation (`engine/interior_env.py`)

The layout optimization problem is formulated as a Markov Decision Process (MDP) with a dense 133-dimensional continuous feature vector:

$$\mathbf{S} \in \mathbb{R}^{133} = \left[ \mathbf{s}_{\text{room}} \,(5), \; \mathbf{s}_{\text{obj}_1} \,(16), \; \dots, \; \mathbf{s}_{\text{obj}_8} \,(16) \right]$$

#### Detailed Vector Breakdown

| Index Range | Dimension | Semantic Feature | Normalization / Scaling |
|---|---|---|---|
| `[0:2]` | 2 | Room Dimensions ($W, L$) | $\text{width} / 10.0$, $\text{length} / 10.0$ |
| `[2]` | 1 | Total Budget | $\text{budget\_inr} / 10000.0$ |
| `[3:5]` | 2 | Door Entry Position ($x_d, y_d$) | $x_d / W$, $y_d / L$ (normalized $[0, 1]$) |
| `[5:21]` | 16 | Furniture Slot 1 | Block of 16 features (see below) |
| `[21:37]` | 16 | Furniture Slot 2 | Block of 16 features |
| `...` | 16 | Furniture Slots 3–7 | Blocks of 16 features each |
| `[117:133]` | 16 | Furniture Slot 8 | Block of 16 features |

#### Per-Object 16-Value Feature Block
For each of the 8 supported furniture slots:
1. `offset + 0`: Normalized X center ($x / W \in [0, 1]$)
2. `offset + 1`: Normalized Y center ($y / L \in [0, 1]$)
3. `offset + 2`: Normalized Width ($w / 3.0$)
4. `offset + 3`: Normalized Depth ($d / 3.0$)
5. `offset + 4`: Normalized Rotation angle ($\theta / 360.0$)
6. `offset + [5:15]`: 10-Class One-Hot Vector (`bed, sofa, chair, table, wardrobe, desk, tv, cabinet, door, window`)
7. `offset + 15`: Existence Flag ($1.0$ if slot contains active item, $0.0$ if empty/padded)

#### Action Space (48 Discrete Actions)
- 8 object indices $\times$ 6 discrete operations:
  - $\Delta x \in \{-0.15\,\text{m}, +0.15\,\text{m}\}$
  - $\Delta y \in \{-0.15\,\text{m}, +0.15\,\text{m}\}$
  - $\Delta \theta \in \{-15^\circ, +15^\circ\}$
- Total discrete action set: $|\mathcal{A}| = 48$.

#### Multi-Objective Reward Function
$$R = R_{\text{clearance}} + R_{\text{circulation}} + R_{\text{boundary}} + R_{\text{alignment}} - \lambda_{\text{collision}} \cdot C$$
- Collision penalty: $-50.0$ per overlapping OBB pair.
- Door/window blockage: $-30.0$ if intersecting aperture swing arc or daylight zone.
- Circulation reward: $+20.0 \times \text{circulation\_ratio}$.
- Boundary penalty: $-25.0$ if any corner exceeds room dimensions.
- Wall alignment: $+5.0$ bonus for large storage/bed pieces positioned along walls.

---

### 2.4 Deep Q-Network (DQN) Architecture (`engine/dqn_agent.py`)

#### Q-Learning Bellman Optimality Target
$$Q_{\text{target}}(s, a) = r + \gamma \max_{a' \in \mathcal{A}} Q(s', a'; \theta^{-}) \cdot (1 - d)$$
- $r$: Multi-objective reward from layout transition.
- $\gamma$: Discount factor ($0.95$).
- $\theta^{-}$: Parameter weights of the frozen target network (updated every $C$ episodes).
- $d \in \{0, 1\}$: Terminal transition mask.

#### Network Architecture
- **Input**: 133-D vector.
- **Hidden Layers**: Dense(128, ReLU) $\to$ Dense(128, ReLU) $\to$ Dense(64, ReLU).
- **Output**: Dense(48, Linear Q-values).
- **Optimization**: Huber Loss ($\delta = 1.0$), Adam optimizer ($\alpha = 0.0005$), Experience Replay buffer ($N = 10,000$).

#### Production Spatial Search Behavior
In the interactive studio, rather than uncontrolled epsilon-greedy sampling, the optimizer executes a **bounded greedy spatial search over valid actions**. It applies candidate moves, evaluates spatial feasibility, and uses trained Q-values as an informed heuristic to break reward ties.

---

### 2.5 YOLO 10-Class Vision Pipeline (`vision/yolo_model.py`, `vision/detector.py`)

#### 10 Indoor Target Classes
`bed (0), sofa (1), chair (2), table (3), wardrobe (4), desk (5), tv (6), cabinet (7), door (8), window (9)`

#### Preprocessing & Letterboxing
1. Calculate scale factor: $s = \min(640 / W_0, 640 / H_0)$.
2. Bilinear resize: $(W_r, H_r) = (\text{round}(W_0 \cdot s), \text{round}(H_0 \cdot s))$.
3. Center onto $640 \times 640$ gray canvas $(114, 114, 114)$ with padding $(p_x, p_y)$.
4. Normalization: Byte intensity $[0, 255] \to [0.0, 1.0]$ float32.
5. Axis transposition: $(H, W, C) \to (C, H, W) \to (1, 3, 640, 640)$.

#### Inverse Letterboxing & Bounding Box Recovery
Recovering original pixel coordinates from model output $(x_1^m, y_1^m, x_2^m, y_2^m)$:
$$x_1 = \text{clamp}\left( \frac{x_1^m - p_x}{s}, 0, W_0 \right), \quad y_1 = \text{clamp}\left( \frac{y_1^m - p_y}{s}, 0, H_0 \right)$$
$$x_2 = \text{clamp}\left( \frac{x_2^m - p_x}{s}, 0, W_0 \right), \quad y_2 = \text{clamp}\left( \frac{y_2^m - p_y}{s}, 0, H_0 \right)$$

#### Bounded Heuristic Metric Projection
Pixel boxes are projected to ground plane metric coordinates $(x_m, y_m)$ using the room's physical dimensions $(W_{\text{room}}, L_{\text{room}})$:
$$x_m = \frac{x_1 + x_2}{2 W_0} \cdot W_{\text{room}}, \quad y_m = \frac{y_1 + y_2}{2 H_0} \cdot L_{\text{room}}$$
*Note: This provides heuristic initialization. When weights are missing or inference fails, the system executes an immediate template preset fallback.*

---

## 3. Database Schema & Data Models (`database/models.py`)

SmartSpace uses pure Python SQLite (`data/smartspace.sqlite3`) for zero-dependency portability.

### Tables
1. **`furniture_catalog`**:
   - `id` (TEXT, PK): Unique item identifier.
   - `name` (TEXT), `category` (TEXT): One of 10 target classes.
   - `width`, `depth`, `height` (REAL): Metric dimensions.
   - `clearance_front`, `clearance_side` (REAL): Ergonomic walking margins.
   - `base_cost_inr` (INTEGER): Estimated Indian Rupee cost.
   - `style_tag` (TEXT): Modern, Minimalist, Scandinavian, Industrial, Contemporary.
2. **`room_presets`**:
   - `id` (TEXT, PK), `room_type` (TEXT), `name` (TEXT).
   - `room_width_m`, `room_length_m` (REAL): Metric dimensions.
   - `furniture_state_json` (TEXT): Encoded furniture positions and orientations.
   - `normalized_geometry_json` (TEXT): Unit-square coordinates for aspect ratio transfer.
   - `expert_ergonomic_score` (REAL): Baseline score.
3. **`replay_buffer_store`**:
   - Stores 133-D transitions $(s, a, r, s', d)$ for offline DQN bootstrapping.

---

## 4. Viva Defense FAQ & Architectural Justifications

### Q1: Why use SQLite instead of SQLAlchemy or PostgreSQL?
**Answer**: SmartSpace AI is engineered as an edge-ready, single-tenant architectural prototype. Using Python's native `sqlite3` eliminates external database daemon dependencies, eliminates ORM serialization overhead, guarantees zero configuration on new machines, and ensures atomic ACID transactions with trivial backup/reset capabilities.

### Q2: Why does the system use a 2D heuristic projection rather than full 3D reconstruction (e.g. NeRF / Gaussian Splatting)?
**Answer**: 3D NeRFs and uncalibrated monocular depth models require multi-gigabyte GPU environments and introduce latency of 15–45 seconds per image. SmartSpace's 2D YOLO + heuristic ground projection operates in under 300 ms on a standard CPU, extracting functional furniture presence while leaving precise geometric positioning to the SAT and A* solvers.

### Q3: How does the system handle missing model checkpoints?
**Answer**: The entire recommendation and vision pipeline adheres to **Graceful Degradation**:
- If YOLO weights (`.pt` or `.onnx`) are absent, the system logs `"[SmartSpace] Vision model skipped, engaging template fallback"` and serves the curated aspect-ratio matched preset bundle (HTTP 200).
- If the DQN `.npz` checkpoint is absent, the optimizer executes candidate spatial reward search directly over the 133-D environment, ensuring layout improvement without model crash.

### Q4: How is responsive layout health communicated to the user?
**Answer**: The Studio interface uses **Progressive Disclosure**:
- The CAD canvas occupies the full central viewport.
- A consolidated top status bar displays a unified **Layout Health** badge (overall ergonomic score), an inline **Cost vs. Budget** tracker, and circulation chips.
- Deep stylistic advice and layout principles are organized in a slide-over drawer toggled via the **Design Insights** button, keeping the primary workspace distraction-free.
- The bottom furniture palette is constrained to `h-64` ($256\,\text{px}$) with internal scrolling, preventing vertical viewport overflow on standard 1080p displays.
