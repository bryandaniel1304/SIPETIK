#!/usr/bin/env python3
"""
SIPETIK — uji "foto hama di layar HP di depan webcam" (cara user menguji).

Set uji dari build_phone_dataset.py (~/sipetik/phone_test), dibuat dari
foto TEST + latar COCO eval — tidak pernah dipakai training:
    pos/  foto hama di layar HP (sebagian dipegang di depan orang)
    neg/  HP yang menampilkan BUKAN hama (orang, ruangan, daun sakit)

Memakai main.PestDetector (filter & ambang sama dengan kamera). Diukur:
    - hama di HP terdeteksi dengan kelas benar (per kelas)
    - serangga DIKIRA ORANG (kotak orang menimpa serangga, IoU > 0.3)
    - frame berisi orang DAN hama: keduanya dikenali benar
    - HP tanpa hama yang tetap memicu alarm (alarm palsu)
    - (opsional) rekaman layar user, diputar dengan tracking

    python training/eval_phone.py --pest pest_v4.pt
    python training/eval_phone.py --pest pest_v5.pt --person yolo11s.pt --rec "...mp4"
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
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from ultralytics import YOLO  # noqa: E402

import main as cam  # noqa: E402

HOME = Path.home() / "sipetik"


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0


def gt_boxes(lbl: Path, w, h, names):
    out = []
    for line in (lbl.read_text().splitlines() if lbl.exists() else []):
        p = line.split()
        if len(p) == 5:
            c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:])
            out.append((names[c], [(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]))
    return out


def run(det, test_dir: Path, names):
    per = defaultdict(lambda: [0, 0])
    insect_as_person = both_frames = both_ok = 0
    for p in sorted((test_dir / "pos" / "images").glob("*.jpg")):
        fr = cv2.imread(str(p))
        h, w = fr.shape[:2]
        gts = gt_boxes(test_dir / "pos" / "labels" / (p.stem + ".txt"), w, h, names)
        humans, pests = det.detect(fr)
        got = {cam.get_display_label(x[0])[0] for x in pests} | {x[0] for x in pests}
        for c in {g[0] for g in gts}:
            per[c][1] += 1
            per[c][0] += c in got
        if any(iou(hb, gb) > 0.3 for _, _, hb in humans for _, gb in gts):
            insect_as_person += 1
        if humans:  # frame berisi orang (latar) + hama di HP
            both_frames += 1
            both_ok += any(g[0] in got for g in gts)
    fp, fp_cls = 0, Counter()
    neg = sorted((test_dir / "neg" / "images").glob("*.jpg"))
    for p in neg:
        _, pests = det.detect(cv2.imread(str(p)))
        pests = [x for x in pests if x[0] != "bird"]
        if pests:
            fp += 1
            fp_cls.update({x[0] for x in pests})
    hit = sum(v[0] for v in per.values())
    tot = sum(v[1] for v in per.values())
    return {"per_class": {c: f"{a}/{b}" for c, (a, b) in sorted(per.items())},
            "pest_hit": f"{hit}/{tot}", "pest_rate": round(hit / tot, 4),
            "insect_as_person": insect_as_person, "person_and_pest_frames": both_frames,
            "person_and_pest_ok": both_ok, "neg_false_alarm": f"{fp}/{len(neg)}", "neg_by_class": dict(fp_cls)}


def run_recording(det, path, crop_top=50):
    det.reset()
    c = cv2.VideoCapture(str(path))
    n = hit = 0
    by = Counter()
    while True:
        ok, fr = c.read()
        if not ok:
            break
        fr = fr[crop_top:]
        fr = cv2.resize(fr, (640, int(640 * fr.shape[0] / fr.shape[1])))
        _, pests = det.detect(fr)
        n += 1
        if pests:
            hit += 1
            by.update(x[0] for x in pests)
    return {"frames": n, "frames_with_pest": hit, "by_class": dict(by)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pest", default="pest_v4.pt")
    ap.add_argument("--person", default="yolov8n.pt", help="Detektor orang (COCO): yolov8n.pt / yolo11s.pt")
    ap.add_argument("--test", default=str(HOME / "phone_test"))
    ap.add_argument("--rec", default=None, help="Rekaman layar user (opsional)")
    ap.add_argument("--out", default=str(ROOT / "training" / "benchmarks" / "phone_eval.json"))
    a = ap.parse_args()

    names = yaml.safe_load((Path(a.test) / "data.yaml").read_text(encoding="utf-8"))["names"]
    pest, person = YOLO(str(ROOT / a.pest)), YOLO(str(ROOT / a.person))
    det = cam.PestDetector(pest, person, device="cuda:0", conf=0.55, human_conf=0.5,
                           human_filter=False, confirm_frames=1)
    res = run(det, Path(a.test), names)
    if a.rec:
        res["recording"] = run_recording(cam.PestDetector(pest, person, device="cuda:0", conf=0.55,
                                                          human_conf=0.5, human_filter=False,
                                                          confirm_frames=3), a.rec)
    key = f"{Path(a.pest).stem} + {Path(a.person).stem}"
    print(f"[{key}]")
    print(f"  hama di HP terdeteksi : {res['pest_hit']} ({res['pest_rate']:.1%})  {res['per_class']}")
    print(f"  serangga dikira orang : {res['insect_as_person']}")
    print(f"  orang + hama 1 frame  : {res['person_and_pest_ok']}/{res['person_and_pest_frames']} hama tetap terdeteksi")
    print(f"  HP tanpa hama -> alarm: {res['neg_false_alarm']} {res['neg_by_class']}")
    if a.rec:
        r = res["recording"]
        print(f"  rekaman user          : {r['frames_with_pest']}/{r['frames']} frame {r['by_class']}")
    out = Path(a.out)
    allres = json.loads(out.read_text()) if out.exists() else {}
    allres[key] = res
    out.write_text(json.dumps(allres, indent=2))


if __name__ == "__main__":
    main()
