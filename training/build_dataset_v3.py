#!/usr/bin/env python3
"""
SIPETIK — dataset v3: semua hama dalam SATU model + gambar "bukan hama"
(negatif) supaya kamera tidak salah kenali orang/tangan/daun sebagai hama.

Kenapa v3:
    pest_v2.pt (9 serangga) & best.pt (tikus) dilatih TANPA satu pun gambar
    latar kosong — model tidak pernah diajari "ini bukan hama". Hasilnya
    wajah, rambut, tangan, bercak penyakit daun, laba-laba sawah dll ikut
    dikenali sebagai hama. v3 menambah ribuan gambar negatif (label kosong)
    dan memasukkan tikus & keong mas dewasa ke model lokal.

Isi dataset v3 (lihat SOURCES di bawah, semua dicek lewat Roboflow API):
    POSITIF  dataset_v2 (9 serangga, sudah ada)        id 0-8
             + tikus (3 dataset, tikus sawah asli)      id 9
             + keong mas DEWASA (digabung ke id 2)      id 2
    NEGATIF  COCO val2017 (orang, wajah, tangan, ruangan, kucing, anjing)
             daun padi sakit (bercak coklat mirip wereng)
             malai padi menguning (v4: dikira wereng coklat saat tiling)

Sebagian negatif disisihkan ke folder `eval_negatives/` (TIDAK dipakai
training) untuk mengukur false-positive secara jujur — lihat
training/eval_false_positives.py.

Data disimpan di SSD internal (default ~/sipetik/dataset_v3), BUKAN di G:
— G: itu HDD USB exFAT; training dari situ jauh lebih lambat.

    python training/build_dataset_v3.py
    python training/build_dataset_v3.py --out D:/data/sipetik_v3
"""

import argparse
import os
import random
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

TRAINING_DIR = Path(__file__).resolve().parent
HOME_DATA    = Path.home() / "sipetik"

# Urutan kelas — HARUS sama dengan training/data_v3.yaml
CLASSES = [
    "wereng_coklat", "walang_sangit", "keong_mas", "wereng_hijau",
    "penggulung_daun", "penggerek_batang", "kepinding_hitam",
    "belalang_padi", "lalat_bibit", "tikus",
]
CID = {n: i for i, n in enumerate(CLASSES)}

# role: "pos" -> box kelas di class_map dipakai, box kelas lain dibuang
#       "neg" -> semua box dibuang, gambar jadi negatif (label kosong)
# only_with_pos: buang gambar yang tidak punya box target sama sekali
# resplit: gabung split asli lalu bagi ulang 80/10/10
#
# Semua sumber di bawah SUDAH dicek visual (contact sheet), bukan cuma
# baca deskripsi. Yang SENGAJA TIDAK dipakai (jangan ditambahkan lagi):
#   computer-vision-oxxob/rat-detection-0d0pi  -> kemasan pakan, kartun,
#       hamster & berang-berang dilabel "rat" -> malah menambah salah deteksi
#   rodent-detection-6ctxr/rodent-detection-and-repulsion -> 966 dari 968
#       gambar ada tikusnya tapi TANPA label -> mengajari "tikus = latar"
#   tempat-pusing/tikus-xbn7r -> crop thermal, box = seluruh gambar
#   winter-zebrafish-test/did-rodent-yolov8 -> tikus lab di arena, dicat
#   baltazar-mu/detection-of-fall-armyworm-... -> label ulat tidak konsisten
#       (box FAW menutup seluruh tanaman); model cloud dari data ini dulu
#       mengenali wajah sebagai ulat grayak
#   laguna-state-polytechnic-university-scc/rice-field-insect-detection ->
#       papan perangkap kuning, ribuan bintik; wereng hijau vs wereng
#       zigzag tidak bisa dibedakan di resolusi itu
SOURCES = [
    # ---- tikus -------------------------------------------------------
    {"ws": "padjadjaran-xrbt3", "proj": "tikus", "ver": 1,          # tikus sawah di perangkap
     "role": "pos", "class_map": {"tikus": "tikus"}},
    {"ws": "kmutnb-n38mm", "proj": "rat-gambf", "ver": 1,
     "role": "pos", "class_map": {"1": "tikus"}},
    {"ws": "object-detection-sccsb", "proj": "biawak-tikus-ular_jumlahsama", "ver": 3,
     "role": "pos", "class_map": {"Tikus": "tikus"}, "only_with_pos": True,
     "resplit": True},  # tikusnya cuma ada di split valid/test asli
    # ---- keong mas dewasa (telurnya sudah ada di dataset_v2) ---------
    {"ws": "egash", "proj": "e-gash", "ver": 1,
     "role": "pos", "class_map": {"GAS": "keong_mas"}},
    # ---- negatif: daun padi sakit (bercak coklat mirip wereng) -------
    {"ws": "utopialab", "proj": "rice-leaf-wfax3", "ver": 2, "role": "neg", "neg_tag": "rice_leaf"},
    # ---- negatif: malai padi menguning (v4) -------------------------
    # Ditemukan lewat training/eval_video.py: dengan --tiles, malai padi
    # kuning-oranye di video demo dikenali sebagai wereng coklat. Foto
    # lapangan dari atas, penuh malai, tanpa hama.
    {"ws": "ewuricedataset", "proj": "rice-panicle-uyxgj", "ver": 5, "role": "neg", "neg_tag": "panicle"},
]

