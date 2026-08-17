@extends('layouts.app')

@section('title', 'Dasbor')
@section('page-title', 'Dasbor')
@section('breadcrumb', 'Beranda / Dasbor')

@section('content')
<div style="margin-bottom: 20px;">
    <p style="color: #666; margin: 0 0 5px;">Selamat datang di Dasbor SIPETIK</p>
    <p style="color: #999; font-size: 14px;">Pantau kondisi sawah Anda di sini.</p>
</div>

<div id="esp32-connection-card" style="margin-bottom: 20px; padding: 14px 16px; border-radius: 12px; background: {{ $isDeviceOnline ? '#e8f5e9' : '#fff3e0' }}; color: {{ $isDeviceOnline ? '#2e7d32' : '#ef6c00' }}; display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
    <div>
        <div style="font-size: 12px; text-transform: uppercase; letter-spacing: .4px; opacity: .85;">Koneksi ESP32</div>
        <div id="esp32-connection-label" style="font-size: 16px; font-weight: 700;">{{ $deviceId }} - {{ $isDeviceOnline ? 'Online' : 'Menunggu data' }}</div>
    </div>
    <div style="font-size: 13px; align-self: center;">Update terakhir: <span id="esp32-last-seen">{{ $lastSeen }}</span></div>
</div>

<style>
.card-flip-wrapper { perspective: 1200px; height: 215px; }
.card-front.metric-card { padding-top: 22px; padding-bottom: 22px; }
.card-inner {
    position: relative; width: 100%; height: 100%;
    transition: transform 0.55s cubic-bezier(.4,0,.2,1);
    transform-style: preserve-3d; cursor: default;
}
@media (hover: hover) {
    .card-flip-wrapper:hover .card-inner { transform: rotateY(180deg); }
}
.card-flip-wrapper.flipped .card-inner { transform: rotateY(180deg); }
.card-front, .card-back {
    position: absolute; inset: 0;
    backface-visibility: hidden; -webkit-backface-visibility: hidden;
    border-radius: 12px;
}
.card-front.metric-card { min-height: unset; }
.card-back {
    transform: rotateY(180deg);
    background: #1e293b; color: #e2e8f0;
    padding: 18px 16px; display: flex;
    flex-direction: column; justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18);
}
.card-back .back-title {
    font-size: 13px; font-weight: 700; color: #fff;
    margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}
