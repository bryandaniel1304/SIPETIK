#!/usr/bin/env python3
"""
SIPETIKCAMERA — Pest Detection with SIPETIK Dashboard Integration
=================================================================
Deteksi hama sawah via webcam menggunakan YOLOv8 dan kirim notifikasi
ke dashboard SIPETIK secara real-time.

Jalankan:
    python main.py
    python main.py --model best.pt --server http://192.168.1.5:8000
    python main.py --model best.pt --conf 0.65 --cooldown 10 --camera 0

Tekan Q pada jendela kamera untuk berhenti.
"""

import sys
import time
import argparse
from datetime import datetime

try:
    import cv2
except ImportError:
    print("ERROR: opencv-python belum terinstall.")
    print("Jalankan: pip install opencv-python")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests belum terinstall.")
    print("Jalankan: pip install requests")
    sys.exit(1)

try:
    from ultralytics import YOLO
except ImportError:
    print("ERROR: ultralytics belum terinstall.")
    print("Jalankan: pip install ultralytics")
    sys.exit(1)

# ================================================================
#  KONSTANTA
# ================================================================
HEARTBEAT_INTERVAL = 30   # detik antar heartbeat ke server
CLEAR_FRAMES       = 5    # frame tanpa deteksi sebelum kirim "clear"


# ================================================================
#  FUNGSI NOTIFIKASI KE SIPETIK
# ================================================================
def notify_detection(server_url: str, pest_class: str, confidence: float) -> bool:
    try:
        resp = requests.post(
            f"{server_url}/api/camera/motion",
            json={
                "detected":     True,
                "animal_class": pest_class,
                "confidence":   round(confidence, 3),
                "device_id":    "laptop-camera",
            },
            timeout=3,
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"  [WARN] Gagal kirim notifikasi: {exc}")
        return False


def notify_clear(server_url: str) -> None:
    try:
        requests.post(
            f"{server_url}/api/camera/motion",
            json={"detected": False, "animal_class": None,
                  "confidence": 0.0, "device_id": "laptop-camera"},
            timeout=3,
        )
    except Exception:
        pass


def send_heartbeat(server_url: str) -> None:
    try:
        requests.get(
            f"{server_url}/api/camera/heartbeat",
            params={"device_id": "laptop-camera"},
            timeout=2,
        )
    except Exception:
        pass


# ================================================================
#  FUNGSI BANTU
# ================================================================
def draw_detection(frame, box, class_name, conf):
    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (30, 220, 30), 2)

    label = f"{class_name} {conf:.2f}"
    (text_w, text_h), baseline = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    label_x = x1
    label_y = y1 - 8
    if label_y - text_h - baseline < 0:
        label_y = y1 + text_h + 8

    bg_tl = (label_x, label_y - text_h - baseline)
    bg_br = (label_x + text_w + 8, label_y + baseline)
    cv2.rectangle(frame, bg_tl, bg_br, (30, 220, 30), -1)
    cv2.putText(frame, label, (label_x + 4, label_y - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)


def passes_size_filter(frame, box, min_area, max_area):
    frame_h, frame_w = frame.shape[:2]
    x1, y1, x2, y2 = map(int, box)
    box_area  = max(0, x2 - x1) * max(0, y2 - y1)
    frame_area = frame_w * frame_h
    if frame_area == 0:
        return False
    return min_area <= (box_area / frame_area) <= max_area


# ================================================================
#  ARGUMEN
# ================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="SIPETIKCAMERA — Pest detection + SIPETIK dashboard integration"
    )
    parser.add_argument("--model",    type=str,   default="best.pt",
                        help="Path ke model YOLO (.pt)")
    parser.add_argument("--server",   type=str,   default="http://192.168.1.5:8000",
                        help="URL server Laravel SIPETIK")
    parser.add_argument("--camera",   type=int,   default=0,
                        help="Index kamera (default: 0)")
    parser.add_argument("--conf",     type=float, default=0.65,
                        help="Confidence threshold (default: 0.65)")
    parser.add_argument("--imgsz",    type=int,   default=640,
                        help="Ukuran inferensi (default: 640)")
    parser.add_argument("--min-area", type=float, default=0.01,
                        help="Abaikan box lebih kecil dari fraksi ini")
    parser.add_argument("--max-area", type=float, default=0.70,
                        help="Abaikan box lebih besar dari fraksi ini")
    parser.add_argument("--cooldown", type=int,   default=10,
                        help="Jeda minimal antar trigger buzzer (detik)")
    return parser.parse_args()


