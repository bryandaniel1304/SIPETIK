#!/usr/bin/env python3
"""
SIPETIK — video uji kamera untuk dinilai manusia.

1. build   : susun video masukan dari bahan uji yang jawabannya diketahui
             (foto hama test set, foto tanpa hama, daun berpenyakit, malai
             padi, video demo SIPETIK) + manifest jawaban per segmen.
             Foto dipilih ACAK (seed tetap), bukan dipilih yang bagus.
2. (manual) python main.py --source <input> --record <raw> --no-window ...
3. compose : tambahkan pita keterangan di BAWAH frame (di luar gambar yang
             dilihat model): "Seharusnya: ... | Sistem: ... | BENAR/SALAH",
             plus papan skor di akhir. Encode H.264 (imageio-ffmpeg).

    python training/make_test_video.py all --out "G:/Projects/sipetik/SIPETIK_uji_kamera.mp4"
"""

import argparse
import csv
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home() / "sipetik"
FPS = 30
W, H = 960, 720          # kanvas masukan (4:3 seperti webcam)
STRIP = 96               # tinggi pita keterangan di bawah
FONT = cv2.FONT_HERSHEY_SIMPLEX

LABEL = {
    "wereng_coklat": "Wereng Coklat", "walang_sangit": "Walang Sangit", "keong_mas": "Keong Mas",
    "wereng_hijau": "Wereng Hijau", "penggulung_daun": "Penggulung Daun",
    "penggerek_batang": "Penggerek Batang", "kepinding_hitam": "Kepinding Hitam",
    "belalang_padi": "Belalang Padi", "lalat_bibit": "Lalat Bibit", "tikus": "Tikus",
    "bird": "Burung", "blas_daun": "Blas Daun", "hawar_daun_bakteri": "Hawar Daun Bakteri",
    "bercak_coklat": "Bercak Coklat", "bercak_coklat_sempit": "Bercak Coklat Sempit",
    "hangus_daun": "Hangus Daun", "gosong_daun": "Gosong Daun",
}


def lab(x):
    return LABEL.get(x, x)


# ---------------------------------------------------------------- build
def fit(img, w=W, h=H):
    ih, iw = img.shape[:2]
    s = min(w / iw, h / ih)
    r = cv2.resize(img, (int(iw * s), int(ih * s)))
    out = np.zeros((h, w, 3), np.uint8)
    y, x = (h - r.shape[0]) // 2, (w - r.shape[1]) // 2
    out[y:y + r.shape[0], x:x + r.shape[1]] = r
    return out


def jitter(img, n, rng):
    """n frame dengan gerakan kamera kecil (geser, zoom, noise, cahaya)."""
    h, w = img.shape[:2]
    dx, dy = rng.uniform(-0.03, 0.03) * w, rng.uniform(-0.03, 0.03) * h
    z1, b0, b1 = rng.uniform(1.0, 1.06), rng.uniform(0.93, 1.07), rng.uniform(0.93, 1.07)
    for i in range(n):
        a = i / max(1, n - 1)
        z = 1 + (z1 - 1) * a
        M = np.float32([[z, 0, (1 - z) * w / 2 + dx * a], [0, z, (1 - z) * h / 2 + dy * a]])
        fr = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_CONSTANT)
        fr = fr.astype(np.float32) * (b0 + (b1 - b0) * a) + rng.normal(0, 3, fr.shape)
        yield np.clip(fr, 0, 255).astype(np.uint8)


