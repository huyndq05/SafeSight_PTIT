import json
import math
import sqlite3
import threading
from collections import Counter
from contextlib import contextmanager, closing
from datetime import datetime, timedelta

from weapon_detection import config
from weapon_detection.labels import normalize_label, normalize_summary, normalize_text

_lock = threading.RLock()
_settings = {}


@contextmanager
def _db():
    with _lock:
        c = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def now():
    return datetime.now().isoformat(timespec="seconds")


def init():
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, name TEXT, type TEXT, url TEXT,
            location TEXT, lat REAL, lon REAL, enabled INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, handled_at TEXT, handled_by TEXT, status TEXT,
            source_id TEXT, source_name TEXT, source_type TEXT, location TEXT, lat REAL, lon REAL,
            weapons TEXT, summary TEXT, total INTEGER, max_conf REAL, image TEXT,
            detections TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS alert_evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL, image TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alert_events(id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER, ts TEXT, text TEXT);
        CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, level TEXT, subject TEXT, info TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL, password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS user_preferences(user_id INTEGER PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mobile_devices(id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, chat_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1);
        """)
        device_columns = {row["name"] for row in c.execute("PRAGMA table_info(mobile_devices)")}
        if "enabled" not in device_columns:
            c.execute("ALTER TABLE mobile_devices ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
        alert_columns = {row["name"] for row in c.execute("PRAGMA table_info(alerts)")}
        if "detections" not in alert_columns:
            c.execute("ALTER TABLE alerts ADD COLUMN detections TEXT NOT NULL DEFAULT '[]'")
        for column in ("notification_status", "notification_info"):
            if column not in alert_columns:
                c.execute(f"ALTER TABLE alerts ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        for column in ("review_reason", "actual_label", "review_note"):
            if column not in alert_columns:
                c.execute(f"ALTER TABLE alerts ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        c.execute("""UPDATE alerts SET notification_status='failed',
            notification_info='Phiên gửi bị gián đoạn. Kiểm tra bên nhận trước khi thử lại.'
            WHERE notification_status='sending'""")
        evidence_columns = {row["name"] for row in c.execute("PRAGMA table_info(alert_evidence)")}
        if "detections" not in evidence_columns:
            c.execute("ALTER TABLE alert_evidence ADD COLUMN detections TEXT NOT NULL DEFAULT '[]'")
        if "captured_at" not in evidence_columns:
            c.execute("ALTER TABLE alert_evidence ADD COLUMN captured_at TEXT")
        for k, v in config.DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, json.dumps(v)))
        profile = c.execute(
            "SELECT value FROM settings WHERE key='detection_profile_version'"
        ).fetchone()
        profile_version = json.loads(profile["value"]) if profile else 0
        if profile_version < config.DETECTION_SETTINGS_PROFILE_VERSION:
            if profile_version < 3:
                for key in (
                    "conf_threshold",
                    *config.CLASS_THRESHOLD_SETTINGS.values(),
                    "confirm_frames",
                    "imgsz",
                    "detect_fps",
                ):
                    c.execute(
                        "INSERT OR REPLACE INTO settings VALUES(?,?)",
                        (key, json.dumps(config.DEFAULT_SETTINGS[key])),
                    )
                c.execute("DELETE FROM settings WHERE key='gun_conf_threshold'")
            else:
                detect_fps = c.execute(
                    "SELECT value FROM settings WHERE key='detect_fps'"
                ).fetchone()
                if detect_fps and json.loads(detect_fps["value"]) == 30:
                    c.execute(
                        "INSERT OR REPLACE INTO settings VALUES(?,?)",
                        ("detect_fps", json.dumps(config.DEFAULT_SETTINGS["detect_fps"])),
                    )
            c.execute(
                "INSERT OR REPLACE INTO settings VALUES(?,?)",
                (
                    "detection_profile_version",
                    json.dumps(config.DETECTION_SETTINGS_PROFILE_VERSION),
                ),
            )
        legacy_chat_id = c.execute(
            "SELECT value FROM settings WHERE key='telegram_chat_id'"
        ).fetchone()
        if legacy_chat_id:
            chat_id = str(json.loads(legacy_chat_id["value"])).strip()
            if chat_id:
                c.execute(
                    "INSERT OR IGNORE INTO mobile_devices(name, chat_id, created_at) VALUES(?,?,?)",
                    ("Thiết bị đã cấu hình", chat_id, now()),
                )
            c.execute("DELETE FROM settings WHERE key='telegram_chat_id'")
        if not c.execute("SELECT 1 FROM sources").fetchone():
            for s in config.DEFAULT_SOURCES:
                c.execute(
                    "INSERT INTO sources VALUES(:id,:name,:type,:url,:location,:lat,:lon,:enabled)",
                    s,
                )
    _load_settings()


def _load_settings():
    with _db() as c:
        rows = c.execute("SELECT key,value FROM settings").fetchall()
    _settings.clear()
    _settings.update(config.DEFAULT_SETTINGS)
    _settings.update(
        {r["key"]: json.loads(r["value"]) for r in rows if r["key"] in config.DEFAULT_SETTINGS}
    )


def get_settings():
    return dict(_settings)


def set_settings(data):
    for key in config.CLASS_ENABLED_SETTINGS.values():
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f"{key} must be true or false")
    thresholds = {}
    for key in config.CLASS_THRESHOLD_SETTINGS.values():
        if key not in data:
            continue
        try:
            value = float(data[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key} phải là số từ 0 đến 1") from None
        if isinstance(data[key], bool) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{key} phải là số từ 0 đến 1")
        thresholds[key] = value

    with _db() as c:
        for k, default in config.DEFAULT_SETTINGS.items():
            if k not in data:
                continue
            try:
                if k in thresholds:
                    v = thresholds[k]
                elif isinstance(default, bool):
                    v = bool(data[k])
                elif isinstance(default, int):
                    v = int(float(data[k]))
                elif isinstance(default, float):
                    v = float(data[k])
                else:
                    v = str(data[k])
            except (TypeError, ValueError):
                continue
            c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, json.dumps(v)))
    _load_settings()
    return get_settings()


def read_detection_settings():
    """Read persisted settings for the standalone screen process without writes."""
    settings = dict(config.DEFAULT_SETTINGS)
    if config.DB_PATH.is_file():
        with closing(sqlite3.connect(config.DB_PATH.as_uri() + "?mode=ro", uri=True)) as connection:
            settings.update(
                {
                    key: json.loads(value)
                    for key, value in connection.execute("SELECT key,value FROM settings")
                    if key in config.DEFAULT_SETTINGS
                }
            )
    return settings


def read_enabled_classes():
    settings = read_detection_settings()
    return [
        label for label, key in config.CLASS_ENABLED_SETTINGS.items() if settings.get(key, True)
    ]


def list_mobile_devices():
    with _db() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT id, name, chat_id, created_at, enabled FROM mobile_devices ORDER BY id"
            )
        ]


def add_mobile_device(name, chat_id):
    with _db() as c:
        cur = c.execute(
            "INSERT INTO mobile_devices(name, chat_id, created_at) VALUES(?,?,?)",
            (name, chat_id, now()),
        )
        return dict(
            c.execute(
                "SELECT id, name, chat_id, created_at, enabled FROM mobile_devices WHERE id=?",
                (cur.lastrowid,),
            ).fetchone()
        )


def update_mobile_device(device_id, name=None, enabled=None):
    updates = []
    values = []
    if name is not None:
        updates.append("name=?")
        values.append(name)
    if enabled is not None:
        updates.append("enabled=?")
        values.append(int(enabled))
    if not updates:
        return None
    values.append(device_id)
    with _db() as c:
        cur = c.execute(
            f"UPDATE mobile_devices SET {', '.join(updates)} WHERE id=?",
            values,
        )
        if not cur.rowcount:
            return None
        return dict(
            c.execute(
                "SELECT id, name, chat_id, created_at, enabled FROM mobile_devices WHERE id=?",
                (device_id,),
            ).fetchone()
        )


def delete_mobile_device(device_id):
    with _db() as c:
        cur = c.execute("DELETE FROM mobile_devices WHERE id=?", (device_id,))
        return cur.rowcount > 0


def list_sources():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM sources ORDER BY type, name")]


def get_source(sid):
    with _db() as c:
        r = c.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def save_source(s):
    with _db() as c:
        c.execute(
            "INSERT OR REPLACE INTO sources VALUES(:id,:name,:type,:url,:location,:lat,:lon,:enabled)",
            s,
        )


def delete_source(sid):
    with _db() as c:
        c.execute("DELETE FROM sources WHERE id=?", (sid,))


def _alert(c, r):
    d = dict(r)
    d["weapons"] = [
        {**weapon, "label": normalize_label(weapon["label"])} for weapon in json.loads(d["weapons"])
    ]
    d["summary"] = normalize_summary(json.loads(d["summary"]))
    d["detections"] = [
        {**detection, "label": normalize_label(detection["label"])}
        for detection in json.loads(d.get("detections") or "[]")
    ]
    d["events"] = [
        dict(e)
        for e in c.execute(
            "SELECT ts,text FROM alert_events WHERE alert_id=? ORDER BY id", (d["id"],)
        )
    ]
    for event in d["events"]:
        event["text"] = normalize_text(event["text"])
    d["evidence_images"] = []
    for evidence in c.execute(
        "SELECT image,detections,captured_at FROM alert_evidence WHERE alert_id=? ORDER BY id",
        (d["id"],),
    ):
        d["evidence_images"].append(
            {
                "image": evidence["image"],
                "detections": [
                    {**detection, "label": normalize_label(detection["label"])}
                    for detection in json.loads(evidence["detections"] or "[]")
                ],
                "captured_at": evidence["captured_at"],
            }
        )
    return d


def _event(c, aid, text):
    c.execute("INSERT INTO alert_events(alert_id,ts,text) VALUES(?,?,?)", (aid, now(), text))


def create_alert(src, dets, image, evidence_images=()):
    weapons = [{"label": normalize_label(d["label"]), "conf": d["conf"]} for d in dets]
    summary = dict(Counter(weapon["label"] for weapon in weapons))
    serialized_detections = json.dumps(
        [
            {
                "label": normalize_label(detection["label"]),
                "conf": detection["conf"],
                **({"box": list(detection["box"])} if detection.get("box") is not None else {}),
            }
            for detection in dets
        ]
    )
    with _db() as c:
        cur = c.execute(
            """INSERT INTO alerts(created_at,status,source_id,source_name,source_type,location,lat,lon,
               weapons,summary,total,max_conf,image,detections) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                now(),
                "pending",
                src["id"],
                src["name"],
                src["type"],
                src.get("location") or "",
                src.get("lat"),
                src.get("lon"),
                json.dumps(weapons),
                json.dumps(summary),
                len(dets),
                max(d["conf"] for d in dets),
                image,
                serialized_detections,
            ),
        )
        _event(c, cur.lastrowid, f"Phát hiện {', '.join(f'{n} {k}' for k, n in summary.items())}")
        c.executemany(
            "INSERT INTO alert_evidence(alert_id,image) VALUES(?,?)",
            ((cur.lastrowid, evidence_image) for evidence_image in evidence_images),
        )
        return cur.lastrowid


