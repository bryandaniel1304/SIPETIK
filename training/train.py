#!/usr/bin/env python3
"""
SIPETIK — Training model deteksi hama sawah multi-kelas (YOLOv8).

Jalankan setelah training/dataset/ terisi (lihat download_datasets.py atau
tambahkan data hasil labeling manual sendiri).

    python training/train.py
    python training/train.py --epochs 120 --batch 16
    python training/train.py --base yolov8s.pt   # model lebih besar, lebih akurat, lebih lambat

Kalau training keputus di tengah jalan (laptop dimatikan, listrik mati,
dll) — TIDAK perlu mulai dari awal lagi. Ultralytics otomatis simpan
checkpoint (last.pt) tiap epoch selesai. Lanjutkan dengan:

    python training/train.py --resume

Progress & hasil training bisa dipantau di training/runs/sipetik_pest/.
Setelah selesai, weights terbaik ada di:
    training/runs/sipetik_pest/weights/best.pt
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import windows_git_fix  # noqa: E402,F401  (fix bug ultralytics di komputer ini — lihat file-nya)

from ultralytics import YOLO  # noqa: E402

TRAINING_DIR = Path(__file__).resolve().parent
DATA_YAML    = TRAINING_DIR / "data.yaml"
DATASET_DIR  = TRAINING_DIR / "dataset"


def resolve_data_yaml() -> Path:
    """ultralytics me-resolve `path:` relatif di data.yaml terhadap folder
    'datasets_dir' GLOBAL di settings.json-nya (bukan terhadap lokasi
    data.yaml itu sendiri) — di komputer ini settingnya kepental ke project
    lain sama sekali. Supaya training/data.yaml tetap portable/relatif buat
    dibaca orang, kita generate salinan dengan `path:` absolut di sini saat
    runtime, tanpa mengubah settings global ultralytics siapa pun."""
    cfg = yaml.safe_load(DATA_YAML.read_text(encoding="utf-8"))
    cfg["path"] = str(DATASET_DIR)
    resolved = TRAINING_DIR / "_data.resolved.yaml"
    resolved.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    return resolved


def parse_args():
    p = argparse.ArgumentParser(description="Training model YOLOv8 hama sawah SIPETIK")
    p.add_argument("--base",    default="yolov8n.pt", help="Model dasar (yolov8n/s/m.pt)")
    p.add_argument("--epochs",  type=int, default=100)
    p.add_argument("--imgsz",   type=int, default=640)
    p.add_argument("--batch",   type=int, default=8,
                    help="Kecilkan (mis. 4) kalau GPU kehabisan memori (CUDA OOM)")
    p.add_argument("--patience", type=int, default=25,
                    help="Stop lebih awal kalau tidak ada perbaikan selama N epoch")
    p.add_argument("--cache", choices=["disk", "ram", "none"], default="disk",
                    help="Cache gambar setelah didecode sekali supaya epoch berikutnya "
                         "tidak decode JPEG ulang dari awal. 'disk' aman untuk RAM "
                         "terbatas (default), 'ram' lebih cepat tapi butuh RAM bebas "
                         "banyak, 'none' matikan caching (setting lama)")
    p.add_argument("--device",  default="0", help="'0' = GPU pertama, 'cpu' = paksa CPU")
    p.add_argument("--resume", action="store_true",
                    help="Lanjutkan training yang terputus dari checkpoint terakhir "
                         "(training/runs/sipetik_pest/weights/last.pt) — abaikan opsi lain di atas")
    return p.parse_args()


def main():
    args = parse_args()

    last_checkpoint = TRAINING_DIR / "runs" / "sipetik_pest" / "weights" / "last.pt"

    if args.resume:
        if not last_checkpoint.exists():
            print(f"ERROR: {last_checkpoint} tidak ditemukan — tidak ada training")
            print("sebelumnya yang bisa dilanjutkan. Jalankan tanpa --resume dulu.")
            sys.exit(1)

        print("=" * 60)
        print("  SIPETIK — Lanjutkan Training yang Terputus")
        print("=" * 60)
        print(f"  Checkpoint : {last_checkpoint}")
        print("=" * 60)
        print()

        model = YOLO(str(last_checkpoint))
        model.train(resume=True)  # epoch, data, batch, dll otomatis dibaca dari checkpoint
    else:
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
        print(f"  Cache       : {args.cache}")
        print("=" * 60)
        print()

        model = YOLO(args.base)
        model.train(
            data     = str(resolve_data_yaml()),
            epochs   = args.epochs,
            imgsz    = args.imgsz,
            batch    = args.batch,
            patience = args.patience,
            device   = args.device,
            cache    = False if args.cache == "none" else args.cache,
            project  = str(TRAINING_DIR / "runs"),
            name     = "sipetik_pest",
            exist_ok = True,  # selalu timpa training/runs/sipetik_pest/ (bukan
                               # numpuk sipetik_pest-2, -3, ... tiap run ulang)
        )

    best_weights = TRAINING_DIR / "runs" / "sipetik_pest" / "weights" / "best.pt"
    print()
    print("=" * 60)
    if best_weights.exists():
        print(f"  Training selesai. Best weights: {best_weights}")
        print()
        print("  Model ini punya 2 kelas (wereng_coklat, walang_sangit) — model")
        print("  TAMBAHAN, bukan pengganti best.pt (yang tetap dipakai untuk tikus).")
        print("  Untuk memakainya di SIPETIK:")
        print(f"    copy \"{best_weights}\" pest_local.pt")
        print("    python main.py   (otomatis dipakai kalau pest_local.pt ada)")
    else:
        print("  Training selesai, tapi best.pt tidak ditemukan — cek log di atas.")
    print("=" * 60)


if __name__ == "__main__":
    main()
