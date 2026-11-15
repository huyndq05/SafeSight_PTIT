from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "ss_final_2.pt"
CASCADE_ENABLED = False
CASCADE_PROPOSAL_RATIO = 0.7
CASCADE_DIRECT_CONF = 0.85
CASCADE_VERIFY_IMGSZ = 320
CASCADE_MAX_VERIFY = 2
CASCADE_CROP_PADDING = 0.25
CASCADE_MAX_RESULT_AGE = 1.0
MODEL_CLASSES = (
    "axe",
    "baseball_bat",
    "hammer",
    "pistol",
    "knife",
    "sword",
    "rifle",
    "machete",
    "stick",
    "spear",
)
CLASS_THRESHOLD_SETTINGS = {label: f"{label}_conf_threshold" for label in MODEL_CLASSES}
CLASS_ENABLED_SETTINGS = {label: f"{label}_enabled" for label in MODEL_CLASSES}
DEFAULT_CLASS_THRESHOLDS = dict.fromkeys(MODEL_CLASSES, 0.5)
DEFAULT_CLASS_THRESHOLDS.update(knife=0.40, hammer=0.45, pistol=0.40, stick=0.45)
DETECTION_SETTINGS_PROFILE_VERSION = 5
ALERT_DIR = BASE_DIR / "data" / "alerts"
VIDEO_DIR = BASE_DIR / "data" / "videos"
DB_PATH = BASE_DIR / "data" / "weapon_guard.db"
MAX_DEMO_VIDEO_BYTES = 512 * 1024 * 1024
HOST, PORT = "127.0.0.1", 5000


DEFAULT_SETTINGS = {
    "theme": "light",
    "site_name": "Test Site",
    "site_address": "",
    "site_lat": 21.0285,
    "site_lon": 105.8542,
    "operator": "Operator 1",
    "conf_threshold": 0.5,
    **{key: DEFAULT_CLASS_THRESHOLDS[label] for label, key in CLASS_THRESHOLD_SETTINGS.items()},
    **{key: True for key in CLASS_ENABLED_SETTINGS.values()},
    "confirm_frames": 2,
    "alert_cooldown": 15,
    "imgsz": 960,
    "detail_scan": False,
    "detect_fps": 45,
    "sound": True,
    "telegram_enabled": False,
    "telegram_token": "",
}


DEFAULT_SOURCES = [
    {
        "id": "cam01",
        "name": "Cam 01",
        "type": "camera",
        "url": "0",
        "location": "Cổng chính",
        "lat": None,
        "lon": None,
        "enabled": 1,
    },
]
