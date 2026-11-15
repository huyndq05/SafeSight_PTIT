"""Reproducible sparse video audit; clip names are hints, not box ground truth."""

import argparse
import json
import time
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from weapon_detection.detection.spatial import detail_views, merge_same_class


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    device = 0 if torch.cuda.is_available() else "cpu"
    records = []
    for weights in ["ss_final_2.pt"] if args.detail else ["ss_final_1.pt", "ss_final_2.pt"]:
        model = YOLO(str(Path("models") / weights))
        for size in [640] if args.detail else [416, 640, 960]:
            model.predict(
                np.zeros((480, 640, 3), np.uint8), imgsz=size, device=device, verbose=False
            )
            for video in sorted(args.source.glob("*.mp4")):
                cap = cv2.VideoCapture(str(video))
                fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
                tiles = []
                for fraction in [0.1, 0.3, 0.5, 0.7, 0.9]:
                    index = int(max(0, count - 1) * fraction)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                    ok, frame = cap.read()
                    if not ok:
                        continue
                    start = time.perf_counter()
                    result = model.predict(
                        frame, conf=0.15, imgsz=size, device=device, verbose=False
                    )[0]
                    predictions = [
                        dict(
                            label=result.names[int(cid)],
                            conf=round(float(conf), 4),
                            box=[round(float(v), 1) for v in box],
                        )
                        for box, conf, cid in zip(
                            result.boxes.xyxy.cpu().tolist(),
                            result.boxes.conf.cpu().tolist(),
                            result.boxes.cls.cpu().tolist(),
                        )
                    ]
                    if args.detail:
                        for left, top, crop in detail_views(frame):
                            detail = model.predict(
                                crop, conf=0.15, imgsz=640, device=device, verbose=False
                            )[0]
                            for row in detail.boxes.data.cpu().tolist():
                                x1, y1, x2, y2, score, cid = row
                                # Reject boxes clipped by internal tile edges.
                                h, w = crop.shape[:2]
                                if (
                                    (left > 0 and x1 < 3)
                                    or (top > 0 and y1 < 3)
                                    or (left + w < frame.shape[1] and x2 > w - 3)
                                    or (top + h < frame.shape[0] and y2 > h - 3)
                                ):
                                    continue
                                predictions.append(
                                    dict(
                                        label=detail.names[int(cid)],
                                        conf=score,
                                        box=[x1 + left, y1 + top, x2 + left, y2 + top],
                                    )
                                )
                        predictions = merge_same_class(predictions)
                    records.append(
                        dict(
                            model=weights,
                            imgsz=size,
                            video=video.name,
                            seconds=round(index / fps, 2),
                            ms=round((time.perf_counter() - start) * 1000, 1),
                            shape=list(frame.shape),
                            detections=predictions,
                        )
                    )
                    if weights == "ss_final_2.pt":
                        preview = frame.copy()
                        for item in predictions:
                            if item["conf"] < 0.35:
                                continue
                            x1, y1, x2, y2 = map(int, item["box"])
                            cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(
                                preview,
                                f"{item['label']} {item['conf']:.2f}",
                                (x1, max(16, y1)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2,
                            )
                        preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
                        tile = Image.fromarray(preview)
                        tile.thumbnail((420, 300))
                        canvas = Image.new("RGB", (420, 325), "white")
                        canvas.paste(tile, (0, 25))
                        ImageDraw.Draw(canvas).text(
                            (4, 4), f"{video.name} {index / fps:.1f}s size={size}", fill="black"
                        )
                        tiles.append(canvas)
                cap.release()
                if tiles:
                    sheet = Image.new("RGB", (420 * len(tiles), 325), "white")
                    for i, tile in enumerate(tiles):
                        sheet.paste(tile, (i * 420, 0))
                    sheet.save(args.output / f"{video.stem}_{size}.jpg")
                print(weights, size, video.name, flush=True)
            (args.output / "predictions.json").write_text(
                json.dumps(records, indent=2), encoding="utf-8"
            )
    print("device", device, "samples", len(records), flush=True)


if __name__ == "__main__":
    main()
