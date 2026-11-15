"""Download a small public Open Images subset for REVIEW, never directly for training."""

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import requests

CLASSES = {
    "/m/0c2jj": "axe",
    "/m/03g8mr": "baseball_bat",
    "/m/03l9g": "hammer",
    "/m/0gxl3": "pistol",
    "/m/04ctx": "knife",
    "/m/058qzx": "knife",
    "/m/06y5r": "sword",
    "/m/06c54": "rifle",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    images = args.output / "images"
    images.mkdir(exist_ok=True)
    grouped = {}
    with args.annotations.open() as stream:
        for row in csv.DictReader(stream):
            if row["LabelName"] in CLASSES:
                row["safesight_class"] = CLASSES[row["LabelName"]]
                grouped.setdefault(row["ImageID"], []).append(row)

    def download(item):
        image_id, boxes = item
        url = f"https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg"
        destination = images / f"{image_id}.jpg"
        try:
            if not destination.exists():
                response = requests.get(url, timeout=45)
                response.raise_for_status()
                if not response.headers.get("Content-Type", "").startswith("image/"):
                    raise ValueError("Response is not an image")
                temporary = destination.with_suffix(".partial")
                temporary.write_bytes(response.content)
                temporary.replace(destination)
            return dict(image_id=image_id, url=url, annotations=boxes, downloaded=True)
        except (requests.RequestException, ValueError) as error:
            return dict(image_id=image_id, url=url, downloaded=False, error=str(error))

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(download, grouped.items()))
    (args.output / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (args.output / "REVIEW_REQUIRED.txt").write_text(
        "NOT A TRAINING DATASET. Original subset: Open Images validation.\n"
        "Review every image, all SafeSight objects (including unannotated classes),\n"
        "class mapping and image-level license/attribution before export.\n"
        "Deduplicate against original dataset and group related images before splitting.\n"
        "No guarantee of camera distance or that these images are new to the old dataset.\n"
        "Source: https://storage.googleapis.com/openimages/web/download_v7.html\n",
        encoding="utf-8",
    )
    print(
        f"Downloaded {sum(r['downloaded'] for r in rows)}/{len(rows)} review candidates", flush=True
    )


if __name__ == "__main__":
    main()
