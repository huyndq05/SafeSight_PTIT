
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "ss_final_1.pt"
MODEL_CLASSES = (
    "axe", "baseball_bat", "hammer", "pistol", "knife",
    "sword", "rifle", "machete", "stick", "spear",
)
CLASS_THRESHOLD_SETTINGS = {
    label: f"{label}_conf_threshold" for label in MODEL_CLASSES
}
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
    **{key: 0.5 for key in CLASS_THRESHOLD_SETTINGS.values()},
    "confirm_frames": 2,
    "alert_cooldown": 15,
    "imgsz": 320,
    "detect_fps": 45,
    "sound": True,
    "telegram_enabled": False,
    "telegram_token": "",
}


DEFAULT_SOURCES = [
    {"id": "cam01", "name": "Cam 01", "type": "camera", "url": "0",
     "location": "Cổng chính", "lat": None, "lon": None, "enabled": 1},
]
