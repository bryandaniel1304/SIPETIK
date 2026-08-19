#!/usr/bin/env python3
"""
SIPETIKCAMERA — Pest Detection with SIPETIK Dashboard Integration
=================================================================
Deteksi hama sawah via webcam dan kirim notifikasi ke dashboard SIPETIK
secara real-time. Dua sumber deteksi digabung:

  1. Model YOLOv8 lokal (best.pt) — cepat, jalan offline. Kelas apa pun
     yang ada di model ini otomatis dipakai (lihat training/README.md
     untuk melatih ulang supaya mengenali lebih banyak hama).
  2. Model-model hasil training di Roboflow, dipanggil lewat API hosted
     mereka (https://serverless.roboflow.com) — dijalankan di thread
     terpisah tiap beberapa detik supaya tidak bikin preview kamera patah-
     patah. Aktif otomatis kalau ROBOFLOW_API_KEY diisi di file .env.

Jalankan:
    python main.py
    python main.py --model best.pt --server http://192.168.1.5:8000
    python main.py --model best.pt --conf 0.65 --cooldown 10 --camera 0
    python main.py --no-remote          # matikan deteksi via Roboflow API

Tekan Q pada jendela kamera untuk berhenti.
"""

import os
import sys
import time
import threading
import argparse
from datetime import datetime

import windows_git_fix  # noqa: F401  (must run before importing ultralytics — see file for why)

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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv opsional — kalau tidak ada, pakai env var OS langsung

try:
    from inference_sdk import InferenceHTTPClient
    REMOTE_SDK_AVAILABLE = True
except ImportError:
    InferenceHTTPClient = None
    REMOTE_SDK_AVAILABLE = False

# ================================================================
#  KONSTANTA
# ================================================================
HEARTBEAT_INTERVAL = 30   # detik antar heartbeat ke server
CLEAR_FRAMES       = 5    # frame tanpa deteksi sebelum kirim "clear"

# ---- Deteksi hama tambahan lewat Roboflow hosted API -----------
# Model-model publik/terlatih yang dipanggil langsung (tanpa training lokal).
# Kalau nanti best.pt lokal sudah dilatih ulang untuk mengenali kelas yang
# sama, model terkait bisa dihapus dari daftar ini untuk hemat kuota API.
ROBOFLOW_API_URL       = "https://serverless.roboflow.com"
REMOTE_CHECK_INTERVAL  = 3.0   # detik antar panggilan API (jaga latency & kuota)
REMOTE_MIN_CONFIDENCE  = 0.60

REMOTE_MODEL_IDS = [
    "paddy-rice-insect-pest-dataset/3",
    "golden-apple-snail/2",
    # "detection-of-fall-armyworm-infestation-with-deep-learning/1" —
    # DIMATIKAN. Dites langsung: model ini salah kenali wajah orang di depan
    # kamera sebagai "ulat grayak" (confidence 0.6–0.75), bukan cuma di
    # gambar noise. Kelihatannya model ini dilatih untuk foto close-up daun
    # yang sudah terserang, bukan untuk membedakan "ada hama" vs "bukan
    # hama" di scene webcam biasa. Jangan aktifkan lagi sampai ketemu
    # model/data ulat grayak yang lebih baik (lihat training/README.md).
]

# Walang sangit & ulat grayak dipanggil lewat 1 Workflow yang sama
# (segmentasi open-vocabulary — daftar kelas dikirim saat runtime lewat
# parameter "classes", jadi 1 workflow bisa dipakai untuk banyak hama
# sekaligus, tidak perlu bikin workflow baru per hama). Dipakai untuk ulat
# grayak karena model project fall-armyworm sebelumnya tidak reliable
# (lihat catatan REMOTE_MODEL_IDS di atas & training/README.md) — workflow
# ini sudah dites bersih (tidak false-positive di gambar noise).
ZERO_SHOT_WORKFLOW = {
    "workspace_name": "bryans-workspace-cfpnz",
    "workflow_id":    "general-segmentation-api",
    "classes_param":  "walang sangit, Walang sangit, ulat grayak, Ulat grayak",
}

