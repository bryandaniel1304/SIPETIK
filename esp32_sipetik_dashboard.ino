// ================================================================
//  SIPETIK Smart Farm Monitor v3.0 — WiFi Mode
//  ESP32 Firmware
//
//  LCD 20x4 | DHT22 | Soil | pH | Buzzer
//  pH → estimasi dari kelembapan tanah (sementara)
//
//  Data → POST /api/sensor setiap 1 detik
//  Perintah ← GET  /api/esp32/command setiap 2 detik
// ================================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "DHT.h"

// ================================================================
//  KONFIGURASI — sesuaikan sebelum upload
// ================================================================
const char* WIFI_SSID   = "Hapeku";
const char* WIFI_PASS   = "113333555555";

const char* SERVER_BASE = "http://10.153.9.142:8000";
const char* DEVICE_ID   = "esp32-sipetik-01";

// ================================================================
//  PIN
// ================================================================
#define SOIL_PIN    34   // Sensor kelembapan tanah (ADC input)
#define DHT_PIN     14   // Sensor suhu & kelembapan udara
#define PH_PIN      33   // Sensor pH
#define BUZZER_PIN  25   // Buzzer (active HIGH)

#define DHTTYPE     DHT22

// ================================================================
//  KALIBRASI SENSOR TANAH
//  1. Celup sensor ke air → catat Raw → SOIL_WET
//  2. Angkat ke udara     → catat Raw → SOIL_DRY
// ================================================================
#define SOIL_WET    3100   // ADC saat sensor di air (basah 100%)
#define SOIL_DRY    3800   // ADC saat sensor di udara (kering 0%)

// ================================================================
//  pH SENSOR — nilai default tanpa kalibrasi (teoritis 25°C)
//  Asam (pH<7) → tegangan naik → ADC tinggi
//  Basa (pH>7) → tegangan turun → ADC rendah
// ================================================================
#define PH_VREF    3.3f    // Tegangan referensi ADC ESP32
#define PH_NEUT_V  2.5f    // Tegangan saat pH = 7.0 (teoritis)
#define PH_SLOPE   0.18f   // Volt per unit pH (Nernst 25°C)

// ================================================================
//  TIMING (ms)
// ================================================================
#define INTERVAL_SAMPLE  1000
#define INTERVAL_SEND    1000
#define INTERVAL_CMD     2000
#define INTERVAL_DHT     2100
#define INTERVAL_WIFI   30000

// ================================================================
//  HARDWARE
// ================================================================
LiquidCrystal_I2C lcd(0x27, 20, 4);
DHT               dht(DHT_PIN, DHTTYPE);

// ================================================================
//  URL API
// ================================================================
String URL_SENSOR;
String URL_COMMAND;

// ================================================================
//  VARIABEL SENSOR
// ================================================================
int   soilRaw = 0;
float soilPct = 0.0f;
float phVal   = 7.0f;
float tempVal = NAN;
float humVal  = NAN;

// ================================================================
//  VARIABEL BUZZER
// ================================================================
bool          buzzerOn    = false;
unsigned long buzzerOffAt = 0;

// ================================================================
//  TIMER
// ================================================================
unsigned long msSample = 0;
unsigned long msSend   = 0;
unsigned long msCmd    = 0;
unsigned long msDht    = 0;
unsigned long msWifi   = 0;

// ================================================================
//  ADC — rata-rata 5 sampel
// ================================================================
int readADC(uint8_t pin) {
    long sum = 0;
    for (int i = 0; i < 5; i++) {
        sum += analogRead(pin);
        delay(2);
    }
    return (int)(sum / 5);
}

// ================================================================
//  SOIL → PERSEN
// ================================================================
float calcSoilPct(int raw) {
    float pct = 100.0f * float(SOIL_DRY - raw) / float(SOIL_DRY - SOIL_WET);
    if (pct < 0.0f)   pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;
    return pct;
}

// ================================================================
//  ADC → pH (tanpa kalibrasi, langsung baca sensor)
//  Asam → tegangan tinggi → pH < 7
//  Basa → tegangan rendah → pH > 7
// ================================================================
float calcPh(int raw) {
    if (raw < 10) return 7.0f;
    float v  = raw * PH_VREF / 4095.0f;
    float ph = 7.0f + (PH_NEUT_V - v) / PH_SLOPE;
    if (ph < 0.0f)  ph = 0.0f;
    if (ph > 14.0f) ph = 14.0f;
    return roundf(ph * 10.0f) / 10.0f;
}

