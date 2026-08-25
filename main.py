#!/usr/bin/env python3
"""
SIPETIKCAMERA — Pest Detection with SIPETIK Dashboard Integration
=================================================================
Deteksi hama sawah via webcam dan kirim notifikasi ke dashboard SIPETIK
secara real-time. Beberapa sumber deteksi digabung:

  1. Model YOLOv8 lokal utama (best.pt) — tikus. Cepat, jalan offline.
  2. yolov8n.pt (COCO) — deteksi manusia/petani & burung, dipakai kalau
     model utama belum kenal kelas "person" (supaya buzzer TIDAK bunyi ke
     orang, cuma ke hama).
  3. pest_local.pt (opsional) — wereng batang coklat + walang sangit,
     lokal juga (lihat training/README.md untuk cara training-nya).
  4. Model/workflow di Roboflow, dipanggil lewat API hosted mereka
     (https://serverless.roboflow.com) untuk ulat grayak & keong mas —
     dua hama yang belum ada dataset lokal yang layak. Dijalankan di
     thread terpisah supaya tidak bikin preview kamera patah-patah. Aktif
     otomatis kalau ROBOFLOW_API_KEY diisi di file .env.

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
    "golden-apple-snail/2",
    # "paddy-rice-insect-pest-dataset/3" — DILEPAS dari cloud. Wereng batang
    # coklat sekarang dideteksi LOKAL oleh pest_local.pt (dilatih dari
    # dataset yang sama, lihat training/README.md), tidak perlu dipanggil
    # dua kali (lokal + cloud) untuk kelas yang sama.
    # "detection-of-fall-armyworm-infestation-with-deep-learning/1" —
    # DIMATIKAN. Dites langsung: model ini salah kenali wajah orang di depan
    # kamera sebagai "ulat grayak" (confidence 0.6–0.75), bukan cuma di
    # gambar noise. Kelihatannya model ini dilatih untuk foto close-up daun
    # yang sudah terserang, bukan untuk membedakan "ada hama" vs "bukan
    # hama" di scene webcam biasa. Jangan aktifkan lagi sampai ketemu
    # model/data ulat grayak yang lebih baik (lihat training/README.md).
]

# Ulat grayak dipanggil lewat Workflow open-vocabulary (segmentasi umum,
# daftar kelas dikirim saat runtime lewat parameter "classes"). Walang
# sangit TIDAK dicari di sini lagi — sekarang dideteksi LOKAL oleh
# pest_local.pt (lihat training/README.md), workflow ini dites bersih
# (tidak false-positive di gambar noise) tapi tetap butuh internet, jadi
# dipakai seperlunya saja (cuma untuk kelas yang belum ada model lokalnya).
ZERO_SHOT_WORKFLOW = {
    "workspace_name": "bryans-workspace-cfpnz",
    "workflow_id":    "general-segmentation-api",
    "classes_param":  "ulat grayak, Ulat grayak",
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
#  PEMETAAN KELAS & LABEL BAHASA INDONESIA
# ================================================================
HUMAN_CLASSES = {"person", "human", "man", "woman"}

PEST_LABELS = {
    "rat":                 "Tikus",
    "tikus":               "Tikus",
    "bird":                "Burung",
    "burung":              "Burung",
    "walang_sangit":       "Walang Sangit",
    "wereng_coklat":       "Wereng Batang Coklat",
    "ulat_grayak":         "Ulat Grayak",
    "keong_mas":           "Keong Mas",
    "dog":                 "Anjing",
    "cat":                 "Kucing",
    "cow":                 "Sapi",
    "pig":                 "Babi Hutan",
    "sheep":               "Kambing",
    "horse":               "Kuda",
}


def get_display_label(raw_name: str) -> tuple[str, bool]:
    """Mengembalikan (display_label, is_human)."""
    low = raw_name.lower().strip()
    if low in HUMAN_CLASSES:
        return "Petani / Manusia", True
    label = PEST_LABELS.get(low, low.replace("_", " ").title())
    return label, False


# ================================================================
#  FUNGSI BANTU VISUALISASI
# ================================================================
def draw_detection(frame, box, class_name, conf, source="local", is_human=False):
    if is_human:
        # Warna Biru Cyan untuk Manusia/Petani (Aman, Non-Agresif)
        box_color = (255, 200, 0)       # BGR: Cyan-Biru
        label_text = f"[AMAN] Petani ({conf:.0%})"
        text_color = (0, 0, 0)
    else:
        # Warna Merah untuk Hama Lokal, Oranye untuk Cloud
        box_color = (0, 0, 230) if source == "local" else (0, 140, 255)
        suffix = "" if source == "local" else " (cloud)"
        label_text = f"[HAMA] {class_name} ({conf:.0%}){suffix}"
        text_color = (255, 255, 255)

    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

    (text_w, text_h), baseline = cv2.getTextSize(
        label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2
    )
    label_x = x1
    label_y = y1 - 8
    if label_y - text_h - baseline < 0:
        label_y = y1 + text_h + 8

    bg_tl = (label_x, label_y - text_h - baseline)
    bg_br = (label_x + text_w + 8, label_y + baseline)
    cv2.rectangle(frame, bg_tl, bg_br, box_color, -1)
    cv2.putText(frame, label_text, (label_x + 4, label_y - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, text_color, 2, cv2.LINE_AA)


def box_overlap_ratio(box_a, box_b) -> float:
    """IoU (intersection-over-union) antara 2 box xyxy, 0.0 kalau tidak overlap."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


