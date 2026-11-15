"""Read-only YOLO dataset audit. Outputs counts and exact duplicate groups."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path

import cv2

CACHED = {}


def inspect(item):
    split, image, label = item
    errors, boxes, classes = [], [], set()
    polygons = 0
    cached = CACHED.get(str(image))
    if cached:
        digest, visual = cached["sha256"], cached["pixels_sha256"]
        if visual is None:
            errors.append("unreadable_image")
    else:
        raw = image.read_bytes()
        import numpy as np

        pixels = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        digest = hashlib.sha256(raw).hexdigest()
        visual = None
        if pixels is None:
            errors.append("unreadable_image")
        else:
            # Equal decoded pixels catches metadata-only differences, not near duplicates.
            visual = hashlib.sha256(str(pixels.shape).encode() + pixels.tobytes()).hexdigest()
    if not label.is_file():
        errors.append("missing_label")
    else:
        for number, line in enumerate(label.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                fields = [float(v) for v in line.split()]
                if not all(math.isfinite(v) for v in fields):
                    raise ValueError("nonfinite values")
                if len(fields) >= 7 and len(fields) % 2 == 1:
                    c = fields[0]
                    xs, ys = fields[1::2], fields[2::2]
                    if not all(0 <= v <= 1 for v in fields[1:]):
                        raise ValueError("polygon coordinates outside image")
                    x, y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
                    w, h = max(xs) - min(xs), max(ys) - min(ys)
                    polygons += 1
                elif len(fields) == 5:
                    c, x, y, w, h = fields
                else:
                    raise ValueError("expected box or polygon")
                if c != int(c) or not 0 <= c < 10:
                    raise ValueError("invalid class ID")
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    raise ValueError("invalid normalized coordinates")
                if (
                    x - w / 2 < -0.001
                    or y - h / 2 < -0.001
                    or x + w / 2 > 1.001
                    or y + h / 2 > 1.001
                ):
                    errors.append(f"box_outside_image:line={number}")
                boxes.append(int(c))
                classes.add(int(c))
            except ValueError as error:
                errors.append(f"line={number}:{error}")
    return dict(
        split=split,
        image=str(image),
        sha256=digest,
        pixels_sha256=visual,
        boxes=boxes,
        classes=sorted(classes),
        polygons=polygons,
        errors=errors,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reuse-hashes",
        type=Path,
        help="Previous manifest for unchanged images ONLY; labels are re-read",
    )
    args = parser.parse_args()
    if args.reuse_hashes:
        with args.reuse_hashes.open(encoding="utf-8") as stream:
            CACHED.update((r["image"], r) for r in map(json.loads, stream))
    items, orphans = [], []
    for split in ("train", "valid", "test"):
        images = sorted(
            p
            for p in (args.root / split / "images").iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp")
        )
        stems = {p.stem for p in images}
        orphans.extend(
            str(p) for p in (args.root / split / "labels").glob("*.txt") if p.stem not in stems
        )
        items.extend((split, p, args.root / split / "labels" / (p.stem + ".txt")) for p in images)
    stats = {
        s: dict(images=0, empty_labels=0, polygons=0, boxes=Counter(), class_images=Counter())
        for s in ("train", "valid", "test")
    }
    hashes, visual_hashes, errors = defaultdict(list), defaultdict(list), []
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "manifest.jsonl").open("w", encoding="utf-8") as manifest:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for index, row in enumerate(pool.map(inspect, items), 1):
                manifest.write(json.dumps(row) + "\n")
                s = stats[row["split"]]
                s["images"] += 1
                s["polygons"] += row["polygons"]
                s["empty_labels"] += not row["boxes"] and not row["errors"]
                s["boxes"].update(row["boxes"])
                s["class_images"].update(row["classes"])
                ref = dict(split=row["split"], image=row["image"])
                hashes[row["sha256"]].append(ref)
                if row["pixels_sha256"]:
                    visual_hashes[row["pixels_sha256"]].append(ref)
                if row["errors"]:
                    errors.append(dict(image=row["image"], errors=row["errors"]))
                if index % 5000 == 0:
                    print(f"Audited {index}/{len(items)}", flush=True)
    duplicate_groups = [v for v in hashes.values() if len(v) > 1]
    pixel_groups = [v for v in visual_hashes.values() if len(v) > 1]
    cross_split = [g for g in pixel_groups if len({r["split"] for r in g}) > 1]
    report = dict(
        root=str(args.root),
        stats=stats,
        errors=errors,
        orphan_labels=orphans,
        exact_duplicate_groups=duplicate_groups,
        identical_pixels_groups=pixel_groups,
        cross_split_identical_pixels=cross_split,
        limits="No near-duplicate search, semantic label review, or distance verification.",
    )
    (args.output / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            dict(
                stats=stats,
                errors=len(errors),
                orphan_labels=len(orphans),
                duplicate_groups=len(duplicate_groups),
                pixel_groups=len(pixel_groups),
                cross_split_groups=len(cross_split),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
