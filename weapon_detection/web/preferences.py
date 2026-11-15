import json
import re
from flask import g, request, jsonify, abort
from weapon_detection.storage import db
from weapon_detection import config

DEFAULTS = dict(
    theme="light",
    density="standard",
    font_size="medium",
    sidebar="auto",
    camera_columns="auto",
    show_camera_name=True,
    show_location=True,
    show_fps=True,
    show_status=True,
    box_width=4,
    label_size=18,
    label_content="both",
    reduce_motion=False,
)
DEFAULTS.update({f"color_{label}": "#22c55e" for label in config.MODEL_CLASSES})
ENUMS = dict(
    theme=("light", "dark"),
    density=("compact", "standard", "spacious"),
    font_size=("small", "medium", "large"),
    sidebar=("auto", "expanded", "collapsed"),
    camera_columns=("auto", "1", "2", "3", "4"),
    label_content=("both", "name", "confidence", "none"),
)


def get_preferences():
    result = dict(DEFAULTS)
    if getattr(g, "user", None):
        with db._db() as connection:
            row = connection.execute(
                "SELECT value FROM user_preferences WHERE user_id=?", (g.user["id"],)
            ).fetchone()
        if row:
            result.update(json.loads(row["value"]))
    return result


def install(app):
    @app.route("/api/preferences", methods=["GET", "PUT"])
    def api_preferences():
        current = get_preferences()
        if request.method == "PUT":
            if not getattr(g, "user", None):
                abort(401)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                abort(400)
            if data.get("reset") is True:
                current = dict(DEFAULTS)
            else:
                for key, value in data.items():
                    if key not in DEFAULTS:
                        return jsonify(error="Unknown preference: " + key), 400
                    if key.startswith("color_"):
                        valid = (
                            isinstance(value, str)
                            and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None
                        )
                    elif key in ENUMS:
                        valid = value in ENUMS[key]
                    elif type(DEFAULTS[key]) is bool:
                        valid = type(value) is bool
                    else:
                        valid = type(value) is int and (
                            1 <= value <= 10 if key == "box_width" else 12 <= value <= 32
                        )
                    if not valid:
                        return jsonify(error="Invalid preference: " + key), 400
                    current[key] = value
            with db._db() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO user_preferences VALUES(?,?)",
                    (g.user["id"], json.dumps(current)),
                )
        return jsonify(current)
