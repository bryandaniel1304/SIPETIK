#!/usr/bin/env python3
"""
SIPETIK — Unduh & gabungkan dataset publik jadi satu dataset YOLO multi-kelas.
================================================================================
PENTING — baca dulu sebelum menjalankan:

Daftar di DATASETS di bawah ini adalah *kandidat* dataset publik di Roboflow
Universe yang saya temukan lewat pencarian (halaman proyeknya sendiri tidak
bisa saya buka langsung untuk verifikasi — Roboflow memblokir scraping).
Sebelum menjalankan script ini kamu WAJIB:

  1. Buka tiap URL di komentar bawah, login/daftar gratis di roboflow.com.
  2. Cek isi datasetnya benar (jumlah gambar, kualitas, kelas yang tersedia).
  3. Klik tombol "Download this Dataset" -> format "YOLOv8" -> pilih
     "show download code" (bukan "download zip"). Roboflow akan menampilkan
     kode Python persis seperti:

         from roboflow import Roboflow
         rf = Roboflow(api_key="XXXXXXXXXXXX")
         project = rf.workspace("ramadhan").project("walang-sangit")
         version = project.version(1)
         dataset = version.download("yolov8")

     Salin nilai workspace / project / version / api_key ke DATASETS di bawah.
  4. Cek nama-nama kelas asli dataset itu (muncul di halaman project, tab
     "Classes"), lalu sesuaikan `class_map` supaya memetakan ke salah satu
     dari 5 kelas target SIPETIK: rat, walang_sangit, wereng_coklat,
     ulat_grayak, keong_mas. Kelas yang TIDAK ada di class_map akan dibuang
     (box-nya dihapus, gambar tetap dipakai sebagai contoh "tidak ada hama"
     kalau semua box-nya terbuang).

Setelah DATASETS diisi & diverifikasi, jalankan:

    pip install -r training/requirements.txt
    python training/download_datasets.py

Hasil akhirnya: folder training/dataset/{train,valid,test}/{images,labels}
siap dipakai oleh training/train.py.
"""

import os
import shutil
import sys
from pathlib import Path

import yaml

try:
    from roboflow import Roboflow
except ImportError:
    print("ERROR: paket 'roboflow' belum terinstall.")
    print("Jalankan: pip install -r training/requirements.txt")
    sys.exit(1)

TRAINING_DIR = Path(__file__).resolve().parent
MERGED_DIR   = TRAINING_DIR / "dataset"
TMP_DIR      = TRAINING_DIR / "_downloads"

# Urutan kelas target SIPETIK — HARUS sama persis dengan training/data.yaml
# dan dengan mapping label di app/Http/Controllers/Api/CameraController.php
TARGET_CLASSES = ["rat", "walang_sangit", "wereng_coklat", "ulat_grayak", "keong_mas"]

# ============================================================================
#  DATASETS — isi/ganti sesuai hasil verifikasi kamu di roboflow.com
#  (lihat instruksi lengkap di training/README.md)
# ============================================================================
DATASETS = [
    {
        # https://universe.roboflow.com/ramadhan/walang-sangit
        # ~600 gambar, kelas tunggal "walang sangit" (belum diverifikasi manual).
        "api_key":   "GANTI_API_KEY_KAMU",
        "workspace": "ramadhan",
        "project":   "walang-sangit",
        "version":   1,
        "class_map": {
            # "nama_kelas_asli_di_dataset": "target_class_sipetik"
            "walang sangit": "walang_sangit",
            "walang-sangit": "walang_sangit",
        },
    },
    {
        # https://universe.roboflow.com/csu-bpvmi/paddy-rice-insect-pest-dataset
        # Dataset multi-hama padi. Kelas yang relevan buat kita cuma sebagian
        # (sisanya otomatis dibuang). CEK ULANG nama kelas persisnya di
        # Roboflow sebelum jalan — nama di bawah ini tebakan dari hasil
        # pencarian, kemungkinan besar perlu disesuaikan huruf besar/kecilnya.
        "api_key":   "GANTI_API_KEY_KAMU",
        "workspace": "csu-bpvmi",
        "project":   "paddy-rice-insect-pest-dataset",
        "version":   1,
        "class_map": {
            "Brown Planthopper":    "wereng_coklat",
            "Rice Leaf Catterpillar": "ulat_grayak",  # aproksimasi, cek visualnya
            # kelas lain (Rice Leaf Roller, Rice Weevil, dst) sengaja tidak
            # dipetakan -> dibuang, karena bukan salah satu dari 5 target kita.
        },
    },
    {
        # https://universe.roboflow.com/baltazar-mu/detection-of-fall-armyworm-infestation-with-deep-learning
        # Fall armyworm (genus sama dgn ulat grayak, Spodoptera) — pelengkap
        # data ulat_grayak kalau dataset CSU di atas kurang banyak.
        "api_key":   "GANTI_API_KEY_KAMU",
        "workspace": "baltazar-mu",
        "project":   "detection-of-fall-armyworm-infestation-with-deep-learning",
        "version":   1,
        "class_map": {
            "armyworm": "ulat_grayak",
            "Armyworm": "ulat_grayak",
        },
    },
    {
        # https://universe.roboflow.com/demape-brayle-q/golden-apple-snail
        "api_key":   "GANTI_API_KEY_KAMU",
        "workspace": "demape-brayle-q",
        "project":   "golden-apple-snail",
        "version":   1,
        "class_map": {
            "golden apple snail": "keong_mas",
            "snail":              "keong_mas",
        },
    },
    # Data tikus yang sudah ada (dipakai untuk melatih best.pt saat ini)
    # berasal dari Roboflow project "rat-detection-6ezx2" (lihat
    # animal_detector.py). Tambahkan konfigurasinya di sini juga kalau kamu
    # mau menyatukan data tikus lama ke dataset gabungan ini:
    # {
    #     "api_key":   "GANTI_API_KEY_KAMU",
    #     "workspace": "GANTI",
    #     "project":   "rat-detection-6ezx2",
    #     "version":   2,
    #     "class_map": {"rat": "rat"},
    # },
]


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def remap_and_copy(src_root: Path, src_names: dict, class_map: dict,
                    dataset_tag: str) -> None:
    """Salin images+labels dari satu dataset yang sudah diunduh ke
    training/dataset/, sambil remap class id ke skema target SIPETIK."""

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
    pending = [d for d in DATASETS if d["api_key"] == "GANTI_API_KEY_KAMU"]
    if pending:
        print("ERROR: masih ada entri DATASETS dengan api_key placeholder.")
        print("Isi dulu api_key (dan verifikasi workspace/project/version/class_map)")
        print("sesuai instruksi di bagian atas file ini / training/README.md.")
        sys.exit(1)

    if MERGED_DIR.exists():
        print(f"Menghapus dataset gabungan lama di {MERGED_DIR} ...")
        shutil.rmtree(MERGED_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    for i, cfg in enumerate(DATASETS, 1):
        tag = f"{cfg['workspace']}-{cfg['project']}"
        print(f"\n[{i}/{len(DATASETS)}] Mengunduh {tag} (v{cfg['version']}) ...")

        rf = Roboflow(api_key=cfg["api_key"])
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
