
import json
import math
import sqlite3
import threading
from collections import Counter
from contextlib import contextmanager
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
                        "confirm_frames", "imgsz", "detect_fps"):
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
                ("detection_profile_version",
                 json.dumps(config.DETECTION_SETTINGS_PROFILE_VERSION)),
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
                c.execute("INSERT INTO sources VALUES(:id,:name,:type,:url,:location,:lat,:lon,:enabled)", s)
    _load_settings()


def _load_settings():
    with _db() as c:
        rows = c.execute("SELECT key,value FROM settings").fetchall()
    _settings.clear()
    _settings.update(config.DEFAULT_SETTINGS)
    _settings.update({r["key"]: json.loads(r["value"]) for r in rows if r["key"] in config.DEFAULT_SETTINGS})


def get_settings():
    return dict(_settings)


def set_settings(data):
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


def list_mobile_devices():
    with _db() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, name, chat_id, created_at, enabled FROM mobile_devices ORDER BY id"
        )]


def add_mobile_device(name, chat_id):
    with _db() as c:
        cur = c.execute(
            "INSERT INTO mobile_devices(name, chat_id, created_at) VALUES(?,?,?)",
            (name, chat_id, now()),
        )
        return dict(c.execute(
            "SELECT id, name, chat_id, created_at, enabled FROM mobile_devices WHERE id=?",
            (cur.lastrowid,),
        ).fetchone())


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
        return dict(c.execute(
            "SELECT id, name, chat_id, created_at, enabled FROM mobile_devices WHERE id=?",
            (device_id,),
        ).fetchone())


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
        c.execute("INSERT OR REPLACE INTO sources VALUES(:id,:name,:type,:url,:location,:lat,:lon,:enabled)", s)


def delete_source(sid):
    with _db() as c:
        c.execute("DELETE FROM sources WHERE id=?", (sid,))


def _alert(c, r):
    d = dict(r)
    d["weapons"] = [
        {**weapon, "label": normalize_label(weapon["label"])}
        for weapon in json.loads(d["weapons"])
    ]
    d["summary"] = normalize_summary(json.loads(d["summary"]))
    d["detections"] = [
        {**detection, "label": normalize_label(detection["label"])}
        for detection in json.loads(d.get("detections") or "[]")
    ]
    d["events"] = [dict(e) for e in c.execute(
        "SELECT ts,text FROM alert_events WHERE alert_id=? ORDER BY id", (d["id"],))]
    for event in d["events"]:
        event["text"] = normalize_text(event["text"])
    d["evidence_images"] = []
    for evidence in c.execute(
            "SELECT image,detections,captured_at FROM alert_evidence WHERE alert_id=? ORDER BY id",
            (d["id"],)):
        d["evidence_images"].append({
            "image": evidence["image"],
            "detections": [
                {**detection, "label": normalize_label(detection["label"])}
                for detection in json.loads(evidence["detections"] or "[]")
            ],
            "captured_at": evidence["captured_at"],
        })
    return d


def _event(c, aid, text):
    c.execute("INSERT INTO alert_events(alert_id,ts,text) VALUES(?,?,?)", (aid, now(), text))


