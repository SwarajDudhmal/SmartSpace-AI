# SmartSpace AI: Vision-Driven DQN Interior Layout Optimization Platform

SmartSpace AI is an interior planning website with a shared design flow, interactive floorplan studio, room evaluation, and layout optimization. Real furniture detection requires trained YOLO weights; when those weights are absent the studio labels photo detection as unavailable and uses a recommended starter layout. The layout optimizer uses a trained DQN checkpoint when present and otherwise performs deterministic spatial search.

---

## 🏛️ System Architecture

```
User Room Photo / Camera
          │
          ▼
┌──────────────────────────────────────────────┐
│       YOLO Interior Vision Front-End        │
│  (10 Classes: bed, sofa, chair, table,       │
│   wardrobe, desk, tv, cabinet, door, window) │
└──────────────────────┬───────────────────────┘
                       │ Quantified Spatial State
                       ▼
┌──────────────────────────────────────────────┐
│        DQN Interior Layout Optimizer         │
│  • Separating Axis Theorem (SAT) Collision   │
│  • A* Walking Path Clearance & Circulation   │
│  • Window Natural Daylight Vectors           │
│  • Ergonomic TV Viewing & Wall Alignments     │
│  • Budget Constraint Optimization            │
└──────────────────────┬───────────────────────┘
                       │ Step-by-Step Trajectory
                       ▼
┌──────────────────────────────────────────────┐
│     Full-Stack Interactive Design Studio     │
│  • Real-Time 2D Architectural Floorplan     │
│  • Interactive 3D WebGL Room (Three.js)      │
│  • Dynamic Animated Layout Convergence       │
│  • Specification & Schedule Export (.txt)    │
└──────────────────────────────────────────────┘
```

---

## 🏷️ YOLO 10-Class Interior Taxonomy

The computer vision front-end is specifically tuned for 10 interior categories:

| ID | Class | Real-World Dim (W × D × H) | Clearance | Base Cost | Wall Preference |
|:--:|:------|:---------------------------|:----------|:----------|:----------------|
| **0** | `bed` | 1.6m × 2.0m × 0.8m | 0.8m front | ₹12,000 | Back to wall |
| **1** | `sofa` | 2.1m × 0.9m × 0.85m | 0.9m front | ₹14,000 | Flexible |
| **2** | `chair` | 0.6m × 0.6m × 0.85m | 0.5m front | ₹1,500 | Flexible |
| **3** | `table` | 1.4m × 0.8m × 0.75m | 0.7m sides | ₹3,500 | Flexible |
| **4** | `wardrobe` | 1.5m × 0.6m × 2.1m | 0.9m front | ₹8,500 | Back to wall |
| **5** | `desk` | 1.3m × 0.65m × 0.75m | 0.8m front | ₹4,200 | Lateral/Back to wall |
| **6** | `tv` | 1.2m × 0.15m × 0.7m | 1.8m front | ₹8,000 | Wall mounted/console |
| **7** | `cabinet` | 1.0m × 0.45m × 0.9m | 0.7m front | ₹3,500 | Back to wall |
| **8** | `door` | 0.9m × 0.15m × 2.1m | 1.0m swing | — | Perimeter wall |
| **9** | `window` | 1.4m × 0.15m × 1.2m | 0.6m light | — | Perimeter wall |

---

## 🚀 Quickstart & Installation

### 1. Requirements
Ensure Python 3.10+ is installed:
```bash
pip install -r requirements.txt
```

For real photo inference, install `pip install -r requirements-vision.txt` using the Python environment that runs Flask. The detector prefers a custom `data/models/yolo_interior.pt` or `.onnx` checkpoint; when absent, Ultralytics automatically downloads `data/models/yolov8n.pt`. Its pretrained labels map to bed, sofa, chair, table and tv. Wardrobe, desk, cabinet, door and window require a custom trained checkpoint. ONNX inference also needs `onnxruntime`. Photo-to-floor coordinates are estimates; missing weights, failed inference or unusable photos use room-type starter furniture.

### 2. Launch the Studio Web Interface
```bash
python app.py
```
Open your browser at: **`http://127.0.0.1:5000`**

### Initialize the furniture and room recommendation database
```bash
python scripts/seed_database.py
```
This creates the SQLite catalog, curated presets, and replay-buffer examples.
The included records are ergonomic-rule seed data, not 3D-FRONT/3D-FUTURE
exports. See [the database and recommendation guide](docs/database-and-recommendations.md)
for schema, importer format, and DQN training details.

---

## 🛠️ Dataset Tools & Training Workflows

### 1. Initialize YOLO Dataset Structure & `data.yaml`
```bash
python vision/dataset_tools/create_dataset.py --path data/yolo_dataset
```
Creates `images/{train,val,test}` and `labels/{train,val,test}` and generates `data.yaml`.

