import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from weapon_detection import config
from weapon_detection.storage import db
import weapon_detection.web.app as web


class AlertWorkflowTests(unittest.TestCase):
    def setUp(self):
        auth_patch = patch.dict(web.app.config, AUTH_REQUIRED=False)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(config, "DB_PATH", Path(self.temp.name) / "test.db")
        self.path_patch.start()
        db.init()
        self.client = web.app.test_client()
        self.aid = db.create_alert(
            {"id": "test", "name": "Test camera", "type": "camera"},
            [{"label": "knife", "conf": 0.9, "box": (10, 10, 40, 40)}],
            "test.jpg",
        )

    def tearDown(self):
        self.path_patch.stop()
        self.temp.cleanup()
        db._settings.clear()
        db._settings.update(config.DEFAULT_SETTINGS)

    def post(self, action, **payload):
        return self.client.post(f"/api/alerts/{self.aid}/{action}", json=payload)

    def test_confirm_and_complete_preserve_evidence_and_events(self):
        self.assertEqual(self.post("complete").status_code, 409)
        self.assertEqual(self.post("confirm").status_code, 200)
        self.assertEqual(len(db.list_alerts()), 1)
        self.assertEqual(self.post("complete").status_code, 200)
        self.assertEqual(db.list_alerts(), [])
        a = db.get_alert(self.aid)
        self.assertEqual(a["status"], "completed")
        self.assertEqual(a["image"], "test.jpg")
        self.assertEqual(len(a["events"]), 3)
        self.assertEqual(db.stats()["completed"], 1)

    def test_false_alarm_stores_reason(self):
        self.assertEqual(self.post("delete", reason="Phone, not a weapon").status_code, 200)
        a = db.get_alert(self.aid)
        self.assertEqual(a["status"], "deleted")
        self.assertIn("Phone, not a weapon", a["events"][-1]["text"])
        self.assertEqual(a["image"], "test.jpg")

    def test_purge_removes_alert_without_false_alarm_verdict(self):
        second = db.create_alert(
            {"id": "test", "name": "Other", "type": "camera"},
            [{"label": "knife", "conf": 0.8, "box": (1, 1, 20, 20)}],
            "other.jpg",
        )
        with patch.object(web.config, "ALERT_DIR", Path(self.temp.name)):
            image = Path(self.temp.name) / "test.jpg"
            image.write_bytes(b"fixture")
            response = self.client.delete(f"/api/alerts/{self.aid}")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(image.exists())
        self.assertIsNone(db.get_alert(self.aid))
        self.assertIsNotNone(db.get_alert(second))
        with db._db() as connection:
            self.assertEqual(
                connection.execute('SELECT count(*) FROM alerts WHERE status="deleted"').fetchone()[
                    0
                ],
                0,
            )
        self.assertEqual(self.client.delete(f"/api/alerts/{self.aid}").status_code, 404)

    def test_purge_rejects_alert_while_notification_is_sending(self):
        self.assertTrue(db.begin_dispatch(self.aid, "Test"))
        self.assertEqual(self.client.delete(f"/api/alerts/{self.aid}").status_code, 409)
        self.assertIsNotNone(db.get_alert(self.aid))

    def test_confirmed_alert_can_receive_later_false_alarm_review(self):
        self.post("confirm")
        self.assertEqual(self.post("delete", reason="test").status_code, 200)
        self.assertEqual(db.clear_pending("test"), 0)
        self.assertEqual(db.get_alert(self.aid)["status"], "deleted")

    def test_log_only_does_not_claim_notification_delivered(self):
        with patch.object(web.notifier, "send_dispatch", return_value=(True, "Log only")):
            self.assertEqual(self.post("dispatch").status_code, 200)
        a = db.get_alert(self.aid)
        self.assertEqual((a["status"], a["notification_status"]), ("confirmed", "logged"))

    def test_failed_send_can_retry_and_success_cannot_duplicate(self):
        db.set_settings({"telegram_enabled": True, "telegram_token": "fake-test-token"})
        with patch.object(web.notifier, "send_dispatch", return_value=(False, "Unavailable")):
            self.assertFalse(self.post("dispatch").json["ok"])
        self.assertEqual(db.get_alert(self.aid)["notification_status"], "failed")
        with patch.object(web.notifier, "send_dispatch", return_value=(True, "Delivered")) as send:
            self.assertTrue(self.post("dispatch").json["ok"])
            self.assertEqual(self.post("dispatch").status_code, 409)
            send.assert_called_once()
        self.assertEqual(db.get_alert(self.aid)["status"], "dispatched")
        self.assertEqual(self.post("complete").status_code, 200)

    def test_exception_releases_send_for_retry(self):
        with patch.object(web.notifier, "send_dispatch", side_effect=OSError("Test")):
            self.assertFalse(self.post("dispatch").json["ok"])
        self.assertEqual(db.get_alert(self.aid)["notification_status"], "failed")
        self.assertTrue(db.begin_dispatch(self.aid, "test"))

    def test_simultaneous_send_claim_is_rejected(self):
        self.assertTrue(db.begin_dispatch(self.aid, "test"))
        self.assertFalse(db.begin_dispatch(self.aid, "test"))
        self.assertFalse(db.set_status(self.aid, "completed", "test"))

    def test_restart_recovers_interrupted_send_without_resending(self):
        db.begin_dispatch(self.aid, "test")
        db.init()
        a = db.get_alert(self.aid)
        self.assertEqual(a["notification_status"], "failed")
        self.assertEqual(a["status"], "confirmed")

    def test_unknown_status_and_long_reason_rejected(self):
        self.assertFalse(db.set_status(self.aid, "arbitrary", "test"))
        self.assertEqual(self.post("delete", reason="x" * 501).status_code, 400)
        self.assertEqual(db.get_alert(self.aid)["status"], "pending")

    def test_migration_is_idempotent_and_preserves_existing_alerts(self):
        db.init()
        db.init()
        self.assertEqual(db.get_alert(self.aid)["status"], "pending")
        self.assertEqual(len(db.list_alerts()), 1)

    def test_one_dispatch_confirms_pending_alert_and_delivers_once(self):
        db.set_settings({"telegram_enabled": True, "telegram_token": "fake-test-token"})
        self.assertEqual(db.get_alert(self.aid)["status"], "pending")
        with patch.object(web.notifier, "send_dispatch", return_value=(True, "Delivered")) as send:
            self.assertEqual(self.post("dispatch").status_code, 200)
            self.assertEqual(self.post("dispatch").status_code, 409)
            send.assert_called_once()
        self.assertEqual(db.get_alert(self.aid)["status"], "dispatched")

    def test_dashboard_periods_use_same_scope_for_trend_objects_and_sources(self):
        src = {"id": "older", "name": "Older camera", "type": "camera"}
        old = db.create_alert(src, [{"label": "pistol", "conf": 0.8}], "older.jpg")
        with db._db() as connection:
            connection.execute(
                "UPDATE alerts SET created_at=? WHERE id=?",
                ((datetime.now() - timedelta(days=10)).isoformat(), old),
            )
        seven = self.client.get("/api/stats?days=7").json
        thirty = self.client.get("/api/stats?days=30").json
        self.assertEqual(seven["period_total"], 1)
        self.assertEqual(thirty["period_total"], 2)
        self.assertEqual(len(seven["per_day"]), 7)
        self.assertEqual(len(thirty["per_day"]), 30)
        self.assertNotIn("pistol", seven["by_weapon"])
        self.assertEqual(thirty["by_weapon"]["pistol"], 1)
        self.assertEqual(sum(item["count"] for item in seven["by_source"]), 1)
        self.assertEqual(sum(item["count"] for item in thirty["by_source"]), 2)
        self.assertEqual(
            sum(
                sum(
                    day[key]
                    for key in ("pending", "confirmed", "dispatched", "completed", "deleted")
                )
                for day in thirty["per_day"]
            ),
            thirty["period_total"],
        )

    def test_invalid_dashboard_period_rejected(self):
        for value in ("0", "-1", "999999", "abc"):
            self.assertEqual(self.client.get(f"/api/stats?days={value}").status_code, 400)

    def test_dashboard_notification_failure_count_tracks_retry(self):
        db.begin_dispatch(self.aid, "test")
        db.finish_dispatch(self.aid, False, "Test failure")
        self.assertEqual(db.stats()["notification_failures"], 1)
        db.begin_dispatch(self.aid, "test")
        db.finish_dispatch(self.aid, True, "Delivered")
        self.assertEqual(db.stats()["notification_failures"], 0)


if __name__ == "__main__":
    unittest.main()