def add_alert_evidence(aid, image, detections, captured_at):
    serialized_detections = json.dumps(
        [
            {
                "label": normalize_label(detection["label"]),
                "conf": detection["conf"],
                **({"box": list(detection["box"])} if detection.get("box") is not None else {}),
            }
            for detection in detections
        ]
    )
    with _db() as c:
        if not c.execute("SELECT 1 FROM alerts WHERE id=?", (aid,)).fetchone():
            return False
        c.execute(
            "INSERT INTO alert_evidence(alert_id,image,detections,captured_at) VALUES(?,?,?,?)",
            (aid, image, serialized_detections, captured_at.isoformat(timespec="seconds")),
        )
        return True


def list_alerts(group="pending", limit=200):
    where = {
        "pending": "status IN ('pending','confirmed','dispatched')",
        "history": "status!='pending'",
        "all": "1=1",
    }[group]
    order = "ASC" if group == "pending" else "DESC"
    with _db() as c:
        return [
            _alert(c, r)
            for r in c.execute(
                f"SELECT * FROM alerts WHERE {where} ORDER BY id {order} LIMIT ?", (limit,)
            )
        ]


def get_alert(aid):
    with _db() as c:
        r = c.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
        return _alert(c, r) if r else None


def export_alerts(status="all"):
    filters = {
        "all": "1=1",
        "processed": "status!='pending'",
        **{
            key: "status=?"
            for key in ("pending", "confirmed", "dispatched", "completed", "deleted")
        },
    }
    if status not in filters:
        raise ValueError("Invalid status")
    with _db() as c:
        parameters = (status,) if filters[status] == "status=?" else ()
        return [
            _alert(c, row)
            for row in c.execute(
                "SELECT * FROM alerts WHERE " + filters[status] + " ORDER BY id DESC", parameters
            )
        ]


