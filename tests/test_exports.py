import csv
import io
import json
import tempfile
import unittest
import zipfile
import cv2
import numpy as np
from xml.etree import ElementTree
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from weapon_detection import config
from weapon_detection.storage import db
import weapon_detection.web.app as web


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for patcher in [
            patch.object(config, "DB_PATH", self.root / "test.db"),
            patch.object(config, "ALERT_DIR", self.root),
            patch.dict(web.app.config, AUTH_REQUIRED=False),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)
        db.init()
        self.client = web.app.test_client()
        self.detection = dict(label="knife", conf=0.9, box=(1, 2, 30, 40))
        self.aid = db.create_alert(
            dict(id="s", name="=formula", type="camera"), [self.detection], "initial.jpg"
        )
        (self.root / "initial.jpg").write_bytes(b"original-image")
        (self.root / "follow.jpg").write_bytes(b"evidence-image")
        db.add_alert_evidence(self.aid, "follow.jpg", [self.detection], datetime.now())

    def test_csv_filter_bom_predictions_and_human_review(self):
        db.review_false_alarm(self.aid, "Operator", "Sai loại", "hammer", "Reviewed manually")
        response = self.client.get("/api/alerts/export?status=deleted&format=csv")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["actual_label"], "hammer")
        self.assertEqual(json.loads(rows[0]["predictions_json"])[0]["label"], "knife")
        self.assertTrue(rows[0]["source_name"].startswith("'="))
        empty = self.client.get("/api/alerts/export?status=completed").data.decode("utf-8-sig")
        self.assertEqual(len(list(csv.DictReader(io.StringIO(empty)))), 0)
        self.assertEqual(self.client.get("/api/alerts/export?status=invalid").status_code, 400)

    def test_zip_contains_matching_images_and_metadata(self):
        response = self.client.get("/api/alerts/export?format=zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn("alerts.csv", archive.namelist())
            self.assertEqual(archive.read("images/initial.jpg"), b"original-image")
            self.assertEqual(archive.read("images/follow.jpg"), b"evidence-image")
            self.assertIn("NOT verified training labels", archive.read("README.txt").decode())
        response.close()

    def test_sent_alert_review_retains_delivery_and_never_sends_again(self):
        db.begin_dispatch(self.aid, "Operator")
        db.finish_dispatch(self.aid, True, "sent")
        with patch.object(web.notifier, "send_dispatch") as send:
            response = self.client.post(
                f"/api/alerts/{self.aid}/delete",
                json={
                    "reason": "Sai loại",
                    "actual_label": "hammer",
                    "note": "Búa, không phải dao",
                },
            )
            self.assertEqual(response.status_code, 200)
            send.assert_not_called()
        alert = db.get_alert(self.aid)
        self.assertEqual(alert["notification_status"], "sent")
        self.assertEqual(alert["status"], "deleted")
        self.assertEqual(alert["actual_label"], "hammer")

    def test_excel_contains_embedded_images_and_review_data(self):
        image = np.full((400, 600, 3), 100, np.uint8)
        cv2.imwrite(str(self.root / "initial.jpg"), image)
        cv2.imwrite(str(self.root / "follow.jpg"), image)
        db.review_false_alarm(self.aid, "Reviewer", "Wrong class", "hammer", "Keep this example")
        response = self.client.get("/api/alerts/export?status=deleted&format=xlsx")
        self.assertEqual(response.status_code, 200)
        self.assertIn(".xlsx", response.headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            media = [name for name in archive.namelist() if name.startswith("xl/media/")]
            self.assertGreaterEqual(len(media), 2)
            for name in media:
                self.assertIsNotNone(
                    cv2.imdecode(np.frombuffer(archive.read(name), np.uint8), cv2.IMREAD_COLOR)
                )
            strings = archive.read("xl/sharedStrings.xml").decode()
            self.assertIn("hammer", strings)
            self.assertIn("Reviewer", strings)
            self.assertIn("Keep this example", strings)
            sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            self.assertEqual(len(sheet.findall(".//m:f", ns)), 0)
            self.assertIsNotNone(sheet.find("m:autoFilter", ns))
            drawing = ElementTree.fromstring(archive.read("xl/drawings/drawing1.xml"))
            self.assertEqual(len(drawing), 4)
        response.close()


if __name__ == "__main__":
    unittest.main()
