# SIPETIK — Model Lokal untuk Wereng Batang Coklat + Walang Sangit

Status deteksi 5 hama SIPETIK sekarang:

| # | Hama | Sumber | Status |
|---|------|--------|--------|
| 0 | Tikus | Lokal — `best.pt` | Sudah jalan (model asli project) |
| 1 | Wereng batang coklat | Lokal — `pest_local.pt` | **Baru**, dilatih dari data ini |
| 2 | Walang sangit | Lokal — `pest_local.pt` | **Baru**, dilatih dari data ini |
| 3 | Ulat grayak | Cloud — Roboflow workflow | Belum ada dataset lokal yang layak |
| 4 | Keong mas | Cloud — Roboflow model | Belum ada dataset lokal yang layak |

Kenapa ulat grayak & keong mas belum bisa lokal — sudah dicek langsung lewat
Roboflow SDK (bukan tebakan), lihat bagian **"Kenapa cuma 2 kelas"** di bawah.

`main.py` otomatis pakai `pest_local.pt` kalau file itu ada di root project
(jalan berdampingan dengan `best.pt`, tidak menggantikannya — lihat header
docstring `main.py`).

---

## ⚠️ Riwayat domain gap dataset (sudah ditangani, tapi baca ini dulu)

**Masalah yang ditemukan (v1):** dataset awal (`csu-bpvmi`) isinya foto
serangga MATI di papan perangkap, latar polos, dilihat dari atas. User tes
tunjukkan foto wereng di layar HP ke `main.py` → **tidak terdeteksi sama
sekali**. Dicek pakai `training/test_image.py --conf 0.1`: tetap nol —
konfirmasi model belum pernah lihat konteks itu, bukan soal threshold.

**Perbaikan (v2 — kondisi sekarang):** ditambahkan dataset kedua
(`data-science-project/common-rice-pests-philippines`, 5.229 gambar) yang
berisi foto natural serangga di tanaman padi (sudah dicek visual langsung,
bukan cuma baca deskripsi). Setelah digabung & training ulang (3 epoch
smoke-test):

- Sebelumnya: foto natural wereng → **0 deteksi**, foto dari user →
  **box nyasar** (bukan di serangganya, cuma noise confidence 30%)
- Sekarang: foto natural wereng & walang sangit (belum pernah dilihat model)
  → **box tepat di serangganya**, confidence 26–41% (lihat hasil lengkap di
  bagian "Hasil smoke-test" di bawah)

Confidence-nya masih rendah karena baru 3 epoch (bukan training penuh) —
kalau kamu jalankan `python training/train.py` sampai selesai (100 epoch,
early-stopping otomatis), confidence-nya akan naik jauh lebih baik lagi.

**Cara cek cepat tanpa kamera** (masih berlaku, sekarang buat validasi
model baru):

```bash
python training/test_image.py foto_kamu.jpg --conf 0.1
```

Kalau masih nol di confidence serendah ini, kemungkinan foto kamu beda
konteks lagi (mis. sudut/spesies yang belum ada di kedua dataset) — tambah
foto sejenis itu sendiri (lihat bagian "Kalau mau nambah data sendiri").

---

## Cara pakai (dataset & training sudah diverifikasi jalan)

```bash
pip install -r training/requirements.txt
python training/download_datasets.py     # ~8.700 gambar (2 dataset), ambil ROBOFLOW_API_KEY dari .env
python training/train.py                 # default 100 epoch, ~ sesuaikan GPU kamu
copy training\runs\sipetik_pest\weights\best.pt pest_local.pt
python main.py
```

### Kalau training harus dihentikan di tengah jalan (laptop mau dimatikan, dll)

Ultralytics otomatis simpan checkpoint (`last.pt`) tiap epoch selesai —
**tidak perlu mulai dari epoch 0 lagi**. Tapi cara berhentinya penting:

- **Aman:** tekan `Ctrl+C` sekali di terminal yang menjalankan `train.py`
  saat SEDANG di tengah training, atau tutup laptop wajar (sleep/hibernate) —
  proses akan selesaikan penulisan checkpoint yang sedang berjalan dulu.
