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

## ⚠️ PENTING — domain gap dataset (kenapa deteksi bisa "gagal" padahal modelnya OK)

Dikonfirmasi lewat testing user + inspeksi langsung ke gambar training:
**semua 3.477 gambar dataset ini adalah foto serangga MATI di atas papan
perangkap lengket/light trap, dilihat dari atas, latar polos** — bukan
serangga hidup di tanaman padi. Model yang dilatih dari data ini bisa
sangat akurat untuk foto sejenis (mAP50 0.97/0.94, lihat hasil smoke-test
di bawah), tapi **tidak otomatis bisa mengenali wereng/walang sangit hidup
di kondisi lapangan** — background hijau daun, pose alami, sudut kamera
bebas, dsb — apalagi kalau yang ditunjukkan ke kamera adalah foto di layar
HP/laptop (nambah lapisan distorsi lagi: glare, moiré, kompresi ulang).

Kalau kamu tunjukkan foto/wereng ke `main.py` dan tidak terdeteksi sama
sekali, ini paling mungkin penyebabnya duluan sebelum dicurigai bug.
**Cara cek cepat tanpa kamera:**

```bash
python training/test_image.py foto_kamu.jpg --conf 0.1
```

Kalau di confidence serendah 0.1 saja tetap nol deteksi, itu konfirmasi
domain gap (bukan soal threshold) — solusinya di bagian "Kalau mau nambah
data sendiri" di bawah: model perlu dilatih ulang dengan foto sejenis
kondisi asli kamera kamu (wereng di daun, live, dari sudut kamera nyata),
bukan cuma menambah epoch atau menurunkan `--conf`.

---

## Cara pakai (dataset & training sudah diverifikasi jalan)

```bash
pip install -r training/requirements.txt
python training/download_datasets.py     # ~3.477 gambar, ambil ROBOFLOW_API_KEY dari .env
python training/train.py                 # default 100 epoch, ~ sesuaikan GPU kamu
copy training\runs\sipetik_pest\weights\best.pt pest_local.pt
python main.py
```

Sudah saya jalankan langsung (bukan cuma ditulis) sampai tahap training
1-epoch untuk pastikan pipeline-nya benar — hasilnya di bagian bawah.

Kalau muncul `CUDA out of memory`, kecilkan batch: `python training/train.py --batch 4`.

---

## Sumber data (diverifikasi langsung lewat Roboflow SDK)

**`csu-bpvmi/paddy-rice-insect-pest-dataset`, version 3** — satu-satunya
sumber yang dipakai untuk kedua kelas ini:

- 3.477 gambar (3.045 train / 289 valid / 143 test)
- 7 kelas asli: `black bug`, `brown plant hopper`, `green leaf hopper`,
  `rice bug`, `rice grasshopper`, `rice leaf roller`, `stem borer`
- Dipetakan (lihat `class_map` di `download_datasets.py`):
  - `brown plant hopper` → `wereng_coklat`
  - `rice bug` → `walang_sangit` (*"rice bug"* = nama Inggris untuk walang
    sangit, *Leptocorisa oratorius*)
- 5 kelas lain otomatis dibuang saat digabung (tidak relevan untuk 2 kelas ini)

Setelah digabung: **20.433 box** across train/valid/test untuk 2 kelas target.

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

## Hasil smoke-test (1 epoch, bukan model final)

Dijalankan langsung untuk pastikan pipeline-nya benar sebelum kamu training
penuh (100 epoch) — angka di bawah **bukan model final**, tapi menunjukkan
datanya sehat:

```
                Class   Images  Instances  Box(P    R    mAP50  mAP50-95)
                  all      289       1081  0.922  0.933  0.966  0.575
        wereng_coklat      250        500  0.911  1.000  0.995  0.672
        walang_sangit      289        581  0.933  0.867  0.936  0.479
```

Training penuh (100 epoch, ada early-stopping) akan jauh lebih baik lagi —
jalankan `python training/train.py` tanpa `--epochs` untuk itu.

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
