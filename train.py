"""Fine-tune or evaluate SafeSight weights on a reviewed YOLO dataset."""

import argparse
from pathlib import Path

from weapon_detection.config import MODEL_CLASSES, MODEL_PATH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--mode", choices=("check", "train", "val"), default="check")
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--name", default="weapons_v2")
    args = parser.parse_args()
    if min(args.epochs, args.batch, args.imgsz) <= 0:
        parser.error("epochs, batch and imgsz must be positive")
    if not args.data.is_file() or not args.model.is_file():
        parser.error("Both --data and --model must be existing files")

    import torch
    import yaml
    from ultralytics import YOLO
    from ultralytics.data.utils import check_det_dataset

    with args.data.open(encoding="utf-8") as stream:
        spec = yaml.safe_load(stream)
    names = spec.get("names", {})
    if isinstance(names, dict):
        try:
            names = [names[i] for i in range(len(names))]
        except KeyError:
            parser.error("names must use contiguous integer IDs starting at zero")
    if names != list(MODEL_CLASSES):
        parser.error(f"Remap dataset labels to this exact order: {list(MODEL_CLASSES)}")
    if args.mode == "val" and not spec.get(args.split):
        parser.error(f"Dataset needs an explicit {args.split} split")
    # Never download arbitrary data from a YAML download directive.
    try:
        dataset = check_det_dataset(str(args.data.resolve()), autodownload=False)
    except (FileNotFoundError, ValueError, SyntaxError) as error:
        parser.error(str(error))
    for split in ("train", "val"):
        paths = dataset[split]
        for path in paths if isinstance(paths, list) else [paths]:
            if not Path(path).exists():
                parser.error(f"Missing {split} path: {path}")
    print(f"PyTorch {torch.__version__}; CUDA available: {torch.cuda.is_available()}")
    print(f"Dataset paths: train={dataset['train']}, val={dataset['val']}")
    if args.mode == "check":
        print("Paths and class order checked; annotations and leakage still need auditing.")
        return
    if args.device != "cpu" and not torch.cuda.is_available():
        parser.error("CUDA unavailable. Use the CUDA-enabled venv or --device cpu")
    model = YOLO(str(args.model.resolve()))
    if args.mode == "val":
        model.val(
            data=str(args.data.resolve()),
            split=args.split,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            workers=0,
            plots=True,
            project=str(Path("runs/weapon_eval").resolve()),
            name=args.name,
        )
        return
    model.train(
        data=str(args.data.resolve()),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        workers=0,
        cache=False,
        optimizer="AdamW",
        lr0=0.0002,
        lrf=0.01,
        cos_lr=True,
        patience=20,
        warmup_epochs=3,
        close_mosaic=10,
        degrees=10,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        mosaic=0.5,
        mixup=0.0,
        seed=42,
        amp=True,
        plots=True,
        save=True,
        project=str(Path("runs/weapon_train").resolve()),
        name=args.name,
        exist_ok=False,
    )


if __name__ == "__main__":
    main()