- **Hindari:** mematikan paksa (shutdown/cabut daya) tepat saat checkpoint
  lagi ditulis — file `last.pt` bisa korup separuh jalan. Kalau harus
  mematikan di jam tertentu, hentikan trainingnya (`Ctrl+C`) beberapa menit
  *sebelum* jam itu, jangan mepet — 1 epoch di sini butuh ~5 menit, kasih
  jeda aman.

Untuk lanjut lagi kapan saja (laptop baru dinyalakan lagi, dll):

```bash
python training/train.py --resume
```

Ini otomatis baca `training/runs/sipetik_pest/weights/last.pt` dan
melanjutkan dari epoch terakhir yang tersimpan (bukan restart dari 0),
termasuk sisa target epoch & early-stopping counter-nya.

Sudah saya jalankan langsung (bukan cuma ditulis) sampai tahap training
beneran (smoke-test 1 & 3 epoch) untuk pastikan pipeline-nya benar dan
hasilnya nyata membaik ke foto natural — hasilnya di bagian bawah.

Kalau muncul `CUDA out of memory`, kecilkan batch: `python training/train.py --batch 4`.

---

## Sumber data (diverifikasi langsung lewat Roboflow SDK, 2 dataset digabung)

**1. `csu-bpvmi/paddy-rice-insect-pest-dataset`, version 3** — gaya TRAP:

- 3.477 gambar (3.045 train / 289 valid / 143 test)
- 7 kelas asli: `black bug`, `brown plant hopper`, `green leaf hopper`,
  `rice bug`, `rice grasshopper`, `rice leaf roller`, `stem borer`
- `brown plant hopper` → `wereng_coklat`, `rice bug` → `walang_sangit`
  (*"rice bug"* = nama Inggris untuk walang sangit, *Leptocorisa oratorius*)

**2. `data-science-project/common-rice-pests-philippines`, version 11** —
campuran foto NATURAL di tanaman + sebagian spesimen latar putih (dicek
visual langsung):

- 5.229 gambar (4.178 train / 546 valid / 505 test)
- 6 kelas asli: `brown-planthopper`, `green-leafhopper`, `leaf-folder`,
  `rice-bug`, `stem-borer`, `whorl-maggot`
- `brown-planthopper` → `wereng_coklat`, `rice-bug` → `walang_sangit`
- Sebagian anotasinya polygon (bukan box biasa) — ultralytics otomatis
  convert ke bounding box saat training, sudah dites jalan normal

Kelas lain di kedua dataset otomatis dibuang saat digabung (tidak relevan
untuk 2 kelas target). Setelah digabung: **train 7.223 gambar** (3.045 +
4.178), total 22.812 box target di seluruh split (train+valid+test).

### Kenapa cuma 2 kelas (bukan 5)?

Sempat dicoba cari sumber untuk kelas lain juga, hasil pengecekan langsung
(pakai `project.versions()` di Roboflow SDK, bukan cuma baca deskripsi):

| Kandidat | Hasil cek |
|---|---|
| `ramadhan/walang-sangit` (dataset khusus) | Ada 640 gambar berlabel, tapi **belum ada "version" yang di-publish** (`versions: []`) → tidak bisa didownload lewat API sampai pemiliknya generate version |
| `sam-yu-gultom/citra-tanaman-padi-2` / `-3` (ada kelas persis "ulat grayak") | Sama — `versions: []`, tidak bisa didownload |
| `demape-brayle-q/golden-apple-snail` | Bisa didownload, tapi cuma **15 label**, itu pun cuma telur (`GAS-eggs`), bukan keong dewasa — terlalu sedikit untuk training layak |

Jadi ulat grayak & keong mas untuk sementara tetap lewat cloud (lihat
`ZERO_SHOT_WORKFLOW` & `REMOTE_MODEL_IDS` di `main.py`). Kalau nanti salah
satu dataset di atas sudah di-publish version-nya oleh pemiliknya, atau kamu
foto sendiri (lihat bagian bawah), tinggal tambahkan ke `DATASETS` di
`download_datasets.py` dan gabungkan ke `training/data.yaml`.

Tikus (`best.pt`) juga sengaja tidak disentuh — sumber data aslinya
(`rat-detection-6ezx2` di `animal_detector.py`) workspace-nya tidak
ditemukan lagi, dan modelnya sudah jalan baik, jadi tidak perlu diutak-atik.

