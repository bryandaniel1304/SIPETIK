#!/usr/bin/env python3
"""
SIPETIK — ukur SALAH DETEKSI (false alarm) dan deteksi hama, per konfigurasi.

Memakai main.PestDetector APA ADANYA — kode yang sama dengan kamera:
deteksi orang, buang hama yang menempel di badan orang, filter ukuran,
filter ukuran tikus, threshold --conf 0.55, dan (opsional) tiling.
Foto diam = satu frame, jadi tracking (--confirm-frames) tidak diuji di
sini; untuk itu lihat training/eval_video.py.

Gambar negatif dari ~/sipetik/eval_negatives/ — disisihkan oleh
build_dataset_v3.py dan TIDAK PERNAH dipakai training model mana pun:
    coco/       orang, wajah, tangan, ruangan, kucing, anjing, jalanan
    rice_leaf/  daun padi berpenyakit (bercak coklat mirip wereng)
Gambar positif = test set dataset_v3 (semua gambar, termasuk serangga yang
terlalu kecil untuk filter --min-area 0.01).

    python training/eval_false_positives.py                    # lama, v3, v3+tiling
    python training/eval_false_positives.py --only v3_tiles2 --new pest_v4.pt
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import windows_git_fix  # noqa: E402,F401

import cv2  # noqa: E402
import yaml  # noqa: E402
from ultralytics import YOLO  # noqa: E402

import main as cam  # noqa: E402

HOME = Path.home() / "sipetik"
IMG_EXT = {".jpg", ".jpeg", ".png"}


def images(d: Path):
    return sorted(p for p in d.glob("*") if p.suffix.lower() in IMG_EXT)


def norm(raw):
    return "tikus" if raw.lower() in ("rat", "tikus") else raw


def run_negatives(det, folders):
    out = {}
    for name, d in folders.items():
        files = images(d)
        fired, by_cls = 0, Counter()
        for p in files:
            _, pests = det.detect(cv2.imread(str(p)))
            if pests:
                fired += 1
                by_cls.update({x[0] for x in pests})
        out[name] = {"images": len(files), "false_alarms": fired,
                     "false_alarm_rate": round(fired / max(1, len(files)), 4),
                     "by_class": dict(by_cls.most_common())}
        print(f"    {name:<10} {fired:>5}/{len(files):<5} = {fired / max(1, len(files)):6.1%}  {dict(by_cls.most_common(5))}")
    return out


def run_positives(det, test_dir: Path, names: dict):
    """Per kelas: berapa gambar test yang kelas benarnya ikut terdeteksi."""
    per = defaultdict(lambda: [0, 0])
    for p in images(test_dir / "images"):
        lbl = test_dir / "labels" / (p.stem + ".txt")
        gt = {names[int(l.split()[0])] for l in lbl.read_text().splitlines() if l.strip()} if lbl.exists() else set()
        if not gt:
            continue
        got = {norm(x[0]) for x in det.detect(cv2.imread(str(p)))[1]}
        for c in gt:
            per[c][1] += 1
            per[c][0] += c in got
    res = {c: {"hit": h, "total": t, "rate": round(h / t, 4)} for c, (h, t) in sorted(per.items())}
    for c, v in res.items():
        print(f"    {c:<18} {v['hit']:>4}/{v['total']:<4} = {v['rate']:6.1%}")
    tot_h, tot_t = sum(v["hit"] for v in res.values()), sum(v["total"] for v in res.values())
    print(f"    {'TOTAL':<18} {tot_h:>4}/{tot_t:<4} = {tot_h / tot_t:6.1%}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", nargs="+", default=["best.pt", "pest_v2.pt"])
    ap.add_argument("--new", default="pest_v3.pt")
    ap.add_argument("--conf", type=float, default=0.55)
    ap.add_argument("--only", nargs="*", default=None,
                    help="Jalankan konfigurasi tertentu saja: old, v3, v3_tiles2")
    ap.add_argument("--neg-dir", default=str(HOME / "eval_negatives"))
    ap.add_argument("--test-dir", default=str(HOME / "dataset_v3" / "test"))
    ap.add_argument("--out", default=str(ROOT / "training" / "benchmarks" / "false_positives.json"))
    a = ap.parse_args()

    coco = YOLO(str(ROOT / "yolov8n.pt"))
    new_name = Path(a.new).stem
    cfgs = {
        "old": dict(models=a.old, tiles=1, min_area=0.01, human_conf=0.35, human_filter=True),
        new_name: dict(models=[a.new], tiles=1, min_area=0.01),
        f"{new_name}_tiles2": dict(models=[a.new], tiles=2, min_area=0.002),
    }
    if a.only:
        cfgs = {k: v for k, v in cfgs.items() if k in a.only or k.replace(new_name, "v3") in a.only}

    neg = {d.name: d for d in sorted(Path(a.neg_dir).iterdir()) if d.is_dir()}
    names = yaml.safe_load((Path(a.test_dir).parent / "data_v3.yaml").read_text(encoding="utf-8"))["names"]
    out_path = Path(a.out)
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    results["conf"] = a.conf
    for key, c in cfgs.items():
        models = [YOLO(str(ROOT / f)) for f in c["models"]]
        det = cam.PestDetector(models[0], coco, models[1] if len(models) > 1 else None,
                               conf=a.conf, device="cuda:0", min_area=c["min_area"],
                               tiles=c["tiles"], confirm_frames=1,
                               human_conf=c.get("human_conf", 0.5), human_filter=c.get("human_filter", False))
        print(f"\n[{key}] {' + '.join(c['models'])}  tiles={c['tiles']} min_area={c['min_area']}")
        print("  Gambar TANPA hama (harus 0 alarm):")
        n = run_negatives(det, neg)
        print("  Gambar DENGAN hama (test set):")
        pos = run_positives(det, Path(a.test_dir), names)
        results[key] = {**c, "negatives": n, "positives": pos}
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2))
    print(f"\nTersimpan: {out_path}")


if __name__ == "__main__":
    main()
