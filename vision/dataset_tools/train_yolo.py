"""Train a YOLO interior detector and install real weights for the web app."""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from config import TARGET_CLASSES


def _absolute_from_root(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _read_history(csv_path: Path):
    if not csv_path.is_file():
        return []
    history = []
    with csv_path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            try:
                history.append({
                    "epoch": int(float(row.get("epoch", len(history) + 1))),
                    "box_loss": float(row.get("train/box_loss", 0) or 0),
                    "cls_loss": float(row.get("train/cls_loss", 0) or 0),
                    "precision": float(row.get("metrics/precision(B)", 0) or 0),
                    "recall": float(row.get("metrics/recall(B)", 0) or 0),
                    "mAP50": float(row.get("metrics/mAP50(B)", 0) or 0),
                    "mAP50_95": float(row.get("metrics/mAP50-95(B)", 0) or 0),
                })
            except (TypeError, ValueError):
                continue
    return history


def train_yolo_model(data_yaml: str = "data/yolo_dataset/data.yaml",
                     model_cfg: str = "yolo11n.yaml", epochs: int = 50,
                     img_size: int = 640, batch_size: int = 8,
                     output_dir: str = "runs/interior_yolo"):
    """Train from scratch, save model weights, export ONNX, and record true metrics."""
    yaml_path = _absolute_from_root(data_yaml)
    output_path = _absolute_from_root(output_dir)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {yaml_path}")

    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise RuntimeError(
            "Ultralytics is required for YOLO training. Install ultralytics and torch, then retry."
        ) from error

    print(f"Training {model_cfg} from scratch for {len(TARGET_CLASSES)} interior classes.")
    print(f"Dataset config: {yaml_path}")
    model = YOLO(model_cfg)
    model.train(data=str(yaml_path), epochs=epochs, imgsz=img_size, batch=batch_size,
                project=str(output_path), name="train_run", exist_ok=True,
                pretrained=False, plots=True)

    trainer = model.trainer
    run_dir = Path(trainer.save_dir)
    best_weights = Path(trainer.best)
    if not best_weights.is_file():
        raise FileNotFoundError(f"Training completed without best weights: {best_weights}")

    models_dir = PROJECT_ROOT / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    installed_weights = models_dir / "yolo_interior.pt"
    shutil.copy2(best_weights, installed_weights)

    production_model = YOLO(str(installed_weights))
    exported_path = Path(production_model.export(format="onnx", imgsz=img_size))
    installed_onnx = models_dir / "yolo_interior.onnx"
    if exported_path.resolve() != installed_onnx.resolve():
        shutil.copy2(exported_path, installed_onnx)

    history = _read_history(run_dir / "results.csv")
    telemetry = {
        "model": "YOLO interior detector",
        "architecture": model_cfg,
        "from_scratch": True,
        "real_training": True,
        "epochs": len(history),
        "weights": installed_weights.name,
        "onnx": installed_onnx.name,
        "history": history,
    }
    telemetry_path = output_path / "yolo_training_telemetry.json"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    telemetry_path.write_text(json.dumps(telemetry, indent=2), encoding="utf-8")
    print(f"Installed PyTorch weights: {installed_weights}")
    print(f"Installed ONNX weights: {installed_onnx}")
    print(f"Real training telemetry: {telemetry_path}")
    return telemetry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the SmartSpace YOLO interior detector")
    parser.add_argument("--data", default="data/yolo_dataset/data.yaml")
    parser.add_argument("--model", default="yolo11n.yaml")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--output", default="runs/interior_yolo")
    args = parser.parse_args()
    train_yolo_model(args.data, args.model, args.epochs, args.imgsz, args.batch, args.output)