---

## Hasil smoke-test (bukan model final — training penuh akan lebih baik)

**v1 — cuma dataset trap (1 epoch):**

```
                Class   Images  Instances  Box(P    R    mAP50  mAP50-95)
                  all      289       1081  0.922  0.933  0.966  0.575
        wereng_coklat      250        500  0.911  1.000  0.995  0.672
        walang_sangit      289        581  0.933  0.867  0.936  0.479
```

Angka mAP50 tinggi, tapi cuma diuji ke gambar trap-style yang mirip
training. Waktu dicoba ke foto natural sungguhan → nol deteksi (lihat
riwayat domain gap di atas).

**v2 — trap + natural digabung (3 epoch):**

```
                Class   Images  Instances  Box(P    R    mAP50  mAP50-95)
                  all      835       1381  0.948  0.878  0.940  0.577
        wereng_coklat      329        669  0.968  0.825  0.925  0.619
        walang_sangit      388        712  0.928  0.930  0.954  0.535
```

mAP50 turun sedikit (0.94 vs 0.97) — **ini wajar dan bagus**, karena
validation set-nya sekarang campuran trap+natural yang jauh lebih sulit,
bukan cuma trap yang gampang. Dites langsung ke foto natural yang belum
pernah dilihat model (bukan bagian training): box-nya sekarang **tepat di
serangganya** dengan spesies benar, confidence 26–41% — dibanding v1 yang
sama sekali nol. Confidence masih akan naik banyak dengan training penuh
(100 epoch vs baru 3 di sini).

Training penuh (100 epoch, ada early-stopping) akan jauh lebih baik lagi —
jalankan `python training/train.py` tanpa `--epochs` untuk itu, lalu
validasi lagi pakai `training/test_image.py` ke foto kondisi kamera kamu
sendiri.

---

## Bug lingkungan yang ditemukan & sudah diperbaiki

- **`ultralytics` crash saat di-import** di komputer ini (`WinError 1337`),
  gara-gara folder profil `AppData\Local\Packages` di-redirect ke
  `D:\WpSystem\...` yang security descriptor-nya rusak. Workaround di
  [`windows_git_fix.py`](../windows_git_fix.py), dipakai di `main.py`,
  `animal_detector.py`, `train.py`, **dan `download_datasets.py`** (paket
  `roboflow` ternyata juga import `ultralytics` secara internal, kena bug
  yang sama pas proses akhir download).
- **`ultralytics` resolve path dataset relatif ke folder `datasets_dir`
  GLOBAL** (`C:\Users\<user>\AppData\Roaming\Ultralytics\settings.json`),
  bukan ke lokasi `data.yaml` itu sendiri — di komputer ini settingnya
  nyasar ke project lain sama sekali (`C:\xampp\htdocs\laravel\...`).
  `train.py` sekarang generate `training/_data.resolved.yaml` (path
  absolut, di-gitignore) saat runtime supaya tidak bergantung ke setting
  global itu.
- `model.train(..., exist_ok=True)` — supaya training ulang selalu menimpa
  `training/runs/sipetik_pest/` yang sama, bukan numpuk jadi
  `sipetik_pest-2`, `-3`, dst tiap kali dijalankan ulang.

---

## Kalau mau nambah data sendiri (rekomendasi jangka panjang)

Dataset publik di atas kondisinya beda dari kamera sawah kamu (angle,
pencahayaan, latar). Untuk akurasi terbaik, terutama buat ulat grayak &
keong mas yang belum ada data lokal sama sekali:

1. Ambil foto/video tiap hama pakai kamera yang sama dengan yang dipakai
   `main.py` nanti, berbagai sudut & jarak.