# ================================================================
#  MAIN
# ================================================================
def main():
    args = parse_args()

    import os
    model_file = args.model if os.path.exists(args.model) else "yolov8n.pt"

    print()
    print("=" * 55)
    print("  SIPETIKCAMERA — SIPETIK Pest Detector")
    print("=" * 55)
    print(f"  Server   : {args.server}")
    print(f"  Model    : {model_file}")
    print(f"  Kamera   : index {args.camera}")
    print(f"  Conf     : {args.conf}")
    print(f"  Cooldown : {args.cooldown} detik")
    print("=" * 55)
    print()

    model = YOLO(model_file)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"ERROR: Kamera index {args.camera} tidak bisa dibuka.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("  Kamera siap. Tekan Q untuk berhenti.")
    print()

    last_trigger_at   = 0.0
    last_heartbeat_at = 0.0
    no_pest_frames    = 0
    fps_count         = 0
    fps_start         = time.time()
    fps_display       = 0.0

    while True:
        now = time.time()

        # Heartbeat ke server
        if now - last_heartbeat_at >= HEARTBEAT_INTERVAL:
            send_heartbeat(args.server)
            last_heartbeat_at = now

        ok, frame = cap.read()
        if not ok:
            print("ERROR: Tidak bisa membaca frame dari kamera.")
            break

        # Hitung FPS
        fps_count += 1
        if fps_count >= 30:
            fps_display = fps_count / (time.time() - fps_start)
            fps_count   = 0
            fps_start   = time.time()

        # Deteksi
        results = model.predict(frame, conf=args.conf,
                                imgsz=args.imgsz, verbose=False)

        detected_pests = []
        for result in results:
            for b in result.boxes:
                cls_id     = int(b.cls[0])
                conf       = float(b.conf[0])
                xyxy       = b.xyxy[0].tolist()
                class_name = result.names.get(cls_id, str(cls_id))

                if not passes_size_filter(frame, xyxy, args.min_area, args.max_area):
                    continue

                draw_detection(frame, xyxy, class_name, conf)
                detected_pests.append((class_name, conf))

        # Logika clear / trigger
        if detected_pests:
            no_pest_frames = 0
            # Trigger buzzer setelah cooldown habis
            if now - last_trigger_at >= args.cooldown:
                best = max(detected_pests, key=lambda x: x[1])
                ts   = datetime.now().strftime("%H:%M:%S")
                print(f"  [{ts}] TERDETEKSI: {best[0]} ({best[1]:.0%}) → Buzzer!")
                ok = notify_detection(args.server, best[0], best[1])
                if ok:
                    last_trigger_at = now
                    print(f"          Server OK. Cooldown {args.cooldown}s dimulai.")
        else:
            no_pest_frames += 1
            if no_pest_frames == CLEAR_FRAMES:
                notify_clear(args.server)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"  [{ts}] Tidak ada hama → Dashboard dibersihkan.")

        # Overlay status
        if detected_pests:
            status_text  = f"HAMA: {len(detected_pests)} terdeteksi"
            status_color = (0, 80, 220)
        else:
            status_text  = "Aman — tidak ada hama"
            status_color = (0, 180, 0)

        cv2.rectangle(frame, (0, 0), (frame.shape[1], 38), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.putText(frame, f"{fps_display:.1f} fps",
                    (frame.shape[1] - 85, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

        cv2.imshow("SIPETIKCAMERA  [Q = keluar]", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print()
    print("  Detector dihentikan.")


if __name__ == "__main__":
    main()
