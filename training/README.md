# SIPETIK — Ekspansi Deteksi Hama (5 kelas)

Model `best.pt` yang sekarang dipakai `main.py` hanya dilatih untuk **1 kelas: tikus**
(`nc: 1, names: {0: 'rat'}` — dicek langsung dari isi file model).

> **Update:** cara tercepat untuk menambah cakupan deteksi ternyata bukan
> training lokal, tapi memanfaatkan model-model yang **sudah dilatih orang
> lain di Roboflow** lewat API hosted mereka. `main.py` sekarang punya mode
> hybrid: tikus tetap dideteksi lokal (cepat, offline) via `best.pt`, dan 4
> hama lain dipanggil lewat API Roboflow di background thread (aktif
> otomatis kalau `ROBOFLOW_API_KEY` diisi di `.env`). Ini **sudah aktif**,
> tidak perlu training apa pun. Sisa dokumen di bawah ini tetap relevan
> kalau suatu saat kamu mau melatih model lokal sendiri (mis. supaya bisa
> jalan tanpa internet, atau akurasi hosted model kurang bagus untuk kamera
> kamu).

Kelas target (dipakai baik oleh mode lokal maupun mode cloud):

| # | Kelas (slug)     | Nama Indonesia          |
|---|------------------|--------------------------|
| 0 | `rat`            | Tikus                    |
| 1 | `walang_sangit`  | Walang Sangit             |
| 2 | `wereng_coklat`  | Wereng Batang Coklat       |
| 3 | `ulat_grayak`    | Ulat Grayak                |
| 4 | `keong_mas`      | Keong Mas                  |

Slug ini **harus** konsisten di tiga tempat: `training/data.yaml`, model hasil
training, dan `animalLabel()` di
[app/Http/Controllers/Api/CameraController.php](../app/Http/Controllers/Api/CameraController.php)
(sudah disiapkan / sudah di-update).

---

## Mode cloud (aktif sekarang) — cara pakai & keterbatasannya

- Isi `ROBOFLOW_API_KEY` di `.env` (sudah ada kalau kamu ikuti setup awal).
- Jalankan seperti biasa: `python main.py`. Kalau key terdeteksi, terminal
  akan menampilkan `Cloud: AKTIF`.
- Box hasil deteksi cloud digambar warna **oranye** dengan label
  `(cloud)`, beda dari box lokal (hijau), supaya kelihatan sumbernya.
- Matikan dengan `--no-remote` kalau tidak ada internet atau mau hemat
  kuota API gratis Roboflow.
- Model/workflow yang dipakai (lihat `REMOTE_MODEL_IDS` &
  `ZERO_SHOT_WORKFLOW` di `main.py`):
  - `paddy-rice-insect-pest-dataset/3` (multi-hama padi, termasuk wereng)
  - `golden-apple-snail/2` (keong mas)
  - 1 workflow segmentasi open-vocabulary di workspace kamu sendiri, dicari
    2 kelas sekaligus lewat parameter `classes`: **walang sangit** dan
    **ulat grayak**. Workflow ini tidak perlu dibuat baru per hama — cukup
    tambahkan nama hama ke `classes_param`, jadi kalau nanti mau nambah
    kelas lain (belalang, hispa padi, penggerek batang — sudah kelihatan
    ada di kandidat dataset padi Indonesia yang saya temukan) tinggal
    ditambahkan ke situ (plus update `REMOTE_KEYWORD_MAP` &
    `CameraController::animalLabel()` biar konsisten).
  - ~~`detection-of-fall-armyworm-infestation-with-deep-learning/1`~~ —
    **dimatikan permanen**, diganti workflow di atas untuk ulat grayak.

**Keterbatasan yang sudah saya uji langsung (bukan asumsi):**
- Nama kelas yang dikembalikan tiap model **tidak seragam** (mis. model
  fall-armyworm mengembalikan `"FAW_Day1"`, `"FAW_Day3"`, dst — bukan
  `"armyworm"`), jadi `main.py` memetakan berdasar **kata kunci**
  (`REMOTE_KEYWORD_MAP`), bukan exact-match.
