#!/usr/bin/env python3
"""
SIPETIK Animal Detector
=======================
Mendeteksi binatang via webcam menggunakan YOLOv8 dan mengirim
notifikasi ke dashboard SIPETIK. Saat binatang terdeteksi, buzzer
ESP32 berbunyi otomatis melalui server Laravel.

Setup:
    pip install -r camera_requirements.txt

Jalankan:
    python animal_detector.py
    python animal_detector.py --server http://192.168.1.5:8000
    python animal_detector.py --camera 1 --confidence 0.6 --cooldown 15

Tekan Q pada jendela kamera untuk berhenti.
"""

import sys
import time
import argparse
from datetime import datetime

import windows_git_fix  # noqa: F401  (must run before importing ultralytics — see file for why)

try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    CUDA_AVAILABLE = False

try:
    import cv2
except ImportError:
    print("ERROR: opencv-python belum terinstall.")
    print("Jalankan: pip install -r camera_requirements.txt")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests belum terinstall.")
    print("Jalankan: pip install -r camera_requirements.txt")
    sys.exit(1)

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

try:
    from inference import get_model as rf_get_model
    ROBOFLOW_AVAILABLE = True
except ImportError:
    rf_get_model = None
    ROBOFLOW_AVAILABLE = False

# ================================================================
#  KONFIGURASI MODEL
#  Mode 1 (default): Roboflow rat detection — mAP 97.6%
#  Mode 2: YOLOv8 lokal (fallback)
#
#  Isi ROBOFLOW_API_KEY dengan API key dari roboflow.com
# ================================================================
ROBOFLOW_API_KEY  = "GANTI_DENGAN_API_KEY_KAMU"
ROBOFLOW_MODEL_ID = "rat-detection-6ezx2/2"

# Jalankan inferensi setiap N frame (1 = setiap frame, 3 = lebih ringan)
INFER_EVERY_N_FRAMES = 2
ANIMAL_CLASSES = {
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
}

ANIMAL_LABELS = {
    "bird":     "Burung",
    "cat":      "Kucing",
    "dog":      "Anjing",
    "horse":    "Kuda",
    "sheep":    "Kambing/Domba",
    "cow":      "Sapi",
    "elephant": "Gajah",
    "bear":     "Beruang",
    "zebra":    "Zebra",
    "giraffe":  "Jerapah",
}

HEARTBEAT_INTERVAL = 30   # detik antar heartbeat ke server
CLEAR_FRAMES       = 5    # frame berturut-turut tanpa binatang sebelum kirim "clear"


def notify_clear(server_url: str) -> None:
    """Kirim notifikasi bahwa tidak ada binatang terdeteksi."""
    try:
        requests.post(
            f"{server_url}/api/camera/motion",
            json={"detected": False, "animal_class": None, "confidence": 0.0, "device_id": "laptop-camera"},
            timeout=3,
        )
    except Exception:
        pass


def notify_detection(server_url: str, animal_class: str, confidence: float) -> bool:
    """Kirim notifikasi deteksi binatang ke dashboard Laravel."""
    try:
        resp = requests.post(
            f"{server_url}/api/camera/motion",
            json={
                "detected":     True,
                "animal_class": animal_class,
                "confidence":   round(confidence, 3),
                "device_id":    "laptop-camera",
            },
            timeout=3,
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"  [WARN] Gagal kirim notifikasi: {exc}")
        return False


def send_heartbeat(server_url: str) -> None:
    """Kirim sinyal 'kamera menyala' ke server (TTL 60 detik)."""
    try:
        requests.get(
            f"{server_url}/api/camera/heartbeat",
            params={"device_id": "laptop-camera"},
            timeout=2,
        )
    except Exception:
        pass


