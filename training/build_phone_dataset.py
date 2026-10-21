#!/usr/bin/env python3
"""
SIPETIK — data sintetis "foto hama di layar HP, dipegang di depan webcam".

Kenapa: pengguna menguji kamera dengan menunjukkan foto hama di layar HP.
Model dilatih dari foto asli; di webcam, foto di layar HP tampil miring,
silau, buram, ada pola moiré & bingkai/UI HP, dan sering dipegang di depan
badan orang. Model hama tetap melihat werengnya (conf 0,49-0,76) tapi di
batas ambang, dan detektor orang ikut salah menandai serangga sebagai orang.

Yang dibuat (semua kotak label ikut ditransformasi secara geometris):
    pos   : foto hama (dataset_v4 train/valid) di layar HP -> label hama
    neg   : foto BUKAN hama di layar HP (COCO, daun sakit, malai) -> label kosong
            supaya model tidak belajar "HP = hama"
    test  : dari split TEST + latar COCO eval (tidak pernah dilatih) -> untuk
            mengukur, bukan untuk training

Latar: foto COCO (orang, ruangan) — HP sering menutupi sebagian badan orang,
persis kasus "hama + manusia dalam satu frame".

    python training/build_phone_dataset.py
"""

import argparse
import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dataset_v3 as v3  # noqa: E402

HOME = v3.HOME_DATA
OUT_W, OUT_H = 640, 480  # resolusi webcam main.py
NP = np.random.default_rng(5)  # acak untuk array (noise, perspektif)