- Model fall-armyworm (dipakai sebelumnya buat ulat grayak) **tidak
  reliable untuk kamera webcam biasa** — dicoba dengan gambar noise acak
  sempat false-positive (confidence ~0.65), lalu dikonfirmasi lagi di
  kamera sungguhan: model ini salah mengenali **wajah orang** sebagai
  "ulat grayak" dengan confidence 0.6–0.75. Kelihatannya model itu dilatih
  khusus foto close-up daun yang sudah terserang, bukan untuk membedakan
  "ada hama" vs "bukan hama" di scene umum. Sudah diganti permanen dengan
  workflow open-vocabulary di atas — baru dites dengan gambar noise acak
  (bersih, tidak false-positive), **belum sempat dites langsung ke kamera
  dengan wajah orang** seperti kasus yang mengungkap masalah di model
  sebelumnya. Coba dulu di kamera kamu sendiri (arahkan ke wajah, ke
  ruangan kosong, dll — bukan cuma ke sawah) sebelum 100% mengandalkannya
  untuk trigger buzzer otomatis.
- Deteksi cloud butuh internet & tunduk pada limit kuota gratis akun
  Roboflow kamu; kalau kena limit/timeout, log `[WARN]` muncul di terminal
  tapi deteksi lokal (tikus) tetap jalan normal.
- **API key kamu jangan pernah ditaruh langsung di source code** yang
  masuk git — selalu lewat `.env` (sudah di-`.gitignore`). Kalau khawatir
  key sempat bocor, tinggal generate ulang di roboflow.com → Settings →
  API Keys, lalu update `.env`.

---

## 0. Kenapa deteksinya "limited" sebelumnya?

Karena model dilatih dari 1 dataset tikus saja. Ini bukan bug di `main.py` —
script itu sudah generic (otomatis pakai kelas apa pun yang ada di `.pt` yang
dipakai). Yang perlu diubah adalah **model-nya**, dengan data lebih banyak
kelas.

> Catatan tambahan yang saya temukan & sudah diperbaiki di komputer ini:
> `import ultralytics` sebelumnya selalu crash (`WinError 1337`) gara-gara bug
> Windows di folder `D:\WpSystem` (profil yang direlokasi ke drive D:).
> Sudah ada workaround di [`windows_git_fix.py`](../windows_git_fix.py) yang
> otomatis dipakai `main.py`, `animal_detector.py`, dan `training/train.py`.
> Kalau kamu training di komputer lain yang tidak kena bug ini, workaround
> tersebut tidak mengganggu apa pun (aman dibiarkan).

---

## 1. Siapkan data

Kamu jawab "belum ada data sama sekali", jadi langkah paling realistis adalah
**menggabungkan dataset publik** dari Roboflow Universe sebagai titik awal,
lalu (opsional, sangat direkomendasikan) menambah foto asli dari sawah kamu
supaya model lebih akurat di kondisi kamera & pencahayaan kamu sendiri.

### 1a. Dataset publik (titik awal)

Saya sudah cari kandidatnya, tapi **halaman Roboflow tidak bisa saya buka
langsung untuk verifikasi isi/lisensinya** (diblokir untuk scraping) — jadi
kamu perlu cek manual sebelum dipakai:

- Walang sangit: https://universe.roboflow.com/ramadhan/walang-sangit
  (dilaporkan ~600 gambar, kelas tunggal)
