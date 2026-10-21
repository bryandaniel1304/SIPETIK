#!/usr/bin/env python3
"""
SIPETIK — benchmark GPU yang sama persis di laptop mana pun.

Mengukur 2 hal yang benar-benar dipakai SIPETIK:
  1. INFERENSI kamera: pipeline main.py per frame (yolov8n COCO untuk
     manusia + model hama), latency ms & FPS, PyTorch dan (--trt)
     TensorRT, plus kapasitas GPU murni (batch 16, FP32 & FP16).
  2. TRAINING: throughput (gambar/detik) yolov8n 640px, batch 8, subset
     tetap 800 gambar dari dataset_v2 yang di-cache ke RAM (supaya yang
     diukur GPU-nya, bukan kecepatan disk). Batch 8 dipilih karena muat di
     VRAM 4 GB GTX 1650 maupun 8 GB RTX 5070 — perbandingan apel-ke-apel.

Hasil disimpan ke training/benchmarks/<nama-gpu>.json. Karena G: adalah
drive USB, colok ke laptop lama (GTX 1650), jalankan script yang sama,
dan training/benchmark_report.py akan membandingkan semua JSON yang ada.

    python training/benchmark_gpu.py
    python training/benchmark_gpu.py --skip-train     # cuma inferensi (cepat)
    python training/benchmark_gpu.py --trt            # + TensorRT (pip install tensorrt-cu12/cu13)
"""

import argparse
import json
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import windows_git_fix  # noqa: E402,F401

import cv2  # noqa: E402
import torch  # noqa: E402
from ultralytics import YOLO  # noqa: E402

TRAINING_DIR = ROOT / "training"
OUT_DIR      = TRAINING_DIR / "benchmarks"
DATASET_V2   = TRAINING_DIR / "dataset_v2"

INFER_MODELS = [  # (label, file) — sama dengan yang dimuat main.py
    ("coco_person", "yolov8n.pt"),
    ("tikus_best", "best.pt"),
    ("hama_v2", "pest_v2.pt"),
    ("hama_v3", "pest_v3.pt"),
    ("hama_v4_11s", "pest_v4.pt"),
    ("penyakit", "disease_v1.pt"),  # dicek tiap 2 dtk di main.py, bukan tiap frame
]


def gpu_info() -> dict:
    p = torch.cuda.get_device_properties(0)
    return {
        "gpu": p.name,
        "vram_gb": round(p.total_memory / 1024**3, 1),
        "sm": f"{p.major}.{p.minor}",
        "sm_count": p.multi_processor_count,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cpu": platform.processor(),
        "date": datetime.now().isoformat(timespec="seconds"),
    }


def load_frames(n=60):
    imgs = sorted((DATASET_V2 / "test" / "images").glob("*.*"))
    random.Random(0).shuffle(imgs)
    frames = []
    for p in imgs[:n]:
        im = cv2.imread(str(p))
        if im is not None:
            frames.append(cv2.resize(im, (640, 480)))  # resolusi webcam main.py
    return frames


def _time_ms(fn, iters, warmup=20):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    samples = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        torch.cuda.synchronize()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


def engine_for(pt: Path) -> Path:
    """Bangun engine TensorRT FP16 khusus GPU ini (engine tidak bisa dipindah
    antar GPU), di-cache di training/benchmarks/engines/<gpu>/."""
    slug = "".join(c if c.isalnum() else "_" for c in torch.cuda.get_device_name(0))
    out = OUT_DIR / "engines" / slug / (pt.stem + ".engine")
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.parent / pt.name
        shutil.copy2(pt, tmp)
        built = Path(YOLO(str(tmp)).export(format="engine", half=True, imgsz=640,
                                           device=0, verbose=False))
        shutil.move(str(built), out)
        for leftover in out.parent.glob(pt.stem + ".*"):
            if leftover.suffix != ".engine":
                leftover.unlink()
    return out


def pipelines(res: dict) -> dict:
    # main.py LAMA = coco + tikus(best.pt) + hama_v2 ; BARU = coco + hama_v3
    old = sum(res.get(k, 0) for k in ("coco_person", "tikus_best", "hama_v2"))
    new = sum(res[k] for k in ("coco_person", "hama_v3")) if "hama_v3" in res else None
    v4 = sum(res[k] for k in ("coco_person", "hama_v4_11s")) if "hama_v4_11s" in res else None
    return {
        "median_ms_per_model": res,
        "pipeline_old_ms": round(old, 2), "pipeline_old_fps": round(1000 / old, 1),
        "pipeline_new_ms": round(new, 2) if new else None,
        "pipeline_new_fps": round(1000 / new, 1) if new else None,
        "pipeline_v4_ms": round(v4, 2) if v4 else None,
        "pipeline_v4_fps": round(1000 / v4, 1) if v4 else None,
    }