def create_alert(src, dets, image, evidence_images=()):
    weapons = [
        {"label": normalize_label(d["label"]), "conf": d["conf"]}
        for d in dets
    ]
    summary = dict(Counter(weapon["label"] for weapon in weapons))
    serialized_detections = json.dumps([
        {
            "label": normalize_label(detection["label"]),
            "conf": detection["conf"],
            **({"box": list(detection["box"])} if detection.get("box") is not None else {}),
        }
        for detection in dets
    ])
    with _db() as c:
        cur = c.execute(
            """INSERT INTO alerts(created_at,status,source_id,source_name,source_type,location,lat,lon,
               weapons,summary,total,max_conf,image,detections) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (now(), "pending", src["id"], src["name"], src["type"], src.get("location") or "",
             src.get("lat"), src.get("lon"), json.dumps(weapons), json.dumps(summary),
             len(dets), max(d["conf"] for d in dets), image, serialized_detections))
        _event(c, cur.lastrowid, f"Phát hiện {', '.join(f'{n} {k}' for k, n in summary.items())}")
        c.executemany(
            "INSERT INTO alert_evidence(alert_id,image) VALUES(?,?)",
            ((cur.lastrowid, evidence_image) for evidence_image in evidence_images),
        )
        return cur.lastrowid


def add_alert_evidence(aid, image, detections, captured_at):
    serialized_detections = json.dumps([
        {
            "label": normalize_label(detection["label"]),
            "conf": detection["conf"],
            **({"box": list(detection["box"])} if detection.get("box") is not None else {}),
        }
        for detection in detections
    ])
    with _db() as c:
        if not c.execute("SELECT 1 FROM alerts WHERE id=?", (aid,)).fetchone():
            return False
        c.execute(
            "INSERT INTO alert_evidence(alert_id,image,detections,captured_at) VALUES(?,?,?,?)",
            (aid, image, serialized_detections, captured_at.isoformat(timespec="seconds")),
        )
        return True


def list_alerts(group="pending", limit=200):
    where = {"pending": "status='pending'", "history": "status!='pending'", "all": "1=1"}[group]
    order = "ASC" if group == "pending" else "DESC"
    with _db() as c:
        return [_alert(c, r) for r in c.execute(
            f"SELECT * FROM alerts WHERE {where} ORDER BY id {order} LIMIT ?", (limit,))]


def get_alert(aid):
    with _db() as c:
        r = c.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
        return _alert(c, r) if r else None


def set_status(aid, status, by):
    with _db() as c:
        cur = c.execute("UPDATE alerts SET status=?,handled_at=?,handled_by=? WHERE id=? AND status='pending'",
                        (status, now(), by, aid))
        if cur.rowcount:
            _event(c, aid, f"{'Dispatched' if status == 'dispatched' else 'Deleted (false alarm)'} bởi {by}")
        return cur.rowcount > 0


def clear_pending(by):
    with _db() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM alerts WHERE status='pending'")]
        for i in ids:
            c.execute("UPDATE alerts SET status='deleted',handled_at=?,handled_by=? WHERE id=?", (now(), by, i))
            _event(c, i, f"Deleted (clear all) bởi {by}")
    return len(ids)


def add_note(aid, text, by):
    with _db() as c:
        if not c.execute("SELECT 1 FROM alerts WHERE id=?", (aid,)).fetchone():
            return False
        _event(c, aid, f"Ghi chú ({by}): {text}")
        return True


def log(level, subject, info=""):
    with _db() as c:
        c.execute("INSERT INTO logs(ts,level,subject,info) VALUES(?,?,?,?)", (now(), level, subject, info))


def list_logs(limit=200):
    with _db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))]
    for row in rows:
        row["subject"] = normalize_text(row["subject"])
        row["info"] = normalize_text(row["info"])
    return rows


def stats():
    with _db() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        out = {"today": q("SELECT COUNT(*) FROM alerts WHERE created_at>=?", today),
               "total": q("SELECT COUNT(*) FROM alerts")}
        for st in ("pending", "dispatched", "deleted"):
            out[st] = q("SELECT COUNT(*) FROM alerts WHERE status=?", st)
        per_day = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            row = {"date": d[5:]}
            for st in ("dispatched", "deleted", "pending"):
                row[st] = q("SELECT COUNT(*) FROM alerts WHERE substr(created_at,1,10)=? AND status=?", d, st)
            per_day.append(row)
        weapons = Counter()
        for r in c.execute("SELECT summary FROM alerts ORDER BY id DESC LIMIT 500"):
            weapons.update(normalize_summary(json.loads(r[0])))
        out["per_day"], out["by_weapon"] = per_day, dict(weapons)
    out["recent"] = list_alerts("all", 5)
    return out
