"""Regression evidence for SAT/A*, state compatibility and background routes."""
import io
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
from flask import Flask

from engine.astar_planner import AStarPlanner
from engine.interior_env import InteriorEnv
from engine.sat_collision import check_obb_collision, get_rotated_corners, is_within_room
from routes.jobs import JobQueue, jobs_bp, submit_work
from routes.projects import projects_bp
from routes.recommendations import recommendations_bp
from vision.detector import VisionStateExtractor


class GeometryRegressions(unittest.TestCase):
    def test_one_overlapping_projection_does_not_prove_collision(self):
        first = get_rotated_corners(0, 0, 2, 2, 0)
        second = get_rotated_corners(4, 0, 2, 2, 0)
        self.assertFalse(check_obb_collision(first, second))

    def test_touching_and_margin_semantics(self):
        first = get_rotated_corners(0, 0, 2, 2, 0)
        touching = get_rotated_corners(2, 0, 2, 2, 0)
        nearby = get_rotated_corners(2.1, 0, 2, 2, 0)
        self.assertTrue(check_obb_collision(first, touching))
        self.assertFalse(check_obb_collision(first, nearby))
        self.assertTrue(check_obb_collision(first, nearby, margin=0.11))

    def test_rotation_preserves_rectangle_area_and_centre(self):
        corners = get_rotated_corners(2, 4, 3, 1, 37)
        np.testing.assert_allclose(corners.mean(axis=0), [2, 4])
        edge_lengths = np.linalg.norm(np.roll(corners, -1, axis=0) - corners, axis=1)
        np.testing.assert_allclose(edge_lengths, [3, 1, 3, 1])

    def test_astar_cannot_cut_diagonal_corner(self):
        planner = AStarPlanner(3, 3, grid_res=1)
        planner.grid[0, 1] = 1
        planner.grid[1, 0] = 1
        self.assertIsNone(planner.plan_path((0.5, 0.5), (1.5, 1.5)))

    def test_state_encoder_preserves_checkpoint_feature_order(self):
        env = InteriorEnv({"dimensions": {"width": 6, "length": 4}, "budget": 80000,
                           "furniture": [{"type": "chair", "x": 3, "y": 2,
                                          "width": 0.6, "depth": 0.6, "rotation": 90}]})
        state = env.get_state()
        self.assertEqual(state.shape, (133,))
        np.testing.assert_allclose(state[:3], [0.6, 0.4, 8])
        np.testing.assert_allclose(state[5:10], [0.5, 0.5, 0.2, 0.2, 0.25])
        self.assertEqual(state[10:20].sum(), 1)
        self.assertEqual(state[20], 1)
        self.assertTrue(np.all(state[21:] == 0))

    def test_rotation_near_wall_keeps_oriented_box_inside(self):
        env = InteriorEnv({"dimensions": {"width": 4, "length": 4},
                           "furniture": [{"type": "sofa", "x": 1.2, "y": 0.55,
                                          "width": 2.1, "depth": 0.9, "rotation": 0}]})
        env.step(4)
        item = env.furniture[0]
        inside, penetration = is_within_room(item['x'], item['y'], item['width'], item['depth'],
                                            item['rotation'], 4, 4)
        self.assertTrue(inside)
        self.assertAlmostEqual(penetration, 0)


