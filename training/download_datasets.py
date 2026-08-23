#!/usr/bin/env python3
"""
SIPETIK — Unduh & siapkan dataset lokal untuk wereng batang coklat + walang
sangit (2 kelas — lihat training/data.yaml untuk kenapa cuma 2, bukan 5).

Sumbernya SUDAH DIVERIFIKASI langsung lewat Roboflow SDK (bukan tebakan):

    csu-bpvmi/paddy-rice-insect-pest-dataset, version 3
    -> 3.477 gambar (3045 train / 289 valid / 143 test)
    -> kelas "brown plant hopper"  -> wereng_coklat
    -> kelas "rice bug"            -> walang_sangit
       ("rice bug" = nama Inggris untuk walang sangit / Leptocorisa oratorius)

Kelas lain di dataset ini (rice grasshopper, black bug, stem borer, green
leaf hopper, rice leaf roller) otomatis dibuang karena tidak ada di
TARGET_CLASSES di bawah.

Sebelum jalan:
    1. Isi ROBOFLOW_API_KEY di .env (sudah ada kalau ikut setup sebelumnya)
    2. pip install -r training/requirements.txt
    3. python training/download_datasets.py
    4. python training/train.py
"""

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import windows_git_fix  # noqa: E402,F401  (roboflow imports ultralytics internally — see file for why)

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from roboflow import Roboflow
except ImportError:
    print("ERROR: paket 'roboflow' belum terinstall.")
    print("Jalankan: pip install -r training/requirements.txt")
    sys.exit(1)

TRAINING_DIR = Path(__file__).resolve().parent
MERGED_DIR   = TRAINING_DIR / "dataset"
TMP_DIR      = TRAINING_DIR / "_downloads"

# Urutan kelas — HARUS sama persis dengan training/data.yaml
TARGET_CLASSES = ["wereng_coklat", "walang_sangit"]

DATASETS = [
    {
        "workspace": "csu-bpvmi",
        "project":   "paddy-rice-insect-pest-dataset",
        "version":   3,
        "class_map": {
            "brown plant hopper": "wereng_coklat",
            "rice bug":           "walang_sangit",
        },
    },
]


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def remap_and_copy(src_root: Path, src_names: dict, class_map: dict,
                    dataset_tag: str) -> None:
    target_id = {name: i for i, name in enumerate(TARGET_CLASSES)}

    for split_src, split_dst in (("train", "train"), ("valid", "valid"), ("test", "test")):
        img_dir = src_root / split_src / "images"
        lbl_dir = src_root / split_src / "labels"
        if not img_dir.exists():
            continue

        dst_img_dir = MERGED_DIR / split_dst / "images"
        dst_lbl_dir = MERGED_DIR / split_dst / "labels"
        dst_img_dir.mkdir(parents=True, exist_ok=True)
        dst_lbl_dir.mkdir(parents=True, exist_ok=True)

        n_copied, n_boxes = 0, 0
        for img_path in img_dir.glob("*.*"):
            lbl_path = lbl_dir / (img_path.stem + ".txt")
            new_name = f"{dataset_tag}_{img_path.name}"

            out_lines = []
            if lbl_path.exists():
                for line in lbl_path.read_text().splitlines():
                    parts = line.strip().split()
                    if not parts:
                        continue
                    src_cls_id = int(parts[0])
                    src_name   = src_names.get(src_cls_id, str(src_cls_id))
                    tgt_name   = class_map.get(src_name)
                    if tgt_name is None or tgt_name not in target_id:
                        continue  # kelas tidak relevan -> box dibuang
                    new_line = " ".join([str(target_id[tgt_name]), *parts[1:]])
                    out_lines.append(new_line)
                    n_boxes += 1

            shutil.copy2(img_path, dst_img_dir / new_name)
            (dst_lbl_dir / f"{dataset_tag}_{img_path.stem}.txt").write_text(
                "\n".join(out_lines)
            )
            n_copied += 1

        print(f"    [{split_src}] {n_copied} gambar disalin, {n_boxes} box relevan disimpan")


def main() -> None:
    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ROBOFLOW_API_KEY belum diisi di .env")
        sys.exit(1)

    if MERGED_DIR.exists():
        print(f"Menghapus dataset gabungan lama di {MERGED_DIR} ...")
        shutil.rmtree(MERGED_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    rf = Roboflow(api_key=api_key)

    for i, cfg in enumerate(DATASETS, 1):
        tag = f"{cfg['workspace']}-{cfg['project']}"
        print(f"\n[{i}/{len(DATASETS)}] Mengunduh {tag} (v{cfg['version']}) ...")

        project = rf.workspace(cfg["workspace"]).project(cfg["project"])
        version = project.version(cfg["version"])
        dl_location = str(TMP_DIR / tag)
        dataset = version.download("yolov8", location=dl_location)

        src_root = Path(dataset.location)
        src_yaml = load_yaml(src_root / "data.yaml")
        src_names = dict(enumerate(src_yaml["names"])) if isinstance(src_yaml["names"], list) \
            else src_yaml["names"]

        print(f"    Kelas asli di dataset ini: {list(src_names.values())}")
        remap_and_copy(src_root, src_names, cfg["class_map"], tag)

    print(f"\nSelesai. Dataset gabungan ada di: {MERGED_DIR}")
    print("Lanjut jalankan: python training/train.py")


if __name__ == "__main__":
    main()
