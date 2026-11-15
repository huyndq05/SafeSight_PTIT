"""Shared annotation contract for OpenCV streams and browser overlays."""

import math

COLORS = {
    "axe": (40, 160, 255),
    "baseball_bat": (255, 170, 40),
    "hammer": (200, 80, 220),
    "knife": (0, 170, 255),
    "machete": (60, 220, 110),
    "pistol": (60, 90, 255),
    "rifle": (180, 70, 70),
    "sword": (255, 90, 180),
    "stick": (220, 220, 40),
    "spear": (180, 120, 40),
}
COLORS = dict.fromkeys(COLORS, (94, 197, 34))
DETECTION_STYLE = {
    "reference_width": 960,
    "line_width": 4,
    "font_size": 18,
    "label_height": 28,
    "padding": 4,
    "text_color": "#ffffff",
    "default_color": "#ff0000",
    "colors": {label: "#%02x%02x%02x" % (r, g, b) for label, (b, g, r) in COLORS.items()},
}


def detection_label(detection):
    confidence = min(1.0, max(0.0, float(detection["conf"])))
    return f"{detection['label']} {math.floor(confidence * 100 + 0.5)}%"