class BackgroundRouteRegressions(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-only-secret"
        self.queue = JobQueue(max_pending=2)
        self.app.extensions["ai_jobs"] = self.queue
        self.app.config["VISION_EXTRACTOR"] = VisionStateExtractor("data/models/test-absent.pt", auto_download=False)
        self.app.config["DQN_AGENT"] = None
        # Keep route tests independent of a populated application database.
        self.catalogue = patch("routes.projects.recommend_designs", return_value={"bundles": []})
        self.catalogue.start()
        self.addCleanup(self.catalogue.stop)
        for bp in (jobs_bp, projects_bp, recommendations_bp):
            self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def tearDown(self):
        self.queue.shutdown()

    def finish(self, response):
        self.assertEqual(response.status_code, 202)
        url = response.get_json()["status_url"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = self.client.get(url)
            if response.status_code != 202:
                return response
            time.sleep(0.01)
        self.fail("Background request did not finish within the test deadline")

    def test_request_returns_before_computation_and_queue_is_bounded(self):
        release = threading.Event()

        def slow_job():
            release.wait(3)
            return {"success": True, "value": 42}

        try:
            with self.app.test_request_context():
                first = self.app.make_response(submit_work(slow_job))
                second = self.app.make_response(submit_work(slow_job))
                rejected = self.app.make_response(submit_work(slow_job))
            self.assertEqual(first.status_code, 202)
            self.assertEqual(second.status_code, 202)
            self.assertEqual(rejected.status_code, 503)
            self.assertEqual(self.client.get(first.get_json()["status_url"]).status_code, 202)
            self.assertEqual(self.client.post('/api/projects', json={"name": "Responsive"}).status_code, 200)
        finally:
            release.set()
        result = self.finish(first)
        self.assertEqual(result.get_json()["value"], 42)

    def test_corrupt_photo_still_prepares_studio_room(self):
        self.app.config["VISION_EXTRACTOR"].detector.available = True
        with self.assertLogs("vision.detector", level="ERROR"):
            response = self.finish(self.client.post("/api/rooms", data={
                "roomName": "Fallback room", "roomType": "Living Room",
                "roomPhoto": (io.BytesIO(b"corrupt photo"), "room.jpg"),
            }))
        self.assertEqual(response.status_code, 200)
        room = response.get_json()["room"]
        self.assertTrue(room["vision_used_starter_furniture"])
        self.assertTrue(room["furniture"])
        self.assertEqual(len(room["state_133d"]), 133)

    def test_missing_weights_prepares_room_with_photo(self):
        response = self.finish(self.client.post("/api/rooms", data={
            "roomType": "Living Room", "roomPhoto": (io.BytesIO(b"photo"), "room.jpg"),
        }))
        self.assertEqual(response.status_code, 200)
        room = response.get_json()["room"]
        self.assertEqual(room["vision_fallback_reason"], "YOLO weights are unavailable.")
        self.assertTrue(room["vision_used_starter_furniture"])
        self.assertEqual(len(room["state_133d"]), 133)

    def test_inference_exception_does_not_fail_room_job(self):
        self.app.config["VISION_EXTRACTOR"].detector.available = True
        with patch.object(self.app.config["VISION_EXTRACTOR"], "process_room_image",
                          side_effect=RuntimeError("inference failed")):
            response = self.finish(self.client.post("/api/rooms", data={
                "roomPhoto": (io.BytesIO(b"photo"), "room.jpg"),
            }))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["room"]["furniture"])

    def test_selected_bundle_is_used_for_room(self):
        furniture = [{"id": "selected_chair", "type": "chair", "x": 1.5, "y": 1.5}]
        with patch("routes.projects.recommend_designs", return_value={"bundles": [
            {"id": "modern-style", "layout": {"furniture": furniture}, "total_cost_inr": 1500},
        ]}):
            response = self.finish(self.client.post("/api/rooms", data={"variation_id": "modern-style"}))
        self.assertEqual(response.status_code, 200)
        room = response.get_json()["room"]
        self.assertEqual(room["selected_bundle_id"], "modern-style")
        self.assertEqual(room["furniture"][0]["id"], "selected_chair")

    def test_worker_exception_becomes_json_failure(self):
        with patch("routes.recommendations.recommend_designs", side_effect=RuntimeError("private details")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.finish(self.client.post("/api/recommendations", json={}))
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["success"])
        self.assertNotIn("private details", response.get_json()["error"])

    def test_invalid_room_returns_400_from_job(self):
        response = self.finish(self.client.post("/api/rooms", data={"width": "nan"}))
        self.assertEqual(response.status_code, 400)

    def test_room_fallback_uses_catalogue_furniture(self):
        furniture = [{"id": "chair_1", "type": "chair", "x": 1.5, "y": 1.5}]
        with patch("routes.projects.recommend_designs", return_value={"bundles": [
            {"layout": {"furniture": furniture}, "total_cost_inr": 1500},
        ]}):
            response = self.finish(self.client.post("/api/rooms", data={"roomType": "Living Room"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["room"]["furniture"][0]["id"], "chair_1")
        self.assertTrue(response.get_json()["room"]["vision_used_starter_furniture"])

    def test_completed_results_are_evicted_instead_of_blocking_new_work(self):
        self.queue.max_results = 1
        with self.app.test_request_context():
            first = self.app.make_response(submit_work(lambda: {"success": True}))
        self.finish(first)
        with self.app.test_request_context():
            second = self.app.make_response(submit_work(lambda: {"success": True}))
        self.assertEqual(second.status_code, 202)
        self.assertEqual(self.client.get(first.get_json()["status_url"]).status_code, 404)

    def test_unknown_job_has_recoverable_message(self):
        self.assertEqual(self.client.get("/api/jobs/missing").status_code, 404)

    def test_malformed_json_is_rejected_before_queueing(self):
        for path in ("/api/recommendations", "/api/optimize", "/api/detect"):
            with self.subTest(path=path):
                response = self.client.post(path, data="{bad", content_type="application/json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.queue.jobs), 0)


    def test_step4_photo_upload_yolo_fallback_returns_200_and_preset_bundles(self):
        response = self.finish(self.client.post("/api/recommendations", data={
            "room_type": "living_room",
            "roomPhoto": (io.BytesIO(b"fake photo data"), "test.jpg"),
        }))
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertTrue(len(data.get("bundles", [])) > 0)

    def test_detect_photo_without_weights_returns_200_fallback(self):
        response = self.finish(self.client.post("/api/detect", data={
            "file": (io.BytesIO(b"fake photo data"), "test.jpg"),
        }))
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertTrue(len(data["room"]["state_133d"]) == 133)
        self.assertTrue(data["room"]["furniture"])


if __name__ == "__main__":
    unittest.main()