# Nama kelas yang dikembalikan tiap model Roboflow di atas tidak selalu
# konsisten (mis. model fall-armyworm mengembalikan kelas seperti
# "FAW_Day3"). Jadi dipetakan berdasar kata kunci, bukan exact-match, ke
# salah satu dari 5 slug target SIPETIK (harus sama dengan
# training/data.yaml dan CameraController::animalLabel()).
REMOTE_KEYWORD_MAP = {
    "walang_sangit": ["walang"],
    "wereng_coklat": ["planthopper", "wereng", "bph", "hopper"],
    "ulat_grayak":   ["armyworm", "faw", "caterpillar", "ulat"],
    "keong_mas":     ["snail", "keong"],
}


def classify_remote_label(raw_name: str):
    """Petakan nama kelas mentah dari model Roboflow ke slug target SIPETIK,
    atau None kalau tidak relevan (dibuang)."""
    low = raw_name.lower()
    for slug, keywords in REMOTE_KEYWORD_MAP.items():
        if any(k in low for k in keywords):
            return slug
    return None


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
def draw_detection(frame, box, class_name, conf, source="local"):
    color = (30, 220, 30) if source == "local" else (0, 165, 255)  # hijau lokal, oranye cloud
    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    suffix = "" if source == "local" else "  (cloud)"
    label = f"{class_name} {conf:.2f}{suffix}"
    (text_w, text_h), baseline = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    label_x = x1
    label_y = y1 - 8
    if label_y - text_h - baseline < 0:
        label_y = y1 + text_h + 8

    bg_tl = (label_x, label_y - text_h - baseline)
    bg_br = (label_x + text_w + 8, label_y + baseline)
    cv2.rectangle(frame, bg_tl, bg_br, color, -1)
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


def parse_remote_predictions(preds, force_slug=None):
    """Ubah list prediction mentah dari Roboflow (format model biasa atau
    format workflow) jadi list (slug, raw_class_name, conf, xyxy)."""
    out = []
    for p in preds or []:
        conf = float(p.get("confidence", 0.0))
        if conf < REMOTE_MIN_CONFIDENCE:
            continue

        raw_name = p.get("class", "")
        slug = force_slug if force_slug is not None else classify_remote_label(raw_name)
        if slug is None:
            continue

        if all(k in p for k in ("x", "y", "width", "height")):
            cx, cy, w, h = p["x"], p["y"], p["width"], p["height"]
            box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        elif p.get("points"):
            xs = [pt["x"] for pt in p["points"]]
            ys = [pt["y"] for pt in p["points"]]
            box = [min(xs), min(ys), max(xs), max(ys)]
        else:
            continue

        out.append((slug, raw_name or slug, conf, box))
    return out


def query_remote_pests(client) -> list:
    """Panggil semua model + workflow Roboflow untuk 1 frame. Tiap sumber
    dibungkus try/except sendiri supaya 1 endpoint error tidak menggagalkan
    yang lain."""
    frame = _LATEST_FRAME.get("frame")
    if frame is None:
        return []

    detections = []

    for model_id in REMOTE_MODEL_IDS:
        try:
            result = client.infer(frame, model_id=model_id)
            detections += parse_remote_predictions(result.get("predictions", []))
        except Exception as exc:
            print(f"  [WARN] Roboflow model {model_id} error: {exc}")

    try:
        wf = ZERO_SHOT_WORKFLOW
        result = client.run_workflow(
            workspace_name=wf["workspace_name"],
            workflow_id=wf["workflow_id"],
            images={"image": frame},
            parameters={"classes": wf["classes_param"]},
            use_cache=True,
        )
        preds = (result[0].get("predictions") or {}).get("predictions", []) if result else []
        # Tanpa force_slug — hasil bisa "walang sangit" ATAU "ulat grayak"
        # (keduanya diminta lewat classes_param), classify_remote_label()
        # yang menentukan slug-nya dari nama kelas yang benar-benar dibalikin.
        detections += parse_remote_predictions(preds)
    except Exception as exc:
        print(f"  [WARN] Roboflow workflow zero-shot error: {exc}")

    return detections


