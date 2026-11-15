"""Verify and unpack Zenodo 11582054 into a provenance-preserving review pack.

This deliberately does not create a training YAML or infer that Gun means pistol.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import cv2
import numpy as np


def file_hash(path, algorithm="sha256"):
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-metadata", type=Path, required=True)
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.source_metadata.read_text(encoding="utf-8"))
    entry = metadata["files"][0]
    algorithm, expected = entry["checksum"].split(":", 1)
    if file_hash(args.archive, algorithm) != expected:
        raise ValueError("Archive checksum differs from Zenodo metadata")
    original_hashes, original_pixels = set(), set()
    with args.original_manifest.open(encoding="utf-8") as stream:
        for row in map(json.loads, stream):
            original_hashes.add(row["sha256"])
            original_pixels.add(row["pixels_sha256"])
    for directory in ("images", "annotations"):
        (args.output / directory).mkdir(parents=True, exist_ok=True)
    (args.output / "source.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    rows, errors, class_images, class_boxes = [], [], Counter(), Counter()
    seen_hashes = set()
    with zipfile.ZipFile(args.archive) as archive:
        infos = archive.infolist()
        images = {}
        for info in infos:
            if Path(info.filename).suffix.lower() in (".jpg", ".jpeg", ".png"):
                stem = Path(info.filename).stem
                if stem in images:
                    raise ValueError(f"Duplicate image stem in archive: {stem}")
                images[stem] = info
        for info in infos:
            if not info.filename.endswith(".xml"):
                continue
            stem = Path(info.filename).stem
            try:
                xml_bytes = archive.read(info)  # zipfile validates each member CRC.
                document = ET.fromstring(xml_bytes)
                image_info = images[stem]
                raw = archive.read(image_info)
                pixels = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if pixels is None:
                    raise ValueError("Unreadable image")
                height, width = pixels.shape[:2]
                objects = []
                for obj in document.findall("object"):
                    name = obj.findtext("name")
                    box = obj.find("bndbox")
                    coords = [float(box.findtext(key)) for key in ("xmin", "ymin", "xmax", "ymax")]
                    x1, y1, x2, y2 = coords
                    if not all(np.isfinite(coords)) or not (
                        0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
                    ):
                        raise ValueError(f"Invalid box: {coords}, image size {(width, height)}")
                    objects.append(dict(source_class=name, bbox_xyxy=coords))
                    class_boxes[name] += 1
                class_images.update({o["source_class"] for o in objects})
                sha = hashlib.sha256(raw).hexdigest()
                pixel_hash = hashlib.sha256(
                    str(pixels.shape).encode() + pixels.tobytes()
                ).hexdigest()
                image_name = Path(image_info.filename).name
                (args.output / "images" / image_name).write_bytes(raw)
                (args.output / "annotations" / (stem + ".xml")).write_bytes(xml_bytes)
                rows.append(
                    dict(
                        image=image_name,
                        source_member=image_info.filename,
                        source_record="https://zenodo.org/records/11582054",
                        width=width,
                        height=height,
                        sha256=sha,
                        pixels_sha256=pixel_hash,
                        objects=objects,
                        overlaps_original_exact=sha in original_hashes
                        or pixel_hash in original_pixels,
                        duplicate_within_source=pixel_hash in seen_hashes,
                        review_status="pending",
                    )
                )
                seen_hashes.add(pixel_hash)
            except (KeyError, ValueError, ET.ParseError) as error:
                errors.append(dict(annotation=info.filename, error=str(error)))
            if len(rows) and len(rows) % 1000 == 0:
                print(f"Prepared {len(rows)} candidates", flush=True)
    (args.output / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    summary = dict(
        images=len(rows),
        class_images=class_images,
        class_boxes=class_boxes,
        exact_overlaps_original=sum(r["overlaps_original_exact"] for r in rows),
        duplicates_within_source=sum(r["duplicate_within_source"] for r in rows),
        errors=errors,
        archive_checksum_verified=True,
        status="Review only; not a training dataset. Near duplicates and source groups not audited.",
    )
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.output / "REVIEW_REQUIRED.txt").write_text(
        "Source: https://zenodo.org/records/11582054 (CC BY 4.0 in record metadata).\n"
        "Citation and source metadata retained in source.json.\n"
        "Review all labels before training. Gun must not be blindly mapped to pistol.\n"
        "Check Rifle/Knife/Machete boundaries and all missing SafeSight objects.\n"
        "Remove duplicates and group related frames before assigning splits.\n"
        "Original source split is random; it is not evidence of video independence.\n"
        "No verified camera distance. Do not claim performance at 2-3 metres.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
