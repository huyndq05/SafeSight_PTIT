import unittest

from weapon_detection.detection.streams import DetectionTracker


class ScreenTrackingTests(unittest.TestCase):
    def test_display_grace_survives_many_fast_detector_misses(self):
        tracker = DetectionTracker(miss_grace=0.6)
        tracker.update([{"label": "knife", "conf": 0.8, "box": (10, 10, 40, 40)}], now=1.0)
        for index in range(1, 16):
            self.assertEqual(len(tracker.update([], now=1 + index / 30)), 1)
        self.assertEqual(tracker.update([], now=1.61), [])

    def test_display_grace_does_not_keep_box_over_different_object(self):
        tracker = DetectionTracker(miss_grace=0.6)
        box = (10, 10, 40, 40)
        tracker.update([{"label": "knife", "conf": 0.8, "box": box}], now=1.0)
        result = tracker.update([{"label": "pistol", "conf": 0.9, "box": box}], now=1.1)
        self.assertEqual([item["label"] for item in result], ["pistol"])

    def test_screen_tolerates_short_detection_gaps_but_expires(self):
        tracker = DetectionTracker(ttl=0.8, max_misses=4)
        detection = {"label": "knife", "conf": 0.8, "box": (10, 10, 40, 40)}
        tracker.update([detection], now=1.0)
        for timestamp in [1.15, 1.30, 1.45]:
            self.assertEqual(len(tracker.update([], now=timestamp)), 1)
        self.assertEqual(tracker.update([], now=1.60), [])

    def test_stalled_inference_does_not_leave_permanent_boxes(self):
        tracker = DetectionTracker(ttl=0.8, max_misses=4)
        tracker.update([{"label": "knife", "conf": 0.8, "box": (10, 10, 40, 40)}], now=1.0)
        self.assertEqual(tracker.current(now=1.81), [])


if __name__ == "__main__":
    unittest.main()