def run(server_url: str, camera_index: int, min_confidence: float, cooldown: int) -> None:
    print()
    print("=" * 55)
    print("  SIPETIK Animal Detector")
    print("=" * 55)
    print(f"  Server     : {server_url}")
    print(f"  Kamera     : index {camera_index}")
    print(f"  Confidence : >= {min_confidence:.0%}")
    print(f"  Cooldown   : {cooldown} detik antar trigger buzzer")
    print("=" * 55)

    # Pilih mode: Roboflow lokal atau YOLOv8
    use_roboflow = ROBOFLOW_AVAILABLE and ROBOFLOW_API_KEY != "GANTI_DENGAN_API_KEY_KAMU"

    if use_roboflow:
        print("  Model      : Roboflow Rat Detection (mAP 97.6%)")
        print("  Mode       : Inference lokal (download sekali, jalan offline)")
        print("  Mengunduh model... (tunggu sebentar pertama kali)")
        rf_client = rf_get_model(model_id=ROBOFLOW_MODEL_ID, api_key=ROBOFLOW_API_KEY)
        yolo_model = None
        print("  Model siap.")
    else:
        if not ROBOFLOW_AVAILABLE:
            print("  [INFO] inference belum terinstall.")
            print("         Jalankan: pip install inference")
        elif ROBOFLOW_API_KEY == "GANTI_DENGAN_API_KEY_KAMU":
            print("  [INFO] API key belum diisi. Gunakan YOLOv8 lokal.")
        print("  Model      : YOLOv8 lokal (best.pt / yolov8n.pt)")
        if YOLO is None:
            print("ERROR: ultralytics tidak terinstall. Jalankan: pip install ultralytics")
            sys.exit(1)
        model_file = "best.pt" if __import__("os").path.exists("best.pt") else "yolov8n.pt"
        yolo_model = YOLO(model_file)
        device = "cuda" if CUDA_AVAILABLE else "cpu"
        yolo_model.to(device)
        rf_client = None
        print(f"  Device     : {device.upper()}")
    print()

    print("  Membuka kamera...")
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"  ERROR: Kamera index {camera_index} tidak bisa dibuka.")
        print("  Coba --camera 1 atau periksa izin kamera di Windows.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 60)

    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"  FPS kamera : {actual_fps:.0f} fps (dikonfirmasi oleh driver kamera)")
    print("  Kamera siap. Tekan  Q  pada jendela untuk berhenti.")
    print()

    last_trigger_at   = 0.0
    last_heartbeat_at = 0.0
    no_animal_frames  = 0
    fps_frame_count   = 0
    fps_start_time    = time.time()
    fps_display       = 0.0

    while True:
        now = time.time()

        # Kirim heartbeat berkala
        if now - last_heartbeat_at >= HEARTBEAT_INTERVAL:
            send_heartbeat(server_url)
            last_heartbeat_at = now

        ret, frame = cap.read()
        if not ret:
            print("  ERROR: Tidak bisa membaca frame dari kamera.")
            break

        # Hitung FPS aktual
        fps_frame_count += 1
        if fps_frame_count >= 30:
            fps_display     = fps_frame_count / (time.time() - fps_start_time)
            fps_frame_count = 0
            fps_start_time  = time.time()

        detected_animals = []

        # Jalankan deteksi setiap N frame untuk performa lebih baik
        if fps_frame_count % INFER_EVERY_N_FRAMES == 0:
            if use_roboflow:
                # Mode Roboflow inference lokal
                try:
                    rf_results = rf_client.infer(frame)
                    preds = rf_results[0].predictions if rf_results else []
                    for pred in preds:
                        conf = float(pred.confidence)
                        if conf < min_confidence:
                            continue
                        raw_name = "rat"
                        label    = "Tikus"
                        x, y, w, h = pred.x, pred.y, pred.width, pred.height
                        x1, y1 = int(x - w/2), int(y - h/2)
                        x2, y2 = int(x + w/2), int(y + h/2)
                        detected_animals.append((raw_name, label, conf, [x1, y1, x2, y2]))
                        display_label = f"{label}  {conf:.0%}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 220), 2)
                        cv2.rectangle(frame, (x1, y1-22), (x1+len(display_label)*9, y1), (0, 0, 220), -1)
                        cv2.putText(frame, display_label, (x1+2, y1-5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                except Exception as exc:
                    print(f"  [WARN] Roboflow error: {exc}")
            else:
                # Mode YOLOv8 lokal
                results = yolo_model(frame, verbose=False, conf=min_confidence)
                for result in results:
                    class_names = result.names
                    for box in result.boxes:
                        cls_id   = int(box.cls[0])
                        conf     = float(box.conf[0])
                        raw_name = class_names.get(cls_id, str(cls_id))
                        label    = ANIMAL_LABELS.get(raw_name, raw_name)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detected_animals.append((raw_name, label, conf, [x1, y1, x2, y2]))
                        display_label = f"{label}  {conf:.0%}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 220), 2)
                        cv2.rectangle(frame, (x1, y1-22), (x1+len(display_label)*9, y1), (0, 0, 220), -1)
                        cv2.putText(frame, display_label, (x1+2, y1-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        # Hitung frame tanpa binatang, kirim "clear" setelah CLEAR_FRAMES berturut-turut
        if detected_animals:
            no_animal_frames = 0
        else:
            no_animal_frames += 1
            if no_animal_frames == CLEAR_FRAMES:
                notify_clear(server_url)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"  [{ts}] Binatang tidak ada lagi → Dashboard dibersihkan.")

        # Trigger buzzer jika cooldown habis
        if detected_animals and (now - last_trigger_at) >= cooldown:
            # Ambil deteksi dengan confidence tertinggi
            best_animal, best_label, best_conf, _ = max(detected_animals, key=lambda x: x[2])
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] TERDETEKSI: {best_label} (confidence {best_conf:.0%}) → Buzzer!")

            ok = notify_detection(server_url, best_animal, best_conf)
            if ok:
                last_trigger_at = now
                print(f"          Server OK. Cooldown {cooldown}s dimulai.")
            else:
                print("          Gagal kirim ke server.")

        # ── Overlay status ────────────────────────────────────────
        if detected_animals:
            status_text  = f"BINATANG: {len(detected_animals)} terdeteksi"
            status_color = (0, 0, 220)
        else:
            status_text  = "Aman — tidak ada binatang"
            status_color = (0, 180, 0)

        # Background strip atas
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 38), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.putText(frame, f"{fps_display:.1f} fps", (frame.shape[1] - 85, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

        # Countdown cooldown
        remaining = max(0.0, cooldown - (now - last_trigger_at))
        if remaining > 0:
            cd_text = f"Cooldown: {remaining:.1f}s"
            cv2.putText(frame, cd_text, (frame.shape[1] - 170, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 1)

        cv2.imshow("SIPETIK Animal Detector  [Q = keluar]", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print()
    print("  Detector dihentikan.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIPETIK Animal Detector — deteksi binatang via webcam, trigger buzzer ESP32",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--server", "-s",
        default="http://192.168.1.5:8000",
        help="URL server Laravel",
    )
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="Index kamera (0 = kamera utama)",
    )
    parser.add_argument(
        "--confidence", "--conf",
        type=float,
        default=0.50,
        help="Minimum confidence deteksi (0.0–1.0)",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=10,
        help="Jeda minimal antar trigger buzzer (detik)",
    )
    args = parser.parse_args()

    run(
        server_url     = args.server,
        camera_index   = args.camera,
        min_confidence = args.confidence,
        cooldown       = args.cooldown,
    )


if __name__ == "__main__":
    main()
