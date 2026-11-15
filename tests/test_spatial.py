import threading
import unittest
from unittest.mock import Mock

import numpy as np

from weapon_detection.detection.model import WeaponDetector
from weapon_detection.detection.spatial import detail_views, merge_same_class


class SpatialTests(unittest.TestCase):
    def test_views_cover_frame_and_overlap(self):
        frame = np.zeros((600, 1000, 3), np.uint8)
        views = list(detail_views(frame))
        self.assertEqual(len(views), 4)
        coverage = np.zeros(frame.shape[:2], np.uint8)
        for left, top, crop in views:
            h, w = crop.shape[:2]
            coverage[top : top + h, left : left + w] += 1
        self.assertTrue((coverage > 0).all())
        self.assertTrue((coverage > 1).any())

    def test_merge_does_not_drop_distinct_objects_or_other_classes(self):
        detections = [
            dict(label="knife", conf=0.9, box=(10, 10, 50, 50)),
            dict(label="knife", conf=0.8, box=(11, 11, 51, 51)),
            dict(label="knife", conf=0.7, box=(80, 10, 120, 50)),
            dict(label="pistol", conf=0.6, box=(10, 10, 50, 50)),
        ]
        self.assertEqual(len(merge_same_class(detections)), 3)

    def test_detail_offsets_and_internal_edge_rejection(self):
        detector = WeaponDetector.__new__(WeaponDetector)
        detector._predict = Mock(
            return_value=[
                dict(label="knife", conf=0.8, box=(0, 0, 20, 20)),
                dict(label="knife", conf=0.7, box=(10, 10, 40, 40)),
            ]
        )
        result = detector._detail_proposals(np.zeros((600, 1000, 3), np.uint8), 0.4)
        self.assertIn((360, 220, 390, 250), [item["box"] for item in result])
        self.assertNotIn((350, 210, 370, 230), [item["box"] for item in result])

    def test_detail_off_keeps_single_inference(self):
        detector = WeaponDetector.__new__(WeaponDetector)
        detector._lock = threading.Lock()
        detector._predict = Mock(return_value=[])
        detector.detect(np.zeros((600, 1000, 3), np.uint8), cascade=False)
        detector._predict.assert_called_once()


if __name__ == "__main__":
    unittest.main()
