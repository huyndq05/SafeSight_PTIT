import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from weapon_detection import config
from weapon_detection.detection import streams
from weapon_detection.detection.model import draw_detections
from weapon_detection.detection.presentation import detection_label, DETECTION_STYLE
import weapon_detection.web.app as web


class SharedDetectionTests(unittest.TestCase):
    def setUp(self):
        auth_patch = patch.dict(web.app.config, AUTH_REQUIRED=False)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)

    def test_simplified_camera_feed_keeps_detection_boxes(self):
        worker = Mock(seq=1)
        worker.get_jpeg.return_value = b"jpeg"
        with patch.dict(streams.workers, {"simple-test": worker}, clear=True):
            response = web.app.test_client().get("/video_feed/simple-test?simple=1", buffered=False)
            next(iter(response.response))
            self.assertFalse(worker.get_jpeg.call_args.args[0]["hide_boxes"])
            response.close()

    def test_live_worker_and_demo_endpoint_pass_identical_model_options(self):
        frame = np.zeros((100, 180, 3), dtype=np.uint8)
        settings = dict(config.DEFAULT_SETTINGS, knife_conf_threshold=0.73, imgsz=640)
        source = dict(id="shared-test", name="Test", type="camera", url="0", enabled=1)
        camera = Mock()
        worker = streams.StreamWorker(source, camera, Mock(), Mock())
        worker._raw, worker._raw_seq, worker._raw_ts = frame, 1, time.monotonic()
        camera.detect.side_effect = lambda *args, **kwargs: worker.stop() or []
        with patch.object(streams, "get_detection_settings", return_value=settings):
            worker._detect_loop()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "fixture.mp4").write_bytes(b"fixture")
            demo = Mock()
            demo.detect.return_value = []
            with (
                patch.object(config, "VIDEO_DIR", root),
                patch.object(
                    web.db, "get_source", return_value=dict(source, url="demo:fixture.mp4")
                ),
                patch.object(web, "detector", demo),
                patch.object(streams, "get_detection_settings", return_value=settings),
                patch.object(streams, "process_demo_detections", return_value=[]),
            ):
                response = web.app.test_client().post(
                    "/api/sources/shared-test/frame",
                    data=cv2.imencode(".jpg", frame)[1].tobytes(),
                    content_type="image/jpeg",
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(camera.detect.call_args.args[1:], demo.detect.call_args.args[1:])
            self.assertEqual(camera.detect.call_args.kwargs, demo.detect.call_args.kwargs)

    def test_browser_receives_the_actual_server_profile(self):
        html = web.app.test_client().get("/").get_data(as_text=True)
        value = re.search(
            r'<script id="detection-style" type="application/json">(.*?)</script>', html, re.DOTALL
        ).group(1)
        self.assertEqual(json.loads(value), DETECTION_STYLE)

    def test_top_edge_label_stays_visible_and_uses_percent(self):
        frame = np.zeros((100, 180, 3), dtype=np.uint8)
        detection = dict(label="knife", conf=0.925, box=(160, 0, 179, 80))
        draw_detections(frame, [detection])
        self.assertEqual(detection_label(detection), "knife 93%")
        self.assertTrue(frame[:28, :160].any(), "Top-edge label should render inside image bounds")
