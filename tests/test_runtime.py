import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weapon_detection.runtime import single_instance
import weapon_detection.web.app as web


class SingleInstanceTests(unittest.TestCase):
    def test_second_instance_is_rejected_and_lock_is_released_after_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "app.lock"
            with single_instance(path):
                with self.assertRaises(RuntimeError):
                    with single_instance(path):
                        self.fail("Second instance acquired an active webcam app lock")
            with single_instance(path):
                pass

    def test_duplicate_start_never_initializes_model_or_webcam(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                single_instance(root / "data/safesight.lock"),
                patch.object(web.config, "BASE_DIR", root),
                patch.object(web, "_run_application") as run,
            ):
                with self.assertRaises(RuntimeError):
                    web.main()
                run.assert_not_called()
