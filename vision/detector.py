"""
SmartSpace AI — Vision-to-State Coordinate Mapping Pipeline
=============================================================
Bridges the gap between **2D image pixels** from YOLO detections and the
**normalised real-world metric dimensions** consumed by the DQN environment.

Pipeline stages
~~~~~~~~~~~~~~~
1. **Image ingestion** — Accepts ``PIL.Image``, raw bytes, or a file path.
2. **YOLO inference** — Delegates to ``vision.yolo_model.YOLOInteriorDetector``
   for bounding-box detection.
3. **Pixel → metric mapping** — Each detection's ``(x1, y1, x2, y2)`` pixel
   bbox is mapped into the room's metric coordinate system using the
   user-supplied ``room_dimensions`` (width, length in metres) and the
   image resolution.
4. **Annotated image** — Draws coloured bounding boxes (palette from
   ``config.CLASS_COLORS``) and class labels, then encodes the result as a
   JPEG Base64 string for the frontend preview.
5. **Room state assembly** — Produces a dict of ``initial_furniture``,
   ``door``, and ``windows`` ready to be fed into ``InteriorEnv``.

Connection to the rest of the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Instantiated once in ``app.py`` as the global ``VISION_EXTRACTOR`` singleton.
``routes/projects.py`` calls ``process_room_image`` when the user uploads a
room photo in the project wizard.  The returned furniture list and 133-D
state vector are then passed to the studio canvas.
"""
import io
import os
import base64
import logging
from typing import Dict, Any, List, Tuple
from PIL import Image, ImageDraw, ImageOps

from config import FURNITURE_SPECS, CLASS_COLORS
from vision.yolo_model import YOLOInteriorDetector

