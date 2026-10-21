#!/usr/bin/env python3
"""
SIPETIK — dataset penyakit daun padi (model terpisah: disease_v1.pt).

Penyakit TIDAK membunyikan buzzer (buzzer untuk mengusir hewan); main.py
mengirimnya ke /api/camera/disease sebagai peringatan di dashboard.

Sumber (dicek visual & dicek duplikat dengan dHash, bukan cuma deskripsi):
    utopialab/rice-leaf-wfax3 v2              5.188 gambar, hanya 3.699 unik
    rice-dataset-evccc/rice-plant-disease-detection-ibpov v5
                                              7.414 gambar, sebagian foto lapangan
    project-khcjh/rice-leaf-disease-detection-obj  TIDAK dipakai: salinan
                                              utopialab (jumlah box per kelas identik)
Gambar kembar (dHash sama) dikumpulkan dalam satu grup dan seluruh grup
masuk ke SATU split saja — kalau tidak, gambar yang sama ada di train dan
test sekaligus dan akurasinya terlihat lebih bagus dari kenyataan.

"Healthy" sengaja TIDAK jadi kelas: box daun sehat dibuang, gambarnya jadi
contoh "normal". Ditambah COCO (orang/ruangan) sebagai negatif.

Asumsi yang perlu diketahui: di utopialab ada kelas "Bacterial Leaf Blight"
DAN "Leaf Blight" (dua sumber yang digabung pemiliknya) — keduanya dipetakan
ke hawar_daun_bakteri.

    python training/build_disease_dataset.py
"""

import argparse
import os
import random
import shutil
import sys
from pathlib import Path

import cv2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dataset_v3 as v3  # noqa: E402  (download, COCO, hardlink helper)

CLASSES = ["blas_daun", "hawar_daun_bakteri", "bercak_coklat",
           "bercak_coklat_sempit", "hangus_daun", "gosong_daun"]
CID = {n: i for i, n in enumerate(CLASSES)}

SOURCES = [
    {"ws": "utopialab", "proj": "rice-leaf-wfax3", "ver": 2, "class_map": {
        "Leaf Blast": "blas_daun", "Bacterial Leaf Blight": "hawar_daun_bakteri",
        "Leaf Blight": "hawar_daun_bakteri", "Brown Spot": "bercak_coklat",
        "Narrow Brown Spot": "bercak_coklat_sempit", "Leaf Scald": "hangus_daun",
        "Leaf Smut": "gosong_daun"}},
    {"ws": "rice-dataset-evccc", "proj": "rice-plant-disease-detection-ibpov", "ver": 5, "class_map": {
        "Rice Blast": "blas_daun", "bacterial blight": "hawar_daun_bakteri",
        "Brown Spot": "bercak_coklat"}},
]


def dhash(path: Path):
    im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    im = cv2.resize(im, (9, 8))
    return (im[:, 1:] > im[:, :-1]).tobytes()


def remap(lbl: Path, names: dict, class_map: dict) -> list:
    """Label sumber -> id kelas penyakit; kelas lain (mis. Healthy) dibuang."""
    out = []
    for line in (lbl.read_text().splitlines() if lbl.exists() else []):
        p = line.split()
        if len(p) < 5:
            continue
        tgt = class_map.get(names.get(int(p[0]), p[0]))
        if tgt is not None:
            out.append(v3.as_box([str(CID[tgt]), *p[1:]]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(v3.HOME_DATA / "dataset_disease"))
    ap.add_argument("--downloads", default=str(v3.HOME_DATA / "_downloads_v3"))
    ap.add_argument("--coco-train", type=int, default=2000)
    ap.add_argument("--coco-val", type=int, default=300)
    a = ap.parse_args()
    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    out, dl = Path(a.out), Path(a.downloads)
    if out.exists():
        shutil.rmtree(out)

    # 1. kumpulkan semua gambar + label hasil remap, dikelompokkan per dHash
    groups = {}  # dhash -> [(img, lines, tag)]
    for src in SOURCES:
        root = v3.roboflow_download(src, api_key, dl)
        names = v3.source_names(root)
        tag = src["ws"][:10]
        for sp in ("train", "valid", "test"):
            for img in v3._images(root / sp / "images"):
                h = dhash(img)
                if h is None:
                    continue
                lines = remap(root / sp / "labels" / (img.stem + ".txt"), names, src["class_map"])
                groups.setdefault(h, []).append((img, lines, tag))

    # 2. satu grup = satu split (anti-bocor), lalu 1 gambar per grup (dedup)
    keys = sorted(groups)
    random.Random(21).shuffle(keys)
    n = len(keys)
    split_of = {k: ("train" if i < 0.8 * n else "valid" if i < 0.9 * n else "test")
                for i, k in enumerate(keys)}
    stats = {}
    for k in keys:
        img, lines, tag = groups[k][0]
        sp = split_of[k]
        name = f"{tag}_{img.stem}"
        v3._place(img, out / sp / "images" / f"{name}{img.suffix.lower()}")
        (out / sp / "labels").mkdir(parents=True, exist_ok=True)
        (out / sp / "labels" / f"{name}.txt").write_text("\n".join(lines))
        s = stats.setdefault(sp, [0, 0, 0])
        s[0] += 1
        s[1] += len(lines)
        s[2] += not lines

    # 3. negatif COCO (subset yang SAMA dengan dataset_v3 train/valid; eval
    #    COCO di ~/sipetik/eval_negatives/coco tetap tidak tersentuh)
    for sp, src_dir in (("train", v3.HOME_DATA / "dataset_v3" / "train" / "images"),
                        ("valid", v3.HOME_DATA / "dataset_v3" / "valid" / "images")):
        coco = [p for p in v3._images(src_dir) if p.name.startswith("coco_")]
        coco = coco[: a.coco_train if sp == "train" else a.coco_val]
        for p in coco:
            v3._place(p, out / sp / "images" / p.name)
            (out / sp / "labels" / f"{p.stem}.txt").write_text("")
        stats[sp][0] += len(coco)
        stats[sp][2] += len(coco)

    total_imgs = sum(len(g) for g in groups.values())
    print(f"{total_imgs} gambar sumber -> {n} unik setelah dedup")
    for sp in ("train", "valid", "test"):
        ni, nb, ne = stats[sp]
        print(f"  {sp:<6} {ni:>6} gambar, {nb:>6} box, {ne} tanpa penyakit")
    cfg = {"path": out.as_posix(), "train": "train/images", "val": "valid/images",
           "test": "test/images", "nc": len(CLASSES), "names": dict(enumerate(CLASSES))}
    (out / "data_disease.yaml").write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    print(f"YAML: {out / 'data_disease.yaml'}")


if __name__ == "__main__":
    main()
