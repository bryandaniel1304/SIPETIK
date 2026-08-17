<x-mail::message>
# {{ $alertType === 'pest_high' ? '⚠️ Peringatan Risiko Hama Tinggi' : ($alertType === 'animal_detected' ? '🐾 Binatang Terdeteksi di Lahan' : '🔔 Notifikasi SIPETIK') }}

@if($alertType === 'pest_high')
Sistem SIPETIK mendeteksi kondisi lingkungan yang **berisiko tinggi** terhadap serangan hama di lahan Anda.

<x-mail::panel>
**Kondisi Saat Ini:**

🌡️ Suhu: {{ $data['temperature'] ?? '-' }} °C

💧 Kelembapan Udara: {{ $data['humidity'] ?? '-' }} %

🌱 Kelembapan Tanah: {{ $data['moisture'] ?? '-' }} %

⚗️ pH Tanah: {{ $data['ph'] ?? '-' }}

👁️ Gerakan PIR: {{ isset($data['motion']) ? ($data['motion'] ? 'Terdeteksi' : 'Tidak ada') : '-' }}

📊 Status Risiko: **{{ strtoupper($data['pest_status'] ?? 'TINGGI') }}**
</x-mail::panel>

**Tindakan yang disarankan:**

1. Segera lakukan pengecekan kondisi lahan
2. Periksa ada/tidaknya hama secara visual
3. Pertimbangkan tindakan pencegahan seperti pestisida atau perangkap

@elseif($alertType === 'animal_detected')
Sistem SIPETIK mendeteksi adanya **binatang di lahan** Anda. Sensor PIR dan kamera AI keduanya aktif.

<x-mail::panel>
**Detail Deteksi:**

🐾 Binatang: {{ $data['animal_label'] ?? $data['animal_class'] ?? 'Tidak diketahui' }}

📷 Confidence: {{ isset($data['confidence']) ? round($data['confidence'] * 100) . '%' : '-' }}

⏰ Waktu: {{ $data['detected_at'] ?? now()->format('d M Y, H:i:s') }} WIB

🔔 Buzzer: Aktif otomatis
</x-mail::panel>

**Tindakan yang disarankan:**

1. Periksa kondisi lahan dan pagar
2. Pastikan binatang tidak merusak tanaman
3. Pertimbangkan pemasangan penghalang tambahan

@else
Ini adalah email percobaan dari sistem SIPETIK. Jika Anda menerima email ini, berarti notifikasi email **berfungsi dengan baik**. ✅
@endif

---

<x-mail::button :url="url('/app/hama-alerts')" color="green">
Lihat Dashboard SIPETIK
</x-mail::button>

Notifikasi ini dikirim otomatis oleh sistem SIPETIK Smart Farm.
Waktu pengiriman: {{ now()->timezone('Asia/Jakarta')->format('d M Y, H:i:s') }} WIB

Thanks,<br>
**SIPETIK Smart Farm**
</x-mail::message>