COCO_VAL_URL = "http://images.cocodataset.org/zips/val2017.zip"


# ================================================================
#  DOWNLOAD
# ================================================================
def roboflow_download(src: dict, api_key: str, dl_root: Path) -> Path:
    """Unduh 1 versi dataset format yolov8 lewat REST API Roboflow (tanpa
    paket `roboflow`, yang memaksa opencv-python-headless dan merusak
    cv2.imshow di main.py). Hasil di-cache: kalau folder sudah ada, skip."""
    tag  = f"{src['ws']}__{src['proj']}__v{src['ver']}"
    dest = dl_root / tag
    if (dest / "data.yaml").exists():
        return dest

    url = f"https://api.roboflow.com/{src['ws']}/{src['proj']}/{src['ver']}/yolov8"
    for _ in range(60):  # export bisa butuh waktu untuk di-generate server
        j = requests.get(url, params={"api_key": api_key}, timeout=60).json()
        link = (j.get("export") or {}).get("link")
        if link:
            break
        time.sleep(5)
    else:
        raise RuntimeError(f"export {tag} tidak siap: {str(j)[:200]}")

    zpath = dl_root / f"{tag}.zip"
    _stream(link, zpath)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
    zpath.unlink()
    return dest


def _stream(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = path.with_suffix(path.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.replace(path)


def coco_download(dl_root: Path) -> Path:
    dest = dl_root / "coco_val2017"
    if (dest / "val2017").exists():
        return dest / "val2017"
    zpath = dl_root / "val2017.zip"
    if not zpath.exists():
        print("    mengunduh COCO val2017 (~780 MB) ...")
        _stream(COCO_VAL_URL, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
    zpath.unlink()
    return dest / "val2017"


def source_names(root: Path) -> dict:
    cfg = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    names = cfg["names"]
    return {int(k): str(v) for k, v in (enumerate(names) if isinstance(names, list) else names.items())}


# ================================================================
#  MERGE
# ================================================================
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _place(src: Path, dst: Path) -> None:
    """Hardlink kalau bisa (instan, tidak makan disk), copy kalau beda drive."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _images(d: Path):
    return sorted(p for p in d.glob("*") if p.suffix.lower() in IMG_EXT) if d.exists() else []


def as_box(parts: list) -> str:
    """Baris label YOLO -> selalu kotak `cls cx cy w h`. Poligon diubah ke kotak
    pembungkusnya: ultralytics membuang SELURUH gambar yang labelnya mencampur
    poligon & kotak ("labels mix segment and detection rows")."""
    v = list(map(float, parts[1:]))
    if len(v) == 4:
        return " ".join(parts)
    xs, ys = v[0::2], v[1::2]
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    return f"{parts[0]} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def remap_label(lbl: Path, names: dict, class_map: dict) -> list:
    out = []
    if not lbl.exists():
        return out
    for line in lbl.read_text().splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        tgt = class_map.get(names.get(int(parts[0]), parts[0]))
        if tgt is not None:
            out.append(as_box([str(CID[tgt]), *parts[1:]]))
    return out


def add_split(files, out_split: Path, tag: str, label_fn) -> tuple:
    n_img = n_box = 0
    for img in files:
        lines = label_fn(img)
        if lines is None:
            continue
        name = f"{tag}_{img.stem}"
        (out_split / "labels").mkdir(parents=True, exist_ok=True)
        _place(img, out_split / "images" / f"{name}{img.suffix.lower()}")
        (out_split / "labels" / f"{name}.txt").write_text("\n".join(lines))
        n_img += 1
        n_box += len(lines)
    return n_img, n_box


def split_list(files, fracs, seed):
    files = list(files)
    random.Random(seed).shuffle(files)
    out, i = [], 0
    for f in fracs:
        n = int(round(len(files) * f))
        out.append(files[i:i + n])
        i += n
    out[-1] += files[i:]
    return out


def build(out: Path, dl_root: Path, v2_dir: Path, eval_dir: Path,
          coco_train: int, coco_val: int, leaf_train: int, leaf_val: int) -> dict:
    for d in (out, eval_dir):
        if d.exists():
            shutil.rmtree(d)
    stats = {}

    # 1. dataset_v2 apa adanya (id 0-8 sama persis)
    for sp in ("train", "valid", "test"):
        def keep(img, sp=sp):
            lbl = v2_dir / sp / "labels" / (img.stem + ".txt")
            return [as_box(l.split()) for l in (lbl.read_text().splitlines() if lbl.exists() else [])
                    if len(l.split()) >= 5]
        stats[f"v2/{sp}"] = add_split(_images(v2_dir / sp / "images"), out / sp, "v2", keep)

    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    for src in SOURCES:
        root  = roboflow_download(src, api_key, dl_root)
        names = source_names(root)
        tag   = src["proj"][:24]

        if src["role"] == "pos":
            def lab(img, src=src, names=names):
                lines = remap_label(img.parent.parent / "labels" / (img.stem + ".txt"),
                                    names, src["class_map"])
                if src.get("only_with_pos") and not lines:
                    return None
                return lines
            have = {sp: _images(root / sp / "images") for sp in ("train", "valid", "test")}
            if src.get("resplit"):
                have = {"train": [p for v in have.values() for p in v], "valid": [], "test": []}
            if not have["valid"]:  # sumber tanpa split -> bagi sendiri 80/10/10
                have["train"], have["valid"], have["test"] = split_list(have["train"], (0.8, 0.1, 0.1), 7)
            for sp, files in have.items():
                stats[f"{tag}/{sp}"] = add_split(files, out / sp, tag, lab)
        else:
            # negatif: train/valid ke dataset, sisanya disisihkan untuk evaluasi
            allimg = [p for sp in ("train", "valid", "test") for p in _images(root / sp / "images")]
            tr, va, ev = split_list(allimg, (leaf_train / len(allimg), leaf_val / len(allimg), 1.0), 11)
            stats[f"{tag}/train(neg)"] = add_split(tr, out / "train", tag, lambda _: [])
            stats[f"{tag}/valid(neg)"] = add_split(va, out / "valid", tag, lambda _: [])
            for img in ev:
                _place(img, eval_dir / src["neg_tag"] / img.name)
            stats[f"{tag}/eval(neg)"] = (len(ev), 0)

    # 2. COCO val2017 sebagai negatif (orang, wajah, tangan, hewan rumah, ruangan)
    coco = _images(coco_download(dl_root))
    tr, va, ev = split_list(coco, (coco_train / len(coco), coco_val / len(coco), 1.0), 13)
    stats["coco/train(neg)"] = add_split(tr, out / "train", "coco", lambda _: [])
    stats["coco/valid(neg)"] = add_split(va, out / "valid", "coco", lambda _: [])
    for img in ev:
        _place(img, eval_dir / "coco" / img.name)
    stats["coco/eval(neg)"] = (len(ev), 0)
    return stats


def write_yaml(out: Path) -> Path:
    cfg = {"path": out.as_posix(), "train": "train/images", "val": "valid/images",
           "test": "test/images", "nc": len(CLASSES), "names": dict(enumerate(CLASSES))}
    y = out / "data_v3.yaml"
    y.write_text(yaml.dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return y


def main():
    ap = argparse.ArgumentParser(description="Bangun dataset v3 SIPETIK")
    ap.add_argument("--out", default=str(HOME_DATA / "dataset_v3"))
    ap.add_argument("--eval-out", default=str(HOME_DATA / "eval_negatives"))
    ap.add_argument("--downloads", default=str(HOME_DATA / "_downloads_v3"))
    ap.add_argument("--v2", default=str(TRAINING_DIR / "dataset_v2"),
                    help="Folder dataset_v2 (9 serangga)")
    ap.add_argument("--coco-train", type=int, default=2000)
    ap.add_argument("--coco-val",   type=int, default=300)
    ap.add_argument("--leaf-train", type=int, default=1000)
    ap.add_argument("--leaf-val",   type=int, default=200)
    a = ap.parse_args()

    if not os.environ.get("ROBOFLOW_API_KEY", "").strip():
        sys.exit("ERROR: ROBOFLOW_API_KEY belum diisi di .env")

    out = Path(a.out)
    stats = build(out, Path(a.downloads), Path(a.v2), Path(a.eval_out),
                  a.coco_train, a.coco_val, a.leaf_train, a.leaf_val)
    print(f"\n{'sumber/split':<42}{'gambar':>8}{'box':>8}")
    for k, (ni, nb) in stats.items():
        print(f"{k:<42}{ni:>8}{nb:>8}")
    for sp in ("train", "valid", "test"):
        lbls = list((out / sp / "labels").glob("*.txt"))
        neg = sum(1 for l in lbls if not l.read_text().strip())
        print(f"TOTAL {sp:<6} {len(lbls):>6} gambar, {neg} negatif ({neg / max(1, len(lbls)):.0%})")
    print(f"\nDataset : {out}\nYAML    : {write_yaml(out)}\nEval neg: {a.eval_out}")


if __name__ == "__main__":
    main()
