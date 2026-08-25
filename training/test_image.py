#!/usr/bin/env python3
"""
SIPETIK — Tes cepat pest_local.pt (atau best.pt) ke 1 file foto, TANPA
kamera. Berguna buat diagnosa: apakah masalahnya di model, atau di cara
motret (mis. foto layar HP lewat webcam yang nambah distorsi).

Jalankan:
    python training/test_image.py foto_wereng.jpg
    python training/test_image.py foto_wereng.jpg --conf 0.1     # confidence rendah, lihat sinyal sekecil apa pun
    python training/test_image.py foto_wereng.jpg --model best.pt

Hasil digambar ke foto_wereng.detected.jpg supaya bisa dilihat box-nya.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import windows_git_fix  # noqa: E402,F401

import cv2  # noqa: E402
from ultralytics import YOLO  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Tes 1 foto ke model SIPETIK tanpa kamera")
    p.add_argument("image", help="Path ke file foto")
    p.add_argument("--model", default="pest_local.pt")
    p.add_argument("--conf", type=float, default=0.1,
                    help="Rendah sengaja (default 0.1) — biar kelihatan sinyal sekecil apa pun")
    args = p.parse_args()

    if not Path(args.image).exists():
        print(f"ERROR: file '{args.image}' tidak ditemukan")
        sys.exit(1)
    if not Path(args.model).exists():
        print(f"ERROR: model '{args.model}' tidak ditemukan")
        sys.exit(1)

    model = YOLO(args.model)
    print(f"Model  : {args.model}  (kelas: {list(model.names.values())})")
    print(f"Foto   : {args.image}")
    print(f"Conf   : >= {args.conf}")
    print()

    frame = cv2.imread(args.image)
    if frame is None:
        print("ERROR: gagal baca file gambar (format tidak didukung?)")
        sys.exit(1)

    results = model.predict(frame, conf=args.conf, verbose=False)[0]

    if len(results.boxes) == 0:
        print("TIDAK ADA deteksi sama sekali, bahkan di confidence serendah ini.")
        print("-> Kemungkinan besar model belum pernah 'lihat' foto sejenis ini saat")
        print("   training (beda konteks/background/pose terlalu jauh), bukan cuma soal")
        print("   threshold. Lihat training/README.md bagian domain gap.")
    else:
        print(f"Ada {len(results.boxes)} deteksi:")
        for b in results.boxes:
            cls_id = int(b.cls[0])
            conf   = float(b.conf[0])
            name   = results.names.get(cls_id, str(cls_id))
            print(f"  - {name}: {conf:.1%}")
            x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, f"{name} {conf:.0%}", (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    out_path = str(Path(args.image).with_suffix("")) + ".detected.jpg"
    cv2.imwrite(out_path, frame)
    print(f"\nHasil (dengan box kalau ada) disimpan ke: {out_path}")


if __name__ == "__main__":
    main()