# Frame terbaru & hasil deteksi remote dibagi antara main loop dan
# background thread lewat dict sederhana (aman dari race condition berkat
# GIL Python untuk assignment reference biasa — cukup untuk kebutuhan ini).
_LATEST_FRAME      = {"frame": None}
_REMOTE_DETECTIONS = {"items": []}


def remote_worker(api_key: str, interval: float, stop_event: threading.Event) -> None:
    client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=api_key)
    while not stop_event.is_set():
        try:
            _REMOTE_DETECTIONS["items"] = query_remote_pests(client)
        except Exception as exc:
            print(f"  [WARN] Remote pest worker error: {exc}")
        stop_event.wait(interval)


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
    parser.add_argument("--no-remote", action="store_true",
                        help="Matikan deteksi tambahan lewat Roboflow API (hemat kuota/tanpa internet)")
    parser.add_argument("--remote-interval", type=float, default=REMOTE_CHECK_INTERVAL,
                        help="Jeda antar panggilan Roboflow API (detik)")
    parser.add_argument("--roboflow-key", type=str, default=None,
                        help="Override ROBOFLOW_API_KEY dari .env")
    return parser.parse_args()


# ================================================================
#  MAIN
# ================================================================
def main():
    args = parse_args()

    model_file = args.model if os.path.exists(args.model) else "yolov8n.pt"

    api_key = args.roboflow_key or os.environ.get("ROBOFLOW_API_KEY", "").strip()
    use_remote = (not args.no_remote) and bool(api_key) and REMOTE_SDK_AVAILABLE

    print()
    print("=" * 55)
    print("  SIPETIKCAMERA — SIPETIK Pest Detector")
    print("=" * 55)
    print(f"  Server   : {args.server}")
    print(f"  Model    : {model_file}")
    print(f"  Kamera   : index {args.camera}")
    print(f"  Conf     : {args.conf}")
    print(f"  Cooldown : {args.cooldown} detik")
    if use_remote:
        print(f"  Cloud    : AKTIF (Roboflow, tiap {args.remote_interval:.0f}s) — "
              f"{len(REMOTE_MODEL_IDS) + 1} model tambahan")
    elif not api_key:
        print("  Cloud    : nonaktif (ROBOFLOW_API_KEY belum diisi di .env)")
    elif not REMOTE_SDK_AVAILABLE:
        print("  Cloud    : nonaktif (paket 'inference-sdk' belum terinstall)")
    else:
        print("  Cloud    : nonaktif (--no-remote)")
    print("=" * 55)
    print()

    model = YOLO(model_file)

    stop_event   = threading.Event()
    remote_thread = None
    if use_remote:
        remote_thread = threading.Thread(
            target=remote_worker,
            args=(api_key, args.remote_interval, stop_event),
            daemon=True,
        )
        remote_thread.start()

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

    try:
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

            _LATEST_FRAME["frame"] = frame  # dibaca oleh remote_worker di thread lain

            # Hitung FPS
            fps_count += 1
            if fps_count >= 30:
                fps_display = fps_count / (time.time() - fps_start)
                fps_count   = 0
                fps_start   = time.time()

            # Deteksi lokal (YOLOv8 / best.pt)
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

                    draw_detection(frame, xyxy, class_name, conf, source="local")
                    detected_pests.append((class_name, conf))

            # Deteksi tambahan dari Roboflow (di-refresh tiap REMOTE_CHECK_INTERVAL
            # detik oleh background thread, di-gambar ulang tiap frame)
            if use_remote:
                for slug, raw_name, conf, box in _REMOTE_DETECTIONS["items"]:
                    if not passes_size_filter(frame, box, args.min_area, args.max_area):
                        continue
                    draw_detection(frame, box, slug, conf, source="cloud")
                    detected_pests.append((slug, conf))

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
    finally:
        stop_event.set()
        if remote_thread is not None:
            remote_thread.join(timeout=2)
        cap.release()
        cv2.destroyAllWindows()

    print()
    print("  Detector dihentikan.")


if __name__ == "__main__":
    main()
