#!/usr/bin/env python3
"""
SIPETIK — uji tracking (--confirm-frames) pada VIDEO, bukan foto diam.

Memakai main.PestDetector APA ADANYA (kode yang sama dengan kamera):

1. Video TANPA hama (default: video demo 1080p miniatur sawah SIPETIK):
   berapa kali buzzer akan bunyi (cooldown 10 dtk seperti main.py) dan
   berapa frame memuat "hama".
2. Klip BERISI hama: tiap foto test set dijadikan klip 1 detik (30 frame)
   dengan gerakan kamera kecil (geser, zoom, noise sensor, perubahan
   cahaya). Mengukur apakah alarm tetap bunyi dan berapa frame jedanya.
   Klip ini SINTETIS — tanda bahwa tracking tidak "membuang" hama nyata,
   bukan pengganti rekaman lapangan.

    python training/eval_video.py
    python training/eval_video.py --video "D:/rekaman/sawah.mp4" --per-class 20
    python training/eval_video.py --only tiling
"""

import argparse
import json
import random
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
FPS = 30
COOLDOWN_S = 10


def configs(pest="pest_v3.pt"):
    coco = YOLO(str(ROOT / "yolov8n.pt"))
    tag = "v3" if pest == "pest_v3.pt" else Path(pest).stem
    m = lambda: YOLO(str(ROOT / pest))  # noqa: E731 - model terpisah per konfigurasi
    return {
        "lama (best.pt + pest_v2.pt)": dict(model_main=YOLO(str(ROOT / "best.pt")), model_coco=coco,
                                            model_extra=YOLO(str(ROOT / "pest_v2.pt")), confirm_frames=1,
                                            human_conf=0.35, human_filter=True),
        f"{tag} tanpa tracking": dict(model_main=m(), model_coco=coco, confirm_frames=1),
        f"{tag} + tracking (3 frame)": dict(model_main=m(), model_coco=coco, confirm_frames=3),
        f"{tag} + tracking + tiling 2x2": dict(model_main=m(), model_coco=coco, confirm_frames=3,
                                               tiles=2, min_area=0.002),
    }


def make_detector(cfg, conf):
    return cam.PestDetector(cfg["model_main"], cfg["model_coco"], cfg.get("model_extra"),
                            conf=conf, device="cuda:0", confirm_frames=cfg["confirm_frames"],
                            tiles=cfg.get("tiles", 1), min_area=cfg.get("min_area", 0.01),
                            human_conf=cfg.get("human_conf", 0.5), human_filter=cfg.get("human_filter", False))


def fit_640(frame):
    h, w = frame.shape[:2]
    return cv2.resize(frame, (640, int(round(640 * h / w))))


def run_negative_video(det, path: Path):
    det.reset()
    capv = cv2.VideoCapture(str(path))
    n = alarms = frames_with = 0
    last = -1e9
    by_cls = Counter()
    while True:
        ok, fr = capv.read()
        if not ok:
            break
        _, pests = det.detect(fit_640(fr))
        t = n / FPS
        if pests:
            frames_with += 1
            by_cls.update(p[0] for p in pests)
            if t - last >= COOLDOWN_S:
                alarms += 1
                last = t
        n += 1
    return {"frames": n, "frames_with_pest": frames_with, "alarms": alarms,
            "by_class": dict(by_cls.most_common())}


def jitter_clip(img, rng, n=FPS):
    """Klip n frame: geser pelan, zoom kecil, noise sensor, cahaya berubah."""
    h, w = img.shape[:2]
    dx, dy = rng.uniform(-0.03, 0.03) * w, rng.uniform(-0.03, 0.03) * h
    z1 = rng.uniform(1.0, 1.06)
    b0, b1 = rng.uniform(0.92, 1.08), rng.uniform(0.92, 1.08)
    for i in range(n):
        a = i / (n - 1)
        z = 1 + (z1 - 1) * a
        M = np.float32([[z, 0, (1 - z) * w / 2 + dx * a], [0, z, (1 - z) * h / 2 + dy * a]])
        fr = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        fr = fr.astype(np.float32) * (b0 + (b1 - b0) * a) + rng.normal(0, 3, fr.shape)
        yield np.clip(fr, 0, 255).astype(np.uint8)