class VisionStateExtractor:
    """
    Coordinates YOLO detection on an uploaded room photo,
    draws bounding box overlays, and converts detections into an interior environment state.
    """
    def __init__(self, model_path: str = "data/models/yolo_interior.pt", auto_download: bool = True):
        """Load local custom weights or automatically fetch a pretrained detector."""
        self.detector = YOLOInteriorDetector(model_path, auto_download=auto_download)
        
    def process_room_image(self, image_input, room_dimensions: Dict[str, float] = None) -> Dict[str, Any]:
        """Return real image detections or explicit, recoverable fallback metadata.

        Input may be a PIL image, encoded bytes, data URL or local path; room
        dimensions are metres. On decoding or inference failure, furniture is
        empty so the caller can use its room-type preset. No boxes are invented.
        """
        try:
            result = self._process_room_image(image_input, room_dimensions)
            has_furniture = bool(result["room_state"]["initial_furniture"])
            result["fallback_used"] = not has_furniture
            result["fallback_reason"] = (
                "YOLO weights are unavailable." if not self.detector.available else
                "No furniture objects were detected." if not has_furniture else None
            )
            return result
        except Exception:
            logging.getLogger(__name__).exception("Room photo processing failed; using starter furniture")
            return {
                "success": True, "detected_count": 0, "detections": [],
                "annotated_image": None,
                "room_state": {"initial_furniture": []},
                "model_available": self.detector.available,
                "model_backend": self.detector.engine_type,
                "model_name": self.detector.model_path.name,
                "fallback_used": True,
                "fallback_reason": "The room photo could not be processed. Starter furniture was used.",
            }

    def _process_room_image(self, image_input, room_dimensions: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Accepts PIL.Image, file path, or bytes.
        Returns:
            - detections: List of detected objects with bounding boxes
            - annotated_image_b64: JPEG Base64 image with colored bounding boxes & labels
            - room_state: Quantified room configuration ready for DQN optimization
        """
        if isinstance(image_input, str):
            if os.path.exists(image_input):
                image_source = image_input
            elif image_input.startswith("data:image"):
                # Data URL
                _, encoded = image_input.split(",", 1)
                data = base64.b64decode(encoded, validate=True)
                if len(data) > 10 * 1024 * 1024:
                    raise ValueError("Photo exceeds 10 MB.")
                image_source = io.BytesIO(data)
            else:
                raise ValueError("Expected a local image path or data URL.")
        elif isinstance(image_input, bytes):
            if len(image_input) > 10 * 1024 * 1024:
                raise ValueError("Photo exceeds 10 MB.")
            image_source = io.BytesIO(image_input)
        else:
            image_source = None

        if image_source is not None:
            with Image.open(image_source) as source:
                if source.format not in {"JPEG", "PNG"}:
                    raise ValueError("Choose a JPG or PNG image.")
                if source.width * source.height > 20_000_000:
                    raise ValueError("Photo exceeds 20 megapixels.")
                img = ImageOps.exif_transpose(source).convert("RGB")
        else:
            img = ImageOps.exif_transpose(image_input).convert("RGB")

        # Keep inference responsive and the studio's persisted preview compact.
        img.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
            
        # 1. Run YOLO object detection
        detections = self.detector.predict(img)
        
        # 2. Render visual annotations on the image
        annotated_img = img.copy()
        draw = ImageDraw.Draw(annotated_img)
        
        for det in detections:
            cls_name = det["class_name"]
            conf = det["confidence"]
            color = CLASS_COLORS.get(cls_name, "#3b82f6")
            x1, y1, x2, y2 = det["bbox_xyxy"]
            
            # Draw bounding box
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Label tag
            label_text = f"{cls_name.upper()} {conf:.2f}"
            text_bg = [x1, max(0, y1 - 20), x1 + len(label_text) * 8 + 12, max(20, y1)]
            draw.rectangle(text_bg, fill=color)
            draw.text((x1 + 4, max(2, y1 - 18)), label_text, fill=(255, 255, 255))
            
        # Convert annotated image to Base64
        buffered = io.BytesIO()
        annotated_img.save(buffered, format="JPEG", quality=78, optimize=True)
        img_b64 = "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # 3. Convert detections to Quantified Room State for DQN
        room_state = self._convert_detections_to_room_state(detections, room_dimensions)
        
        return {
            "success": True,
            "detected_count": len(detections),
            "detections": detections,
            "annotated_image": img_b64,
            "room_state": room_state,
            "model_available": self.detector.available,
            "model_backend": self.detector.engine_type,
            "model_name": self.detector.model_path.name
        }

    def _convert_detections_to_room_state(self, detections: List[Dict[str, Any]],
                                          room_dimensions: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Maps image detections to real-world metric space (meters)
        Default room dimensions: 4.8m width x 4.0m length
        """
        room_dimensions = room_dimensions or {}
        room_w = max(1.0, float(room_dimensions.get("width", 4.8)))
        room_l = max(1.0, float(room_dimensions.get("length", 4.0)))
        room_h = max(2.0, float(room_dimensions.get("height", 2.8)))
        
        door_info = {"wall": "south", "offset": 0.8, "width": 0.9}
        windows = []
        furniture = []
        
        item_counters: Dict[str, int] = {}
        
        for det in detections:
            cls_name = det["class_name"]
            cx, cy, nw, nh = det["bbox_norm"]
            
            # Estimate metric floor coordinates from normalized image coordinates
            metric_x = round(cx * room_w, 2)
            metric_y = round((1.0 - cy) * room_l, 2) # Perspective invert for top-down floorplan
            
            if cls_name == "door":
                # Determine closest wall
                door_info = {
                    "wall": "south" if cy > 0.6 else "west",
                    "offset": max(0.2, min(room_w - 1.0, metric_x)),
                    "width": 0.9
                }
            elif cls_name == "window":
                windows.append({
                    "wall": "north" if cy < 0.4 else "east",
                    "offset": max(0.2, min(room_w - 1.5, metric_x)),
                    "width": 1.4
                })
            else:
                specs = FURNITURE_SPECS.get(cls_name, FURNITURE_SPECS["chair"])
                count = item_counters.get(cls_name, 0) + 1
                item_counters[cls_name] = count
                
                # Metric clamp within room
                fw = specs["width"]
                fd = specs["depth"]
                clamped_x = max(fw/2 + 0.1, min(room_w - fw/2 - 0.1, metric_x))
                clamped_y = max(fd/2 + 0.1, min(room_l - fd/2 - 0.1, metric_y))
                
                furniture.append({
                    "id": f"{cls_name}_{count}",
                    "type": cls_name,
                    "x": round(clamped_x, 2),
                    "y": round(clamped_y, 2),
                    "width": fw,
                    "depth": fd,
                    "height": specs["height"],
                    "rotation": 0,
                    "cost": specs["base_cost"],
                    "preferred_wall": specs["preferred_wall"],
                    "label": f"{specs['label']} #{count}"
                })
                
        if not windows:
            windows.append({"wall": "north", "offset": 1.6, "width": 1.5})
            
        return {
            "room_type": "detected_room",
            "dimensions": {"width": room_w, "length": room_l, "height": room_h},
            "door": door_info,
            "windows": windows,
            "initial_furniture": furniture,
            "budget": 35000.0
        }
