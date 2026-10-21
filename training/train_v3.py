#!/usr/bin/env python3
"""
SIPETIK — training model v3 (10 kelas + gambar negatif) di RTX 5070.

Fine-tune dari pest_v2.pt (sudah kenal 9 serangga) -> cukup ~40 epoch,
bukan 100 dari nol. Layer klasifikasi terakhir otomatis di-reset oleh
ultralytics karena jumlah kelas berubah 9 -> 10 (tambah tikus).

Dataset harus sudah dibangun:  python training/build_dataset_v3.py
Data dibaca dari SSD internal (~/sipetik/dataset_v3) — JANGAN dari G:
(HDD USB exFAT, training dari situ berkali lipat lebih lambat).

    python training/train_v3.py
    python training/train_v3.py --resume
    python training/train_v3.py --base yolo11s.pt --name sipetik_pest_v4_11s --epochs 60
Setelah selesai:
    copy %USERPROFILE%\\sipetik\\runs\\sipetik_pest_v3\\weights\\best.pt pest_v3.pt
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
NAME = "sipetik_pest_v3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HOME / "dataset_v3" / "data_v3.yaml"))
    ap.add_argument("--base", default=str(ROOT / "pest_v2.pt"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=32,
                    help="32 muat di 8 GB RTX 5070 (GTX 1650 4 GB maksimal ~8)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--name", default=NAME,
                    help="Nama folder run (mis. sipetik_pest_v4_11s untuk --base yolo11s.pt)")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    last = RUNS / a.name / "weights" / "last.pt"
    if a.resume:
        YOLO(str(last)).train(resume=True)
    else:
        YOLO(a.base).train(
            data=a.data, epochs=a.epochs, imgsz=640, batch=a.batch,
            patience=15, device=0, workers=a.workers, cache="disk",
            close_mosaic=5, project=str(RUNS), name=a.name, exist_ok=True,
        )
    print(f"\nSelesai. Best weights: {RUNS / a.name / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()
