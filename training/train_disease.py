#!/usr/bin/env python3
"""
SIPETIK — training model penyakit daun padi (6 kelas) di RTX 5070.

Dari YOLO11n pretrained COCO. Dataset harus sudah dibangun:
    python training/build_disease_dataset.py
Data dibaca dari SSD internal (~/sipetik/dataset_disease), bukan dari G:.

    python training/train_disease.py
    python training/train_disease.py --resume
Setelah selesai:
    copy %USERPROFILE%\\sipetik\\runs\\sipetik_disease_v1\\weights\\best.pt disease_v1.pt
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import windows_git_fix  # noqa: E402,F401

from ultralytics import YOLO  # noqa: E402

HOME = Path.home() / "sipetik"
RUNS = HOME / "runs"
NAME = "sipetik_disease_v1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HOME / "dataset_disease" / "data_disease.yaml"))
    ap.add_argument("--base", default="yolo11n.pt")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch", type=int, default=32,
                    help="32 muat di 8 GB RTX 5070")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    last = RUNS / NAME / "weights" / "last.pt"
    if a.resume:
        YOLO(str(last)).train(resume=True)
    else:
        YOLO(a.base).train(
            data=a.data, epochs=a.epochs, imgsz=640, batch=a.batch,
            patience=15, device=0, workers=a.workers, cache="disk",
            close_mosaic=5, project=str(RUNS), name=NAME, exist_ok=True,
        )
    print(f"\nSelesai. Best weights: {RUNS / NAME / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()