// ================================================================
//  KONTROL BUZZER
// ================================================================
void setBuzzer(bool state, unsigned long durationMs = 0) {
    buzzerOn = state;
    digitalWrite(BUZZER_PIN, state ? HIGH : LOW);
    buzzerOffAt = (state && durationMs > 0) ? millis() + durationMs : 0;
}

void updateBuzzer(unsigned long now) {
    if (buzzerOn && buzzerOffAt > 0 && now >= buzzerOffAt) {
        setBuzzer(false);
    }
}

// ================================================================
//  EKSEKUSI PERINTAH DARI SERVER
// ================================================================
void executeCommand(const String& cmd, int duration) {
    if (cmd == "BUZZER:ON") {
        setBuzzer(true);
        Serial.println("[CMD] Buzzer ON (manual)");
    } else if (cmd == "BUZZER:OFF") {
        setBuzzer(false);
        Serial.println("[CMD] Buzzer OFF");
    } else if (cmd == "BUZZER:TRIGGER") {
        setBuzzer(true, (unsigned long)duration * 1000UL);
        Serial.printf("[CMD] Buzzer TRIGGER %d detik\n", duration);
    }
}

// ================================================================
//  BACA SEMUA SENSOR
// ================================================================
void bacaSensor(unsigned long now) {
    // Tanah
    soilRaw = readADC(SOIL_PIN);
    soilPct = calcSoilPct(soilRaw);

    // pH — baca dari sensor analog, simpan hanya jika nilai masuk akal (3.5–10.0)
    // Nilai di luar rentang ini biasanya berarti pin floating / sensor tidak tersambung
    float phRead = calcPh(readADC(PH_PIN));
    if (phRead >= 3.5f && phRead <= 10.0f) {
        phVal = phRead;
    }
    // Jika tidak valid, phVal tetap pakai nilai terakhir yang valid (default 7.0)

    // DHT22 — baca setiap 2.1 detik
    if (now - msDht >= INTERVAL_DHT) {
        msDht = now;
        float t = dht.readTemperature();
        float h = dht.readHumidity();
        if (!isnan(t) && t > -40.0f && t < 80.0f)   tempVal = t;
        if (!isnan(h) && h >=   0.0f && h <= 100.0f) humVal  = h;
    }
}

// ================================================================
//  UPDATE LCD 20x4
//
//  Baris 0:  Soil: 66%    pH: 6.4
//  Baris 1:  Suhu: 27.5C Hum:  68%
//  Baris 2:  Raw ADC: 1870
//  Baris 3:  WiFi:ON   Buz:OFF
// ================================================================
void updateLcd() {
    char buf[21];

    lcd.setCursor(0, 0);
    snprintf(buf, sizeof(buf), "Soil:%3d%%    pH:%4.1f",
             (int)roundf(soilPct), phVal);
    lcd.print(buf);

    lcd.setCursor(0, 1);
    if (!isnan(tempVal) && !isnan(humVal)) {
        snprintf(buf, sizeof(buf), "Suhu:%5.1fC Hum:%3d%%",
                 tempVal, (int)roundf(humVal));
    } else if (!isnan(tempVal)) {
        snprintf(buf, sizeof(buf), "Suhu:%5.1fC Hum: -- ", tempVal);
    } else {
        snprintf(buf, sizeof(buf), "Suhu: --.-C Hum: -- ");
    }
    lcd.print(buf);

    lcd.setCursor(0, 2);
    snprintf(buf, sizeof(buf), "Raw ADC: %-6d      ", soilRaw);
    lcd.print(buf);

    lcd.setCursor(0, 3);
    snprintf(buf, sizeof(buf), "WiFi:%-3s   Buz:%-3s   ",
             (WiFi.status() == WL_CONNECTED ? "ON" : "OFF"),
             buzzerOn ? "ON" : "OFF");
    lcd.print(buf);
}