def review_false_alarm(aid, by, reason, actual_label="", note=""):
    with _db() as c:
        c.execute("BEGIN IMMEDIATE")
        result = c.execute(
            """UPDATE alerts SET status='deleted',handled_at=?,handled_by=?,
            review_reason=?,actual_label=?,review_note=? WHERE id=? AND notification_status!='sending'""",
            (now(), by, reason, actual_label, note, aid),
        )
        if result.rowcount:
            _event(c, aid, f"Nhận diện sai bởi {by}")
            _event(
                c,
                aid,
                f"Ghi chú ({by}): Lý do nhận diện sai: {reason}"
                + (f"; Nhãn thực tế: {actual_label}" if actual_label else "")
                + (f"; {note}" if note else ""),
            )
        return result.rowcount > 0


def set_status(aid, status, by):
    transitions = {
        "confirmed": ("pending",),
        "dispatched": ("pending", "confirmed"),
        "completed": ("confirmed", "dispatched"),
        "deleted": ("pending",),
    }
    if status not in transitions:
        return False
    with _db() as c:
        placeholders = ",".join("?" for _ in transitions[status])
        cur = c.execute(
            f"UPDATE alerts SET status=?,handled_at=?,handled_by=? WHERE id=? AND status IN ({placeholders}) AND notification_status!='sending'",
            (status, now(), by, aid, *transitions[status]),
        )
        if cur.rowcount:
            names = {
                "confirmed": "Đã xác nhận",
                "dispatched": "Đã gửi thông báo",
                "completed": "Đã hoàn tất",
                "deleted": "Nhận diện sai",
            }
            _event(c, aid, f"{names[status]} bởi {by}")
        return cur.rowcount > 0


