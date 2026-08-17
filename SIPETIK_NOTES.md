# SIPETIK — Catatan Developer

Dokumen ini berisi referensi teknis yang tidak ditampilkan di dashboard/pengaturan.
Buka file ini di VSCode kapan pun dibutuhkan.

---

## 1. Menjalankan Server

Jalankan perintah berikut di **terminal terpisah** masing-masing:

```bash
# Terminal 1 — Laravel (bisa diakses dari jaringan lokal)
php artisan serve --host=0.0.0.0 --port=8000

# Terminal 2 — Vite (hot reload CSS/JS)
npm run dev

# Terminal 3 — Reverb (WebSocket realtime) — opsional
php artisan reverb:start
```

> **Catatan:** Jika Reverb tidak dijalankan, pastikan `.env` berisi:
> ```
> BROADCAST_CONNECTION=log
> ```
> agar server tidak hang saat ESP32 mengirim data.

---

## 2. Koneksi ESP32 via WiFi

**IP server (sesuaikan dengan IP komputer Anda):**
```
http://192.168.1.5:8000
```
Cek IP komputer dengan perintah `ipconfig` di Command Prompt, lihat "IPv4 Address".

**Endpoint utama:**
| Tujuan | URL |
|--------|-----|
| Kirim data sensor | `POST http://192.168.1.5:8000/api/sensor` |
| Cek data terbaru | `GET  http://192.168.1.5:8000/api/sensor/latest` |
| Poll perintah buzzer | `GET  http://192.168.1.5:8000/api/esp32/command` |
| Notifikasi kamera | `POST http://192.168.1.5:8000/api/camera/motion` |
| Heartbeat kamera | `GET  http://192.168.1.5:8000/api/camera/heartbeat` |

---

## 3. Payload JSON ke ESP32

```json
{
  "device_id": "esp32-sawah-01",
  "temperature": 29.4,
  "humidity": 82.1,
  "soil_raw": 1870,
  "motion": false,
  "ph": 6.4
}
```

**Sensor aktif:**
- `temperature` — DHT22, pin 14
- `humidity` — DHT22, pin 14
- `soil_raw` — ADC tanah, pin 34
- `motion` — PIR sensor, pin (sesuai sketch)
- `ph` — Sensor pH, pin 35

---

## 4. Contoh Kode ESP32 (Kirim Data)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* serverUrl = "http://192.168.1.5:8000/api/sensor";

void sendData(float temperature, float humidity, int soilRaw, bool motion, float ph) {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<256> doc;
  doc["device_id"]   = "esp32-sawah-01";
  doc["temperature"] = temperature;
  doc["humidity"]    = humidity;
  doc["soil_raw"]    = soilRaw;
  doc["motion"]      = motion;
  doc["ph"]          = ph;

  String body;
  serializeJson(doc, body);
  int statusCode = http.POST(body);
  http.end();
}
```

---

## 5. Kalibrasi Soil Raw (ADC)

Edit di `config/esp32.php`:

```php
'soil_raw_wet' => 1200,   // nilai ADC saat tanah basah
'soil_raw_dry' => 3200,   // nilai ADC saat tanah kering
```

Formula konversi ke persen:
```
moisture% = (dry - raw) / (dry - wet) × 100
```

---

## 6. Koneksi Kabel ESP32 (Serial/USB — tanpa WiFi)

```bash
php artisan esp32:serial-bridge [PORT] 115200
```

Ganti `[PORT]` dengan port yang terdeteksi di Device Manager, contoh:
- Windows: `COM14`
- Linux/Mac: `/dev/ttyUSB0`

---

## 7. Deteksi Binatang via Webcam (Python)

```bash
# Install dependensi
pip install -r camera_requirements.txt

# Jalankan detector
python animal_detector.py --server http://192.168.1.5:8000

# Opsi tambahan
python animal_detector.py --server http://192.168.1.5:8000 --camera 1 --confidence 0.6 --cooldown 15
```

**Parameter:**
| Flag | Default | Keterangan |
|------|---------|------------|
| `--server` | `http://192.168.1.5:8000` | URL server Laravel |
| `--camera` | `0` | Index kamera (0 = utama) |
| `--confidence` | `0.50` | Minimum confidence deteksi |
| `--cooldown` | `10` | Jeda antar trigger buzzer (detik) |

---

## 8. Logika Buzzer

| Kondisi | Aksi |
|---------|------|
| PIR aktif **+** Kamera deteksi binatang | Buzzer berbunyi 5 detik |
| Hanya PIR aktif | Tidak berbunyi |
| Hanya Kamera deteksi | Tidak berbunyi |
| Mode Manual ON (dari Pengaturan) | Buzzer ON terus sampai dimatikan |
| Mode Otomatis (interval dalam jam aktif) | Berbunyi sesuai jadwal |

---

## 9. Reset / Troubleshooting

```bash
# Bersihkan semua cache Laravel
php artisan optimize:clear

# Jalankan ulang semua migrasi (HATI-HATI: hapus semua data)
php artisan migrate:fresh

# Cek log error
tail -f storage/logs/laravel.log
```

**File penting:**
| File | Keterangan |
|------|------------|
| `.env` | Konfigurasi database, broadcast, timezone |
| `config/esp32.php` | Kalibrasi soil raw, IP sensor |
| `storage/app/buzzer_command.txt` | Antrian perintah buzzer ke ESP32 |
| `esp32_sipetik_dashboard.ino` | Sketch Arduino ESP32 |
| `animal_detector.py` | Script deteksi binatang Python |
| `camera_requirements.txt` | Dependensi Python |
