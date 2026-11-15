"""Overlapping views preserve small-object detail without changing weights."""

import math


def detail_views(frame):
    height, width = frame.shape[:2]
    if min(height, width) < 320:
        return
    tile_w, tile_h = math.ceil(width * 0.65), math.ceil(height * 0.65)
    for top in (0, height - tile_h):
        for left in (0, width - tile_w):
            yield left, top, frame[top : top + tile_h, left : left + tile_w]


def merge_same_class(detections, iou_threshold=0.5):
    kept = []
    for item in sorted(detections, key=lambda d: d["conf"], reverse=True):
        a = item["box"]
        duplicate = False
        for other in kept:
            if item["label"] != other["label"]:
                continue
            b = other["box"]
            intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
                0, min(a[3], b[3]) - max(a[1], b[1])
            )
            union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
            if union > 0 and intersection / union >= iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept
