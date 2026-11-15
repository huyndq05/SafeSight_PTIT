"""Combine original positives with 350 reviewed empty-label backgrounds."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import shutil

import yaml

NAMES = [
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
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--original-manifest", type=Path, required=True)
    args = parser.parse_args()
    selected = json.loads((args.pack / "selected.json").read_text(encoding="utf-8"))
    if len(selected) != 350 or len({r["name"] for r in selected}) != 350:
        raise ValueError("Expected 350 unique reviewed images")
    for row in selected:
        if row.get("review_status") != "approved_negative":
            raise ValueError("Image has not been approved as a negative")
        if Path(row["name"]).name != row["name"] or not row["name"].startswith("bg_"):
            raise ValueError("Invalid filename")
        raw = (args.pack / "candidates" / row["name"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Image changed after review")
    originals = [
        json.loads(line) for line in args.original_manifest.read_text(encoding="utf-8").splitlines()
    ]
    if any(row["errors"] for row in originals):
        raise ValueError("Original dataset has unresolved audit errors")
    manifests = {split: [] for split in ("train", "val", "test")}
    original_backgrounds_excluded = 0
    for row in originals:
        if not row["boxes"]:
            original_backgrounds_excluded += 1
            continue
        split = "val" if row["split"] == "valid" else row["split"]
        manifests[split].append(Path(row["image"]).resolve().as_posix())
    groups = defaultdict(list)
    for row in selected:
        groups[row["group"]].append(row)
    rng = random.Random(42)
    for rows in groups.values():
        rng.shuffle(rows)
    held = {split: [] for split in ("train", "val", "test")}
    # Seed each holdout with one image per group, then round-robin to 35.
    for split in ("val", "test"):
        for rows in groups.values():
            held[split].append(rows.pop())
    while len(held["val"]) < 35 or len(held["test"]) < 35:
        for split in ("val", "test"):
            if len(held[split]) >= 35:
                continue
            available = [key for key, rows in groups.items() if len(rows) > 1]
            key = rng.choice(available)
            held[split].append(groups[key].pop())
    held["train"] = [row for rows in groups.values() for row in rows]
    split_counts = {}
    for split, rows in held.items():
        images, labels = args.pack / "images" / split, args.pack / "labels" / split
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        for row in rows:
            image = images / row["name"]
            label = labels / (Path(row["name"]).stem + ".txt")
            if label.exists() and label.stat().st_size:
                raise ValueError(f"Refusing to overwrite a nonempty label: {label}")
            shutil.copy2(args.pack / "candidates" / row["name"], image)
            label.write_bytes(b"")
            row["split"] = split
            manifests[split].append(image.resolve().as_posix())
        split_counts[split] = dict(backgrounds=len(rows), total_images=len(manifests[split]))
        rng.shuffle(manifests[split])
        (args.pack / f"{split}.txt").write_text(
            "\n".join(manifests[split]) + "\n", encoding="utf-8"
        )
    spec = dict(
        path=args.pack.resolve().as_posix(),
        train="train.txt",
        val="val.txt",
        test="test.txt",
        names=NAMES,
    )
    (args.pack / "data.with_backgrounds.yaml").write_text(
        yaml.safe_dump(spec, sort_keys=False), encoding="utf-8"
    )
    (args.pack / "selected.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
    report = dict(
        background_images=350,
        label_bytes=0,
        persons_annotated=False,
        category_counts=Counter(r["group"] for r in selected),
        original_backgrounds_excluded=original_backgrounds_excluded,
        original_files_modified=False,
        splits=split_counts,
        limits="Original positive splits retained, including known leakage. Background absence checked visually, not guaranteed by model predictions.",
    )
    (args.pack / "dataset_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
