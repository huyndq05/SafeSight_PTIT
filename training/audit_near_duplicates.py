"""Flag visually similar images for review using 64-bit DCT perceptual hashes.

Distance is a heuristic, not proof of duplicate content. No image is deleted.
"""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import cv2
import numpy as np


def fingerprint(path):
    pixels = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if pixels is None:
        return dict(path=str(path), error="unreadable_image")
    sample = cv2.resize(pixels, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    coefficients = cv2.dct(sample)[:8, :8].flatten()
    bits = coefficients > np.median(coefficients[1:])
    value = int.from_bytes(np.packbits(bits).tobytes(), "big")
    return dict(path=str(path), phash=f"{value:016x}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--distance", type=int, default=6)
    args = parser.parse_args()
    if not 0 <= args.distance <= 7:
        parser.error("distance must be between 0 and 7 for this bucket index")
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "original_phash.jsonl"
    if cache.exists():
        originals = [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines()]
    else:
        with args.original_manifest.open(encoding="utf-8") as stream:
            paths = [row["image"] for row in map(json.loads, stream)]
        originals = []
        with cache.open("w", encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=4) as pool:
            for i, row in enumerate(pool.map(fingerprint, paths), 1):
                originals.append(row)
                stream.write(json.dumps(row) + "\n")
                if i % 5000 == 0:
                    print(f"Original perceptual hashes {i}/{len(paths)}", flush=True)
    buckets = defaultdict(set)
    values = []
    for i, row in enumerate(originals):
        value = int(row["phash"], 16) if "phash" in row else None
        values.append(value)
        if value is not None:
            for chunk in range(8):
                buckets[(chunk, (value >> (chunk * 8)) & 255)].add(i)
    paths = []
    for directory in args.candidate_dir:
        paths.extend(
            sorted(p for p in directory.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        )
    flagged, failures, totals = [], [], defaultdict(int)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(fingerprint, paths):
            totals[str(Path(row["path"]).parent)] += 1
            if "error" in row:
                failures.append(row)
                continue
            value = int(row["phash"], 16)
            possible = set()
            for chunk in range(8):
                possible.update(buckets[(chunk, (value >> (chunk * 8)) & 255)])
            matches = []
            for i in possible:
                distance = (value ^ values[i]).bit_count()
                if distance <= args.distance:
                    matches.append(dict(original=originals[i]["path"], distance=distance))
            if matches:
                matches.sort(key=lambda m: (m["distance"], m["original"]))
                flagged.append(
                    dict(
                        candidate=row["path"],
                        matches=matches[:5],
                        total_matches=len(matches),
                        review_status="pending",
                    )
                )
    report = dict(
        distance=args.distance,
        original_images=len(originals),
        candidate_images=len(paths),
        candidates_by_directory=totals,
        flagged_candidates=len(flagged),
        matches=flagged,
        errors=failures,
        limits="pHash may miss crops/overlays or flag unrelated similar shapes. Manual review required. Cache assumes original files unchanged.",
    )
    (args.output / "near_duplicate_review.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "matches"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