.card-back .back-body {
    font-size: 11.5px; color: #94a3b8; line-height: 1.7;
}
.card-back .back-body b { color: #e2e8f0; }
.card-tap-hint {
    position: absolute; bottom: 8px; right: 10px;
    font-size: 10px; color: #64748b; pointer-events: none;
}
@media (hover: hover) { .card-tap-hint { display: none; } }
</style>

<div class="row mb-4">
    {{-- Kelembapan Tanah --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front">
                    <div class="icon" style="color: #4caf50;"><i class="fas fa-tint"></i></div>
                    <div class="label">Kelembapan Tanah</div>
                    <div class="value" id="val-moisture">{{ $latest ? round($latest->moisture) : '-' }}{{ $latest ? '%' : '' }}</div>
                    <span id="badge-moisture" class="status-badge" style="background: {{ $moistureStatus['bg'] }}; color: {{ $moistureStatus['color'] }};">{{ $moistureStatus['label'] }}</span>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-tint" style="color:#4caf50;"></i> Kelembapan Tanah</div>
                    <div class="back-body">
                        Mengukur kadar air di tanah untuk menentukan kapan lahan perlu disiram.<br>
                        🟢 <b>Normal</b>: 30–70%<br>
                        🔵 <b>Rendah</b>: &lt;30% — perlu disiram<br>
                        🟠 <b>Tinggi</b>: &gt;70% — terlalu basah
                    </div>
                </div>
            </div>
        </div>
    </div>
    {{-- Suhu --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front">
                    <div class="icon" style="color: #ff6b35;"><i class="fas fa-temperature-high"></i></div>
                    <div class="label">Suhu</div>
                    <div class="value" id="val-temperature">{{ $latest ? round($latest->temperature) : '-' }}{{ $latest ? ' °C' : '' }}</div>
                    <span id="badge-temperature" class="status-badge" style="background: {{ $tempStatusBackground }}; color: {{ $tempStatusColor }};">{{ $tempStatus }}</span>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-temperature-high" style="color:#ff6b35;"></i> Suhu</div>
                    <div class="back-body">
                        Mengukur temperatur lingkungan. Membantu memantau stres panas atau kondisi terlalu dingin.<br>
                        🟢 <b>Normal</b>: 20–30°C<br>
                        🔵 <b>Rendah</b>: &lt;20°C — terlalu dingin<br>
                        🟠 <b>Tinggi</b>: &gt;30°C — stres panas
                    </div>
                </div>
            </div>
        </div>
    </div>
    {{-- Kelembapan Udara --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front">
                    <div class="icon" style="color: #00bcd4;"><i class="fas fa-wind"></i></div>
                    <div class="label">Kelembapan Udara</div>
                    <div class="value" id="val-humidity">{{ $latest && !is_null($latest->humidity) ? round($latest->humidity) : '-' }}{{ $latest && !is_null($latest->humidity) ? '%' : '' }}</div>
                    <span id="badge-humidity" class="status-badge" style="background: {{ $humidityStatus['bg'] }}; color: {{ $humidityStatus['color'] }};">{{ $humidityStatus['label'] }}</span>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-wind" style="color:#00bcd4;"></i> Kelembapan Udara</div>
                    <div class="back-body">
                        Mengukur kadar uap air di udara. Berguna untuk membaca risiko jamur dan penyakit tanaman.<br>
                        🟢 <b>Normal</b>: 30–70%<br>
                        🔵 <b>Rendah</b>: &lt;30% — udara kering<br>
                        🟠 <b>Tinggi</b>: &gt;70% — risiko jamur
                    </div>
                </div>
            </div>
        </div>
    </div>
    {{-- Risiko Hama --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card alert-card card-front">
                    <div class="icon" style="color: rgba(255,255,255,0.9);"><i class="fas fa-shield-virus"></i></div>
                    <div class="label">RISIKO HAMA</div>
                    <div class="value" id="val-risk">{{ strtoupper($ai['risk'] ?? 'RENDAH') }}</div>
                    <div id="val-risk-sub" style="font-size: 12px; color: rgba(255,255,255,0.75); margin-top: 4px;">{{ $deviceId }} - {{ $lastSeen }}</div>
                    <span class="card-tap-hint" style="color:rgba(255,255,255,0.4);">Tap untuk info</span>
                </div>
                <div class="card-back" style="background: linear-gradient(135deg,#7f1d1d,#991b1b);">
                    <div class="back-title"><i class="fas fa-shield-virus" style="color:#fca5a5;"></i> Risiko Hama</div>
                    <div class="back-body">
                        Tingkat risiko berdasarkan kondisi semua sensor secara bersamaan.<br>
                        🟢 <b>Rendah</b>: kondisi aman<br>
                        🟡 <b>Sedang</b>: waspada, perlu pantauan<br>
                        🔴 <b>Tinggi</b>: segera ambil tindakan
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row mb-4">
    {{-- pH Tanah --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front">
                    <div class="icon" style="color: #8e44ad;"><i class="fas fa-flask"></i></div>
                    <div class="label">pH Tanah</div>
                    <div class="value" id="val-ph">{{ is_null($dummyPh) ? '-' : number_format($dummyPh, 1) }}</div>
                    <span id="badge-ph" class="status-badge" style="background: {{ $phStatus['bg'] }}; color: {{ $phStatus['color'] }};">{{ $phStatus['label'] }}</span>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-flask" style="color:#c084fc;"></i> pH Tanah</div>
                    <div class="back-body">
                        Mengukur keasaman tanah (0–14). Memengaruhi penyerapan unsur hara tanaman.<br>
                        🟣 <b>Ideal</b>: 6.0–7.0<br>
                        🟠 <b>Perlu Penyesuaian</b>: di luar rentang<br>
                        ↑ Terlalu asam → tambah kapur<br>
                        ↓ Terlalu basa → tambah belerang
                    </div>
                </div>
            </div>
        </div>
    </div>
    {{-- Deteksi Gerakan --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front">
                    <div class="icon" style="color: #e67e22;"><i class="fas fa-person-walking"></i></div>
                    <div class="label">Deteksi Gerakan (PIR)</div>
                    <div class="value" id="val-motion">{{ $motionStatus['value'] }}</div>
                    <span id="badge-motion" class="status-badge" style="background: {{ $motionStatus['bg'] }}; color: {{ $motionStatus['color'] }};">{{ $motionStatus['label'] }}</span>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-person-walking" style="color:#fb923c;"></i> Deteksi Gerakan</div>
                    <div class="back-body">
                        Sensor gerak inframerah pasif. Mendeteksi aktivitas di area sekitar perangkat.<br>
                        🟢 <b>AMAN</b>: tidak ada aktivitas<br>
                        🔴 <b>TERDETEKSI</b>: ada gerakan di area sensor
                    </div>
                </div>
            </div>
        </div>
    </div>
    {{-- Soil Raw ADC --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front">
                    <div class="icon" style="color: #2c3e50;"><i class="fas fa-microchip"></i></div>
                    <div class="label">Soil (Raw ADC)</div>
                    <div class="value" id="val-soil-raw">{{ is_null($dummySoilRaw) ? '-' : number_format($dummySoilRaw) }}</div>
                    <span id="badge-soil-raw" class="status-badge" style="background: {{ $soilRawStatus['bg'] }}; color: {{ $soilRawStatus['color'] }};">{{ $soilRawStatus['label'] }}</span>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-microchip" style="color:#94a3b8;"></i> Soil Raw ADC</div>
                    <div class="back-body">
                        Nilai mentah (0–4095) sensor kapasitif tanah sebelum dikonversi ke persen.<br>
                        ⬛ <b>~3750–3800</b>: tanah kering<br>
                        🟫 <b>~3100–3200</b>: tanah lembap<br>
                        Semakin <b>turun</b> = semakin <b>basah</b>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {{-- Kamera AI --}}
    <div class="col-md-3 mb-3">
        <div class="card-flip-wrapper" onclick="flipCard(this)">
            <div class="card-inner">
                <div class="metric-card card-front" id="camera-card">
                    <div class="icon" style="color: #e91e63;"><i class="fas fa-camera"></i></div>
                    <div class="label">Deteksi Kamera AI</div>
                    <div class="value" id="val-camera-animal" style="font-size: 20px;">-</div>
                    <span id="badge-camera" class="status-badge" style="background: #eeeeee; color: #616161;">Kamera Offline</span>
                    <div id="camera-confidence" style="font-size: 11px; color: #999; margin-top: 5px;"></div>
                    <div id="camera-time" style="font-size: 11px; color: #aaa;"></div>
                    <span class="card-tap-hint">Tap untuk info</span>
                </div>
                <div class="card-back">
                    <div class="back-title"><i class="fas fa-camera" style="color:#f472b6;"></i> Deteksi Kamera AI</div>
                    <div class="back-body">
                        Kamera mendeteksi binatang via YOLOv8 AI secara real-time.<br>
                        🟢 <b>Kamera Aktif</b>: script Python berjalan<br>
                        ⚫ <b>Kamera Offline</b>: script tidak berjalan<br>
                        🔴 <b>Binatang Terdeteksi</b>: buzzer 3 detik
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
window.flipCard = function(wrapper) {
    wrapper.classList.toggle('flipped');
};
</script>




<div class="row mb-4">
    <div class="col-md-6">
        <div class="alerts-section" style="margin-bottom: 20px; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h5 style="margin: 0;">Peringatan</h5>
                <a href="{{ route('app.hama-alerts') }}" style="color: #3a7d5a; font-size: 13px; text-decoration: none;">></a>
            </div>

            <div class="alert-item">
                <i class="fas fa-exclamation-circle"></i>
                <div class="alert-item-text">
                    <h6>STATUS SENSOR TERBARU</h6>
                    <p>{{ $latest ? ($ai['summary'] ?? 'Data sensor berhasil diterima dari ESP32.') : 'Belum ada data masuk dari ESP32. Periksa URL endpoint, jaringan Wi-Fi, dan payload yang dikirim perangkat.' }}</p>
                </div>
            </div>

        </div>
    </div>
    <div class="col-md-6">
        <div class="alerts-section" style="margin-bottom: 20px; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h5 style="margin: 0;">AI Analisis &amp; Rekomendasi</h5>
                <span class="status-badge" style="background: rgba(0,0,0,0.04); color: {{ $ai['riskColor'] ?? '#4caf50' }};">
                    Risiko: {{ $ai['risk'] ?? 'Rendah' }}
                </span>
            </div>
            <p style="margin: 0 0 14px; font-size: 13px; color: #666; line-height: 1.5;">
                {{ $ai['summary'] ?? 'Analisis belum tersedia.' }}
            </p>

            @foreach(($ai['recommendations'] ?? []) as $rec)
                @php
                    $priority = strtolower($rec['priority'] ?? 'low');
                    $icon = $priority === 'high' ? 'fa-bolt' : ($priority === 'medium' ? 'fa-circle-info' : 'fa-check-circle');
                    $border = $priority === 'high' ? '#ff4757' : ($priority === 'medium' ? '#ffb300' : '#4caf50');
                    $bg = $priority === 'high' ? '#fff2f2' : ($priority === 'medium' ? '#fff8e1' : '#f1f8e9');
                @endphp
                <div class="alert-item" style="background: {{ $bg }}; border-left-color: {{ $border }}; margin-bottom: 10px;">
                    <i class="fas {{ $icon }}" style="color: {{ $border }};"></i>
                    <div class="alert-item-text">
                        <h6 style="margin: 0 0 6px;">{{ $rec['title'] ?? 'Rekomendasi' }}</h6>
                        <p style="margin: 0;">{{ $rec['text'] ?? '' }}</p>
                    </div>
                </div>
            @endforeach
        </div>
    </div>
</div>

<script>
(function () {
    const latestEndpoint = @json($latestEndpoint ?? url('/api/sensor/latest'));

    const card   = document.getElementById('esp32-connection-card');
    const label  = document.getElementById('esp32-connection-label');
    const seen   = document.getElementById('esp32-last-seen');

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function setBadge(id, bg, color, text) {
        const el = document.getElementById(id);
        if (!el) return;
        el.style.background = bg;
        el.style.color = color;
        el.textContent = text;
    }

    function rangeStatus(val, low, high) {
        if (val == null) return { label: 'Belum ada data', bg: '#eeeeee', color: '#616161' };
        if (val < low)  return { label: 'Rendah',         bg: '#e3f2fd', color: '#2196f3' };
        if (val > high) return { label: 'Tinggi',         bg: '#ffe0cc', color: '#ff6b35' };
        return             { label: 'Normal',         bg: '#e8f5e9', color: '#2e7d32' };
    }

    function renderAll(p) {
        // Connection card
        if (card && label && seen) {
            const online   = Boolean(p.is_online);
            const deviceId = p.device_id || 'Perangkat belum terdeteksi';
            label.textContent    = `${deviceId} - ${online ? 'Online' : 'Menunggu data'}`;
            seen.textContent     = p.last_seen_human || 'Belum ada data';
            card.style.background = online ? '#e8f5e9' : '#fff3e0';
            card.style.color      = online ? '#2e7d32' : '#ef6c00';
        }

        // Moisture
        const moist = p.moisture != null ? Math.round(p.moisture) : null;
        setText('val-moisture', moist != null ? `${moist}%` : '-');
        const ms = rangeStatus(moist, 30, 70);
        setBadge('badge-moisture', ms.bg, ms.color, ms.label);

        // Temperature
        const temp = p.temperature != null ? Math.round(p.temperature) : null;
        setText('val-temperature', temp != null ? `${temp} °C` : '-');
        const ts = rangeStatus(temp, 20, 30);
        setBadge('badge-temperature', ts.bg, ts.color, ts.label);

        // Humidity
        const hum = p.humidity != null ? Math.round(p.humidity) : null;
        setText('val-humidity', hum != null ? `${hum}%` : '-');
        const hs = rangeStatus(hum, 30, 70);
        setBadge('badge-humidity', hs.bg, hs.color, hs.label);

        // pH
        const ph = p.ph != null ? parseFloat(p.ph) : null;
        setText('val-ph', ph != null ? ph.toFixed(1) : '-');
        if (ph != null) {
            const phOk = ph >= 6.0 && ph <= 7.0;
            setBadge('badge-ph', phOk ? '#f3e5f5' : '#fff3e0', phOk ? '#6a1b9a' : '#ef6c00', phOk ? 'Ideal' : 'Perlu Penyesuaian');
        }

        // Motion
        const motion = p.motion;
        if (motion === true)  { setText('val-motion', 'TERDETEKSI'); setBadge('badge-motion', '#ffebee', '#c62828', 'TERDETEKSI'); }
        if (motion === false) { setText('val-motion', 'AMAN');       setBadge('badge-motion', '#e8f5e9', '#2e7d32', 'AMAN'); }

        // Soil raw
        const raw = p.soil_raw != null ? parseInt(p.soil_raw) : null;
        setText('val-soil-raw', raw != null ? raw.toLocaleString() : '-');
        if (raw != null) setBadge('badge-soil-raw', '#eceff1', '#37474f', 'Dari ESP32');

        // Risk sub-line
        if (p.device_id || p.last_seen_human) {
            setText('val-risk-sub', `${p.device_id || 'ESP32'} - ${p.last_seen_human || ''}`);
        }
    }


    async function poll() {
        try {
            const res = await fetch(latestEndpoint, { headers: { Accept: 'application/json' }, cache: 'no-store' });
            if (!res.ok) return;
            renderAll(await res.json());
        } catch (_) {}
    }

    if (window.Echo) {
        try { window.Echo.channel('sensor-data').listen('.SensorDataReceived', poll); } catch (_) {}
    }

    setInterval(poll, 1000);
    poll();
})();
</script>

<script>
(function () {
    const cameraStatusEndpoint = @json(url('/api/camera/status'));

    function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }
    function setBadge(id, bg, color, text) {
        const el = document.getElementById(id);
        if (!el) return;
        el.style.background = bg;
        el.style.color      = color;
        el.textContent      = text;
    }

    async function pollCamera() {
        try {
            const res = await fetch(cameraStatusEndpoint, { cache: 'no-store' });
            if (!res.ok) return;
            const data = await res.json();

            if (data.camera_online) {
                setBadge('badge-camera', '#e8f5e9', '#2e7d32', 'Kamera Aktif');
            } else {
                setBadge('badge-camera', '#eeeeee', '#616161', 'Kamera Offline');
                setText('val-camera-animal', '-');
                setText('camera-confidence', '');
                setText('camera-time', '');
            }

            const d = data.detection;
            if (d && d.detected) {
                setText('val-camera-animal', 'Binatang Terdeteksi');
                setText('camera-confidence', '');
                setText('camera-time', d.detected_human || '');
                setBadge('badge-camera', '#ffebee', '#c62828', 'TERDETEKSI');
            } else if (data.camera_online) {
                setText('val-camera-animal', 'Aman');
                setText('camera-confidence', '');
                setText('camera-time', d ? (d.detected_human || '') : '');
            }
        } catch (_) {}
    }

    setInterval(pollCamera, 2000);
    pollCamera();
})();
</script>

<!-- Chat Widget: Tanya SIPETIK -->
<div id="sipetikChatLauncher" style="position: fixed; right: 22px; bottom: 22px; z-index: 999; display: flex; align-items: flex-end; flex-direction: column; gap: 10px;">

    {{-- Tooltip Legend API AI --}}
    <div id="chat-api-tooltip" style="
        display: none; width: 260px;
        background: #1e293b; color: #e2e8f0;
        border-radius: 12px; padding: 14px 16px;
        font-size: 12px; line-height: 1.6;
        box-shadow: 0 8px 24px rgba(0,0,0,0.28);
        position: relative;">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #94a3b8; margin-bottom: 8px;">Tanya SIPETIK — Info AI</div>
        <div style="margin-bottom: 6px;">
            <span style="color: #94a3b8;">Provider:</span>
            <strong style="color: #fff; margin-left: 4px;">{{ $assistantLegend['provider_label'] ?? '-' }}</strong>
        </div>
        <div style="margin-bottom: 6px;">
            <span style="color: #94a3b8;">Status Key:</span>
            <strong style="margin-left: 4px; color: {{ ($assistantLegend['has_provider_key'] ?? false) ? '#4ade80' : '#f87171' }};">
                {{ $assistantLegend['key_status_label'] ?? '-' }}
            </strong>
        </div>
        <div style="margin-bottom: 6px;">
            <span style="color: #94a3b8;">Model:</span>
            <strong style="color: #fff; margin-left: 4px;">{{ $assistantLegend['model'] ?? '-' }}</strong>
        </div>
        <div>
            <span style="color: #94a3b8;">Target:</span>
            <span style="color: #93c5fd; margin-left: 4px; word-break: break-all; font-size: 11px;">{{ $assistantLegend['api_target'] ?? '-' }}</span>
        </div>
        @if(!($assistantLegend['has_provider_key'] ?? false))
        <div style="margin-top: 8px; padding: 8px 10px; background: rgba(248,113,113,0.15); border-radius: 8px; font-size: 11px; color: #fca5a5;">
            ⚠ API Key belum diisi di .env
        </div>
        @endif
        {{-- Arrow --}}
        <div style="position: absolute; bottom: -8px; right: 24px; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 8px solid #1e293b;"></div>
    </div>

    <div id="sipetikChatHint" style="display:none; background: white; border: 1px solid #eee; box-shadow: 0 2px 10px rgba(0,0,0,0.10); padding: 10px 12px; border-radius: 10px; font-size: 12px; color: #555;">
        Tanya SIPETIK
    </div>
    <button type="button" id="sipetikChatBtn" aria-label="Buka chat SIPETIK"
        style="width: 56px; height: 56px; border-radius: 50%; border: none; cursor: pointer; background: #3a7d5a; color: white; box-shadow: 0 8px 18px rgba(0,0,0,0.18); display:flex; align-items:center; justify-content:center;">
        <i class="fas fa-comments" style="font-size: 20px;"></i>
    </button>
</div>

<script>
(function () {
    const launcher = document.getElementById('sipetikChatLauncher');
    const tooltip  = document.getElementById('chat-api-tooltip');
    const chatBtn  = document.getElementById('sipetikChatBtn');
    if (!launcher || !tooltip || !chatBtn) return;

    // Desktop: hover
    launcher.addEventListener('mouseenter', () => { tooltip.style.display = 'block'; });
    launcher.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });

    // Mobile: long-press atau tap tombol info — tambahkan ⓘ kecil di atas tombol chat
    const infoBtn = document.createElement('button');
    infoBtn.innerHTML = 'ⓘ';
    infoBtn.style.cssText = 'position:absolute;top:-8px;right:-6px;width:20px;height:20px;border-radius:50%;border:none;background:#fff;color:#3a7d5a;font-size:11px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.15);z-index:10;padding:0;';
    chatBtn.style.position = 'relative';
    chatBtn.appendChild(infoBtn);

    let tooltipOpen = false;
    infoBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        tooltipOpen = !tooltipOpen;
        tooltip.style.display = tooltipOpen ? 'block' : 'none';
    });

    document.addEventListener('click', (e) => {
        if (!launcher.contains(e.target)) {
            tooltipOpen = false;
            tooltip.style.display = 'none';
        }
    });
})();
</script>

<div id="sipetikChatPanel" style="position: fixed; right: 22px; bottom: 90px; width: 360px; max-width: calc(100vw - 44px); height: 520px; max-height: calc(100vh - 140px); background: white; border-radius: 14px; box-shadow: 0 12px 30px rgba(0,0,0,0.18); z-index: 1000; overflow: hidden; display:none; border: 1px solid #eee;">
    <div style="background: linear-gradient(135deg, #2d5f47 0%, #3a7d5a 100%); color: white; padding: 14px 14px; display:flex; align-items:center; justify-content: space-between;">
        <div style="display:flex; flex-direction:column; gap:2px;">
            <div style="font-weight: 700; letter-spacing: .3px;">Tanya SIPETIK</div>
            <div style="font-size: 12px; opacity: .9;">Asisten AI umum (Indonesia/English)</div>
        </div>
        <button type="button" id="sipetikChatClose" aria-label="Tutup chat" style="background: rgba(255,255,255,0.15); color: white; border: none; width: 34px; height: 34px; border-radius: 10px; cursor: pointer;">
            <i class="fas fa-xmark"></i>
        </button>
    </div>

    <div id="sipetikChatMessages" style="padding: 14px; height: calc(100% - 64px - 66px); overflow-y: auto; background: #fafafa;">
        <div style="display:flex; gap:10px; margin-bottom: 12px;">
            <div style="width: 34px; height: 34px; border-radius: 10px; background:#e8f5e9; display:flex; align-items:center; justify-content:center; color:#3a7d5a;">
                <i class="fas fa-seedling"></i>
            </div>
            <div style="flex:1;">
                <div style="font-size: 12px; color:#777; margin-bottom: 4px;">SIPETIK</div>
                <div style="background: white; border: 1px solid #eee; border-radius: 12px; padding: 10px 12px; font-size: 13px; color:#333; line-height:1.45;">
                    Halo! Anda bisa tanya topik apa saja. I can also answer in English.
                </div>
                <div style="margin-top: 8px; display:flex; flex-wrap:wrap; gap:8px;">
                    <button type="button" class="sipetikQuick" data-q="Jelaskan perbedaan AI dan machine learning secara singkat." style="border:1px solid #e6e6e6; background:white; border-radius: 999px; padding:6px 10px; font-size: 12px; cursor:pointer;">AI basics</button>
                    <button type="button" class="sipetikQuick" data-q="Can you help me write a short professional email?" style="border:1px solid #e6e6e6; background:white; border-radius: 999px; padding:6px 10px; font-size: 12px; cursor:pointer;">Write email</button>
                    <button type="button" class="sipetikQuick" data-q="Berikan ide konten Instagram untuk bisnis kecil." style="border:1px solid #e6e6e6; background:white; border-radius: 999px; padding:6px 10px; font-size: 12px; cursor:pointer;">Ide konten</button>
                </div>
            </div>
        </div>
    </div>

    <div style="padding: 12px; border-top: 1px solid #eee; background: white;">
        <div style="display:flex; gap:10px; align-items: center;">
            <input id="sipetikChatInput" type="text" placeholder="Tulis pertanyaan..." autocomplete="off"
                style="flex:1; border: 1px solid #ddd; border-radius: 10px; padding: 10px 12px; outline: none; font-size: 13px;">
            <button type="button" id="sipetikChatSend" class="btn-primary-custom" style="padding: 10px 14px; border-radius: 10px;">
                <i class="fas fa-paper-plane"></i>
            </button>
        </div>
        <div id="sipetikChatNote" style="margin-top: 8px; font-size: 11px; color:#999;">
            Tips: Anda bisa bertanya dalam Bahasa Indonesia atau English.
        </div>
    </div>
</div>

<script>
    (function() {
        const btn = document.getElementById('sipetikChatBtn');
        const panel = document.getElementById('sipetikChatPanel');
        const closeBtn = document.getElementById('sipetikChatClose');
        const messages = document.getElementById('sipetikChatMessages');
        const input = document.getElementById('sipetikChatInput');
        const sendBtn = document.getElementById('sipetikChatSend');
        const hint = document.getElementById('sipetikChatHint');
        const browserLocale = (navigator.language || 'id').toLowerCase();
        const assistantEndpoint = @json(url('/api/assistant/ask'));

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

        const context = {
            page: 'dashboard',
            ui_locale: browserLocale,
            snapshot: {
                temperature: {{ $latest ? (is_null($latest->temperature) ? 'null' : $latest->temperature) : 'null' }},
                humidity: {{ $latest ? (is_null($latest->humidity) ? 'null' : $latest->humidity) : 'null' }},
                moisture: {{ $latest ? (is_null($latest->moisture) ? 'null' : $latest->moisture) : 'null' }},
                ph: {{ is_null($dummyPh) ? 'null' : $dummyPh }},
                motion: {{ is_null($dummyMotionDetected) ? 'null' : (($dummyMotionDetected ?? false) ? 'true' : 'false') }}
            }
        };

        function toggle(open) {
            panel.style.display = open ? 'block' : 'none';
            if (open) {
                setTimeout(() => input?.focus(), 50);
            }
        }

        function scrollToBottom() {
            messages.scrollTop = messages.scrollHeight;
        }

        function escapeHtml(str) {
            return String(str)
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#039;');
        }

        function addBubble({ from, text, meta }) {
            const isUser = from === 'user';
            const wrap = document.createElement('div');
            wrap.style.display = 'flex';
            wrap.style.gap = '10px';
            wrap.style.marginBottom = '12px';
            wrap.style.justifyContent = isUser ? 'flex-end' : 'flex-start';

            const bubble = document.createElement('div');
            bubble.style.maxWidth = '82%';
            bubble.style.background = isUser ? '#3a7d5a' : 'white';
            bubble.style.color = isUser ? 'white' : '#333';
            bubble.style.border = isUser ? 'none' : '1px solid #eee';
            bubble.style.borderRadius = '12px';
            bubble.style.padding = '10px 12px';
            bubble.style.fontSize = '13px';
            bubble.style.lineHeight = '1.45';
            bubble.innerHTML = escapeHtml(text).replaceAll('\n', '<br>');

            if (!isUser) {
                const left = document.createElement('div');
                left.style.width = '34px';
                left.style.height = '34px';
                left.style.borderRadius = '10px';
                left.style.background = '#e8f5e9';
                left.style.display = 'flex';
                left.style.alignItems = 'center';
                left.style.justifyContent = 'center';
                left.style.color = '#3a7d5a';
                left.innerHTML = '<i class="fas fa-seedling"></i>';
                wrap.appendChild(left);
            }

            const content = document.createElement('div');
            if (!isUser) {
                content.style.flex = '1';
                const who = document.createElement('div');
                who.style.fontSize = '12px';
                who.style.color = '#777';
                who.style.marginBottom = '4px';
                who.textContent = 'SIPETIK';
                content.appendChild(who);
            } else {
                content.style.display = 'flex';
                content.style.justifyContent = 'flex-end';
            }
            content.appendChild(bubble);

            if (meta?.followUps?.length) {
                const follow = document.createElement('div');
                follow.style.marginTop = '8px';
                follow.style.display = 'flex';
                follow.style.flexWrap = 'wrap';
                follow.style.gap = '8px';

                meta.followUps.slice(0, 3).forEach(q => {
                    const b = document.createElement('button');
                    b.type = 'button';
                    b.className = 'sipetikQuick';
                    b.dataset.q = q;
                    b.textContent = q;
                    b.style.border = '1px solid #e6e6e6';
                    b.style.background = 'white';
                    b.style.borderRadius = '999px';
                    b.style.padding = '6px 10px';
                    b.style.fontSize = '12px';
                    b.style.cursor = 'pointer';
                    follow.appendChild(b);
                });
                content.appendChild(follow);
            }

            wrap.appendChild(content);
            messages.appendChild(wrap);
            scrollToBottom();
        }

        async function sendQuestion(q) {
            const question = (q ?? input.value ?? '').trim();
            if (!question) return;

            input.value = '';
            addBubble({ from: 'user', text: question });

            const typingId = 'sipetikTyping';
            const typing = document.createElement('div');
            typing.id = typingId;
            typing.style.marginBottom = '12px';
            typing.innerHTML = `
                <div style="display:flex; gap:10px;">
                    <div style="width:34px; height:34px; border-radius:10px; background:#e8f5e9; display:flex; align-items:center; justify-content:center; color:#3a7d5a;">
                        <i class="fas fa-seedling"></i>
                    </div>
                    <div style="flex:1;">
                        <div style="font-size: 12px; color:#777; margin-bottom: 4px;">SIPETIK</div>
                        <div style="background:white; border:1px solid #eee; border-radius:12px; padding:10px 12px; font-size:13px; color:#333;">
                            Mengetik...
                        </div>
                    </div>
                </div>
            `;
            messages.appendChild(typing);
            scrollToBottom();

            try {
                const res = await fetch(assistantEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-TOKEN': csrfToken
                    },
                    body: JSON.stringify({
                        question,
                        locale: 'auto',
                        context
                    })
                });

                const json = await res.json().catch(() => ({}));
                document.getElementById(typingId)?.remove();

                if (!res.ok) {
                    const fallbackError = 'Maaf, terjadi kendala saat memproses pertanyaan. Coba lagi.';
                    const backendAnswer = typeof json.answer === 'string' ? json.answer.trim() : '';
                    const backendError = typeof json?.error?.message === 'string' ? json.error.message.trim() : '';
                    const detail = backendAnswer || backendError || fallbackError;
                    addBubble({ from: 'assistant', text: detail });
                    return;
                }

                addBubble({
                    from: 'assistant',
                    text: json.answer || 'Maaf, saya belum bisa menjawab pertanyaan itu.',
                    meta: { followUps: json.follow_up_questions || [] }
                });
            } catch (e) {
                document.getElementById(typingId)?.remove();
                addBubble({ from: 'assistant', text: 'Koneksi bermasalah. Coba cek internet/server lalu ulangi.' });
            }
        }

        btn?.addEventListener('click', () => toggle(panel.style.display === 'none'));
        closeBtn?.addEventListener('click', () => toggle(false));
        sendBtn?.addEventListener('click', () => sendQuestion());
        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendQuestion();
            }
        });

        document.addEventListener('click', (e) => {
            const t = e.target;
            if (t && t.classList && t.classList.contains('sipetikQuick')) {
                sendQuestion(t.dataset.q);
            }
        });

        setTimeout(() => {
            if (!panel || panel.style.display !== 'none') return;
            hint.style.display = 'block';
            setTimeout(() => hint.style.display = 'none', 4500);
        }, 900);
    })();
</script>

@endsection


