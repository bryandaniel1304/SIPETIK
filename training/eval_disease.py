#!/usr/bin/env python3
"""
SIPETIK — evaluasi model penyakit daun (disease_v1.pt).

1. mAP pada split TEST dataset_disease (tidak dipakai training/validasi).
2. Peringatan palsu: berapa gambar TANPA penyakit yang memunculkan
   peringatan, memakai main.DiseaseDetector apa adanya (conf 0.5):
     - COCO eval negatives (orang, ruangan, hewan) — tidak pernah dilatih
     - foto hama test set dataset_v3 (serangga di tanaman padi)
     - video demo SIPETIK (miniatur sawah), dicek tiap 2 detik seperti main.py
3. Contact sheet prediksi di test set untuk dicek mata.

    python training/eval_disease.py
    python training/eval_disease.py --model disease_v1.pt --conf 0.6
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import windows_git_fix  # noqa: E402,F401

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from ultralytics import YOLO  # noqa: E402

import main as cam  # noqa: E402

HOME = Path.home() / "sipetik"
IMG_EXT = {".jpg", ".jpeg", ".png"}


def images(d: Path):
    return sorted(p for p in d.glob("*") if p.suffix.lower() in IMG_EXT)


def fresh(model, conf):
    # confirm=1: foto diam = satu pengecekan; every_s=0: cek tiap panggilan
    return cam.DiseaseDetector(model, conf=conf, device="cuda:0", every_s=0, confirm=1)


def false_warnings(model, conf, files):
    fired, by = 0, Counter()
    for p in files:
        d = fresh(model, conf).maybe_detect(cv2.imread(str(p)), 0)
        if d:
            fired += 1
            by.update({x[0] for x in d})
    return {"images": len(files), "warnings": fired,
            "rate": round(fired / max(1, len(files)), 4), "by_class": dict(by.most_common())}


def video_warnings(model, conf, path: Path):
    det = cam.DiseaseDetector(model, conf=conf, device="cuda:0", every_s=2.0, confirm=2)
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = checks = warn_checks = 0
    by = Counter()
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        t = n / fps
        if t - det.last_run >= det.every_s:
            checks += 1
            d = det.maybe_detect(cv2.resize(fr, (640, 360)), t)
            if d:
                warn_checks += 1
                by.update({x[0] for x in d})
        n += 1
    return {"seconds": round(n / fps, 1), "checks": checks, "checks_with_warning": warn_checks,
            "by_class": dict(by.most_common())}


def sheet(model, conf, test_dir: Path, out: Path, n=12):
    files = images(test_dir / "images")
    files = [p for p in files if (test_dir / "labels" / (p.stem + ".txt")).read_text().strip()]
    random.Random(3).shuffle(files)
    tiles = []
    for p in files[:n]:
        r = model.predict(str(p), conf=conf, device=0, verbose=False)[0]
        im = r.plot(line_width=2, font_size=10)
        h, w = im.shape[:2]
        for line in (test_dir / "labels" / (p.stem + ".txt")).read_text().splitlines():
            c, cx, cy, bw, bh = line.split()[:5]
            cx, cy, bw, bh = map(float, (cx, cy, bw, bh))
            cv2.rectangle(im, (int((cx - bw / 2) * w), int((cy - bh / 2) * h)),
                          (int((cx + bw / 2) * w), int((cy + bh / 2) * h)), (0, 255, 0), 1)
        tiles.append(cv2.resize(im, (400, 300)))
    rows = [np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]
    cv2.imwrite(str(out), np.vstack(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="disease_v1.pt")
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--data", default=str(HOME / "dataset_disease" / "data_disease.yaml"))
    ap.add_argument("--video", default=str(ROOT.parent.parent / "VIDEO DEMO SIPETIK.mp4"))
    ap.add_argument("--out", default=str(ROOT / "training" / "benchmarks" / "disease_eval.json"))
    a = ap.parse_args()

    model = YOLO(str(ROOT / a.model) if (ROOT / a.model).exists() else a.model)
    res = {"model": a.model, "conf": a.conf}

    m = model.val(data=a.data, split="test", device=0, verbose=False, plots=False)
    res["test_map50"] = round(float(m.box.map50), 4)
    res["test_map50_95"] = round(float(m.box.map), 4)
    res["test_per_class_map50"] = {model.names[int(c)]: round(float(v), 4)
                                   for c, v in zip(m.box.ap_class_index, m.box.ap50)}
    print(f"\nTest mAP50 {res['test_map50']}  mAP50-95 {res['test_map50_95']}")
    for k, v in res["test_per_class_map50"].items():
        print(f"    {k:<22} {v:.3f}")

    print(f"\nPeringatan palsu (conf {a.conf}):")
    for name, files in (("coco", images(HOME / "eval_negatives" / "coco")),
                        ("foto_hama", images(HOME / "dataset_v3" / "test" / "images"))):
        res[f"false_{name}"] = r = false_warnings(model, a.conf, files)
        print(f"    {name:<10} {r['warnings']:>4}/{r['images']:<5} = {r['rate']:6.1%}  {r['by_class']}")
    if Path(a.video).exists():
        res["video_demo"] = v = video_warnings(model, a.conf, Path(a.video))
        print(f"    video demo {v['checks_with_warning']}/{v['checks']} pengecekan berisi peringatan {v['by_class']}")

    sheet_path = Path(a.out).with_name("disease_test_sheet.jpg")
    sheet(model, a.conf, Path(a.data).parent / "test", sheet_path)
    Path(a.out).write_text(json.dumps(res, indent=2))
    print(f"\nTersimpan: {a.out}\nContact sheet: {sheet_path}")


if __name__ == "__main__":
    main()