# ------------------------------------------------------------------ helpers
def read_boxes(lbl: Path):
    """label YOLO -> [(cls, x1, y1, x2, y2) dalam 0..1]"""
    out = []
    for line in (lbl.read_text().splitlines() if lbl.exists() else []):
        p = line.split()
        if len(p) < 5:
            continue
        b = v3.as_box(p).split()
        c, cx, cy, w, h = int(b[0]), *map(float, b[1:5])
        out.append((c, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


def screen_content(img, boxes, rng, sw, sh):
    """Tampilan layar HP: gambar di tengah, bilah status, judul/teks di bawah
    (seperti Google Images). Kembalikan (layar, boxes dalam piksel layar)."""
    bg = (255, 255, 255) if rng.random() < 0.5 else (18, 18, 18)
    fg = (40, 40, 40) if bg[0] > 128 else (225, 225, 225)
    scr = np.full((sh, sw, 3), bg, np.uint8)
    top = int(sh * rng.uniform(0.04, 0.18))
    cv2.rectangle(scr, (0, 0), (sw, int(sh * 0.035)), (bg[0] * 0.9,) * 3, -1)  # status bar
    ih, iw = img.shape[:2]
    max_h = int(sh * rng.uniform(0.45, 0.8))
    s = min(sw / iw, max_h / ih) * rng.uniform(0.85, 1.0)
    nw, nh = int(iw * s), int(ih * s)
    x0 = (sw - nw) // 2
    scr[top:top + nh, x0:x0 + nw] = cv2.resize(img, (nw, nh))
    # teks palsu di bawah gambar (judul artikel, tombol)
    y = top + nh + int(sh * 0.04)
    for _ in range(rng.randint(1, 3)):
        if y > sh - 10:
            break
        L = rng.randint(int(sw * 0.4), int(sw * 0.9))
        cv2.rectangle(scr, (int(sw * 0.06), y), (int(sw * 0.06) + L, y + max(4, sh // 70)), fg, -1)
        y += int(sh * 0.035)
    pb = [(c, x0 + a * nw, top + b * nh, x0 + cc * nw, top + d * nh) for c, a, b, cc, d in boxes]
    return scr, pb


def phone_frame(scr, rng):
    """Bingkai HP (bezel hitam membulat)."""
    sh, sw = scr.shape[:2]
    pad = max(6, int(sw * rng.uniform(0.03, 0.06)))
    ph = np.zeros((sh + 2 * pad, sw + 2 * pad, 3), np.uint8)
    ph[:] = (rng.randint(5, 40),) * 3
    ph[pad:pad + sh, pad:pad + sw] = scr
    return ph, pad


def moire(img, rng):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    f = rng.uniform(0.6, 1.4)
    ang = rng.uniform(0, np.pi)
    pat = np.sin((xx * np.cos(ang) + yy * np.sin(ang)) * f)
    amp = rng.uniform(3, 12)
    return np.clip(img.astype(np.float32) + amp * pat[..., None], 0, 255).astype(np.uint8)


def glare(img, rng):
    h, w = img.shape[:2]
    m = np.zeros((h, w), np.float32)
    c = (rng.randint(0, w), rng.randint(0, h))
    ax = (rng.randint(w // 6, w // 2), rng.randint(h // 8, h // 3))
    cv2.ellipse(m, c, ax, rng.uniform(0, 180), 0, 360, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), max(w, h) / 10) * rng.uniform(0.25, 0.7)
    return np.clip(img * (1 - m[..., None]) + 255 * m[..., None], 0, 255).astype(np.uint8)


def finger(canvas, quad, rng):
    """Jari/tangan menutupi tepi HP."""
    if rng.random() > 0.5:
        return
    tone = np.array([rng.randint(120, 200), rng.randint(140, 200), rng.randint(170, 240)], float)
    i = rng.randint(0, 3)
    p, q = quad[i], quad[(i + 1) % 4]
    t = rng.uniform(0.2, 0.8)
    cx, cy = p + (q - p) * t
    L = np.linalg.norm(q - p)
    cv2.ellipse(canvas, (int(cx), int(cy)), (int(L * 0.08), int(L * 0.18)),
                rng.uniform(0, 180), 0, 360, tone.tolist(), -1)


def compose(content, boxes, bg, rng):
    """content (gambar) -> layar HP -> di atas latar dengan perspektif & efek.
    Kembalikan (frame 640x480, boxes YOLO terhadap frame)."""
    sw = rng.randint(300, 520)
    sh = int(sw * rng.uniform(1.6, 2.1)) if rng.random() < 0.75 else int(sw * rng.uniform(0.5, 0.65))
    scr, pboxes = screen_content(content, boxes, rng, sw, sh)
    scr = moire(scr, rng) if rng.random() < 0.6 else scr
    ph, pad = phone_frame(scr, rng)
    pboxes = [(c, a + pad, b + pad, cc + pad, d + pad) for c, a, b, cc, d in pboxes]

    frame = cv2.resize(bg, (OUT_W, OUT_H))
    # ukuran & posisi HP di frame
    ph_h, ph_w = ph.shape[:2]
    target_h = OUT_H * rng.uniform(0.45, 1.05)
    s = target_h / ph_h
    w2, h2 = ph_w * s, ph_h * s
    cx, cy = rng.uniform(w2 * 0.3, OUT_W - w2 * 0.3), rng.uniform(OUT_H * 0.3, OUT_H * 0.75)
    src = np.float32([[0, 0], [ph_w, 0], [ph_w, ph_h], [0, ph_h]])
    base = np.float32([[-w2 / 2, -h2 / 2], [w2 / 2, -h2 / 2], [w2 / 2, h2 / 2], [-w2 / 2, h2 / 2]])
    ang = np.deg2rad(rng.uniform(-18, 18))
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]], np.float32)
    dst = base @ R.T
    dst += NP.uniform(-0.08, 0.08, dst.shape).astype(np.float32) * np.float32([w2, h2])  # perspektif
    dst += np.float32([cx, cy])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(ph, M, (OUT_W, OUT_H))
    mask = cv2.warpPerspective(np.full((ph_h, ph_w), 255, np.uint8), M, (OUT_W, OUT_H))
    # layar memancarkan cahaya: sedikit lebih terang / beda warna dari ruangan
    warped = np.clip(warped.astype(np.float32) * rng.uniform(0.85, 1.25)
                     + NP.uniform(-15, 15, 3), 0, 255).astype(np.uint8)
    frame[mask > 0] = warped[mask > 0]
    finger(frame, dst, rng)
    if rng.random() < 0.7:
        frame = glare(frame, rng)
    if rng.random() < 0.6:
        k = rng.choice([3, 5, 7])
        frame = cv2.GaussianBlur(frame, (k, k), 0)
    if rng.random() < 0.3:  # motion blur
        k = rng.choice([5, 9])
        ker = np.zeros((k, k), np.float32)
        ker[k // 2, :] = 1 / k
        frame = cv2.filter2D(frame, -1, ker)
    frame = np.clip(frame.astype(np.float32) + NP.normal(0, rng.uniform(2, 6), frame.shape), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(55, 90)])
    frame = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    out = []
    for c, a, b, cc, d in pboxes:
        pts = np.float32([[a, b], [cc, b], [cc, d], [a, d]]).reshape(-1, 1, 2)
        t = cv2.perspectiveTransform(pts, M).reshape(-1, 2)
        x1, y1 = np.clip(t.min(0), 0, [OUT_W, OUT_H])
        x2, y2 = np.clip(t.max(0), 0, [OUT_W, OUT_H])
        full = (t.max(0) - t.min(0)).prod()
        if (x2 - x1) < 5 or (y2 - y1) < 5 or (x2 - x1) * (y2 - y1) < 0.5 * full:
            continue
        out.append(f"{c} {(x1 + x2) / 2 / OUT_W:.6f} {(y1 + y2) / 2 / OUT_H:.6f} "
                   f"{(x2 - x1) / OUT_W:.6f} {(y2 - y1) / OUT_H:.6f}")
    return frame, out


# ------------------------------------------------------------------ main
def pest_images(split_dir: Path):
    """Gambar dengan minimal satu box hama (bukan negatif)."""
    imgs = {p.stem: p for p in v3._images(split_dir / "images")}  # satu kali scan folder
    res = []
    for lbl in sorted((split_dir / "labels").glob("*.txt")):
        boxes = read_boxes(lbl)
        if boxes and lbl.stem in imgs:
            res.append((imgs[lbl.stem], boxes))
    return res


def write(out_split: Path, name, frame, lines):
    (out_split / "images").mkdir(parents=True, exist_ok=True)
    (out_split / "labels").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_split / "images" / f"{name}.jpg"), frame)
    (out_split / "labels" / f"{name}.txt").write_text("\n".join(lines))


def _one(job):
    img_p, boxes, bg_p, seed, out_split, name = job
    rng = random.Random(seed)
    global NP
    NP = np.random.default_rng(seed)
    img, bg = cv2.imread(str(img_p)), cv2.imread(str(bg_p))
    if img is None or bg is None:
        return 0
    frame, lines = compose(img, boxes, bg, rng)
    if boxes and not lines:
        return 0  # semua box terpotong — jangan jadikan negatif palsu
    write(Path(out_split), name, frame, lines)
    return 1


def make(items, bgs, n, out_split, tag, rng, close_bgs=None):
    """n gambar komposit; separuh latar dari close_bgs (orang dekat kamera)."""
    from multiprocessing import Pool
    jobs = []
    for i in range(n):
        img_p, boxes = items[i % len(items)]
        pool_bg = close_bgs if close_bgs and rng.random() < 0.5 else bgs
        jobs.append((img_p, boxes, rng.choice(pool_bg), rng.randrange(1 << 30), str(out_split), f"{tag}_{i:05d}"))
    (out_split / "images").mkdir(parents=True, exist_ok=True)
    (out_split / "labels").mkdir(parents=True, exist_ok=True)
    with Pool(8) as pool:
        return sum(pool.imap_unordered(_one, jobs, chunksize=16))


def close_up_people(paths, min_area=0.20):
    """Foto yang orangnya besar di frame (seperti orang duduk di depan webcam)."""
    from ultralytics import YOLO
    m = YOLO(str(Path(__file__).resolve().parent.parent / "yolov8n.pt"))
    keep = []
    for i in range(0, len(paths), 32):
        for p, r in zip(paths[i:i + 32], m.predict([str(x) for x in paths[i:i + 32]], classes=[0],
                                                     conf=0.5, device=0, verbose=False)):
            h, w = r.orig_shape
            if any((b[2] - b[0]) * (b[3] - b[1]) / (w * h) >= min_area for b in r.boxes.xyxy.tolist()):
                keep.append(p)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4", default=str(HOME / "dataset_v4"))
    ap.add_argument("--out", default=str(HOME / "dataset_v5"))
    ap.add_argument("--test-out", default=str(HOME / "phone_test"))
    ap.add_argument("--pos", type=int, default=6000)
    ap.add_argument("--neg", type=int, default=2500)
    a = ap.parse_args()
    rng = random.Random(5)
    np.random.seed(5)
    v4, out, test_out = Path(a.v4), Path(a.out), Path(a.test_out)
    for d in (out, test_out):
        if d.exists():
            shutil.rmtree(d)

    # 1. salin dataset_v4 (hardlink)
    for sp in ("train", "valid", "test"):
        for img in v3._images(v4 / sp / "images"):
            v3._place(img, out / sp / "images" / img.name)
            lbl = v4 / sp / "labels" / (img.stem + ".txt")
            (out / sp / "labels").mkdir(parents=True, exist_ok=True)
            (out / sp / "labels" / lbl.name).write_text(lbl.read_text() if lbl.exists() else "")

    # latar & konten negatif: train/valid pakai COCO dari v4; test pakai COCO eval (held-out)
    coco_tr = [p for p in v3._images(v4 / "train" / "images") if p.name.startswith("coco_")]
    coco_va = [p for p in v3._images(v4 / "valid" / "images") if p.name.startswith("coco_")]
    neg_tr = coco_tr + [p for p in v3._images(v4 / "train" / "images") if p.name.startswith(("rice-leaf", "rice-panicle"))]
    neg_va = coco_va + [p for p in v3._images(v4 / "valid" / "images") if p.name.startswith(("rice-leaf", "rice-panicle"))]
    coco_ev = v3._images(HOME / "eval_negatives" / "coco")
    leaf_ev = v3._images(HOME / "eval_negatives" / "rice_leaf")

    pos_tr = pest_images(v4 / "train")
    pos_va = pest_images(v4 / "valid")
    pos_te = pest_images(v4 / "test")
    for lst in (pos_tr, pos_va, pos_te, neg_tr, neg_va):
        rng.shuffle(lst)

    close_tr, close_va, close_ev = (close_up_people(x) for x in (coco_tr, coco_va, coco_ev[:1500]))
    print(f"  latar orang-dekat: train {len(close_tr)}, valid {len(close_va)}, test {len(close_ev)}")
    st = {}
    st["train pos"] = make(pos_tr, coco_tr, a.pos, out / "train", "phone", rng, close_tr)
    st["train neg"] = make([(p, []) for p in neg_tr], coco_tr, a.neg, out / "train", "phoneneg", rng, close_tr)
    st["valid pos"] = make(pos_va, coco_va, a.pos // 10, out / "valid", "phone", rng, close_va)
    st["valid neg"] = make([(p, []) for p in neg_va], coco_va, a.neg // 10, out / "valid", "phoneneg", rng, close_va)
    # TEST (untuk evaluasi saja): foto hama test set + latar COCO eval
    st["test pos"] = make(pos_te, coco_ev[:1500], 1200, test_out / "pos", "phone", rng, close_ev)
    st["test neg"] = make([(p, []) for p in coco_ev[1500:] + leaf_ev[:600]], coco_ev[:1500], 800,
                          test_out / "neg", "phoneneg", rng, close_ev)
    for k, v in st.items():
        print(f"  {k:<10} {v}")
    cfg = yaml.safe_load((v4 / "data_v3.yaml").read_text(encoding="utf-8"))
    cfg["path"] = out.as_posix()
    (out / "data_v5.yaml").write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    (test_out / "data.yaml").write_text(yaml.dump({**cfg, "path": test_out.as_posix(),
                                                  "train": "pos/images", "val": "pos/images", "test": "pos/images"},
                                                 sort_keys=False), encoding="utf-8")
    print(f"dataset: {out}\ntest   : {test_out}")


if __name__ == "__main__":
    main()
