"""Download negative-image candidates. Export empty labels only after visual review."""

import argparse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import random
from urllib.parse import urlparse

import cv2
import requests
import numpy as np

GROUPS = {
    "pen": ("/m/0k1tl", 30),
    "phone": ("/m/050k8", 40),
    "chair": ("/m/01mzpv", 35),
    "table": ("/m/04bcr3", 35),
    "laptop": ("/m/01c648", 30),
    "book": ("/m/0bt_c3", 30),
    "bottle": ("/m/04dr76w", 25),
    "umbrella": ("/m/0hnnb", 25),
    "handbag": ("/m/080hkjn", 25),
    "keyboard": ("/m/01m2v", 25),
    "mouse": ("/m/020lf", 15),
    "tablet": ("/m/0bh9flk", 10),
    "remote": ("/m/0qjjc", 5),
    "flashlight": ("/m/01kb5b", 3),
    "wallet": (None, 17),
}
BANNED = {
    "/m/0c2jj",
    "/m/03g8mr",
    "/m/03l9g",
    "/m/0gxl3",
    "/m/04ctx",
    "/m/058qzx",
    "/m/02gzp",
    "/m/06c54",
    "/m/06c7f7",
    "/m/06nrc",
    "/m/06y5r",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=Path("training/source_metadata"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "candidates").mkdir(exist_ok=True)
    by_class, banned = defaultdict(set), set()
    with (args.metadata / "openimages_validation_boxes.csv").open() as stream:
        for row in csv.DictReader(stream):
            if row["LabelName"] in BANNED:
                banned.add(row["ImageID"])
            if row.get("IsDepiction", "0") != "1":
                by_class[row["LabelName"]].add(row["ImageID"])
    selected, used = [], set()
    for group, (label, count) in GROUPS.items():
        if label is None:
            continue
        pool = sorted(by_class[label] - banned - used)
        random.Random(42).shuffle(pool)
        for image_id in pool[: count + 5]:
            used.add(image_id)
            selected.append(
                dict(
                    group=group,
                    id=image_id,
                    source="openimages_validation",
                    name=f"bg_oi_{image_id}.jpg",
                    url=f"https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg",
                )
            )
    wallet = json.loads((args.metadata / "lvis_wallet_candidates.json").read_text())
    random.Random(42).shuffle(wallet)
    for image in wallet[:22]:
        image_id = image["id"]
        selected.append(
            dict(
                group="wallet",
                id=str(image_id),
                source="lvis_val",
                name=f"bg_lvis_{image_id:012}.jpg",
                source_image=image,
                url="https://s3.amazonaws.com/images.cocodataset.org"
                + urlparse(image["coco_url"]).path,
            )
        )
    wanted = {r["id"] for r in selected if r["source"] == "openimages_validation"}
    attributes = {}
    with (args.metadata / "openimages_validation_attribution.csv").open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["ImageID"] in wanted:
                attributes[row["ImageID"]] = row

    def download(row):
        path = args.output / "candidates" / row["name"]
        try:
            if not path.exists():
                response = requests.get(row["url"], timeout=(15, 40))
                response.raise_for_status()
                raw = response.content
            else:
                raw = path.read_bytes()
            pixels = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if pixels is None:
                raise ValueError("Unreadable image")
            path.write_bytes(raw)
            row.update(
                downloaded=True,
                sha256=hashlib.sha256(raw).hexdigest(),
                pixels_sha256=hashlib.sha256(
                    str(pixels.shape).encode() + pixels.tobytes()
                ).hexdigest(),
                review_status="pending",
            )
            if row["source"] == "openimages_validation":
                row["attribution"] = attributes.get(row["id"])
        except (requests.RequestException, ValueError) as error:
            row.update(downloaded=False, error=str(error))
        return row

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(download, selected))
    (args.output / "candidates.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(
        json.dumps(
            dict(
                downloaded=sum(r["downloaded"] for r in rows),
                groups=Counter(r["group"] for r in rows if r["downloaded"]),
            ),
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
