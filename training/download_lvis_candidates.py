"""Select rare-class LVIS images for review without downloading all COCO images."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import zipfile
from urllib.parse import urlparse

import cv2
import ijson
import numpy as np
import requests

# LVIS v1 uses one-based category IDs. Walking sticks are only a subset of stick.
CLASSES = {30: "axe", 530: "hammer", 994: "spear", 1046: "sword", 1153: "stick"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit-per-class", type=int, default=150)
    args = parser.parse_args()
    if args.limit_per_class < 1:
        parser.error("--limit-per-class must be positive")
    grouped, counts = defaultdict(list), Counter()
    with zipfile.ZipFile(args.annotations) as archive:
        member = next(n for n in archive.namelist() if n.endswith(".json"))
        with archive.open(member) as stream:
            for annotation in ijson.items(stream, "annotations.item", use_float=True):
                category = annotation["category_id"]
                if category in CLASSES:
                    grouped[annotation["image_id"]].append(
                        dict(
                            category_id=category,
                            safesight_candidate_class=CLASSES[category],
                            bbox_xywh=annotation["bbox"],
                            annotation_id=annotation["id"],
                        )
                    )
                    counts[CLASSES[category]] += 1
        by_class = defaultdict(list)
        for image_id, annotations in grouped.items():
            for category in {a["category_id"] for a in annotations}:
                by_class[category].append(image_id)
        selected = set()
        for category, ids in by_class.items():
            selected.update(
                random.Random(42).sample(sorted(ids), min(len(ids), args.limit_per_class))
            )
        images = {}
        with archive.open(member) as stream:
            for image in ijson.items(stream, "images.item", use_float=True):
                if image["id"] in selected:
                    images[image["id"]] = image
    print("LVIS target box counts:", dict(counts), flush=True)
    print("Selected images:", len(images), flush=True)
    original_sha, original_pixels = set(), set()
    with args.original_manifest.open(encoding="utf-8") as stream:
        for row in map(json.loads, stream):
            original_sha.add(row["sha256"])
            original_pixels.add(row["pixels_sha256"])
    (args.output / "images").mkdir(parents=True, exist_ok=True)

    def download(image):
        image_id = image["id"]
        row = dict(
            image_id=image_id,
            source_image_metadata=image,
            annotations=grouped[image_id],
            review_status="pending",
        )
        # COCO's dotted bucket hostname can fail HTTPS hostname validation.
        # Use the same public bucket via S3's valid path-style HTTPS endpoint.
        source_path = urlparse(image["coco_url"]).path
        url = "https://s3.amazonaws.com/images.cocodataset.org" + source_path
        destination = args.output / "images" / f"{image_id:012}.jpg"
        try:
            if not destination.exists():
                response = requests.get(url, timeout=(15, 35))
                response.raise_for_status()
                raw = response.content
            else:
                raw = destination.read_bytes()
            pixels = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if pixels is None:
                raise ValueError("Unreadable source image")
            if pixels.shape[:2] != (image["height"], image["width"]):
                raise ValueError("Image dimensions differ from LVIS metadata")
            destination.write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            ph = hashlib.sha256(str(pixels.shape).encode() + pixels.tobytes()).hexdigest()
            row.update(
                downloaded=True,
                image=destination.name,
                sha256=sha,
                pixels_sha256=ph,
                overlaps_original_exact=sha in original_sha or ph in original_pixels,
            )
        except (requests.RequestException, ValueError) as error:
            row.update(downloaded=False, error=str(error))
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(download, images.values()))
    (args.output / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    class_images = Counter()
    for row in rows:
        if row["downloaded"]:
            class_images.update({a["safesight_candidate_class"] for a in row["annotations"]})
    summary = dict(
        source="https://github.com/lvis-dataset/lvis-api",
        annotation_archive=str(args.annotations),
        selected=len(rows),
        downloaded=sum(r["downloaded"] for r in rows),
        class_images=class_images,
        exact_overlap_original=sum(r.get("overlaps_original_exact", False) for r in rows),
        status="Review only. LVIS is partially annotated; inspect missing SafeSight objects, class mapping and near duplicates.",
    )
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.output / "REVIEW_REQUIRED.txt").write_text(
        "This is NOT a training dataset. Original LVIS v1 annotations and COCO image metadata retained.\n"
        "Check source image license/attribution and cite LVIS.\n"
        "LVIS has non-exhaustive labels; inspect all SafeSight objects before YOLO export.\n"
        "Walking stick is only a subset of stick. Verify all proposed class mappings.\n"
        "Source split is retained in annotation_archive; assign SafeSight splits after grouping.\n"
        "No verified physical camera distance. No generalization claim.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
