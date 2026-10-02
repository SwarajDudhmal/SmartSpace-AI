"""
SmartSpace AI — YOLO Interior Object Detection Model
======================================================
Handles loading of YOLO model weights and running 10-class interior object
detection inference.

Supported backends
~~~~~~~~~~~~~~~~~~
1. **Ultralytics** — If the ``ultralytics`` package is installed and a
   ``.pt`` checkpoint exists at ``data/models/yolo_interior.pt``, the
   native Ultralytics YOLO inference engine is used.
2. **ONNX Runtime** — Falls back to an exported ``.onnx`` checkpoint via
   ``onnxruntime`` if Ultralytics is unavailable.
3. **Pretrained fallback** — Downloads ``yolov8n.pt`` via Ultralytics when
   custom checkpoints are absent. Download/loading failure uses room templates.

The 10 target classes match the project's taxonomy defined in ``config.py``:
bed, sofa, chair, table, wardrobe, desk, tv, cabinet, door, window.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Instantiated by ``vision/detector.py`` (``VisionStateExtractor``).
The detector is never called directly by routes — the extractor provides
the higher-level ``process_room_image`` interface.
"""
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from config import TARGET_CLASSES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Keep library settings in the writable project rather than requiring AppData access.
os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / "data/models/ultralytics"))
_MODEL_LOAD_LOCK = Lock()
LOGGER = logging.getLogger(__name__)
CLASS_ALIASES = {"couch": "sofa", "dining table": "table", "television": "tv"}