- Wereng batang coklat + hama padi lain (multi-kelas, termasuk "Brown
  Planthopper"): https://universe.roboflow.com/csu-bpvmi/paddy-rice-insect-pest-dataset
- Ulat grayak — pelengkap dari fall armyworm (spesies serumpun, *Spodoptera*):
  https://universe.roboflow.com/baltazar-mu/detection-of-fall-armyworm-infestation-with-deep-learning
- Keong mas: https://universe.roboflow.com/demape-brayle-q/golden-apple-snail

Cara pakai:

1. Daftar akun gratis di https://roboflow.com (gratis, cukup email).
2. Buka tiap link di atas → cek isi datasetnya masuk akal (foto jelas, label
   benar, jumlah cukup) → klik **Download this Dataset** → format **YOLOv8**
   → pilih **"show download code"** (jangan download zip manual).
3. Roboflow akan menampilkan kode Python seperti ini — salin nilai
   `workspace`, `project`, `version`, `api_key` ke
   [`download_datasets.py`](download_datasets.py) (variabel `DATASETS`):

   ```python
   from roboflow import Roboflow
   rf = Roboflow(api_key="XXXXXXXXXXXX")
   project = rf.workspace("ramadhan").project("walang-sangit")
   version = project.version(1)
   dataset = version.download("yolov8")
   ```

4. Cek juga tab **"Classes"** di tiap project untuk tahu nama kelas persis
   yang dipakai, sesuaikan `class_map` di `download_datasets.py` supaya
   memetakan ke salah satu dari 5 slug target di atas. Kelas yang tidak ada
   di `class_map` otomatis dibuang.

5. (Opsional) Data tikus yang sekarang dipakai `best.pt` berasal dari project
   Roboflow `rat-detection-6ezx2` (lihat `ROBOFLOW_MODEL_ID` di
   [`animal_detector.py`](../animal_detector.py)) — kalau mau digabung juga,
   tambahkan entrinya (ada template comment di `download_datasets.py`).

### 1b. Foto asli dari sawah kamu (opsional, sangat disarankan)

Dataset publik biasanya beda kondisi (angle kamera, pencahayaan, latar
belakang) dari kamera sawah kamu sendiri, jadi model bisa kurang akurat di
lapangan. Kalau sempat:

1. Ambil video/foto tiap hama pakai kamera yang sama dengan yang dipakai
   `main.py` nanti (webcam laptop / kamera lapangan), berbagai sudut & jarak.
2. Label pakai [Roboflow Annotate](https://roboflow.com) (upload gambar,
   gambar kotak, ekspor YOLOv8) — paling gampang, atau
   [LabelImg](https://github.com/heartexlabs/labelImg) kalau mau offline.
3. Taruh hasilnya (folder `images/` + `labels/` format YOLO) di
   `training/dataset/train/` (atau `valid/`) mengikuti struktur yang sama
   dengan hasil `download_datasets.py` — atau gabungkan manual sebelum
   training.

---

## 2. Install dependency training

```bash
pip install -r training/requirements.txt
```

---

## 3. Unduh & gabungkan dataset

Setelah `DATASETS` di `download_datasets.py` diisi & diverifikasi:

```bash
python training/download_datasets.py
```

Ini akan mengunduh tiap dataset, remap ke 5 kelas target SIPETIK, dan
menggabungkannya ke `training/dataset/{train,valid,test}/{images,labels}`.

---

## 4. Training

```bash
python training/train.py
```

GPU kamu (**GTX 1650, 4GB VRAM**) cukup untuk YOLOv8n dengan setting default
(`batch=8`, `imgsz=640`). Kalau muncul error `CUDA out of memory`, kecilkan:

```bash
python training/train.py --batch 4
```

Perkiraan waktu: tergantung jumlah total gambar gabungan, tapi untuk beberapa
ribu gambar biasanya beberapa jam di GTX 1650 (100 epoch, ada early-stopping
lewat `--patience` jadi bisa berhenti lebih cepat kalau sudah tidak membaik).
Progress bisa dipantau langsung di terminal, hasil ada di
`training/runs/sipetik_pest/`.

---

## 5. Pakai model barunya

```bash
copy best.pt best.rat-only.pt
copy training\runs\sipetik_pest\weights\best.pt best.pt
python main.py --model best.pt
```

Cek di jendela kamera: semua 5 kelas hama harusnya sudah kedeteksi. Label
Indonesia di dashboard SIPETIK otomatis muncul benar karena
`CameraController.php` sudah di-update untuk kelas-kelas ini.

---

## 6. Kalau hasil deteksi kurang akurat

- Tambah lebih banyak foto asli dari sawah kamu (langkah 1b) — ini biasanya
  paling berpengaruh, lebih dari sekadar nambah epoch.
- Naikkan `--epochs` atau coba model dasar lebih besar (`--base yolov8s.pt`).
- Turunkan `--conf` sedikit di `main.py` kalau model sering "ngeles" dari
  hama yang jelas ada, atau naikkan kalau terlalu banyak salah deteksi
  (false positive).
