import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weapon_detection import config
from weapon_detection.storage import db
import weapon_detection.web.app as web


class StaffAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(config, "DB_PATH", Path(self.temp.name) / "auth.db")
        self.db_patch.start()
        self.auth_patch = patch.dict(web.app.config, AUTH_REQUIRED=True)
        self.auth_patch.start()
        db.init()
        self.client = web.app.test_client()

    def tearDown(self):
        self.auth_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def token(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def admin(self):
        self.client.post(
            "/login",
            data=dict(
                csrf=self.token(),
                username="admin",
                display_name="Quan tri",
                password="TestPassword123!",
            ),
        )
        response = self.client.post(
            "/login", data=dict(csrf=self.token(), username="admin", password="TestPassword123!")
        )
        self.assertEqual(response.status_code, 302)

    def test_requires_authentication_and_csrf(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.get("/api/settings").status_code, 401)
        self.assertEqual(self.client.post("/login", data={"username": "admin"}).status_code, 400)
        self.admin()
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.put("/api/settings", json={"sound": False}).status_code, 400)

    def test_create_employee_switch_shift_and_record_identity(self):
        self.admin()
        with self.client.session_transaction() as session:
            csrf = session["csrf"]
        response = self.client.post(
            "/accounts",
            data=dict(
                csrf=csrf, username="ca2", display_name="Nhan vien ca 2", password="Employee123!"
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.client.post("/logout", data={"csrf": csrf})
        self.assertEqual(self.client.get("/api/settings").status_code, 401)
        self.client.post(
            "/login", data=dict(csrf=self.token(), username="ca2", password="Employee123!")
        )
        self.assertEqual(self.client.get("/accounts").status_code, 403)
        with self.client.session_transaction() as session:
            csrf = session["csrf"]
        response = self.client.put(
            "/api/settings", json={"sound": False}, headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 200)
        with db._db() as connection:
            record = connection.execute(
                "SELECT password_hash FROM users WHERE username=?", ("ca2",)
            ).fetchone()
            self.assertNotEqual(record["password_hash"], "Employee123!")
            info = connection.execute("SELECT info FROM logs ORDER BY id DESC LIMIT 1").fetchone()[
                "info"
            ]
            self.assertEqual(info, "Nhan vien ca 2")

    def test_personal_preferences_validate_persist_and_reset(self):
        self.admin()
        with self.client.session_transaction() as session:
            csrf = session["csrf"]
        headers = {"X-CSRF-Token": csrf}
        original = db.get_settings()
        response = self.client.put(
            "/api/preferences",
            json={"theme": "dark", "box_width": 7, "density": "compact", "color_knife": "#ff2244"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/preferences").get_json()["box_width"], 7)
        self.assertEqual(self.client.get("/api/preferences").get_json()["color_knife"], "#ff2244")
        self.assertEqual(
            self.client.put(
                "/api/preferences", json={"color_knife": "red"}, headers=headers
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                "/api/preferences", json={"box_width": 100}, headers=headers
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                "/api/preferences", json={"show_fps": "false"}, headers=headers
            ).status_code,
            400,
        )
        self.client.post(
            "/accounts",
            data=dict(csrf=csrf, username="other", display_name="Other", password="Employee123!"),
        )
        self.client.post("/logout", data={"csrf": csrf})
        self.client.post(
            "/login", data=dict(csrf=self.token(), username="other", password="Employee123!")
        )
        self.assertEqual(self.client.get("/api/preferences").get_json()["theme"], "light")
        self.assertEqual(self.client.get("/api/preferences").get_json()["color_knife"], "#22c55e")
        with self.client.session_transaction() as session:
            csrf = session["csrf"]
        self.client.put("/api/preferences", json={"theme": "dark"}, headers={"X-CSRF-Token": csrf})
        reset = self.client.put(
            "/api/preferences", json={"reset": True}, headers={"X-CSRF-Token": csrf}
        ).get_json()
        self.assertEqual(reset["theme"], "light")
        self.assertEqual(db.get_settings(), original)


if __name__ == "__main__":
    unittest.main()
