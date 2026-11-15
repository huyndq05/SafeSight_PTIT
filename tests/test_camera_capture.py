import unittest
from unittest.mock import Mock, patch

import numpy as np

from weapon_detection.detection import streams


class CameraCaptureTests(unittest.TestCase):
    def test_black_driver_buffer_is_rejected_but_dim_scene_is_valid(self):
        frame = np.zeros((90, 120, 3), dtype=np.uint8)
        self.assertTrue(streams._black_placeholder(frame))
        frame[:, 60:] = 8
        self.assertFalse(streams._black_placeholder(frame))

    def test_black_directshow_frames_fall_back_to_media_foundation(self):
        first, second = Mock(), Mock()
        first.read.return_value = (True, np.zeros((90, 120, 3), np.uint8))
        second.read.return_value = (True, np.full((90, 120, 3), 50, np.uint8))
        with (
            patch.object(streams.os, "name", "nt"),
            patch.object(streams.cv2, "VideoCapture", side_effect=[first, second]) as capture,
            patch.object(streams.time, "sleep"),
        ):
            self.assertIs(streams._open(0), second)
        first.release.assert_called_once()
        self.assertEqual(capture.call_args_list[1].args, (0, streams.cv2.CAP_MSMF))

    def test_green_with_black_border_is_not_a_valid_camera_signal(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[60:440, 60:580] = (0, 170, 0)
        self.assertTrue(streams._green_placeholder(frame))

    def test_varied_green_scene_and_dark_image_are_not_rejected(self):
        frame = np.random.default_rng(1).integers(0, 256, (90, 120, 3), dtype=np.uint8)
        self.assertFalse(streams._green_placeholder(frame))
        self.assertFalse(streams._green_placeholder(np.zeros_like(frame)))

    def test_green_backend_falls_back_to_valid_backend(self):
        first, second = Mock(), Mock()
        green = np.zeros((90, 120, 3), np.uint8)
        green[:] = (0, 170, 0)
        first.read.return_value = (True, green)
        second.read.return_value = (True, np.full_like(green, 50))
        with (
            patch.object(streams.os, "name", "nt"),
            patch.object(streams.cv2, "VideoCapture", side_effect=[first, second]),
            patch.object(streams.time, "sleep"),
        ):
            self.assertIs(streams._open(0), second)
        first.release.assert_called_once()

    def test_virtual_camera_uses_native_format(self):
        cap = Mock()
        cap.read.return_value = (True, np.full((2, 2, 3), 50, dtype=np.uint8))
        with (
            patch.object(streams.os, "name", "nt"),
            patch.object(streams.cv2, "VideoCapture", return_value=cap) as capture,
        ):
            self.assertIs(streams._open(1), cap)
        capture.assert_called_once_with(1, streams.cv2.CAP_DSHOW)
        cap.set.assert_not_called()

    def test_open_but_no_frames_falls_back_and_releases_device(self):
        first, second = Mock(), Mock()
        first.read.return_value = (False, None)
        second.read.return_value = (True, np.full((2, 2, 3), 50, dtype=np.uint8))
        with (
            patch.object(streams.os, "name", "nt"),
            patch.object(streams.cv2, "VideoCapture", side_effect=[first, second]) as capture,
            patch.object(streams.time, "sleep"),
        ):
            self.assertIs(streams._open(0), second)
        first.release.assert_called_once()
        self.assertEqual(capture.call_args_list[1].args, (0, streams.cv2.CAP_MSMF))

    def test_file_capture_does_not_consume_first_frame(self):
        cap = Mock()
        with patch.object(streams.cv2, "VideoCapture", return_value=cap):
            self.assertIs(streams._open("video.mp4"), cap)
        cap.read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
