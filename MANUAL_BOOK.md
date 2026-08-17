# MANUAL BOOK
# SIPETIK — Smart Integrated Pest and Environment Tracking for Intelligent Krop-field
### Sistem Monitoring Sawah Cerdas Berbasis IoT dan AI

---

## DAFTAR ISI

1. [Pendahuluan](#1-pendahuluan)
2. [Persyaratan Sistem](#2-persyaratan-sistem)
3. [Cara Menjalankan Sistem](#3-cara-menjalankan-sistem)
4. [Halaman Dasbor](#4-halaman-dasbor)
5. [Halaman Data Sensor](#5-halaman-data-sensor)
6. [Halaman Peringatan Hama](#6-halaman-peringatan-hama)
7. [Halaman Pengaturan](#7-halaman-pengaturan)
8. [Kamera Deteksi AI](#8-kamera-deteksi-ai)
9. [Notifikasi Email](#9-notifikasi-email)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. PENDAHULUAN

SIPETIK adalah sistem monitoring sawah cerdas yang memadukan teknologi **IoT (ESP32)**, **Kecerdasan Buatan (YOLOv8)**, dan **dashboard berbasis web (Laravel)** untuk membantu petani memantau kondisi lahan secara real-time.

### Fitur Utama
| Fitur | Keterangan |
|---|---|
| Monitoring Sensor | Suhu, kelembapan udara, kelembapan tanah, pH, gerakan PIR |
| Deteksi Hama AI | Kamera mendeteksi binatang dan hama secara real-time |
| Buzzer Otomatis | ESP32 berbunyi saat hama atau binatang terdeteksi |
| Notifikasi Email | Email dikirim otomatis saat risiko hama tinggi |
| Dashboard Web | Pantau semua data dari browser PC maupun HP |
| Riwayat Data | Semua data tersimpan di database MySQL |

### Komponen Sistem
```
[Sensor ESP32] ──── WiFi ────▶ [Server Laravel] ◀──── [Kamera AI (Python)]
                                      │
                              [Dashboard Web]
                              [Database MySQL]
```

---

## 2. PERSYARATAN SISTEM

### Hardware
| Komponen | Spesifikasi |
|---|---|
| ESP32 | ESP32 Dev Module |
| Sensor Suhu/Kelembapan | DHT22 |
| Sensor Kelembapan Tanah | Kapasitif (pin 34) |
| Sensor pH | Analog pH Module (pin 35) |
| Sensor Gerak | PIR Sensor |
| Buzzer | Active Buzzer (pin 25) |
| LCD | LCD 20x4 I2C (alamat 0x27) |
| Kamera | Webcam (bawaan laptop atau eksternal) |

### Software
| Software | Keterangan |
|---|---|
| XAMPP | PHP + MySQL + Apache |
| Laravel 11 | Framework web backend |
| Python 3.11+ | Untuk kamera deteksi AI |
| Arduino IDE | Upload sketch ke ESP32 |
| Browser | Chrome / Firefox / Edge |

### Library Python
```
pip install ultralytics opencv-python requests
```

---

## 3. CARA MENJALANKAN SISTEM

### 3.1 Menjalankan Server Laravel

1. Buka terminal di folder project SIPETIK:
   ```
   cd c:\xampp\htdocs\laravel\studiopengembangansistem
   ```

2. Jalankan server Laravel:
   ```
   php artisan serve --host=0.0.0.0 --port=8000
   ```

3. Buka browser dan akses:
   ```
   http://localhost:8000
   ```

> **Catatan:** Gunakan `--host=0.0.0.0` agar bisa diakses dari HP atau ESP32 di jaringan yang sama.

### 3.2 Menjalankan ESP32

1. Buka file `esp32_sipetik_dashboard.ino` di Arduino IDE
2. Sesuaikan konfigurasi:
   ```cpp
   const char* WIFI_SSID   = "Nama WiFi kamu";
   const char* WIFI_PASS   = "Password WiFi";
   const char* SERVER_BASE = "http://IP_LAPTOP:8000";
   const char* DEVICE_ID   = "esp32-sipetik-01";
   ```
3. Upload sketch ke ESP32
4. Buka Serial Monitor (115200 baud) untuk cek koneksi

> **Cara cari IP laptop:** Buka CMD → ketik `ipconfig` → lihat IPv4 Address

### 3.3 Menjalankan Kamera AI

1. Pastikan model `best.pt` ada di folder project
2. Jalankan di terminal:
   ```
   python main.py --model best.pt --conf 0.50 --min-area 0.005 --max-area 0.70 --camera 0 --server http://IP_LAPTOP:8000
   ```
3. Jendela kamera akan terbuka
4. Tekan **Q** untuk menghentikan

### 3.4 Urutan Menjalankan yang Benar
```
1. Jalankan XAMPP (MySQL harus aktif)
2. Jalankan php artisan serve
3. Upload sketch ke ESP32 (ESP32 otomatis kirim data)
4. Jalankan python main.py (opsional, untuk deteksi kamera)
```

---

## 4. HALAMAN DASBOR

Dasbor adalah halaman utama yang menampilkan kondisi sawah secara real-time.

### 4.1 Kartu Sensor (8 Kartu)

| Kartu | Fungsi |
|---|---|
| Kelembapan Tanah | Persentase kadar air tanah (0–100%) |
| Suhu | Temperatur lingkungan (°C) |
| Kelembapan Udara | Kadar uap air udara (%) |
| Risiko Hama | Tingkat risiko hama keseluruhan |
| pH Tanah | Keasaman tanah (0–14) |
| Deteksi Gerakan (PIR) | Status sensor gerak inframerah |
| Soil Raw ADC | Nilai mentah ADC sensor tanah |
| Deteksi Kamera AI | Status deteksi kamera real-time |

> **Tips:** Arahkan kursor ke kartu (hover) untuk melihat penjelasan sensor dan arti setiap status. Di HP, tap kartu untuk membalik ke penjelasan.

### 4.2 Indikator Status

| Warna/Label | Arti |
|---|---|
| 🟢 Normal / Aman | Kondisi ideal |
| 🔵 Rendah | Di bawah rentang normal |
| 🟠 Tinggi / Perlu Penyesuaian | Di atas rentang normal |
| 🟣 Ideal | Khusus pH (6.0–7.0) |
| 🔴 TERDETEKSI | Ada gerakan atau binatang terdeteksi |

### 4.3 Koneksi ESP32
Banner di bagian atas menampilkan:
- **Online** (hijau): ESP32 aktif mengirim data
- **Menunggu data** (oranye): Belum ada data masuk dari ESP32

### 4.4 AI Analisis & Rekomendasi
Bagian bawah dasbor menampilkan analisis otomatis berdasarkan kondisi sensor dan rekomendasi tindakan yang perlu dilakukan.

### 4.5 Tanya SIPETIK (Chatbot)
Klik tombol hijau di pojok kanan bawah untuk membuka chatbot AI. Hover tombol untuk melihat info API yang digunakan.

---

## 5. HALAMAN DATA SENSOR

Menampilkan riwayat seluruh data yang telah dikirim ESP32.

### 5.1 Cara Mengakses
Klik menu **Data Sensor** di sidebar kiri.

### 5.2 Kolom Tabel
| Kolom | Keterangan |
|---|---|
| Waktu | Tanggal dan jam pengiriman data |
| Suhu (°C) | Nilai suhu saat itu |
| Tanah (%) | Kelembapan tanah saat itu |
| Udara (%) | Kelembapan udara saat itu |
| pH | Nilai pH tanah |
| Gerakan | Status PIR (AMAN / TERDETEKSI) |
| Status Hama | Rendah / Sedang / Tinggi |
| ID | Nomor urut data |

### 5.3 Filter Data
- **Status Hama**: Filter berdasarkan Rendah / Sedang / Tinggi
- **Dari Tanggal / Sampai Tanggal**: Filter rentang waktu
- **Pencarian**: Cari berdasarkan nilai atau status tertentu
- **Reset**: Hapus semua filter
- **Ekspor**: Download data sebagai file

---

## 6. HALAMAN PERINGATAN HAMA

Menampilkan riwayat kejadian dengan status hama khusus untuk pemantauan risiko.

### 6.1 Cara Mengakses
Klik menu **Peringatan Hama** di sidebar kiri.

### 6.2 Filter Status
| Tombol | Fungsi |
|---|---|
| Semua | Tampilkan semua data |
| Risiko Tinggi | Filter data dengan status Tinggi |
| Waspada | Filter data dengan status Sedang |
| Aman | Filter data dengan status Rendah |

### 6.3 Arti Status Hama
| Status | Kondisi |
|---|---|
| **Aman (Rendah)** | Semua kondisi sensor normal |
| **Waspada (Sedang)** | Ada kondisi sensor di luar normal |
| **Risiko Tinggi** | Kamera + PIR aktif bersamaan, atau kondisi lingkungan sangat buruk |

---

## 7. HALAMAN PENGATURAN

### 7.1 Cara Mengakses
Klik ikon **Pengaturan** di sidebar kiri atau klik nama profil.

### 7.2 Pengaturan Buzzer

#### Override OFF
Tombol darurat untuk mematikan buzzer secara paksa.
- **Aktifkan Override**: Buzzer dikunci mati, tidak bisa menyala dari sumber manapun
- **Nonaktifkan Override**: Buzzer kembali normal

#### Mode Manual
- Tombol **Nyala** (hijau): Buzzer menyala sampai dimatikan manual
- Tombol **Mati** (merah): Buzzer dimatikan

#### Mode Otomatis
- **Aktifkan/Nonaktifkan**: Toggle buzzer otomatis
- **Jam aktif**: Buzzer hanya aktif dalam rentang jam yang ditentukan
- **Interval**: Seberapa sering buzzer berbunyi otomatis
- **Durasi bunyi**: Berapa lama buzzer berbunyi setiap trigger
- **Aktifkan saat risiko tinggi**: Buzzer ikut berbunyi saat status hama Tinggi

> **Catatan:** Buzzer juga menyala otomatis saat **kamera mendeteksi binatang**, terlepas dari mode yang dipilih (kecuali Override aktif).

### 7.3 Notifikasi Email
- **Notifikasi Email**: Toggle untuk aktifkan/nonaktifkan email otomatis
- **Kirim Email Percobaan**: Test apakah email berfungsi
- Email dikirim ke akun yang digunakan untuk login SIPETIK

---

## 8. KAMERA DETEKSI AI

### 8.1 Cara Menjalankan
```
python main.py --model best.pt --conf 0.50 --min-area 0.005 --max-area 0.70 --camera 0 --server http://IP_LAPTOP:8000
```

### 8.2 Parameter yang Bisa Disesuaikan
| Parameter | Default | Keterangan |
|---|---|---|
| `--model` | best.pt | File model YOLOv8 |
| `--conf` | 0.65 | Threshold kepercayaan deteksi (0.0–1.0) |
| `--min-area` | 0.01 | Ukuran minimum objek (fraksi frame) |
| `--max-area` | 0.70 | Ukuran maksimum objek |
| `--camera` | 0 | Index kamera (0 = kamera utama) |
| `--server` | localhost:8000 | URL server Laravel |
| `--cooldown` | 10 | Jeda antar trigger buzzer (detik) |

### 8.3 Tips Penggunaan
- **Confidence terlalu tinggi (>0.85)**: Banyak hama tidak terdeteksi
- **Confidence terlalu rendah (<0.40)**: Banyak false positive (salah deteksi)
- Nilai **0.50–0.65** direkomendasikan untuk kondisi normal
- Tekan **Q** di jendela kamera untuk menghentikan

### 8.4 Status Kamera di Dashboard
| Status | Arti |
|---|---|
| Kamera Aktif (hijau) | Script Python berjalan normal |
| Kamera Offline (abu) | Script Python tidak berjalan |
| Binatang Terdeteksi (merah) | Ada objek terdeteksi, buzzer aktif |

---

## 9. NOTIFIKASI EMAIL

### 9.1 Cara Mengaktifkan
1. Buka **Pengaturan** → bagian **Notifikasi Email**
2. Toggle **Notifikasi Email** ke posisi aktif
3. Klik **Kirim Email Percobaan** untuk test

### 9.2 Kapan Email Dikirim
| Kondisi | Email |
|---|---|
| Status hama berubah ke **Tinggi** | Email peringatan hama |
| Kamera mendeteksi **binatang** | Email deteksi binatang |
| Manual klik **Kirim Email Percobaan** | Email uji coba |

### 9.3 Konfigurasi SMTP
Edit file `.env` di folder project:
```
MAIL_MAILER=smtp
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=email@gmail.com
MAIL_PASSWORD=app_password_gmail
MAIL_FROM_ADDRESS=email@gmail.com
```
> Gunakan **App Password** Gmail (bukan password Gmail biasa).
> Aktifkan di: Google Account → Security → 2-Step Verification → App Passwords

---

## 10. TROUBLESHOOTING

### ESP32 tidak terkoneksi
| Masalah | Solusi |
|---|---|
| WiFi tidak tersambung | Cek SSID dan password di sketch |
| Data tidak masuk dashboard | Cek IP laptop di `SERVER_BASE` sketch |
| LCD tidak menyala | Cek alamat I2C (default 0x27) |

### Dashboard tidak bisa diakses dari HP
1. Pastikan HP dan laptop di WiFi/hotspot yang sama
2. Jalankan `php artisan serve --host=0.0.0.0 --port=8000`
3. Cek firewall: `netsh advfirewall firewall add rule name="Laravel 8000" dir=in action=allow protocol=TCP localport=8000`

### Kamera tidak terdeteksi
```
python main.py --camera 1  # coba index 1
```

### Email tidak terkirim
1. Pastikan App Password Gmail sudah dibuat
2. Cek konfigurasi `.env`
3. Jalankan: `php artisan optimize:clear`

### Buzzer tidak berhenti
1. Buka **Pengaturan** → klik **Aktifkan Override**
2. Buzzer akan berhenti paksa

### Data sensor tidak berubah
- Cek koneksi WiFi ESP32 (lihat LCD baris 4)
- Pastikan `php artisan serve` masih berjalan
- Cek Serial Monitor Arduino IDE (115200 baud)

---

## INFORMASI SISTEM

| Item | Detail |
|---|---|
| Framework | Laravel 11 |
| Database | MySQL (via XAMPP) |
| AI Model | YOLOv8n (Ultralytics) |
| Mikrokontroler | ESP32 Dev Module |
| Bahasa | PHP, Python, JavaScript |
| Versi SIPETIK | v3.0 |

---

*Manual Book SIPETIK — Smart Integrated Pest and Environment Tracking for Intelligent Krop-field*