HUMAN_OVERLAP_SUPPRESS_IOU = 0.3  # box hama yg overlap segini besar dgn box
                                   # manusia dianggap salah deteksi, dibuang


def suppress_pests_overlapping_humans(detected_pests, detected_humans):
    """Buang deteksi hama yang box-nya tumpang tindih signifikan dengan box
    manusia yang sudah terkonfirmasi — model hama (terutama best.pt yang
    cuma 1 kelas) kadang salah kira wajah/badan orang sebagai hama."""
    if not detected_humans:
        return detected_pests
    human_boxes = [box for _, _, box in detected_humans]
    kept = []
    for raw_name, label, conf, box in detected_pests:
        if any(box_overlap_ratio(box, hbox) >= HUMAN_OVERLAP_SUPPRESS_IOU
               for hbox in human_boxes):
            continue  # kemungkinan besar false-positive di wajah/badan manusia
        kept.append((raw_name, label, conf, box))
    return kept


def passes_size_filter(frame, box, min_area, max_area):
    frame_h, frame_w = frame.shape[:2]
    x1, y1, x2, y2 = map(int, box)
    box_area  = max(0, x2 - x1) * max(0, y2 - y1)
    frame_area = frame_w * frame_h
    if frame_area == 0:
        return False
    return min_area <= (box_area / frame_area) <= max_area