def bench_infer(frames, iters=300, trt=False) -> dict:
    """Latency per frame persis seperti main.py: model.predict() 1 frame
    640x480 (preprocess + GPU + NMS), median dari `iters` frame."""
    out = {}
    avail = [(lbl, ROOT / f) for lbl, f in INFER_MODELS if (ROOT / f).exists()]
    modes = [("pytorch_fp32", lambda p: p)]
    if trt:
        modes.append(("tensorrt_fp16", engine_for))
    for mode, to_file in modes:
        res = {}
        for lbl, pt in avail:
            m = YOLO(str(to_file(pt)), task="detect")
            it = iter(range(10**9))
            res[lbl] = round(_time_ms(lambda: m.predict(
                frames[next(it) % len(frames)], imgsz=640, device=0, verbose=False), iters), 2)
        out[mode] = pipelines(res)
        print(f"  [{mode}] {res} -> lama {out[mode]['pipeline_old_ms']} ms"
              + (f", baru {out[mode]['pipeline_new_ms']} ms" if out[mode]["pipeline_new_ms"] else ""))

    # Kapasitas GPU murni (tanpa overhead Python/Windows): yolov8n, batch 16.
    net = YOLO(str(ROOT / "yolov8n.pt")).model.cuda().eval()
    cap = {}
    with torch.no_grad():
        for dt in (torch.float32, torch.float16):
            n = net.half() if dt == torch.float16 else net.float()
            x = torch.rand(16, 3, 640, 640, device="cuda", dtype=dt)
            ms = _time_ms(lambda: n(x), 50, warmup=10)
            cap[str(dt).split(".")[-1]] = round(16 * 1000 / ms, 1)
    out["gpu_raw_img_per_s_batch16"] = cap
    print(f"  [kapasitas GPU] yolov8n 640px batch16: {cap} gambar/detik")
    return out


def bench_train(n_train=800, n_val=100, batch=8, epochs=3) -> dict:
    src_tr = sorted((DATASET_V2 / "train" / "images").glob("*.*"))
    src_va = sorted((DATASET_V2 / "valid" / "images").glob("*.*"))
    random.Random(0).shuffle(src_tr)
    random.Random(0).shuffle(src_va)
    tmp = Path(tempfile.mkdtemp(prefix="sipetik_bench_"))
    try:
        for split, files in (("train", src_tr[:n_train]), ("valid", src_va[:n_val])):
            (tmp / split / "images").mkdir(parents=True)
            (tmp / split / "labels").mkdir(parents=True)
            for f in files:
                shutil.copy2(f, tmp / split / "images" / f.name)
                lbl = DATASET_V2 / split / "labels" / (f.stem + ".txt")
                if lbl.exists():
                    shutil.copy2(lbl, tmp / split / "labels" / lbl.name)
        names = {i: f"c{i}" for i in range(9)}
        (tmp / "data.yaml").write_text(
            f"path: {tmp.as_posix()}\ntrain: train/images\nval: valid/images\nnames: {json.dumps(names)}\n")

        model = YOLO(str(ROOT / "yolov8n.pt"))
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        model.train(data=str(tmp / "data.yaml"), epochs=epochs, imgsz=640, batch=batch,
                    workers=4, cache="ram", device=0, val=False, plots=False,
                    project=str(tmp / "runs"), name="b", exist_ok=True, verbose=False)
        wall = time.perf_counter() - t0
        import csv
        rows = list(csv.DictReader(open(tmp / "runs" / "b" / "results.csv")))
        times = [float(r["time"]) for r in rows]
        per_epoch = [b - a for a, b in zip([0] + times[:-1], times)]
        steady = statistics.median(per_epoch[1:]) if len(per_epoch) > 1 else per_epoch[0]
        amp = bool(model.trainer.amp) if getattr(model, "trainer", None) else None
        return {
            "images_per_epoch": n_train, "batch": batch, "epochs": epochs,
            "sec_per_epoch_steady": round(steady, 2),
            "train_img_per_s": round(n_train / steady, 1),
            "amp_fp16_training": amp,
            "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1024**3, 2),
            "wall_s": round(wall, 1),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--skip-infer", action="store_true")
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--trt", action="store_true", help="Ikut ukur TensorRT (bangun engine dulu, beberapa menit)")
    args = ap.parse_args()

    if not torch.cuda.is_available():
        sys.exit("CUDA tidak tersedia — benchmark ini butuh GPU NVIDIA.")

    info = gpu_info()
    print(f"GPU: {info['gpu']}  VRAM {info['vram_gb']} GB  sm_{info['sm']}")
    result = {"info": info}
    if not args.skip_infer:
        print("Benchmark inferensi ...")
        result["inference"] = bench_infer(load_frames(), args.iters, args.trt)
    if not args.skip_train:
        print("Benchmark training (3 epoch kecil) ...")
        result["training"] = bench_train()
        print(f"  {result['training']}")

    OUT_DIR.mkdir(exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in info["gpu"]).strip("_")
    path = OUT_DIR / f"{slug}.json"
    if path.exists():  # --skip-train / --skip-infer: simpan bagian yang tidak diulang
        result = {**json.loads(path.read_text()), **result}
    path.write_text(json.dumps(result, indent=2))
    print(f"\nTersimpan: {path}")


if __name__ == "__main__":
    main()