### 2. Generate Synthetic Labeled Training Images
```bash
python vision/dataset_tools/synthetic_gen.py --output data/yolo_dataset --train 30 --val 8 --test 6
```
Generates annotated indoor room images with matching normalized YOLO labels (`class cx cy w h`).

### 3. Remap Public Datasets (Kaggle Architecture, COCO, Roboflow)
```bash
python vision/dataset_tools/remap_dataset.py --src-labels path/to/raw --dst-labels data/yolo_dataset/labels/train
```

### 4. Train YOLO11 from Scratch (Option B)
```bash
python vision/dataset_tools/train_yolo.py --data data/yolo_dataset/data.yaml --epochs 50
```
Trains YOLO11 using `yolo11n.yaml` (random initialization), installs `yolo_interior.pt` and `yolo_interior.onnx` under `data/models`, and writes telemetry from the actual training run. The dataset YAML uses paths relative to its own folder.

### 5. Train the DQN Layout Agent
```bash
python engine/train_dqn.py --episodes 50 --steps 30
```
Trains the Deep Q-Network with multi-objective rewards, then saves `dqn_policy.npz` and training history under `data/models`. The NumPy fallback trains with mini-batch backpropagation as well.

---

## 🧠 Research Paper Formulation (DQN Layout Optimizer)

### Markov Decision Process (MDP)
- **State Space $S$**: Normalized room dimensions $(W, L)$, entry door vector, window daylight vectors, and for each piece of furniture: $[x_i, y_i, w_i, d_i, \theta_i, \text{one\_hot}(c_i), \text{placed}_i]$.
- **Action Space $A$**: Discrete parameterized actions: $\{\pm \Delta X, \pm \Delta Y, +90^\circ \text{ rotation}, \text{Snap to Wall}\}$.
- **Reward Function**:
  $$R = w_{\text{coll}} R_{\text{coll}} + w_{\text{circ}} R_{\text{circ}} + w_{\text{align}} R_{\text{align}} + w_{\text{light}} R_{\text{light}} + w_{\text{ergo}} R_{\text{ergo}} + w_{\text{budget}} R_{\text{budget}}$$

---

## 📂 Project Directory Structure

```
SmartSpace-AI/
├── app.py                      # Flask Server & REST APIs
├── config.py                   # 10 Target Classes, Dimensions & Rules
├── requirements.txt            # Dependencies
├── README.md                   # Documentation
│
├── engine/                     # DQN & Spatial Optimization Engine
│   ├── interior_env.py         # Gymnasium-compatible Interior Design MDP
│   ├── dqn_agent.py            # Deep Q-Network Agent & Trajectory Generator
│   ├── astar_planner.py        # A* Circulation Pathfinding
│   ├── spatial_utils.py        # SAT 2D Collision & Bounding Box Math
│   └── train_dqn.py            # CLI Batch Training for DQN
│
├── vision/                     # YOLO Vision Module
│   ├── detector.py             # Room Image Analyzer & State Converter
│   ├── yolo_model.py           # Multi-backend YOLO Inference
│   └── dataset_tools/
│       ├── create_dataset.py   # Dataset Folder & data.yaml Initializer
│       ├── synthetic_gen.py    # Synthetic Indoor Labeled Data Generator
│       ├── remap_dataset.py    # Kaggle/COCO/Roboflow Class Remapper
│       └── train_yolo.py       # Option B From-Scratch YOLO11 Training
│
├── static/                     # Web Frontend
│   ├── css/style.css           # Glassmorphism Dark Mode Styling
│   └── js/
│       ├── app.js              # Application Coordinator
│       ├── floorplan_canvas.js # Interactive 2D Floorplan & A* Paths
│       ├── room_3d.js          # Three.js 3D WebGL Room Viewer
│       └── charts.js           # DQN & YOLO Training Curves
│
├── templates/
│   └── index.html              # Main Studio Interface
│
├── data/
│   ├── samples/                # Sample Test Room Photos
│   ├── models/                 # Model Weights & Telemetry
│   └── yolo_dataset/           # YOLO Dataset (images & labels)
│
└── tests/                      # Automated Unit Test Suite
    ├── test_spatial.py
    ├── test_astar.py
    ├── test_dqn.py
    └── test_vision.py
```

### Viva refinement and local verification

See [the Viva review guide](docs/VIVA_REVIEW.md) for the annotated SAT/A*/DQN/YOLO walkthrough, background-job API contract, cleanup record and verified demo commands. On this machine, use `.venv-viva\Scripts\python.exe app.py`; the original virtual environments reference Python installations from another computer. The guide clearly distinguishes trained-model inference from the catalogue/spatial fallback.
