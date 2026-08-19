#!/usr/bin/env python3
"""
SIPETIK — Training model deteksi hama sawah multi-kelas (YOLOv8).

Jalankan setelah training/dataset/ terisi (lihat download_datasets.py atau
tambahkan data hasil labeling manual sendiri).

    python training/train.py
    python training/train.py --epochs 120 --batch 16
    python training/train.py --base yolov8s.pt   # model lebih besar, lebih akurat, lebih lambat

Progress & hasil training bisa dipantau di training/runs/sipetik_pest/.
Setelah selesai, weights terbaik ada di:
    training/runs/sipetik_pest/weights/best.pt
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import windows_git_fix  # noqa: E402,F401  (fix bug ultralytics di komputer ini — lihat file-nya)

from ultralytics import YOLO  # noqa: E402

TRAINING_DIR = Path(__file__).resolve().parent
DATA_YAML    = TRAINING_DIR / "data.yaml"
DATASET_DIR  = TRAINING_DIR / "dataset"


def parse_args():
    p = argparse.ArgumentParser(description="Training model YOLOv8 hama sawah SIPETIK")
    p.add_argument("--base",    default="yolov8n.pt", help="Model dasar (yolov8n/s/m.pt)")
    p.add_argument("--epochs",  type=int, default=100)
    p.add_argument("--imgsz",   type=int, default=640)
    p.add_argument("--batch",   type=int, default=8,
                    help="Kecilkan (mis. 4) kalau GPU kehabisan memori (CUDA OOM)")
    p.add_argument("--patience", type=int, default=25,
                    help="Stop lebih awal kalau tidak ada perbaikan selama N epoch")
    p.add_argument("--device",  default="0", help="'0' = GPU pertama, 'cpu' = paksa CPU")
    return p.parse_args()


def main():
    args = parse_args()

    if not DATASET_DIR.exists():
        print(f"ERROR: {DATASET_DIR} belum ada.")
        print("Jalankan dulu: python training/download_datasets.py")
        print("(atau isi manual mengikuti struktur di training/README.md)")
        sys.exit(1)

    print("=" * 60)
    print("  SIPETIK — Training Model Hama Sawah")
    print("=" * 60)
    print(f"  Model dasar : {args.base}")
    print(f"  Dataset     : {DATASET_DIR}")
    print(f"  Epochs      : {args.epochs}")
    print(f"  Image size  : {args.imgsz}")
    print(f"  Batch size  : {args.batch}")
    print(f"  Device      : {args.device}")
    print("=" * 60)
    print()

    model = YOLO(args.base)
    model.train(
        data     = str(DATA_YAML),
        epochs   = args.epochs,
        imgsz    = args.imgsz,
        batch    = args.batch,
        patience = args.patience,
        device   = args.device,
        project  = str(TRAINING_DIR / "runs"),
        name     = "sipetik_pest",
    )

    best_weights = TRAINING_DIR / "runs" / "sipetik_pest" / "weights" / "best.pt"
    print()
    print("=" * 60)
    if best_weights.exists():
        print(f"  Training selesai. Best weights: {best_weights}")
        print()
        print("  Untuk memakainya di SIPETIK:")
        print(f"    1. Backup model lama:  copy best.pt best.rat-only.pt")
        print(f"    2. Ganti dengan yang baru:  copy \"{best_weights}\" best.pt")
        print("    3. Test: python main.py --model best.pt")
    else:
        print("  Training selesai, tapi best.pt tidak ditemukan — cek log di atas.")
    print("=" * 60)


if __name__ == "__main__":
    main()
