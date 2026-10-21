#!/usr/bin/env python3
"""
SIPETIKCAMERA — Pest Detection with SIPETIK Dashboard Integration
=================================================================
Deteksi hama sawah via webcam dan kirim notifikasi ke dashboard SIPETIK
secara real-time. Beberapa sumber deteksi digabung:

  1. pest_v4.pt (YOLO11s) — SATU model lokal untuk 10 hama (9 serangga +
     tikus + keong mas dewasa), dilatih dengan ribuan gambar "bukan hama"
     (orang, wajah, tangan, daun padi sakit, malai padi) supaya tidak salah
     deteksi. Lihat training/README.md bagian "v3" & "dataset v4". Urutan
     cadangan: pest_v3.pt, lalu susunan lama best.pt (tikus) + pest_v2.pt.
  1b. disease_v1.pt (opsional) — 6 penyakit daun padi, dicek tiap 2 detik.
     Penyakit TIDAK membunyikan buzzer; dikirim ke /api/camera/disease
     sebagai peringatan di dashboard.
  2. yolov8n.pt (COCO) — deteksi manusia/petani & burung, dipakai kalau
     model utama belum kenal kelas "person" (supaya buzzer TIDAK bunyi ke
     orang, cuma ke hama).
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
    python main.py --trt                # TensorRT FP16 (frame ~2x lebih cepat)
    python main.py --width 1920 --tiles 2   # serangga kecil: kamera 1080p + tiling 2x2

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
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    CUDA_AVAILABLE = False

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
    def _send():
        try:
            requests.post(
                f"{server_url}/api/camera/motion",
                json={
                    "detected":     True,
                    "animal_class": pest_class,
                    "confidence":   round(confidence, 3),
                    "device_id":    "laptop-camera",
                },
                timeout=2,
            )
        except Exception as exc:
            print(f"  [WARN] Gagal kirim notifikasi: {exc}")
    threading.Thread(target=_send, daemon=True).start()
    return True


def notify_disease(server_url: str, disease_class: str, confidence: float) -> None:
    """Penyakit daun -> dashboard saja (endpoint terpisah, tidak memicu buzzer)."""
    def _send():
        try:
            requests.post(
                f"{server_url}/api/camera/disease",
                json={"disease_class": disease_class, "confidence": round(confidence, 3),
                      "device_id": "laptop-camera"},
                timeout=2,
            )
        except Exception as exc:
            print(f"  [WARN] Gagal kirim notifikasi penyakit: {exc}")
    threading.Thread(target=_send, daemon=True).start()


def notify_clear(server_url: str) -> None:
    def _send():
        try:
            requests.post(
                f"{server_url}/api/camera/motion",
                json={"detected": False, "animal_class": None,
                      "confidence": 0.0, "device_id": "laptop-camera"},
                timeout=2,
            )
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


def send_heartbeat(server_url: str) -> None:
    def _send():
        try:
            requests.get(
                f"{server_url}/api/camera/heartbeat",
                params={"device_id": "laptop-camera"},
                timeout=2,
            )
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


# ================================================================
#  PEMETAAN KELAS & LABEL BAHASA INDONESIA
# ================================================================
HUMAN_CLASSES = {"person", "human", "man", "woman"}

PEST_LABELS = {
    "rat":                 "Tikus",
    "tikus":               "Tikus",
    "bird":                "Burung",
    "burung":              "Burung",
    "wereng_coklat":       "Wereng Coklat",
    "walang_sangit":       "Walang Sangit",
    "keong_mas":           "Keong Mas",
    "wereng_hijau":        "Wereng Hijau",
    "penggulung_daun":     "Penggulung Daun",
    "penggerek_batang":    "Penggerek Batang",
    "kepinding_hitam":     "Kepinding Hitam",
    "belalang_padi":       "Belalang Padi",
    "lalat_bibit":         "Lalat Bibit",
    "ulat_grayak":         "Ulat Grayak",
    "blas_daun":           "Blas Daun",
    "hawar_daun_bakteri":  "Hawar Daun Bakteri",
    "bercak_coklat":       "Bercak Coklat",
    "bercak_coklat_sempit": "Bercak Coklat Sempit",
    "hangus_daun":         "Hangus Daun",
    "gosong_daun":         "Gosong Daun",
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
    if source == "disease":
        box_color = (0, 140, 255)       # BGR: oranye — peringatan, bukan alarm
        label_text = f"[PENYAKIT] {class_name} ({conf:.0%})"
        text_color = (0, 0, 0)
    elif is_human:
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


def is_pest_on_human(pest_box, human_box, min_pest_overlap=0.15) -> bool:
    """Cek apakah bounding box hama berada di dalam atau menempel pada tubuh manusia.
    Menggunakan:
    1. Center-point containment (titik tengah box hama di dalam box manusia).
    2. IoP (Intersection over Pest Area): jika >= 15% bagian hama menempel di badan manusia.
    3. IoU standar jika ukuran box sebanding (>= 0.15).
    """
    px1, py1, px2, py2 = pest_box
    hx1, hy1, hx2, hy2 = human_box

    pest_area = max(0, px2 - px1) * max(0, py2 - py1)
    if pest_area <= 0:
        return True  # box tidak valid, drop

    # 1. Cek jika titik tengah hama ada di dalam box manusia -> pasti false-positive
    pcx = (px1 + px2) / 2.0
    pcy = (py1 + py2) / 2.0
    if (hx1 <= pcx <= hx2) and (hy1 <= pcy <= hy2):
        return True

    # 2. Hitung luas irisan (intersection)
    ix1, iy1 = max(px1, hx1), max(py1, hy1)
    ix2, iy2 = min(px2, hx2), min(py2, hy2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return False

    # 3. IoP (Intersection over Pest Area): seberapa besar porsi hama nempel di manusia
    if (inter / pest_area) >= min_pest_overlap:
        return True

    # 4. IoU jika box sebanding
    human_area = max(0, hx2 - hx1) * max(0, hy2 - hy1)
    union = pest_area + human_area - inter
    if union > 0 and (inter / union) >= 0.15:
        return True

    return False


def suppress_pests_overlapping_humans(detected_pests, detected_humans):
    """Buang deteksi hama yang menempel atau berada di badan/wajah/pakaian manusia.
    Model hama tunggal (seperti best.pt tikus) sering salah mendeteksi rambut,
    tangan, atau lipatan baju manusia sebagai tikus."""
    if not detected_humans:
        return detected_pests
    human_boxes = [box for _, _, box in detected_humans]
    kept = []
    for raw_name, label, conf, box in detected_pests:
        if any(is_pest_on_human(box, hbox) for hbox in human_boxes):
            continue  # False-positive pada tubuh manusia, dibuang!
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


def load_model(path: str, device: str, use_trt: bool):
    """Muat model YOLO. Dengan --trt: pakai engine TensorRT FP16 (dibangun
    sekali ~20 dtk per model, di-cache di weights/engines/<gpu>/ karena engine
    hanya cocok untuk GPU tempat ia dibangun). Di RTX 5070 satu frame turun
    dari ~15 ms ke ~7 ms — lihat training/benchmarks/."""
    if not use_trt:
        return YOLO(path).to(device)
    import shutil
    gpu = "".join(c if c.isalnum() else "_" for c in torch.cuda.get_device_name(0))
    stem = os.path.splitext(os.path.basename(path))[0]
    engine = os.path.join("weights", "engines", gpu, stem + ".engine")
    if not os.path.exists(engine):
        print(f"  [TensorRT] membangun engine {stem} untuk {gpu} (sekali saja) ...")
        os.makedirs(os.path.dirname(engine), exist_ok=True)
        built = YOLO(path).export(format="engine", half=True, imgsz=640, device=0, verbose=False)
        shutil.move(str(built), engine)
        import glob
        for onnx in glob.glob(os.path.join(os.path.dirname(os.path.abspath(path)), stem + "*.onnx")):
            os.remove(onnx)  # file perantara ekspor (mis. pest_v3.fp16.onnx)
    return YOLO(engine, task="detect")


# ================================================================
#  DETEKTOR PER FRAME (dipakai main() dan training/eval_video.py)
# ================================================================
class PestDetector:
    """Satu frame -> (manusia, hama), dengan semua filter kamera SIPETIK.

    Dipisah dari loop kamera supaya training/eval_video.py dan
    training/eval_false_positives.py menguji logika yang PERSIS sama.

    confirm_frames > 1 menyalakan tracking (ByteTrack): sebuah hama baru
    dihitung kalau objek dengan ID track yang sama terlihat di N inferensi
    berturut-turut dengan confidence >= conf. Salah deteksi biasanya cuma
    muncul 1-2 frame lalu hilang, sedangkan hama sungguhan terus terlihat.

    tiles > 1 menyalakan tiling: selain frame utuh, frame dipotong jadi
    tiles x tiles bagian (tumpang tindih 20%) yang masing-masing dideteksi
    di imgsz penuh — serangga kecil (wereng ~0,4% luas frame) jadi terlihat
    2-3x lebih besar oleh model. Semua potongan dijalankan dalam satu batch
    GPU, lalu digabung dengan NMS per kelas.
    """

    TRACK_CONF = 0.25  # tracker butuh deteksi lemah juga supaya ID tidak putus
    ANIMALS = (15, 16, 17, 18, 19, 20, 21, 22, 23)  # COCO: kucing, anjing, kuda, domba, sapi, gajah, beruang, zebra, jerapah
    TILE_OVERLAP = 0.2

    def __init__(self, model_main, model_coco=None, model_extra=None, *, conf=0.55,
                 imgsz=640, device="cuda:0", min_area=0.01, max_area=0.85,
                 confirm_frames=1, tiles=1, human_conf=0.5, human_filter=False,
                 animal_filter=False):
        self.model_main, self.model_coco, self.model_extra = model_main, model_coco, model_extra
        # human_conf  : keyakinan minimum sebelum sesuatu dianggap orang
        # human_filter: buang hama yang menempel di badan orang (dibuat untuk
        #               model lama yang mengira rambut/tangan sebagai hama)
        self.human_conf, self.human_filter = human_conf, human_filter
        # animal_filter: "tikus" yang menimpa kucing/anjing/beruang/dll yang
        # dikenali COCO (>= 0.5) dibuang. Bawaan MATI: dengan --tiles 2 ia
        # membuang 18 alarm palsu di 2.700 foto, tapi juga 7 dari 18 tikus asli
        # (COCO kadang menyebut tikus "kucing"/"anjing").
        self.animal_filter = animal_filter
        self.conf, self.imgsz, self.device = conf, imgsz, device
        self.min_area, self.max_area = min_area, max_area
        self.confirm_frames = max(1, confirm_frames)
        self.tiles = max(1, tiles)
        self.reset()

    def reset(self):
        """Mulai video/kamera baru: lupakan semua track."""
        self.trackers = {}  # id(model) -> BYTETracker (ruang kelas tiap model beda)
        self.streak = {}    # (id(model), track_id) -> inferensi berturut-turut

    def _tracker(self, model):
        if id(model) not in self.trackers:
            from ultralytics.trackers.byte_tracker import BYTETracker
            from ultralytics.utils import YAML, IterableSimpleNamespace
            from ultralytics.utils.checks import check_yaml
            cfg = IterableSimpleNamespace(**YAML.load(check_yaml("bytetrack.yaml")))
            self.trackers[id(model)] = BYTETracker(args=cfg)
        return self.trackers[id(model)]

    def _tile_boxes(self, w, h):
        n, ov = self.tiles, self.TILE_OVERLAP
        tw, th = int(w / (n - (n - 1) * ov)), int(h / (n - (n - 1) * ov))
        xs = [round(i * (w - tw) / (n - 1)) for i in range(n)]
        ys = [round(i * (h - th) / (n - 1)) for i in range(n)]
        return [(x, y, x + tw, y + th) for y in ys for x in xs]

    def _predict(self, model, frame, conf):
        """Deteksi frame utuh (+ potongan tiling) -> (N,6) [x1,y1,x2,y2,conf,cls], names."""
        r = model.predict(frame, conf=conf, imgsz=self.imgsz, device=self.device, verbose=False)[0]
        dets = [r.boxes.data[:, :6].cpu()]
        if self.tiles > 1:
            h, w = frame.shape[:2]
            regions = self._tile_boxes(w, h)
            crops = [frame[y1:y2, x1:x2] for x1, y1, x2, y2 in regions]
            kw = dict(conf=conf, imgsz=self.imgsz, device=self.device, verbose=False)
            if isinstance(getattr(model, "model", None), str):  # engine TensorRT: batch tetap 1
                outs = [model.predict(c, **kw)[0] for c in crops]
            else:                                               # PyTorch: satu batch GPU
                outs = model.predict(crops, **kw)
            for (x1, y1, _, _), rt in zip(regions, outs):
                d = rt.boxes.data[:, :6].cpu().clone()
                d[:, [0, 2]] += x1
                d[:, [1, 3]] += y1
                dets.append(d)
            d = torch.cat(dets)
            if len(d):
                import torchvision
                keep = torchvision.ops.batched_nms(d[:, :4], d[:, 4], d[:, 5].long(), 0.5)
                d = d[keep]
            return d.numpy(), r.names
        return dets[0].numpy(), r.names

    def _accept_pest(self, frame, raw_name, xyxy, humans) -> bool:
        if not passes_size_filter(frame, xyxy, self.min_area, self.max_area):
            return False
        low = raw_name.lower()
        # tikus sawah tidak mungkin melebihi 20% luas kamera (biasanya badan/wajah manusia)
        if ("rat" in low or "tikus" in low) and not passes_size_filter(frame, xyxy, self.min_area, 0.20):
            return False
        return not (self.human_filter and any(is_pest_on_human(xyxy, h) for _, _, h in humans))

    def _confirmed(self, model, dets, names, frame):
        """Deteksi (N,6) -> [(raw_name, conf, xyxy)] yang lolos conf, dan kalau
        tracking aktif, sudah terlihat confirm_frames inferensi berturut-turut."""
        if self.confirm_frames <= 1:
            return [(names[int(c)], float(s), [x1, y1, x2, y2])
                    for x1, y1, x2, y2, s, c in dets if s >= self.conf]
        from ultralytics.engine.results import Boxes
        rows, seen = [], set()
        for x1, y1, x2, y2, tid, score, cls, _ in self._tracker(model).update(
                Boxes(dets, frame.shape[:2]), frame):
            key = (id(model), int(tid))
            if score < self.conf:
                continue
            seen.add(key)
            self.streak[key] = self.streak.get(key, 0) + 1
            if self.streak[key] >= self.confirm_frames:
                rows.append((names[int(cls)], float(score), [x1, y1, x2, y2]))
        # track yang hilang/lemah di frame ini mulai dari nol lagi
        self.streak = {k: n for k, n in self.streak.items() if k[0] != id(model) or k in seen}
        return rows

    def _run_pest_model(self, model, frame, humans, pests):
        tracked = self.confirm_frames > 1
        dets, names = self._predict(model, frame, min(self.TRACK_CONF, self.conf) if tracked else self.conf)
        for raw_name, conf, xyxy in self._confirmed(model, dets, names, frame):
            label, is_human = get_display_label(raw_name)
            if is_human:
                humans.append((label, conf, xyxy))
            elif self._accept_pest(frame, raw_name, xyxy, humans):
                pests.append((raw_name, label, conf, xyxy))

    def detect(self, frame, remote_items=()):
        humans, pests = [], []
        animals = []

        # 1. COCO: manusia (agar buzzer tidak bunyi ke orang) & burung
        if self.model_coco is not None:
            r = self.model_coco.predict(frame, conf=min(self.conf, 0.35), classes=[0, 14, *self.ANIMALS],
                                        imgsz=self.imgsz, device=self.device, verbose=False)[0]
            d = r.boxes.data[:, :6].cpu().numpy()
            animals = [b[:4] for b in d if int(b[5]) in self.ANIMALS and b[4] >= 0.5]
            min_a = max(self.min_area, 0.01)
            for x1, y1, x2, y2, conf, _ in d[d[:, 5] == 0]:
                if conf >= self.human_conf and passes_size_filter(frame, [x1, y1, x2, y2], min_a, self.max_area):
                    humans.append(("Petani / Manusia", float(conf), [x1, y1, x2, y2]))
            for raw_name, conf, xyxy in self._confirmed(self.model_coco, d[d[:, 5] == 14], r.names, frame):
                if passes_size_filter(frame, xyxy, min_a, self.max_area):
                    pests.append((raw_name, get_display_label(raw_name)[0], conf, xyxy))

        # 2-3. Model hama utama (+ model tambahan kalau best.pt tetap dipakai)
        self._run_pest_model(self.model_main, frame, humans, pests)
        if self.model_extra is not None:
            self._run_pest_model(self.model_extra, frame, humans, pests)

        # 4. Deteksi cloud Roboflow (kalau aktif)
        for slug, raw_name, conf, box in remote_items:
            if not passes_size_filter(frame, box, self.min_area, self.max_area):
                continue
            label, is_human = get_display_label(slug)
            if is_human:
                humans.append((label, conf, box))
            elif not (self.human_filter and any(is_pest_on_human(box, h) for _, _, h in humans)):
                pests.append((slug, label, conf, box))

        # 5. Filter akhir: "tikus" di atas kucing/anjing/dll = salah kenal
        if self.animal_filter and animals:
            pests = [x for x in pests
                     if not (x[0] in ("tikus", "rat") and any(is_pest_on_human(x[3], a) for a in animals))]
        # buang hama yang menempel di badan manusia (hanya untuk model lama)
        if self.human_filter:
            pests = suppress_pests_overlapping_humans(pests, humans)
        return humans, pests


class DiseaseDetector:
    """Penyakit daun padi. Penyakit tidak bergerak, jadi cukup dicek tiap
    `every_s` detik, dan baru dilaporkan kalau kelas yang sama terlihat di
    `confirm` pengecekan berturut-turut (bukan kedipan satu frame)."""

    def __init__(self, model, *, conf=0.5, imgsz=640, device="cuda:0",
                 every_s=2.0, confirm=2, min_area=0.002):
        self.model, self.conf, self.imgsz, self.device = model, conf, imgsz, device
        self.every_s, self.confirm, self.min_area = every_s, max(1, confirm), min_area
        self.last_run = -1e9
        self.streak = {}       # kelas -> jumlah pengecekan berturut-turut
        self.current = []      # deteksi terkonfirmasi terakhir (untuk digambar)

    def maybe_detect(self, frame, now, humans=()):
        if now - self.last_run < self.every_s:
            return self.current
        self.last_run = now
        r = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz,
                               device=self.device, verbose=False)[0]
        found = {}
        for b in r.boxes:
            xyxy = b.xyxy[0].tolist()
            if not passes_size_filter(frame, xyxy, self.min_area, 0.95):
                continue
            if any(is_pest_on_human(xyxy, h) for _, _, h in humans):
                continue  # baju/kulit orang bukan daun
            raw = r.names[int(b.cls[0])]
            found.setdefault(raw, []).append((raw, get_display_label(raw)[0], float(b.conf[0]), xyxy))
        self.streak = {c: self.streak.get(c, 0) + 1 for c in found}
        self.current = [d for c, dets in found.items() if self.streak[c] >= self.confirm for d in dets]
        return self.current


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
    parser.add_argument("--record",   type=str,   default=None,
                        help="Simpan video beranotasi ke file .mp4 (+ log per frame .csv di sebelahnya)")
    parser.add_argument("--no-window", action="store_true",
                        help="Jangan tampilkan jendela kamera (mis. saat --record dari file)")
    parser.add_argument("--source",   type=str,   default=None,
                        help="File video / URL stream (RTSP, HTTP) sebagai ganti --camera")
    parser.add_argument("--confirm-frames", type=int, default=3,
                        help="Hama baru dihitung kalau terlihat di N inferensi berturut-turut "
                             "(tracking ByteTrack). 1 = matikan tracking (perilaku lama)")
    parser.add_argument("--conf",     type=float, default=0.55,
                        help="Confidence threshold (default: 0.55)")
    parser.add_argument("--imgsz",    type=int,   default=640,
                        help="Ukuran inferensi (default: 640)")
    parser.add_argument("--min-area", type=float, default=None,
                        help="Abaikan box lebih kecil dari fraksi luas frame ini "
                             "(default 0.01; 0.002 kalau --tiles dipakai)")
    parser.add_argument("--tiles", type=int, default=1,
                        help="Potong frame jadi NxN bagian untuk serangga kecil (mis. 2). "
                             "Paling berguna dengan kamera resolusi tinggi (--width 1920)")
    parser.add_argument("--width", type=int, default=640,
                        help="Lebar frame kamera yang diminta (640, 1280, 1920)")
    parser.add_argument("--max-area", type=float, default=0.85,
                        help="Abaikan box lebih besar dari fraksi ini")
    parser.add_argument("--cooldown", type=int,   default=10,
                        help="Jeda minimal antar trigger buzzer (detik)")
    parser.add_argument("--infer-every", type=int, default=1,
                        help="Jalankan inferensi setiap N frame (1 = tiap frame, 2 = 2x lebih ringan)")
    parser.add_argument("--device", type=str, default=None,
                        help="Device inferensi ('0', 'cuda', 'cpu', default: otomatis pakai GPU RTX)")
    parser.add_argument("--trt", action="store_true",
                        help="Pakai TensorRT FP16 (butuh pip install tensorrt-cu12/cu13), ~2x lebih cepat")
    parser.add_argument("--no-disease", action="store_true",
                        help="Matikan deteksi penyakit daun (disease_v1.pt)")
    parser.add_argument("--disease-conf", type=float, default=0.5,
                        help="Confidence minimum penyakit daun (default: 0.5)")
    parser.add_argument("--disease-cooldown", type=int, default=300,
                        help="Jeda minimal notifikasi penyakit yang sama ke dashboard (detik)")
    parser.add_argument("--human-conf", type=float, default=0.5,
                        help="Keyakinan minimum sebelum sesuatu dianggap orang (default 0.5; "
                             "0.35 membuat serangga di layar HP ikut dianggap orang)")
    parser.add_argument("--animal-filter", action="store_true",
                        help="Buang 'tikus' yang menimpa kucing/anjing/dll (kurangi alarm palsu, "
                             "tapi sebagian tikus asli ikut terbuang)")
    parser.add_argument("--human-filter", action="store_true",
                        help="Buang hama yang menempel di badan orang. Otomatis aktif untuk "
                             "best.pt lama; pest_v4/v5 tidak butuh (diukur: 0 alarm palsu di "
                             "2.700 foto orang tanpa filter ini)")
    parser.add_argument("--keep-rat-model", action="store_true",
                        help="Tetap muat best.pt (tikus lama) walau pest_v4/v3 sudah punya kelas tikus")
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
    print(f"  Kamera       : {args.source or f'index {args.camera}'}")
    device = args.device or ("cuda:0" if CUDA_AVAILABLE else "cpu")
    device_name = torch.cuda.get_device_name(0) if (CUDA_AVAILABLE and "cpu" not in str(device).lower()) else "CPU"
    use_trt = args.trt and CUDA_AVAILABLE and "cpu" not in str(device).lower()
    print(f"  Device       : {device.upper()} ({device_name}){' + TensorRT FP16' if use_trt else ''}")
    print(f"  Confidence   : >= {args.conf:.0%}")
    print(f"  Cooldown     : {args.cooldown} detik antar trigger buzzer")
    
    # Model hama lokal: pest_v4.pt (YOLO11s) > pest_v3.pt > pest_v2.pt > pest_local.pt
    pest_local_path = None
    for cand in ("pest_v4.pt", "pest_v3.pt", "pest_v2.pt", "pest_local.pt"):
        if os.path.exists(cand) and os.path.abspath(cand) != os.path.abspath(model_file):
            pest_local_path = cand
            break
    model_pest_local = load_model(pest_local_path, device, use_trt) if pest_local_path else None

    # pest_v4/v3 sudah punya kelas tikus -> best.pt (tikus lama, sering salah
    # kenali rambut/tangan) tidak dimuat lagi, kecuali diminta --keep-rat-model
    pest_has_rat = model_pest_local is not None and any(
        str(n).lower() in ("tikus", "rat") for n in model_pest_local.names.values())
    legacy_models = False  # True kalau best.pt lama / model --model custom yang dipakai
    if pest_has_rat and args.model == "best.pt" and not args.keep_rat_model:
        model_main, model_pest_local = model_pest_local, None
        print(f"  Model Utama  : {pest_local_path} (10 hama termasuk tikus)")
    else:
        legacy_models = True
        model_main = load_model(model_file, device, use_trt)
        print(f"  Model Utama  : {model_file}")
        if model_pest_local is not None:
            print(f"  Model Tambahan: {pest_local_path} (Hama serangga sawah terlatih)")

    # Model utama custom tidak kenal "person" -> muat yolov8n.pt (COCO)
    # untuk mengenali Manusia & Burung.
    model_coco = None
    main_has_person = any("person" in str(name).lower() for name in model_main.names.values())

    if not main_has_person:
        try:
            print("  Model Sekunder: yolov8n.pt (Deteksi Petani/Manusia & Burung)")
            model_coco = load_model("yolov8n.pt", device, use_trt)
        except Exception as e:
            print(f"  [WARN] Gagal memuat yolov8n.pt: {e}")

    if args.min_area is None:
        args.min_area = 0.002 if args.tiles > 1 else 0.01
    # Filter "hama di badan orang" dibuat untuk best.pt lama (rambut/tangan
    # dikira tikus). Model v4/v5 dilatih dengan ribuan foto orang & tidak
    # butuh filter itu; filter justru membuang hama di HP yang dipegang orang.
    human_filter = args.human_filter or legacy_models
    detector = PestDetector(
        model_main, model_coco, model_pest_local, conf=args.conf, imgsz=args.imgsz,
        device=device, min_area=args.min_area, max_area=args.max_area,
        confirm_frames=args.confirm_frames, tiles=args.tiles,
        human_conf=args.human_conf, human_filter=human_filter, animal_filter=args.animal_filter,
    )
    print(f"  Filter Orang : orang >= {args.human_conf:.0%}"
          f"{', hama di badan orang dibuang' if human_filter else ''}")
    if args.tiles > 1:
        print(f"  Tiling       : {args.tiles}x{args.tiles} + frame utuh, min-area {args.min_area:.1%}")
    disease_detector = None
    if not args.no_disease and os.path.exists("disease_v1.pt"):
        disease_detector = DiseaseDetector(
            load_model("disease_v1.pt", device, use_trt), conf=args.disease_conf,
            imgsz=args.imgsz, device=device)
        print("  Penyakit Daun: disease_v1.pt (6 penyakit, tiap 2 dtk, tanpa buzzer)")
    last_disease_sent = {}

    if args.confirm_frames > 1:
        print(f"  Tracking     : AKTIF (hama dikonfirmasi setelah {args.confirm_frames} frame berturut-turut)")
    else:
        print("  Tracking     : nonaktif")

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

    # Inisialisasi kamera dengan DirectShow di Windows untuk hilangkan latency buffer
    if args.source:
        cap = cv2.VideoCapture(args.source)
    elif sys.platform.startswith("win"):
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(args.camera)
    else:
        cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        print(f"ERROR: {'Sumber ' + args.source if args.source else f'Kamera index {args.camera}'} tidak bisa dibuka.")
        sys.exit(1)

    if not args.source:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.width * 3 // 4 if args.width <= 640 else args.width * 9 // 16)

    print("  Kamera siap. Tekan Q pada jendela untuk berhenti.")
    print()

    # Sumber file video: pakai detik VIDEO (bukan jam dinding) untuk cooldown
    # buzzer & jadwal cek penyakit, supaya hasil sama dengan kamera real-time
    # walau file diproses lebih cepat/lambat dari aslinya.
    is_file = bool(args.source) and os.path.isfile(args.source)
    video_fps = (cap.get(cv2.CAP_PROP_FPS) or 30.0) if is_file else 0.0

    writer = log_f = None
    if args.record:
        import csv
        log_f = open(os.path.splitext(args.record)[0] + ".csv", "w", newline="", encoding="utf-8")
        log_csv = csv.writer(log_f)
        log_csv.writerow(["frame", "t", "pests", "humans", "diseases", "alarm"])

    last_trigger_at   = 0.0
    last_heartbeat_at = 0.0
    no_pest_frames    = 0
    fps_count         = 0
    fps_start         = time.time()
    fps_display       = 0.0
    frame_idx         = 0

    cached_humans = []
    cached_pests  = []

    try:
        while True:
            now = time.time()

            # Heartbeat ke server (asinkron)
            if now - last_heartbeat_at >= HEARTBEAT_INTERVAL:
                send_heartbeat(args.server)
                last_heartbeat_at = now

            ok, frame = cap.read()
            if not ok:
                print("  Video selesai." if is_file else "ERROR: Tidak bisa membaca frame dari kamera.")
                break

            _LATEST_FRAME["frame"] = frame
            frame_idx += 1
            if video_fps:
                now = frame_idx / video_fps
            alarm_now = False

            # Hitung FPS
            fps_count += 1
            if fps_count >= 30:
                fps_display = fps_count / (time.time() - fps_start)
                fps_count   = 0
                fps_start   = time.time()

            should_infer = (frame_idx % max(1, args.infer_every) == 0)

            if should_infer:
                remote_items = _REMOTE_DETECTIONS["items"] if use_remote else ()
                detected_humans, detected_pests = detector.detect(frame, remote_items)
                cached_humans = detected_humans
                cached_pests  = detected_pests
            else:
                detected_humans = cached_humans
                detected_pests  = cached_pests

            # Penyakit daun (tiap 2 detik, tidak memicu buzzer)
            detected_diseases = []
            if disease_detector is not None:
                detected_diseases = disease_detector.maybe_detect(frame, now, detected_humans)
                for raw, label, conf, box in detected_diseases:
                    draw_detection(frame, box, label, conf, source="disease")
                for raw, label, conf, _ in detected_diseases:
                    if now - last_disease_sent.get(raw, -1e9) >= args.disease_cooldown:
                        last_disease_sent[raw] = now
                        notify_disease(args.server, raw, conf)
                        ts = datetime.now().strftime("%H:%M:%S")
                        print(f"  [{ts}] PENYAKIT DAUN: {label} ({conf:.0%}) -> dashboard (tanpa buzzer)")

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
                        alarm_now = True
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
            elif detected_diseases:
                d_label = max(detected_diseases, key=lambda x: x[2])[1]
                status_text  = f"[!] PENYAKIT DAUN: {d_label} - cek tanaman (buzzer OFF)"
                status_color = (0, 140, 255)  # Oranye
            elif detected_humans:
                status_text  = f"[OK] PETANI / MANUSIA DI LOKASI ({len(detected_humans)} orang) - AMAN (Buzzer OFF)"
                status_color = (255, 200, 0)  # Cyan
            else:
                status_text  = "[OK] LAHAN AMAN - Tidak Ada Hama"  # putText tidak bisa gambar tanda pisah panjang
                status_color = (0, 200, 0)    # Hijau

            cv2.rectangle(frame, (0, 0), (frame.shape[1], 42), (20, 20, 20), -1)
            cv2.putText(frame, status_text, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_color, 2, cv2.LINE_AA)
            cv2.putText(frame, f"{fps_display:.1f} fps",
                        (frame.shape[1] - 95, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

            if args.record:
                if writer is None:
                    writer = cv2.VideoWriter(args.record, cv2.VideoWriter_fourcc(*"mp4v"),
                                             video_fps or 30.0, (frame.shape[1], frame.shape[0]))
                writer.write(frame)
                log_csv.writerow([frame_idx, round(now, 3),
                                  "|".join(p[0] for p in detected_pests), len(detected_humans),
                                  "|".join(d[0] for d in detected_diseases), int(alarm_now)])

            if not args.no_window:
                cv2.imshow("SIPETIK AI CAMERA - Deteksi Hama & Manusia [Q = Keluar]", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        stop_event.set()
        if remote_thread is not None:
            remote_thread.join(timeout=2)
        cap.release()
        if writer is not None:
            writer.release()
            print(f"  Rekaman tersimpan: {args.record}")
        if log_f is not None:
            log_f.close()
        cv2.destroyAllWindows()

    print()
    print("  Detector dihentikan.")


if __name__ == "__main__":
    main()