// ================================================================
//  KIRIM DATA SENSOR KE DASHBOARD
// ================================================================
void kirimData() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[SEND] WiFi tidak terhubung, skip.");
        return;
    }

    float sendTemp  = isnan(tempVal) ? 0.0f : roundf(tempVal * 10.0f) / 10.0f;
    float sendHum   = isnan(humVal)  ? 0.0f : roundf(humVal  * 10.0f) / 10.0f;
    float sendPh    =                         roundf(phVal    * 10.0f) / 10.0f;
    float sendMoist =                         roundf(soilPct  * 10.0f) / 10.0f;

    StaticJsonDocument<512> doc;
    doc["device_id"]   = DEVICE_ID;
    doc["temperature"] = sendTemp;
    doc["humidity"]    = sendHum;
    doc["moisture"]    = sendMoist;  // persentase kelembapan, dihitung ESP32
    doc["soil_raw"]    = soilRaw;    // nilai mentah ADC sensor
    doc["motion"]      = false;
    doc["ph"]          = sendPh;

    JsonObject meta        = doc.createNestedObject("metadata");
    meta["buzzer_on"]      = buzzerOn;
    meta["wifi_connected"] = true;

    String body;
    serializeJson(doc, body);

    HTTPClient http;
    http.begin(URL_SENSOR);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(2000);

    int code = http.POST(body);
    if (code > 0) {
        Serial.printf("[SEND] OK %d | Soil:%.1f%% Tmp:%.1f pH:%.1f Buz:%s\n",
                      code, soilPct, sendTemp, sendPh, buzzerOn ? "ON" : "OFF");
    } else {
        Serial.printf("[SEND] Gagal: %s\n", http.errorToString(code).c_str());
    }
    http.end();
}

// ================================================================
//  CEK PERINTAH DARI SERVER
// ================================================================
void cekPerintah() {
    if (WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    http.begin(URL_COMMAND);
    http.setTimeout(1500);

    int code = http.GET();
    if (code == 200) {
        String resp = http.getString();
        StaticJsonDocument<256> doc;
        if (deserializeJson(doc, resp) == DeserializationError::Ok) {
            const char* cmd = doc["command"];
            if (cmd && strlen(cmd) > 0) {
                int dur = doc["duration"] | 3;
                executeCommand(String(cmd), dur);
            }
        }
    }
    http.end();
}

// ================================================================
//  KONEKSI WIFI
// ================================================================
void connectWifi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.printf("[WiFi] Menghubungkan ke %s...\n", WIFI_SSID);
    lcd.clear();
    lcd.setCursor(0, 0); lcd.print("Menghubungkan WiFi");
    lcd.setCursor(0, 1); lcd.print(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    unsigned long t = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t < 15000) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WiFi] Terhubung! IP ESP32: %s\n",
                      WiFi.localIP().toString().c_str());
        lcd.clear();
        lcd.setCursor(0, 0); lcd.print("WiFi Terhubung!");
        lcd.setCursor(0, 1); lcd.print(WiFi.localIP());
        delay(2000);
    } else {
        Serial.println("[WiFi] Gagal. Cek SSID/password.");
        lcd.clear();
        lcd.setCursor(0, 0); lcd.print("WiFi Gagal!");
        lcd.setCursor(0, 1); lcd.print("Cek SSID/Password");
        delay(1500);
    }
    lcd.clear();
}

// ================================================================
//  SETUP
// ================================================================
void setup() {
    Serial.begin(115200);
    analogReadResolution(12);
    delay(100);

    Serial.println();
    Serial.println("=====================================");
    Serial.println("  SIPETIK Smart Farm v3.0 — WiFi");
    Serial.println("  pH: estimasi dari kelembapan tanah");
    Serial.println("=====================================");

    URL_SENSOR  = String(SERVER_BASE) + "/api/sensor";
    URL_COMMAND = String(SERVER_BASE) + "/api/esp32/command";
    Serial.println("[URL] Sensor : " + URL_SENSOR);
    Serial.println("[URL] Command: " + URL_COMMAND);

    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);   // buzzer OFF

    lcd.init();
    lcd.backlight();
    lcd.clear();
    lcd.setCursor(0, 0); lcd.print("SIPETIK v3.0");
    lcd.setCursor(0, 1); lcd.print("Smart Farm WiFi");
    lcd.setCursor(0, 2); lcd.print("Inisialisasi...");

    dht.begin();
    delay(2000);

    connectWifi();

    unsigned long now = millis();
    bacaSensor(now);
    updateLcd();

    Serial.println("[OK] Monitoring aktif.");
    Serial.println("=====================================");
}

// ================================================================
//  LOOP UTAMA
// ================================================================
void loop() {
    unsigned long now = millis();

    if (now - msSample >= INTERVAL_SAMPLE) {
        msSample = now;
        bacaSensor(now);
        updateBuzzer(now);
        updateLcd();
    }

    if (now - msSend >= INTERVAL_SEND) {
        kirimData();
        msSend = millis();
    }

    if (now - msCmd >= INTERVAL_CMD) {
        cekPerintah();
        msCmd = millis();
    }

    if (WiFi.status() != WL_CONNECTED && now - msWifi >= INTERVAL_WIFI) {
        msWifi = now;
        connectWifi();
    }

    delay(10);
}