import unittest
from unittest.mock import patch

from weapon_detection.notifications import notifier


class NotificationLocationTests(unittest.TestCase):
    def message(self, location, **settings):
        alert = dict(
            id=1,
            summary={"knife": 1},
            source_name="Cam_01",
            source_type="camera",
            location=location,
            created_at="2026-11-12T10:00:00",
        )
        with patch.object(notifier.db, "get_settings", return_value=settings):
            return notifier.build_message(alert)

    def test_system_site_and_camera_location_have_separate_fields(self):
        message = self.message("Phòng 601", site_name="Cơ sở PTIT", site_address="Đường A, Hà Nội")
        self.assertIn("Địa điểm: Cơ sở PTIT", message)
        self.assertIn("Địa chỉ: Đường A, Hà Nội", message)
        self.assertIn("Vị trí camera: Phòng 601", message)
        self.assertIn("Nguồn: Cam_01 (camera)", message)

    def test_missing_camera_location_keeps_system_site(self):
        message = self.message("", site_name="Cơ sở PTIT", site_address="")
        self.assertIn("Địa điểm: Cơ sở PTIT", message)
        self.assertIn("Chưa khai báo vị trí chi tiết", message)
        self.assertNotIn("Địa chỉ:", message)


if __name__ == "__main__":
    unittest.main()