def visible_test_images(test_dir: Path, names, per_class, seed=0):
    """Gambar test yang hamanya cukup besar untuk lolos filter --min-area."""
    by_cls = defaultdict(list)
    for lbl in sorted((test_dir / "labels").glob("*.txt")):
        best = {}
        for line in lbl.read_text().splitlines():
            p = line.split()
            if len(p) < 5:
                continue
            v = list(map(float, p[1:]))
            area = v[2] * v[3] if len(v) == 4 else (max(v[0::2]) - min(v[0::2])) * (max(v[1::2]) - min(v[1::2]))
            best[int(p[0])] = max(best.get(int(p[0]), 0), area)
        for c, a in best.items():
            if a >= 0.01:
                img = next((test_dir / "images").glob(lbl.stem + ".*"), None)
                if img:
                    by_cls[names[c]].append(img)
    rng = random.Random(seed)
    return {c: rng.sample(v, min(per_class, len(v))) for c, v in sorted(by_cls.items())}


def norm(raw):
    return "tikus" if raw.lower() in ("rat", "tikus") else raw


def run_positive_clips(det, picks):
    res = {}
    for cls, imgs in picks.items():
        hit, delays = 0, []
        for k, p in enumerate(imgs):
            det.reset()
            rng = np.random.default_rng(k)
            for i, fr in enumerate(jitter_clip(fit_640(cv2.imread(str(p))), rng)):
                _, pests = det.detect(fr)
                if any(norm(x[0]) == cls for x in pests):
                    hit += 1
                    delays.append(i + 1)
                    break
        res[cls] = {"clips": len(imgs), "alarm": hit,
                    "median_frame_to_alarm": float(np.median(delays)) if delays else None}
        print(f"      {cls:<18} {hit:>3}/{len(imgs):<3} alarm, median frame ke-{res[cls]['median_frame_to_alarm']}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(ROOT.parent.parent / "VIDEO DEMO SIPETIK.mp4"))
    ap.add_argument("--test-dir", default=str(HOME / "dataset_v3" / "test"))
    ap.add_argument("--per-class", type=int, default=30)
    ap.add_argument("--conf", type=float, default=0.55)
    ap.add_argument("--only", default=None, help="Jalankan konfigurasi yang namanya memuat teks ini")
    ap.add_argument("--pest", default="pest_v3.pt", help="Model hama yang diuji (mis. pest_v4.pt)")
    ap.add_argument("--out", default=str(ROOT / "training" / "benchmarks" / "tracking_video.json"))
    a = ap.parse_args()

    names = yaml.safe_load((Path(a.test_dir).parent / "data_v3.yaml").read_text(encoding="utf-8"))["names"]
    picks = visible_test_images(Path(a.test_dir), names, a.per_class)
    out_path = Path(a.out)
    out = json.loads(out_path.read_text()) if out_path.exists() else {}
    out.update({"video": Path(a.video).name, "conf": a.conf, "cooldown_s": COOLDOWN_S})
    out.setdefault("results", {})
    for name, cfg in configs(a.pest).items():
        if a.only and a.only not in name:
            continue
        det = make_detector(cfg, a.conf)
        print(f"\n[{name}]")
        neg = run_negative_video(det, Path(a.video))
        print(f"    video tanpa hama: {neg['alarms']} alarm buzzer, "
              f"{neg['frames_with_pest']}/{neg['frames']} frame berisi 'hama' {neg['by_class']}")
        entry = {"negative_video": neg}
        if not name.startswith("lama"):
            print("    klip berisi hama (sintetis, 30 frame):")
            entry["positive_clips"] = run_positive_clips(det, picks)
        out["results"][name] = entry
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nTersimpan: {a.out}")


if __name__ == "__main__":
    main()