def title_card(text, sub, n):
    fr = np.full((H, W, 3), 18, np.uint8)
    for t, y, sc, th in ((text, H // 2 - 10, 1.1, 2), (sub, H // 2 + 40, 0.7, 1)):
        (tw, _), _ = cv2.getTextSize(t, FONT, sc, th)
        cv2.putText(fr, t, ((W - tw) // 2, y), FONT, sc, (220, 220, 220), th, cv2.LINE_AA)
    for _ in range(n):
        yield fr


def label_classes(lbl: Path, names):
    out = {}
    for line in (lbl.read_text().splitlines() if lbl.exists() else []):
        p = line.split()
        if len(p) < 5:
            continue
        v = list(map(float, p[1:]))
        area = v[2] * v[3] if len(v) == 4 else (max(v[0::2]) - min(v[0::2])) * (max(v[1::2]) - min(v[1::2]))
        c = names[int(p[0])]
        out[c] = max(out.get(c, 0), area)
    return out


def build(inp: Path, manifest: Path, per_class: int):
    rng_py = random.Random(7)
    rng = np.random.default_rng(7)
    pest_names = yaml.safe_load((HOME / "dataset_v3" / "data_v3.yaml").read_text(encoding="utf-8"))["names"]
    dis_names = yaml.safe_load((HOME / "dataset_disease" / "data_disease.yaml").read_text(encoding="utf-8"))["names"]

    segs = []  # {title, kind, truth, n}
    frames_writer = cv2.VideoWriter(str(inp), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    count = 0

    def add(kind, title, truth, gen):
        nonlocal count
        start = count + 1
        for fr in gen:
            frames_writer.write(fr)
            count += 1
        if kind != "card":
            segs.append({"kind": kind, "title": title, "truth": truth, "start": start, "end": count})

    # 1. hama — per kelas, gambar yang hamanya cukup besar untuk kamera
    test = HOME / "dataset_v3" / "test"
    by_cls = defaultdict(list)
    small = defaultdict(list)
    for lbl in sorted((test / "labels").glob("*.txt")):
        for c, a in label_classes(lbl, pest_names).items():
            img = next((test / "images").glob(lbl.stem + ".*"), None)
            if img:
                (by_cls if a >= 0.01 else small)[c].append(img)
    add("card", "", None, title_card("BAGIAN 1: FOTO HAMA", "foto test acak, belum pernah dilihat model", FPS * 2))
    for c in pest_names.values():
        pool = by_cls.get(c) or []
        picks = rng_py.sample(pool, min(per_class, len(pool))) if pool else rng_py.sample(small[c], 1)
        for p in picks:
            note = "" if pool else " (sangat kecil)"
            add("pest", f"Hama: {lab(c)}{note}", c, jitter(fit(cv2.imread(str(p))), int(FPS * 2.5), rng))

    # 1b. hama DI LAYAR HP, sering dipegang di depan orang (phone_test: dari
    #     foto test + latar COCO eval, tidak pernah dilatih) — cara user menguji
    ptest = HOME / "phone_test"
    if (ptest / "pos").exists():
        add("card", "", None, title_card("BAGIAN 1B: HAMA DI LAYAR HP",
                                         "dipegang di depan orang / ruangan (acak)", FPS * 2))
        ph_by = defaultdict(list)
        for lbl in sorted((ptest / "pos" / "labels").glob("*.txt")):
            cls = label_classes(lbl, pest_names)
            if len(cls) == 1:
                ph_by[next(iter(cls))].append(ptest / "pos" / "images" / (lbl.stem + ".jpg"))
        for c in pest_names.values():
            for p in rng_py.sample(ph_by.get(c, []), min(per_class, len(ph_by.get(c, [])))):
                add("pest", f"HP: {lab(c)}", c, jitter(fit(cv2.imread(str(p))), int(FPS * 2.5), rng))
        for p in rng_py.sample(sorted((ptest / "neg" / "images").glob("*.jpg")), 6):
            add("neg", "HP tanpa hama (orang/ruangan/daun)", None, jitter(fit(cv2.imread(str(p))), FPS * 2, rng))

    # 2. tanpa hama — foto sehari-hari COCO (disisihkan, tidak pernah dilatih)
    add("card", "", None, title_card("BAGIAN 2: BUKAN HAMA", "orang, hewan, ruangan, jalan (foto acak)", FPS * 2))
    coco = sorted((HOME / "eval_negatives" / "coco").glob("*.jpg"))
    for p in rng_py.sample(coco, 10):
        add("neg", "Bukan hama: foto sehari-hari", None, jitter(fit(cv2.imread(str(p))), FPS * 2, rng))
    pan = sorted((HOME / "eval_negatives" / "panicle").glob("*.jpg"))
    for p in rng_py.sample(pan, 3):
        add("neg", "Bukan hama: malai padi", None, jitter(fit(cv2.imread(str(p))), FPS * 2, rng))

    # 3. penyakit daun — satu foto test per penyakit (yang ada di test set)
    add("card", "", None, title_card("BAGIAN 3: PENYAKIT DAUN", "peringatan oranye, buzzer TIDAK bunyi", FPS * 2))
    dtest = HOME / "dataset_disease" / "test"
    dis_by = defaultdict(list)
    for lbl in sorted((dtest / "labels").glob("*.txt")):
        cls = label_classes(lbl, dis_names)
        if len(cls) == 1:
            img = next((dtest / "images").glob(lbl.stem + ".*"), None)
            if img:
                dis_by[next(iter(cls))].append(img)
    for c in dis_names.values():
        if dis_by.get(c):
            p = rng_py.choice(dis_by[c])
            add("disease", f"Penyakit: {lab(c)}", c, jitter(fit(cv2.imread(str(p))), FPS * 6, rng))

    # 4. video demo SIPETIK asli (tanpa hama)
    add("card", "", None, title_card("BAGIAN 4: VIDEO DEMO SIPETIK", "miniatur sawah asli, tanpa hama", FPS * 2))
    cap = cv2.VideoCapture(str(ROOT.parent.parent / "VIDEO DEMO SIPETIK.mp4"))

    def demo():
        while True:
            ok, fr = cap.read()
            if not ok:
                return
            yield fit(fr)
    add("neg", "Video demo SIPETIK (tanpa hama)", None, demo())

    frames_writer.release()
    manifest.write_text(json.dumps({"fps": FPS, "frames": count, "segments": segs}, indent=2))
    print(f"masukan: {inp} ({count} frame, {count / FPS:.0f} dtk), {len(segs)} segmen")


# ---------------------------------------------------------------- compose
def verdict(seg, rows):
    pests = Counter(p for r in rows for p in r["pests"].split("|") if p)
    dis = Counter(d for r in rows for d in r["diseases"].split("|") if d)
    alarms = sum(int(r["alarm"]) for r in rows)
    first = next((i for i, r in enumerate(rows) if seg["truth"] in r["pests"].split("|")), None) \
        if seg["kind"] == "pest" else None
    if seg["kind"] == "pest":
        ok = first is not None
        extra = [lab(p) for p in pests if p != seg["truth"]]
        got = (f"TERDETEKSI {lab(seg['truth'])} (frame ke-{first + 1})" if ok else "TIDAK TERDETEKSI") \
            + (f" + juga: {', '.join(extra)}" if extra else "")
    elif seg["kind"] == "disease":
        ok = seg["truth"] in dis and not pests
        got = ("Peringatan: " + ", ".join(lab(d) for d in dis)) if dis else "Tidak ada peringatan penyakit"
        if pests:
            got += " | ALARM HAMA: " + ", ".join(lab(p) for p in pests)
    else:
        ok = not pests
        got = "AMAN" if ok else "ALARM PALSU: " + ", ".join(lab(p) for p in pests)
        if dis:
            got += " | peringatan penyakit: " + ", ".join(lab(d) for d in dis)
    want = {"pest": f"{lab(seg['truth'])}, buzzer bunyi",
            "disease": f"peringatan {lab(seg['truth'])}, buzzer tidak bunyi",
            "neg": "AMAN, buzzer tidak bunyi"}[seg["kind"]]
    return ok, want, got, alarms


def strip(width, seg_no, total, seg, ok, want, got):
    s = np.full((STRIP, width, 3), 32, np.uint8)
    cv2.putText(s, f"Segmen {seg_no}/{total}  |  {seg['title']}", (12, 26), FONT, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.putText(s, f"Seharusnya : {want}", (12, 54), FONT, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    col = (80, 200, 80) if ok else (60, 60, 230)
    cv2.putText(s, f"Sistem     : {got}"[:110], (12, 82), FONT, 0.55, col, 1, cv2.LINE_AA)
    tag = "BENAR" if ok else "SALAH"
    (tw, _), _ = cv2.getTextSize(tag, FONT, 0.9, 2)
    cv2.rectangle(s, (width - tw - 34, 12), (width - 12, 46), col, -1)
    cv2.putText(s, tag, (width - tw - 23, 39), FONT, 0.9, (20, 20, 20), 2, cv2.LINE_AA)
    return s


def scoreboard(width, height, results):
    fr = np.full((height, width, 3), 18, np.uint8)
    cv2.putText(fr, "HASIL UJI KAMERA SIPETIK (main.py: hama + tracking + penyakit daun)", (24, 44), FONT, 0.7, (230, 230, 230), 2, cv2.LINE_AA)
    groups = defaultdict(lambda: [0, 0])
    for seg, ok, *_ in results:
        g = {"pest": "Foto hama terdeteksi", "neg": "Gambar/video tanpa hama tetap AMAN",
             "disease": "Penyakit daun diberi peringatan"}[seg["kind"]]
        if seg["title"].startswith("HP"):
            g = "Hama di layar HP terdeteksi" if seg["kind"] == "pest" else "HP tanpa hama tetap AMAN"
        groups[g][0] += ok
        groups[g][1] += 1
    y = 100
    for g, (a, b) in groups.items():
        cv2.putText(fr, f"{g}: {a} dari {b}", (40, y), FONT, 0.75, (200, 230, 200) if a == b else (220, 220, 220), 2, cv2.LINE_AA)
        y += 44
    y += 10
    cv2.putText(fr, "Yang SALAH:", (40, y), FONT, 0.65, (180, 180, 180), 1, cv2.LINE_AA)
    y += 32
    for seg, ok, want, got, _ in results:
        if not ok and y < height - 20:
            cv2.putText(fr, f"- {seg['title']}: {got}"[:105], (56, y), FONT, 0.5, (120, 120, 240), 1, cv2.LINE_AA)
            y += 26
    return fr


def compose(raw: Path, log: Path, manifest: Path, out: Path):
    import imageio_ffmpeg
    m = json.loads(manifest.read_text())
    rows = {int(r["frame"]): r for r in csv.DictReader(open(log, encoding="utf-8"))}
    segs = m["segments"]
    results = []
    for seg in segs:
        ok, want, got, alarms = verdict(seg, [rows[i] for i in range(seg["start"], seg["end"] + 1) if i in rows])
        results.append((seg, ok, want, got, alarms))
    by_frame = {}
    for k, (seg, ok, want, got, _) in enumerate(results, 1):
        for i in range(seg["start"], seg["end"] + 1):
            by_frame[i] = (k, seg, ok, want, got)

    cap = cv2.VideoCapture(str(raw))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = imageio_ffmpeg.write_frames(str(out), (w, h + STRIP), fps=m["fps"], codec="libx264",
                                         quality=7, macro_block_size=8, pix_fmt_out="yuv420p")
    writer.send(None)
    idx = 0
    blank = np.full((STRIP, w, 3), 32, np.uint8)
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        idx += 1
        info = by_frame.get(idx)
        s = strip(w, info[0], len(results), *info[1:]) if info else blank
        writer.send(cv2.cvtColor(np.vstack([fr, s]), cv2.COLOR_BGR2RGB).tobytes())
    board = cv2.cvtColor(scoreboard(w, h + STRIP, results), cv2.COLOR_BGR2RGB).tobytes()
    for _ in range(m["fps"] * 8):
        writer.send(board)
    writer.close()

    summary = out.with_suffix(".csv")
    with open(summary, "w", newline="", encoding="utf-8-sig") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["segmen", "mulai_detik", "judul", "seharusnya", "sistem", "hasil", "alarm_buzzer"])
        for k, (seg, ok, want, got, alarms) in enumerate(results, 1):
            wcsv.writerow([k, round((seg["start"] - 1) / m["fps"], 1), seg["title"], want, got,
                           "BENAR" if ok else "SALAH", alarms])
    n_ok = sum(r[1] for r in results)
    print(f"video: {out}\nringkasan: {summary}\nbenar {n_ok}/{len(results)} segmen")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["build", "compose", "all"])
    ap.add_argument("--work", default=str(HOME / "uji_video"))
    ap.add_argument("--out", default=str(ROOT.parent.parent / "SIPETIK_uji_kamera.mp4"))
    ap.add_argument("--per-class", type=int, default=2)
    ap.add_argument("--main-args", default="", help="Argumen tambahan untuk main.py (mis. '--tiles 2')")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    inp, man, raw = work / "input.mp4", work / "manifest.json", work / "raw.mp4"
    if a.step in ("build", "all"):
        build(inp, man, a.per_class)
    if a.step == "all":
        cmd = [sys.executable, "main.py", "--source", str(inp), "--record", str(raw), "--no-window",
               "--no-remote", "--server", "http://127.0.0.1:9", *a.main_args.split()]
        print("menjalankan:", " ".join(cmd))
        subprocess.run(cmd, cwd=ROOT, check=True)
    if a.step in ("compose", "all"):
        compose(raw, raw.with_suffix(".csv"), man, Path(a.out))


if __name__ == "__main__":
    main()
