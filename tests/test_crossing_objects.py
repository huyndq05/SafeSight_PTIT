import unittest

from weapon_detection.detection.model import _suppress_cross_class_duplicates
from weapon_detection.detection.streams import DetectionTracker


def detection(label, x, y=10):
    return {"label": label, "conf": 0.9, "box": (x, y, x + 30, y + 30)}


class CrossingObjectsTests(unittest.TestCase):
    def test_label_jump_cannot_drag_existing_track_to_other_object(self):
        tracker = DetectionTracker(max_misses=4)
        tracker.update([detection("knife", 10), detection("pistol", 150)], now=1.0)
        result = tracker.update([detection("knife", 10), detection("pistol", 10)], now=1.1)
        pistol = next(item for item in result if item["label"] == "pistol")
        self.assertEqual(pistol["box"], (150, 10, 180, 40))
        self.assertEqual(len(tracker._tracks), 2)

    def test_crossing_different_classes_recover_after_occlusion(self):
        tracker = DetectionTracker(max_misses=4)
        for index, x in enumerate([10, 40, 70, 100, 130, 160]):
            result = tracker.update(
                [detection("knife", x), detection("pistol", 100)], now=1 + index * 0.15
            )
        by_label = {item["label"]: item for item in result}
        self.assertEqual(set(by_label), {"knife", "pistol"})
        self.assertGreater(by_label["knife"]["box"][0], 140)
        self.assertAlmostEqual(by_label["pistol"]["box"][0], 100, delta=2)

    def test_missing_box_is_hidden_when_another_object_occupies_it(self):
        tracker = DetectionTracker(max_misses=4)
        tracker.update([detection("knife", 100), detection("pistol", 100)], now=1.0)
        result = tracker.update([detection("knife", 100)], now=1.1)
        self.assertEqual([item["label"] for item in result], ["knife"])
        result = tracker.update([detection("knife", 160), detection("pistol", 100)], now=1.2)
        self.assertEqual({item["label"] for item in result}, {"knife", "pistol"})

    def test_near_identical_duplicate_boxes_still_choose_higher_confidence(self):
        result = _suppress_cross_class_duplicates(
            [detection("knife", 10), {**detection("pistol", 11), "conf": 0.7}]
        )
        self.assertEqual([item["label"] for item in result], ["knife"])


if __name__ == "__main__":
    unittest.main()
