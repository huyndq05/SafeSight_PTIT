import threading
import unittest
from unittest.mock import Mock

import numpy as np

from weapon_detection import config
from weapon_detection.detection.model import WeaponDetector


class CascadeTests(unittest.TestCase):
    def setUp(self):
        self.detector = WeaponDetector.__new__(WeaponDetector)
        self.detector._lock = threading.Lock()
        self.frame = np.zeros((200, 200, 3), np.uint8)
        self.proposal = dict(label="knife", conf=0.6, box=(50, 50, 90, 90))
        self.verified = dict(label="knife", conf=0.8, box=(10, 10, 50, 50))

    def test_crop_confirmation_maps_coordinates_back(self):
        self.detector._predict = Mock(side_effect=[[self.proposal], [self.verified]])
        result = self.detector.detect(self.frame, cascade=True)
        self.assertEqual(result[0]["box"], (50, 50, 90, 90))
        self.assertEqual(result[0]["label"], "knife")
        self.assertEqual(self.detector._predict.call_args.args[0].shape, (60, 60, 3))

    def test_rejects_wrong_class_and_spatially_unrelated_verification(self):
        for candidate in [
            {**self.verified, "label": "pistol"},
            {**self.verified, "box": (0, 0, 5, 5)},
        ]:
            self.detector._predict = Mock(side_effect=[[self.proposal], [candidate]])
            self.assertEqual(self.detector.detect(self.frame, cascade=True), [])

    def test_strong_detection_bypasses_crop(self):
        self.detector._predict = Mock(return_value=[{**self.proposal, "conf": 0.95}])
        self.assertEqual(len(self.detector.detect(self.frame, cascade=True)), 1)
        self.detector._predict.assert_called_once()

    def test_lower_proposal_can_be_rescued_by_verified_crop(self):
        self.detector._predict = Mock(
            side_effect=[[{**self.proposal, "conf": 0.4}], [{**self.verified, "conf": 0.9}]]
        )
        self.assertEqual(len(self.detector.detect(self.frame, cascade=True)), 1)

    def test_verification_work_is_bounded(self):
        proposals = [{**self.proposal, "box": (i * 50, 50, i * 50 + 30, 90)} for i in range(3)]
        self.detector._predict = Mock(side_effect=[proposals, [], []])
        self.assertEqual(self.detector.detect(self.frame, cascade=True), [])
        self.assertEqual(self.detector._predict.call_count, 1 + config.CASCADE_MAX_VERIFY)

    def test_disabled_preserves_single_pass_and_class_thresholds(self):
        self.detector._predict = Mock(return_value=[self.proposal])
        self.assertEqual(
            self.detector.detect(self.frame, class_thresholds={"knife": 0.7}, cascade=False), []
        )
        self.detector._predict.assert_called_once()

    def test_empty_proposals_do_not_run_verifier(self):
        self.detector._predict = Mock(return_value=[])
        self.assertEqual(self.detector.detect(self.frame, cascade=True), [])
        self.detector._predict.assert_called_once()


if __name__ == "__main__":
    unittest.main()