def begin_dispatch(aid, by):
    with _db() as c:
        cur = c.execute(
            """UPDATE alerts SET status='confirmed', notification_status='sending',
            handled_at=?, handled_by=? WHERE id=? AND status IN ('pending','confirmed')
            AND notification_status!='sending'""",
            (now(), by, aid),
        )
        if cur.rowcount:
            _event(c, aid, f"Xác nhận và yêu cầu gửi thông báo bởi {by}")
        return cur.rowcount > 0


def finish_dispatch(aid, delivered, info, logged_only=False):
    with _db() as c:
        c.execute(
            """UPDATE alerts SET status=?, notification_status=?, notification_info=?
            WHERE id=? AND notification_status='sending'""",
            (
                "dispatched" if delivered else "confirmed",
                "sent" if delivered else "logged" if logged_only else "failed",
                info,
                aid,
            ),
        )
        _event(c, aid, info)


def purge_alert(aid, by):
    """Remove an alert without assigning any recognition verdict."""
    with _db() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute(
            "SELECT image,notification_status FROM alerts WHERE id=?", (aid,)
        ).fetchone()
        if row is None:
            return None
        if row["notification_status"] == "sending":
            return False
        images = {
            row["image"],
            *(
                r["image"]
                for r in c.execute("SELECT image FROM alert_evidence WHERE alert_id=?", (aid,))
            ),
        }
        c.execute("DELETE FROM alert_evidence WHERE alert_id=?", (aid,))
        c.execute("DELETE FROM alert_events WHERE alert_id=?", (aid,))
        c.execute("DELETE FROM alerts WHERE id=?", (aid,))
        c.execute(
            "INSERT INTO logs(ts,level,subject,info) VALUES(?,?,?,?)",
            (now(), "INFO", f"Xóa cảnh báo #{aid}", by),
        )
        return [
            image
            for image in images
            if image
            and not c.execute(
                "SELECT 1 FROM alerts WHERE image=? UNION ALL SELECT 1 FROM alert_evidence WHERE image=? LIMIT 1",
                (image, image),
            ).fetchone()
        ]