def parse_remote_predictions(preds, force_slug=None):
    """Ubah list prediction mentah dari Roboflow jadi list (slug, raw_class_name, conf, xyxy)."""
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
    """Panggil semua model + workflow Roboflow untuk 1 frame."""
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
        detections += parse_remote_predictions(preds)
    except Exception as exc:
        print(f"  [WARN] Roboflow workflow zero-shot error: {exc}")

    return detections


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
        description="SIPETIKCAMERA — Deteksi Hama & Manusia + Integrasi Dashboard SIPETIK"
    )
    parser.add_argument("--model",    type=str,   default="best.pt",
                        help="Path ke model YOLO (.pt)")
    parser.add_argument("--server",   type=str,   default="http://192.168.1.5:8000",
                        help="URL server Laravel SIPETIK")
    parser.add_argument("--camera",   type=int,   default=0,
                        help="Index kamera (default: 0)")
    parser.add_argument("--conf",     type=float, default=0.55,
                        help="Confidence threshold (default: 0.55)")
    parser.add_argument("--imgsz",    type=int,   default=640,
                        help="Ukuran inferensi (default: 640)")
    parser.add_argument("--min-area", type=float, default=0.01,
                        help="Abaikan box lebih kecil dari fraksi ini")
    parser.add_argument("--max-area", type=float, default=0.85,
                        help="Abaikan box lebih besar dari fraksi ini")
    parser.add_argument("--cooldown", type=int,   default=10,
                        help="Jeda minimal antar trigger buzzer (detik)")
    parser.add_argument("--no-remote", action="store_true",
                        help="Matikan deteksi tambahan lewat Roboflow API")
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
    print("=" * 60)
    print("  SIPETIKCAMERA — Sistem Deteksi Cerdas Hama Sawah & Manusia")
    print("=" * 60)
    print(f"  Server       : {args.server}")
    print(f"  Model Utama  : {model_file}")
    print(f"  Kamera       : index {args.camera}")
    print(f"  Confidence   : >= {args.conf:.0%}")
    print(f"  Cooldown     : {args.cooldown} detik antar trigger buzzer")
    
    # Load model utama
    model_main = YOLO(model_file)
    
    # Cek apakah model utama sudah memiliki kelas person / burung
    # Jika model utama adalah custom (seperti best.pt yang hanya deteksi tikus),
    # kita muat juga yolov8n.pt secara ringan untuk mengenali Manusia & Burung.
    model_coco = None
    main_has_person = any("person" in str(name).lower() for name in model_main.names.values())
    
    if not main_has_person and os.path.exists("yolov8n.pt"):
        print("  Model Sekunder: yolov8n.pt (Deteksi Petani/Manusia & Burung)")
        model_coco = YOLO("yolov8n.pt")

    # Model lokal tambahan: wereng batang coklat + walang sangit (lihat
    # training/README.md). Kalau file ini belum ada (belum ditraining),
    # kedua hama itu tetap terdeteksi lewat cloud sebagai fallback — lihat
    # REMOTE_MODEL_IDS / ZERO_SHOT_WORKFLOW di atas.
    model_pest_local = None
    pest_local_path  = "pest_local.pt"
    if os.path.exists(pest_local_path):
        print(f"  Model Tambahan: {pest_local_path} (Wereng Batang Coklat + Walang Sangit, lokal)")
        model_pest_local = YOLO(pest_local_path)

    if use_remote:
        print(f"  Cloud        : AKTIF (Roboflow, tiap {args.remote_interval:.0f}s)")
    elif not api_key:
        print("  Cloud        : nonaktif (ROBOFLOW_API_KEY belum diisi)")
    else:
        print("  Cloud        : nonaktif")
    print("=" * 60)
    print()

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

    print("  Kamera siap. Tekan Q pada jendela untuk berhenti.")
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

            _LATEST_FRAME["frame"] = frame

            # Hitung FPS
            fps_count += 1
            if fps_count >= 30:
                fps_display = fps_count / (time.time() - fps_start)
                fps_count   = 0
                fps_start   = time.time()

            detected_pests  = []
            detected_humans = []

            # 1. Inferensi Model Utama (best.pt atau yolov8n.pt)
            results_main = model_main.predict(frame, conf=args.conf,
                                              imgsz=args.imgsz, verbose=False)

            for result in results_main:
                for b in result.boxes:
                    cls_id     = int(b.cls[0])
                    conf       = float(b.conf[0])
                    xyxy       = b.xyxy[0].tolist()
                    raw_name   = result.names.get(cls_id, str(cls_id))

                    if not passes_size_filter(frame, xyxy, args.min_area, args.max_area):
                        continue

                    label, is_human = get_display_label(raw_name)
                    if is_human:
                        detected_humans.append((label, conf, xyxy))
                    else:
                        detected_pests.append((raw_name, label, conf, xyxy))

            # 2. Inferensi Model Sekunder (COCO untuk deteksi Manusia & Burung jika model utama spesifik hama)
            if model_coco is not None and not detected_humans:
                # Class 0: person, Class 14: bird
                results_coco = model_coco.predict(frame, conf=args.conf,
                                                  classes=[0, 14],
                                                  imgsz=args.imgsz, verbose=False)
                for result in results_coco:
                    for b in result.boxes:
                        cls_id   = int(b.cls[0])
                        conf     = float(b.conf[0])
                        xyxy     = b.xyxy[0].tolist()
                        raw_name = result.names.get(cls_id, str(cls_id))

                        if not passes_size_filter(frame, xyxy, args.min_area, args.max_area):
                            continue

                        label, is_human = get_display_label(raw_name)
                        if is_human:
                            detected_humans.append((label, conf, xyxy))
                        else:
                            detected_pests.append((raw_name, label, conf, xyxy))

            # 3. Inferensi Model Lokal Tambahan (pest_local.pt — wereng
            #    batang coklat + walang sangit, kalau sudah ditraining)
            if model_pest_local is not None:
                results_pest_local = model_pest_local.predict(
                    frame, conf=args.conf, imgsz=args.imgsz, verbose=False)
                for result in results_pest_local:
                    for b in result.boxes:
                        cls_id   = int(b.cls[0])
                        conf     = float(b.conf[0])
                        xyxy     = b.xyxy[0].tolist()
                        raw_name = result.names.get(cls_id, str(cls_id))

                        if not passes_size_filter(frame, xyxy, args.min_area, args.max_area):
                            continue

                        label, is_human = get_display_label(raw_name)
                        if is_human:
                            detected_humans.append((label, conf, xyxy))
                        else:
                            detected_pests.append((raw_name, label, conf, xyxy))

            # 4. Deteksi Cloud Roboflow (jika aktif)
            if use_remote:
                for slug, raw_name, conf, box in _REMOTE_DETECTIONS["items"]:
                    if not passes_size_filter(frame, box, args.min_area, args.max_area):
                        continue
                    label, is_human = get_display_label(slug)
                    if is_human:
                        detected_humans.append((label, conf, box))
                    else:
                        detected_pests.append((slug, label, conf, box))

            # Buang deteksi hama yang box-nya nempel di box manusia (kemungkinan
            # besar false-positive — lihat suppress_pests_overlapping_humans)
            detected_pests = suppress_pests_overlapping_humans(detected_pests, detected_humans)

            # Gambar Bounding Box Manusia (Cyan/Biru - Aman)
            for label, conf, box in detected_humans:
                draw_detection(frame, box, label, conf, source="local", is_human=True)

            # Gambar Bounding Box Hama (Merah - Bahaya)
            for raw_slug, label, conf, box in detected_pests:
                draw_detection(frame, box, label, conf, source="local", is_human=False)

            # ── Logika Buzzer & Notifikasi SIPETIK ───────────────────
            # PENTING: Hanya hama yang memicu buzzer! Manusia TIDAK memicu buzzer.
            if detected_pests:
                no_pest_frames = 0
                if now - last_trigger_at >= args.cooldown:
                    best_slug, best_label, best_conf, _ = max(detected_pests, key=lambda x: x[2])
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"  [{ts}] ⚠️ HAMA TERDETEKSI: {best_label} ({best_conf:.0%}) → Buzzer ESP32!")
                    ok = notify_detection(args.server, best_slug, best_conf)
                    if ok:
                        last_trigger_at = now
                        print(f"          Notifikasi Dashboard Berhasil. Cooldown {args.cooldown}s.")
            else:
                no_pest_frames += 1
                if no_pest_frames == CLEAR_FRAMES:
                    notify_clear(args.server)
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"  [{ts}] Sawah aman — Dashboard dibersihkan.")

            # ── Status Bar Banner di Atas ────────────────────────────
            if detected_pests:
                best_slug, best_label, best_conf, _ = max(detected_pests, key=lambda x: x[2])
                status_text  = f"[!] HAMA TERDETEKSI: {best_label} ({len(detected_pests)} objek) - BUZZER AKTIF"
                status_color = (0, 0, 240)    # Merah
            elif detected_humans:
                status_text  = f"[OK] PETANI / MANUSIA DI LOKASI ({len(detected_humans)} orang) - AMAN (Buzzer OFF)"
                status_color = (255, 200, 0)  # Cyan
            else:
                status_text  = "[OK] LAHAN AMAN — Tidak Ada Hama"
                status_color = (0, 200, 0)    # Hijau

            cv2.rectangle(frame, (0, 0), (frame.shape[1], 42), (20, 20, 20), -1)
            cv2.putText(frame, status_text, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_color, 2, cv2.LINE_AA)
            cv2.putText(frame, f"{fps_display:.1f} fps",
                        (frame.shape[1] - 95, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.imshow("SIPETIK AI CAMERA — Deteksi Hama & Manusia [Q = Keluar]", frame)

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