class YOLOInteriorDetector:
    """Load an interior checkpoint and map PIL images to real detections.

    Results include pixel boxes and normalized centre/size coordinates.
    Missing weights produce an explicit unavailable state and no detections.
    """

    def __init__(self, model_path: Optional[str] = None, auto_download: bool = True):
        """Prefer custom checkpoints; optionally fetch official pretrained weights."""
        requested = Path(model_path) if model_path else Path("data/models/yolo_interior.pt")
        self.model_path = requested if requested.is_absolute() else PROJECT_ROOT / requested
        self.classes = TARGET_CLASSES
        self.loaded_model = None
        self.engine_type = "unavailable"
        self.available = False
        self.input_size = (640, 640)
        self._inference_lock = Lock()
        self.auto_download = auto_download
        with _MODEL_LOAD_LOCK:
            self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Load local weights or download the official COCO checkpoint under a lock."""
        try:
            Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            LOGGER.warning("Could not create YOLO settings directory: %s", error)
        candidates = [self.model_path]
        onnx_path = self.model_path.with_suffix(".onnx")
        if onnx_path not in candidates:
            candidates.append(onnx_path)

        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() == ".pt":
                try:
                    from ultralytics import YOLO
                    self.loaded_model = YOLO(str(path))
                    self.engine_type = "ultralytics"
                    self.available = True
                    self.model_path = path
                    print(f"[YOLO] Loaded weights: {path.name}")
                    return
                except Exception as error:
                    print(f"[YOLO] Could not load {path.name}: {error}")
            elif path.suffix.lower() == ".onnx":
                try:
                    import onnxruntime as ort
                    self.loaded_model = ort.InferenceSession(
                        str(path), providers=ort.get_available_providers()
                    )
                    input_shape = self.loaded_model.get_inputs()[0].shape
                    if len(input_shape) == 4:
                        height, width = input_shape[-2:]
                        self.input_size = (
                            int(width) if isinstance(width, int) else 640,
                            int(height) if isinstance(height, int) else 640,
                        )
                    self.engine_type = "onnx"
                    self.available = True
                    self.model_path = path
                    print(f"[YOLO] Loaded ONNX weights: {path.name}")
                    return
                except Exception as error:
                    print(f"[YOLO] Could not load {path.name}: {error}")

        if self.auto_download:
            try:
                from ultralytics import YOLO
                fallback_path = PROJECT_ROOT / "data/models/yolov8n.pt"
                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                # Ultralytics fetches its official asset when this file is absent.
                model = YOLO(str(fallback_path))
                self.loaded_model = model
                self.model_path = fallback_path
                self.engine_type = "ultralytics"
                self.available = True
                LOGGER.info("Loaded pretrained YOLO weights: %s", fallback_path)
                return
            except Exception as error:
                LOGGER.warning("YOLO download/loading failed; using room templates: %s", error)
        self.loaded_model = None
        self.available = False
        self.engine_type = "unavailable"
        LOGGER.warning("No usable YOLO weights found at %s or %s", self.model_path, onnx_path)

    def predict(self, image: Image.Image, conf_threshold: float = 0.25) -> List[Dict[str, Any]]:
        """Return detections above a confidence threshold for a PIL image.

        Calls are serialized because a shared Ultralytics predictor is mutable.
        Missing weights or inference failures return no detections; the vision
        service supplies fallback metadata to the room builder.
        """
        try:
            if not self.available or self.loaded_model is None or image is None:
                import logging
                logging.getLogger(__name__).warning("[SmartSpace] Vision model skipped, engaging template fallback")
                print("[SmartSpace] Vision model skipped, engaging template fallback")
                return []
            with self._inference_lock:
                return self._predict_available(image, conf_threshold)
        except Exception as error:
            import logging
            logging.getLogger(__name__).warning("[SmartSpace] Vision model skipped, engaging template fallback: %s", error)
            print("[SmartSpace] Vision model skipped, engaging template fallback")
            return []

    def _predict_available(self, image: Image.Image, conf_threshold: float) -> List[Dict[str, Any]]:
        """Run the selected backend under the inference lock; return box dicts."""
        if not self.available or self.loaded_model is None:
            return []
        image = image.convert("RGB")
        if self.engine_type == "ultralytics":
            results = self.loaded_model.predict(image, conf=conf_threshold, device="cpu", verbose=False)[0]
            detections = []
            if results.boxes is None:
                return detections
            for box in results.boxes:
                model_class_id = int(box.cls[0].item())
                model_name = str(results.names[model_class_id]).strip().lower()
                class_name = CLASS_ALIASES.get(model_name, model_name)
                # COCO IDs are not the project's ten-class indices. Its default
                # model supports bed/sofa/chair/table/tv; other classes need training.
                if class_name not in self.classes:
                    continue
                cls_id = self.classes.index(class_name)
                confidence = float(box.conf[0].item())
                xyxy = [float(value) for value in box.xyxy[0].tolist()]
                if not np.isfinite(xyxy).all() or xyxy[2] <= xyxy[0] or xyxy[3] <= xyxy[1]:
                    continue
                detections.append(self._format_detection(cls_id, confidence, xyxy, image.size))
            return sorted(detections, key=lambda item: item["confidence"], reverse=True)
        if self.engine_type == "onnx":
            return self._predict_onnx(image, conf_threshold)
        return []

    def _predict_onnx(self, image: Image.Image, conf_threshold: float) -> List[Dict[str, Any]]:
        """Letterbox a PIL image and return thresholded, NMS-filtered boxes.

        ``conf_threshold`` filters confidence in [0, 1]. Output coordinates
        undo model padding and scaling to recover original-image pixels.
        """
        input_w, input_h = self.input_size
        original_w, original_h = image.size
        scale = min(input_w / original_w, input_h / original_h)
        resized_w, resized_h = int(round(original_w * scale)), int(round(original_h * scale))
        resized = image.resize((resized_w, resized_h), Image.Resampling.BILINEAR)
        canvas = Image.new("RGB", (input_w, input_h), (114, 114, 114))
        pad_x, pad_y = (input_w - resized_w) // 2, (input_h - resized_h) // 2
        canvas.paste(resized, (pad_x, pad_y))

        # **Input normalization:** byte intensities [0,255] become floats [0,1].
        normalized_pixels = np.asarray(canvas, dtype=np.float32) / 255.0
        # **Tensor axes:** HWC -> CHW, then add batch axis -> (1,3,H,W).
        channels_first = np.transpose(normalized_pixels, (2, 0, 1))
        tensor = channels_first[None, ...]
        input_meta = self.loaded_model.get_inputs()[0]
        raw_outputs = self.loaded_model.run(None, {input_meta.name: tensor})
        if not raw_outputs:
            return []
        rows = self._output_rows(np.asarray(raw_outputs[0]))
        if rows.size == 0:
            return []

        boxes: List[List[float]] = []
        scores: List[float] = []
        class_ids: List[int] = []
        for row in rows:
            if row.size == 6:  # Exported with NMS: x1, y1, x2, y2, confidence, class.
                x1, y1, x2, y2, confidence, class_id = row.tolist()
                cls_id = int(class_id)
            else:
                # Standard YOLOv8/11 output has cx, cy, w, h and class scores;
                # YOLOv5 also includes an objectness column.
                if row.size < 5:
                    continue
                cx, cy, width, height = row[:4]
                class_scores = row[4:]
                if class_scores.size == len(self.classes) + 1:
                    objectness = float(class_scores[0])
                    class_scores = class_scores[1:] * objectness
                cls_id = int(np.argmax(class_scores))
                confidence = float(class_scores[cls_id])
                x1, y1 = cx - width / 2, cy - height / 2
                x2, y2 = cx + width / 2, cy + height / 2
            if cls_id < 0 or cls_id >= len(self.classes) or confidence < conf_threshold:
                continue

            # Some exports return normalized coordinates instead of model pixels.
            if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 2.0:
                x1, x2 = x1 * input_w, x2 * input_w
                y1, y2 = y1 * input_h, y2 * input_h
            # **Inverse letterboxing:** subtract padding, divide by resize scale,
            # then clip to the original image's physical pixel boundaries.
            x1 = max(0.0, min(original_w, (x1 - pad_x) / scale))
            x2 = max(0.0, min(original_w, (x2 - pad_x) / scale))
            y1 = max(0.0, min(original_h, (y1 - pad_y) / scale))
            y2 = max(0.0, min(original_h, (y2 - pad_y) / scale))
            if x2 <= x1 or y2 <= y1:
                continue
            boxes.append([x1, y1, x2, y2])
            scores.append(float(confidence))
            class_ids.append(cls_id)

        keep = self._nms(boxes, scores, class_ids, iou_threshold=0.45)
        return [self._format_detection(class_ids[i], scores[i], boxes[i], image.size) for i in keep]

    @staticmethod
    def _output_rows(output: np.ndarray) -> np.ndarray:
        """Convert an ONNX output tensor to candidate rows, or an empty matrix."""
        output = np.squeeze(output)
        if output.ndim == 1:
            output = output[None, :]
        if output.ndim != 2:
            return np.empty((0, 0), dtype=np.float32)
        # YOLO exports commonly use [features, candidates]. Transpose that form.
        if output.shape[0] in (6, 14, 15) and output.shape[1] > output.shape[0]:
            output = output.T
        return output.astype(np.float32, copy=False)

    @staticmethod
    def _nms(boxes: List[List[float]], scores: List[float], class_ids: List[int],
             iou_threshold: float) -> List[int]:
        """Return kept box indices after class-specific nonmaximum suppression.

        Inputs are xyxy pixel boxes, confidence scores, class indices, and an
        intersection-over-union threshold. Higher-confidence boxes win overlaps.
        """
        kept: List[int] = []
        for cls_id in set(class_ids):
            order = sorted((i for i, cls in enumerate(class_ids) if cls == cls_id),
                           key=lambda i: scores[i], reverse=True)
            while order:
                current = order.pop(0)
                kept.append(current)
                x1, y1, x2, y2 = boxes[current]
                area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                remaining = []
                for idx in order:
                    ox1, oy1, ox2, oy2 = boxes[idx]
                    intersection_width = max(0.0, min(x2, ox2) - max(x1, ox1))
                    intersection_height = max(0.0, min(y2, oy2) - max(y1, oy1))
                    intersection = intersection_width * intersection_height
                    other_area = max(0.0, ox2 - ox1) * max(0.0, oy2 - oy1)
                    union = area + other_area - intersection
                    # **IoU:** shared area / combined area, within the same class.
                    intersection_over_union = intersection / union if union > 0 else 0.0
                    if intersection_over_union <= iou_threshold:
                        remaining.append(idx)
                order = remaining
        return sorted(kept, key=lambda i: scores[i], reverse=True)

    def _format_detection(self, cls_id: int, confidence: float, xyxy: List[float],
                          image_size: Tuple[int, int]) -> Dict[str, Any]:
        """Return class metadata plus pixel and normalized boxes for one detection."""
        img_w, img_h = image_size
        x1, y1, x2, y2 = xyxy
        center_x_pixels = (x1 + x2) / 2.0
        center_y_pixels = (y1 + y2) / 2.0
        normalized_center_x = center_x_pixels / img_w
        normalized_center_y = center_y_pixels / img_h
        normalized_width = (x2 - x1) / img_w
        normalized_height = (y2 - y1) / img_h
        normalized_box = (normalized_center_x, normalized_center_y, normalized_width, normalized_height)
        return {
            "class_id": cls_id,
            "class_name": self.classes[cls_id],
            "confidence": round(float(confidence), 3),
            "bbox_xyxy": [round(float(value), 1) for value in xyxy],
            "bbox_norm": [round(float(value), 4) for value in normalized_box],
        }