def clear_pending(by):
    with _db() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM alerts WHERE status='pending'")]
        for i in ids:
            c.execute(
                "UPDATE alerts SET status='deleted',handled_at=?,handled_by=? WHERE id=?",
                (now(), by, i),
            )
            _event(c, i, f"Nhận diện sai (xử lý hàng loạt) bởi {by}")
    return len(ids)


def add_note(aid, text, by):
    with _db() as c:
        if not c.execute("SELECT 1 FROM alerts WHERE id=?", (aid,)).fetchone():
            return False
        _event(c, aid, f"Ghi chú ({by}): {text}")
        return True


def log(level, subject, info=""):
    with _db() as c:
        c.execute(
            "INSERT INTO logs(ts,level,subject,info) VALUES(?,?,?,?)", (now(), level, subject, info)
        )


def list_logs(limit=200):
    with _db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))]
    for row in rows:
        row["subject"] = normalize_text(row["subject"])
        row["info"] = normalize_text(row["info"])
    return rows


def stats(days=7):
    if days not in (7, 30):
        raise ValueError("Chỉ hỗ trợ 7 hoặc 30 ngày")
    with _db() as c:

        def q(sql, *args):
            return c.execute(sql, args).fetchone()[0]

        today = datetime.now().strftime("%Y-%m-%d")
        out = {
            "today": q("SELECT COUNT(*) FROM alerts WHERE created_at>=?", today),
            "total": q("SELECT COUNT(*) FROM alerts"),
        }
        for st in ("pending", "confirmed", "dispatched", "completed", "deleted"):
            out[st] = q("SELECT COUNT(*) FROM alerts WHERE status=?", st)
        out["notification_failures"] = q(
            "SELECT COUNT(*) FROM alerts WHERE status='confirmed' AND notification_status='failed'"
        )
        out["days"] = days
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        out["period_total"] = q("SELECT COUNT(*) FROM alerts WHERE created_at>=?", since)
        out["period_status"] = {
            row["status"]: row["count"]
            for row in c.execute(
                "SELECT status, COUNT(*) AS count FROM alerts WHERE created_at>=? GROUP BY status",
                (since,),
            )
        }
        out["by_source"] = [
            dict(row)
            for row in c.execute(
                """SELECT source_id, source_name, COUNT(*) AS count FROM alerts
            WHERE created_at>=? GROUP BY source_id ORDER BY count DESC, source_id LIMIT 5""",
                (since,),
            )
        ]
        per_day = []
        for i in range(days - 1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            row = {"date": d[5:]}
            for st in ("dispatched", "deleted", "pending", "confirmed", "completed"):
                row[st] = q(
                    "SELECT COUNT(*) FROM alerts WHERE substr(created_at,1,10)=? AND status=?",
                    d,
                    st,
                )
            per_day.append(row)
        weapons = Counter()
        for r in c.execute("SELECT summary FROM alerts WHERE created_at>=?", (since,)):
            weapons.update(normalize_summary(json.loads(r[0])))
        out["per_day"], out["by_weapon"] = per_day, dict(weapons)
    out["recent"] = list_alerts("all", 5)
    return out
