"""
Unit Tests for SmartSpace AI Vision Module & State Extractor
"""
import unittest
from unittest.mock import patch
from PIL import Image

from vision.detector import VisionStateExtractor

class TestVisionModule(unittest.TestCase):
    def setUp(self):
        self.extractor = VisionStateExtractor("data/models/test-absent-model.pt", auto_download=False)

    def test_vision_pipeline(self):
        # Create a blank test image
        img = Image.new("RGB", (640, 640), (230, 230, 230))
        result = self.extractor.process_room_image(img)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["detected_count"], 0)
        self.assertTrue(result["fallback_used"])
        self.assertIn("unavailable", result["fallback_reason"])
        self.assertIn("annotated_image", result)
        self.assertIn("room_state", result)
        
        # Verify room state contains required fields
        room_state = result["room_state"]
        self.assertIn("dimensions", room_state)
        self.assertIn("door", room_state)
        self.assertIn("windows", room_state)
        self.assertIn("initial_furniture", room_state)

    def test_corrupt_payload_uses_fallback(self):
        with self.assertLogs("vision.detector", level="ERROR"):
            result = self.extractor.process_room_image(b"this is not an image")
        self.assertTrue(result["success"])
        self.assertTrue(result["fallback_used"])
        self.assertIsNone(result["annotated_image"])

    def test_inference_exception_uses_fallback(self):
        with patch.object(self.extractor.detector, "predict", side_effect=RuntimeError("model failure")):
            with self.assertLogs("vision.detector", level="ERROR"):
                result = self.extractor.process_room_image(Image.new("RGB", (64, 64)))
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["detected_count"], 0)

    def test_empty_inference_uses_fallback(self):
        self.extractor.detector.available = True
        with patch.object(self.extractor.detector, "predict", return_value=[]):
            result = self.extractor.process_room_image(Image.new("RGB", (64, 64)))
        self.assertEqual(result["fallback_reason"], "No furniture objects were detected.")

    def test_detection_maps_to_metric_state(self):
        detection = {
            "class_name": "chair", "confidence": 0.91,
            "bbox_xyxy": [200, 200, 400, 400], "bbox_norm": [0.5, 0.5, 0.3125, 0.3125],
        }
        self.extractor.detector.available = True
        with patch.object(self.extractor.detector, "predict", return_value=[detection]):
            result = self.extractor.process_room_image(Image.new("RGB", (640, 640)), {"width": 6, "length": 4})
        self.assertFalse(result["fallback_used"])
        item = result["room_state"]["initial_furniture"][0]
        self.assertEqual((item["x"], item["y"]), (3, 2))
        self.assertTrue(result["annotated_image"].startswith("data:image/jpeg;base64,"))

if __name__ == '__main__':
    unittest.main()