2. Label pakai [Roboflow Annotate](https://roboflow.com) (upload, gambar
   kotak, ekspor YOLOv8) atau [LabelImg](https://github.com/heartexlabs/labelImg)
   kalau mau offline.
3. Taruh hasilnya (folder `images/` + `labels/` format YOLO) di
   `training/dataset/train/` (atau `valid/`) mengikuti struktur yang sama
   dengan hasil `download_datasets.py`, atau tambahkan sebagai entri baru
   di `DATASETS` kalau datanya juga di-publish ke Roboflow.
4. Update `training/data.yaml` (tambah kelas baru) dan
   `CameraController::animalLabel()` di PHP supaya label Indonesia-nya ikut
   muncul di dashboard.


---

# v3 — Satu model untuk 10 hama + data "bukan hama" (Oktober 2026, RTX 5070)

## Masalah yang diperbaiki

`best.pt` (tikus) dan `pest_v2.pt` (9 serangga) dilatih **tanpa satu pun
gambar latar kosong** — model tidak pernah diajari "ini bukan hama". Diukur
langsung pakai `training/eval_false_positives.py` (logika filter `main.py`
diimport apa adanya: deteksi orang, buang hama yang menempel di badan orang,
filter ukuran, conf 0.55), pada gambar yang **tidak pernah dipakai training**:

| Gambar tanpa hama (disisihkan) | Lama: `best.pt` + `pest_v2.pt` | Baru: `pest_v3.pt` |
|---|---|---|
| 2.700 foto sehari-hari COCO (orang, wajah, tangan, ruangan, hewan rumah) | **338 alarm palsu (12,5%)** — 173 di antaranya "tikus" dari `best.pt` | **10 (0,4%)** |
| 3.988 foto daun padi berpenyakit | **491 alarm palsu (12,3%)** | **44 (1,1%)** |

Deteksi hama sungguhan (test set, gambar yang lolos filter ukuran `--min-area 0.01`
di `main.py`) tetap terjaga: keong mas 63→87 dari 89, tikus 5→7 dari 25,
walang sangit 227/233, belalang 143/143, kelas lain ±2 gambar. Hasil lengkap:
`training/benchmarks/false_positives.json`.

Catatan jujur: tikus masih lemah (7/25) karena data tikus publik yang layak
cuma ~320 gambar. Rekam video tikus dari kamera sawah sendiri, label, lalu
tambahkan — itu peningkatan terbesar berikutnya. Serangga sangat kecil
(mis. kepinding hitam di papan perangkap, semua box < 1% frame) memang
dibuang oleh filter `--min-area` di `main.py`, baik model lama maupun baru.

## Dataset v3 (`training/build_dataset_v3.py`)

| Isi | Jumlah gambar train | Sumber |
|---|---|---|
| 9 serangga (dataset_v2, tetap) | 9.921 | lihat bagian v2 di atas |
| Tikus sawah (kelas baru, id 9) | 319 | `padjadjaran-xrbt3/tikus` v1, `kmutnb-n38mm/rat-gambf` v1, `object-detection-sccsb/biawak-tikus-ular_jumlahsama` v3 (hanya gambar tikus) |
| Keong mas **dewasa** (digabung ke id 2) | 498 | `egash/e-gash` v1 |
| **Negatif**: orang, wajah, tangan, ruangan, kucing, anjing | 2.000 | COCO val2017 |
| **Negatif**: daun padi berpenyakit (bercak coklat mirip wereng) | 1.000 | `utopialab/rice-leaf-wfax3` v2 |

Total train 13.738 gambar (22% negatif). Disisihkan untuk evaluasi saja
(tidak pernah ikut training): 2.700 COCO + 3.988 daun padi di
`~/sipetik/eval_negatives/`. Semua sumber lisensi CC BY 4.0 / Public Domain.

Dataset yang **sudah dicek dan sengaja ditolak** (alasannya tercatat di
`SOURCES` dalam `build_dataset_v3.py` supaya tidak ditambahkan lagi):
kemasan pakan & kartun dilabel "rat", 966 gambar tikus tanpa label, crop
thermal satu-box-penuh, tikus lab dicat, label ulat grayak tidak konsisten,
papan perangkap kuning dengan wereng hijau vs zigzag yang tidak bisa
dibedakan.

## Cara menjalankan

```bash
python training/build_dataset_v3.py --v2 "%USERPROFILE%\sipetik\dataset_v2"
python training/train_v3.py                  # ~64 menit di RTX 5070
copy "%USERPROFILE%\sipetik\runs\sipetik_pest_v3\weights\best.pt" pest_v3.pt
python training/eval_false_positives.py      # lama vs baru
python main.py                               # otomatis pakai pest_v3.pt
```

Dataset & training sengaja di SSD internal (`%USERPROFILE%\sipetik\`),
bukan di `G:` — `G:` adalah HDD USB exFAT. Run v2 yang sama persis butuh
~800 dtk/epoch dari `G:` vs ~88 dtk/epoch dari SSD.

`main.py` sekarang memuat `pest_v3.pt` sebagai model utama dan **tidak lagi
memuat `best.pt`** (tikus sudah ada di v3). Pakai `--keep-rat-model` kalau
ingin tetap menyalakan model tikus lama.

## GTX 1650 vs RTX 5070

Lihat `training/benchmarks/` dan laporan. Untuk perbandingan apel-ke-apel,
colok drive `G:` ke laptop lama lalu jalankan script yang sama di sana:

```bash
python training/benchmark_gpu.py --trt
```

Hasilnya tersimpan sebagai `training/benchmarks/<nama-gpu>.json` di
sebelah hasil RTX 5070.


---

# Tracking, penyakit daun, tiling & dataset v4 (Oktober 2026)

Semua logika per frame kamera sekarang ada di `main.PestDetector` (hama)
dan `main.DiseaseDetector` (penyakit). Skrip evaluasi mengimport kelas
yang sama, jadi angka di bawah = perilaku kamera sungguhan.

## 1. Tracking (`--confirm-frames`, bawaan 3)

Hama (dan burung) baru dihitung kalau objek dengan ID track yang sama
(ByteTrack) terlihat di 3 inferensi berturut-turut dengan conf ≥ 0,55.
`--confirm-frames 1` = perilaku lama. Diukur dengan `training/eval_video.py`:

| Konfigurasi | Alarm buzzer di video demo tanpa hama (54 dtk) | Klip hama yang membunyikan alarm |
|---|---|---|
| Lama (`best.pt` + `pest_v2.pt`) | 4 | – |
| v3 tanpa tracking | 1 | 224 / 258 |
| **v3 + tracking** | **0** | 223 / 258 |
| v3 + tracking + tiling 2×2 | 2 | 239 / 258 |

Klip hama = foto test dijadikan klip 1 detik dengan gerakan kamera
sintetis. Harga tracking: alarm di frame ke-3, bukan ke-1 (~0,1 dtk).
Tracking menyaring "kedipan", tapi TIDAK menyaring salah deteksi yang
menetap pada objek diam (lihat tiling di bawah).

## 2. Penyakit daun padi (`disease_v1.pt`, model terpisah)

6 kelas: blas daun, hawar daun bakteri, bercak coklat, bercak coklat
sempit, hangus daun, gosong daun. Dicek tiap 2 detik, dilaporkan kalau
terlihat di 2 pengecekan berturut-turut. **Tidak membunyikan buzzer**:
`main.py` mengirim ke `POST /api/camera/disease`, dashboard menampilkan
baris oranye di kartu "Deteksi Kamera AI". `--no-disease` untuk mematikan.

```bash
python training/build_disease_dataset.py   # utopialab + evccc, dedup dHash
python training/train_disease.py           # YOLO11n, ~1,8 jam di RTX 5070
copy "%USERPROFILE%\sipetik\runs\sipetik_disease_v1\weights\best.pt" disease_v1.pt
python training/eval_disease.py
```

Data: 12.602 gambar sumber → 10.811 unik. `utopialab` ternyata berisi
banyak duplikat (5.188 gambar, 3.699 unik; 290 kembar tersebar di
train & test) dan `project-khcjh` adalah salinannya — gambar kembar
dikelompokkan supaya tidak ada yang muncul di train dan test sekaligus.

Hasil (`training/benchmarks/disease_eval.json`):

| | |
|---|---|
| mAP50 di split **test** | 0,499 (blas 0,53 · hawar bakteri 0,47 · bercak coklat 0,46 · bercak sempit 0,30 · hangus 0,74) |
| Peringatan palsu, 2.700 foto COCO | 2 (0,1%) |
| Peringatan palsu, 838 foto hama di tanaman | 38 (4,5%) — batas atas: sebagian foto itu mungkin memang berpenyakit tapi tidak dilabel |
| Peringatan palsu, video demo | 0 dari 28 pengecekan |

Batasan jujur: label dataset publiknya longgar (ada box yang menutup
seluruh daun atau latar kosong), jadi mAP rendah sebagian karena label.
Model dilatih dari foto close-up daun — paling berguna kalau kamera dekat
ke daun. Gosong daun cuma punya beberapa contoh. Anggap sebagai
peringatan awal, bukan diagnosis.

## 3. Tiling (`--tiles 2`, opsional)

Frame utuh + 4 potongan (2×2, tumpang tindih 20%) dalam satu batch GPU,
digabung dengan NMS per kelas; `--min-area` otomatis turun ke 0,2%.
Paling berguna dengan kamera resolusi tinggi: `--width 1920 --tiles 2`.
Diukur dengan `training/eval_false_positives.py` (foto, tanpa tracking):

| | v3 biasa | v3 + tiling 2×2 |
|---|---|---|
| Foto test yang hamanya terdeteksi | 812 / 1.652 (49,2%) | **1.435 / 1.652 (86,9%)** |
| Wereng coklat | 15 / 157 | 153 / 157 |
| Kepinding hitam | 0 / 143 | 143 / 143 |
| Alarm palsu, foto sehari-hari COCO | 39 / 2.700 (1,4%)* | 140 / 2.700 (5,2%) |
| Alarm palsu, daun berpenyakit | 47 / 3.988 (1,2%) | 346 / 3.988 (8,7%) |

\* 30 di antaranya burung asli di foto COCO (SIPETIK memang menganggap
burung hama).

Karena alarm palsunya naik, tiling **tidak** dinyalakan bawaan. Di video
demo, tiling membuat **malai padi kuning-oranye** dikenali sebagai wereng
coklat — tracking tidak bisa menyaringnya karena objeknya diam. Itu
alasan dataset v4.

## 4. Dataset v4 + YOLO11s

- **Malai padi** (`ewuricedataset/rice-panicle-uyxgj` v5, 2.628 foto
  lapangan) ditambahkan sebagai negatif: 1.000 train, 200 valid, 1.428
  disisihkan di `eval_negatives/panicle/`.
- **Perbaikan label**: ultralytics membuang SELURUH gambar yang labelnya
  mencampur poligon & kotak ("labels mix segment and detection rows") —
  59 gambar di v3 dan 51 di dataset penyakit hilang diam-diam. Builder
  sekarang mengubah semua poligon jadi kotak (`as_box`); v4 memakai
  14.738/14.738 gambar train.
- Model: YOLO11s (9,4 jt parameter vs 3,0 jt YOLOv8n), batch 16
  (batch 32 melebihi 8 GB VRAM dan jatuh ke RAM sistem: 10 dtk/batch).

```bash
python training/build_dataset_v3.py --v2 "%USERPROFILE%\sipetik\dataset_v2" --out "%USERPROFILE%\sipetik\dataset_v4"
python training/train_v3.py --base yolo11s.pt --name sipetik_pest_v4_11s --epochs 60 --batch 16 --data "%USERPROFILE%\sipetik\dataset_v4\data_v3.yaml"
```

Training ~4,5 jam lebih lama dari batas tugas latar belakang, jadi
jalankan di terminal biasa (bukan dari tool yang punya batas waktu).

### Hasil v4 (YOLO11s) vs v3 — data uji yang sama persis

Training 60 epoch = 4,1 jam di RTX 5070. mAP50 validasi 0,975 (v3: 0,972).
Diukur dengan `eval_false_positives.py` dan `eval_video.py` (conf 0,55):

| | v3 | **v4** | v3 + tiling | **v4 + tiling** |
|---|---|---|---|---|
| Alarm palsu hama, 2.700 foto COCO† | 9 | **0** | 110 | 68 |
| Alarm palsu, 3.988 daun berpenyakit | 47 (1,2%) | **10 (0,2%)** | 346 (8,7%) | 252 (6,3%) |
| Alarm palsu, 1.428 foto malai padi | 0 | 0 | 1 | 0 |
| Foto test yang hamanya terdeteksi | 812 (49,2%) | 814 (49,3%) | 1.435 (86,9%) | 1.438 (87,0%) |
| Video demo: alarm buzzer (dengan tracking) | 0 | 0 | 2 | 1 |
| Klip hama yang membunyikan alarm | 223 / 258 | 224 / 258 | 239 / 258 | 244 / 258 |

† Tanpa 30 burung asli di foto COCO (burung memang dianggap hama).

Kecepatan per frame (`benchmark_gpu.py`, kamera 640×480): YOLO11s 12,8 ms
di PyTorch (v3: 8,4 ms) — pipeline lengkap ~20 ms ≈ 49 FPS, masih di atas
30 FPS webcam. Dengan `--trt` sama cepat dengan v3: ~3,5 ms per model.

`main.py` sekarang memakai `pest_v4.pt` bawaan (cadangan: `pest_v3.pt`).
Tiling tetap opsional: dengan v4 alarm palsunya turun ~30% tapi masih
1 alarm di video demo (malai padi plastik dari samping — data malai v4
diambil dari atas). Rekam video sawah/miniatur sendiri tanpa hama dan
jadikan negatif kalau ingin menyalakan tiling permanen.



---

# Uji dengan foto hama di layar HP (Oktober 2026)

Kasus: user menunjukkan foto wereng di layar HP ke webcam; kamera
menampilkan "Petani / AMAN". Dianalisis dari rekaman layar user
(1.230 frame berisi wereng di HP, diputar ulang lewat `PestDetector`).

## Penyebab & perbaikan

1. **Detektor orang terlalu longgar (0,35)** — wereng di HP ikut dianggap
   "orang" (0,29–0,49). Sekarang `--human-conf 0.5`.
2. **Filter "hama di badan orang dibuang"** (dibuat untuk `best.pt` lama)
   membuang wereng di HP yang dipegang di depan badan. Untuk pest_v4
   filter ini dimatikan (`--human-filter` untuk menyalakan; otomatis aktif
   kalau `best.pt` lama dipakai). Diukur: 0 alarm palsu di 2.700 foto
   orang/ruangan dengan maupun tanpa filter.
3. **Serangga di layar HP hanya ~50×100 piksel di 640×480** — model melihat
   wereng di 16% frame saja. Tiling (`--tiles 2`, zoom 2×) menaikkan
   deteksi ~4×.

| Rekaman user (1.230 frame wereng di HP), dengan tracking | frame terdeteksi |
|---|---|
| Sebelumnya (orang 0,35 + filter) | ~66 |
| pest_v4, orang 0,5, filter mati | 123 (10%) |
| **pest_v4 + `--tiles 2`** | **482 (39%)**, 593 box wereng coklat, 12 kelas salah |

Biaya tiling (foto diam, tanpa tracking): alarm palsu di foto sehari-hari
0 → 79 dari 2.700 (30 di antaranya "tikus" pada kucing/anjing/beruang),
daun berpenyakit 7 → 251 dari 3.988; video demo dengan tracking: 0 → 1
alarm. Karena itu tiling **tidak** bawaan — pakai untuk uji dengan HP atau
untuk serangga kecil. `--animal-filter` membuang "tikus" di atas hewan
yang dikenali COCO (−18 alarm palsu) tapi juga 7 dari 18 tikus asli,
jadi bawaan mati.

## Percobaan v5 (data sintetis "hama di layar HP") — tidak dipakai

`training/build_phone_dataset.py` membuat 5.689 komposit hama di layar HP
(bingkai, UI, silau, moiré, jari, perspektif, latar orang COCO) + 2.500 HP
tanpa hama; v5 = fine-tune pest_v4 20 epoch (2 jam). Di set uji HP
sintetis mAP50 naik 0,053 → 0,848, **tapi di rekaman nyata user lebih buruk
dari v4** (18 vs 123 frame; dengan tiling sering mengira wereng sebagai
walang sangit). Data sintetis tidak mewakili kamera asli dengan cukup baik.
Bobot disimpan di `%USERPROFILE%\sipetik\runs\sipetik_pest_v5_phone\`.
Langkah berikutnya yang benar: rekam video webcam asli (`--record`) saat
menunjukkan berbagai foto hama, label, dan latih dengan data itu.

```bash
python training/eval_phone.py --pest pest_v4.pt --rec "rekaman.mp4"
```
