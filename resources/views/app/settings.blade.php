@extends('layouts.app')

@section('title', 'Pengaturan')
@section('page-title', 'Pengaturan')
@section('breadcrumb', 'Beranda / Pengaturan')

@section('content')
<div style="margin-bottom: 20px;">
    <p style="color: #666; margin: 0 0 5px;">Pengaturan</p>
    <p style="color: #999; font-size: 14px;">Kelola akun dan preferensi Anda.</p>
</div>

<!-- User Profile -->
<div class="settings-section">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 20px;">
            <img src="https://ui-avatars.com/api/?name={{ $user['name'] ?? 'Andi' }}&background=3a7d5a&color=fff&size=80" alt="User" style="width: 80px; height: 80px; border-radius: 50%;">
            <div>
                <h6 style="margin: 0 0 5px; font-size: 16px;">{{ $user['name'] ?? 'Andi' }}</h6>
                <p style="margin: 0; color: #999; font-size: 13px;">{{ $user['email'] ?? 'andi@example.com' }}</p>
            </div>
        </div>
        <button class="btn-primary-custom" onclick="showEditProfileModal()">Edit Profil</button>
    </div>
</div>




<!-- Pengaturan Buzzer -->
<div class="settings-section" style="margin-top: 30px;">
    <h5 style="display: flex; align-items: center; gap: 8px;">
        <i class="fas fa-bell" style="color: #e67e22;"></i> Pengaturan Buzzer
    </h5>
    <p style="margin-top: 4px; color: #999; font-size: 12px;">
        Atur mode dan jadwal buzzer ESP32. Integrasi PIR + Kamera AI tetap aktif di semua mode.
    </p>

    {{-- Override OFF --}}
    <div id="override-banner" style="margin: 16px 0; padding: 14px 16px; border-radius: 10px; background: #fff3e0; border: 2px solid #ff9800; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas fa-lock" id="override-icon" style="color: #e65100; font-size: 16px;"></i>
            <div>
                <div id="override-label" style="font-size: 13px; font-weight: 700; color: #e65100;">Override OFF Tidak Aktif</div>
                <div style="font-size: 12px; color: #888; margin-top: 2px;">Saat diaktifkan, buzzer dimatikan paksa dan tidak bisa dinyalakan sampai override dinonaktifkan.</div>
            </div>
        </div>
        <button type="button" id="override-btn"
            style="padding: 9px 20px; border-radius: 8px; border: none; font-size: 13px; font-weight: 700; cursor: pointer; background: #e65100; color: white; white-space: nowrap;">
            <i class="fas fa-lock-open" id="override-btn-icon"></i>
            <span id="override-btn-label">Aktifkan Override</span>
        </button>
    </div>

    {{-- Status buzzer real-time --}}
    <div style="margin: 16px 0; padding: 14px 16px; border-radius: 10px; background: #fafafa; border: 1px solid #eee; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas fa-circle" id="buzzer-live-dot" style="font-size: 10px; color: #ccc;"></i>
            <span style="font-size: 13px; color: #555;">Status buzzer saat ini:</span>
            <span id="buzzer-live-state" style="font-size: 13px; font-weight: 700; color: #888;">Memuat...</span>
        </div>
        <span style="font-size: 12px; color: #aaa;" id="buzzer-live-time"></span>
    </div>

    {{-- Mode Selector --}}
    <div class="settings-row" style="border-bottom: none; padding-bottom: 0;">
        <div>
            <h6 style="margin-bottom: 5px; color: #333;">Mode Buzzer</h6>
            <p style="margin: 0; color: #999; font-size: 12px;">Manual: kontrol ON/OFF langsung. Otomatis: aktif sesuai jadwal &amp; interval.</p>
        </div>
        <select id="buzzer-mode" style="padding: 8px 10px; border-radius: 6px; border: 1px solid #ddd; font-size: 13px;">
            <option value="manual">Manual</option>
            <option value="auto">Otomatis</option>
        </select>
    </div>

    {{-- Manual Panel --}}
    <div id="buzzer-manual-panel" style="margin-top: 18px; border-top: 1px solid #f0f0f0; padding-top: 18px;">
        <h6 style="margin-bottom: 12px; color: #333;">Kontrol Manual</h6>
        <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
            <button type="button" id="buzzer-toggle-btn"
                style="padding: 12px 32px; border-radius: 8px; border: none; font-size: 15px; font-weight: 700; cursor: pointer; transition: background .2s; background: #e0e0e0; color: #555;">
                <i class="fas fa-bell"></i> <span id="buzzer-toggle-label">Memuat...</span>
            </button>
            <span style="font-size: 12px; color: #999;">Tekan tombol untuk mengganti status buzzer.</span>
        </div>
    </div>

    {{-- Auto Panel --}}
    <div id="buzzer-auto-panel" style="display:none; margin-top: 18px; border-top: 1px solid #f0f0f0; padding-top: 18px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-bottom: 18px;">
            <div>
                <h6 style="margin: 0; color: #333;">Pengaturan Otomatis</h6>
                <p style="margin: 4px 0 0; font-size: 12px; color: #999;">Jadwal dan interval bunyi otomatis.</p>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span id="auto-enabled-label" style="font-size: 13px; color: #888;">Memuat...</span>
                <button type="button" id="auto-enabled-btn"
                    style="padding: 8px 20px; border-radius: 8px; border: none; font-size: 13px; font-weight: 700; cursor: pointer; background: #e0e0e0; color: #555;">
                    <i id="auto-enabled-icon" class="fas fa-power-off"></i>
                    <span id="auto-enabled-btn-label">Memuat...</span>
                </button>
            </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 16px;">
            {{-- Jam aktif --}}
            <div>
                <label style="font-size: 12px; color: #666; display: block; margin-bottom: 6px;">Jam aktif (WIB)</label>
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                    <div>
                        <span style="font-size: 12px; color: #888;">Dari</span>
                        <input type="time" id="buzzer-schedule-start" value="06:00"
                            style="margin-left: 6px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
                    </div>
                    <div>
                        <span style="font-size: 12px; color: #888;">Sampai</span>
                        <input type="time" id="buzzer-schedule-end" value="18:00"
                            style="margin-left: 6px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
                    </div>
                </div>
                <small style="font-size: 11px; color: #aaa; display: block; margin-top: 4px;">Di luar jam ini buzzer tidak akan menyala otomatis.</small>
            </div>

            {{-- Interval --}}
            <div>
                <label style="font-size: 12px; color: #666; display: block; margin-bottom: 6px;">Interval bunyi otomatis</label>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <span style="font-size: 12px; color: #888;">Setiap</span>
                    <input type="number" id="buzzer-interval-min" min="0" max="1440" value="5"
                        style="width: 72px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
                    <span style="font-size: 12px; color: #888;">menit</span>
                    <input type="number" id="buzzer-interval-sec" min="0" max="59" value="0"
                        style="width: 72px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;">
                    <span style="font-size: 12px; color: #888;">detik</span>
                </div>
                <small style="font-size: 11px; color: #aaa; display: block; margin-top: 4px;">Set ke 0 menit 0 detik untuk menonaktifkan interval.</small>
            </div>

            {{-- Durasi --}}
            <div>
                <label style="font-size: 12px; color: #666; display: block; margin-bottom: 6px;">Durasi bunyi</label>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <select id="buzzer-duration-auto"
                        style="padding: 6px 10px; border-radius: 6px; border: 1px solid #ddd; font-size: 13px;">
                        <option value="1">1 detik</option>
                        <option value="3" selected>3 detik</option>
                        <option value="5">5 detik</option>
                        <option value="10">10 detik</option>
                        <option value="30">30 detik</option>
                    </select>
                </div>
            </div>

            {{-- Trigger risiko hama --}}
            <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; color: #333;">
                <input type="checkbox" id="buzzer-risk-trigger-auto" style="width: 15px; height: 15px;">
                Aktifkan juga saat risiko hama <strong style="color:#ff4757;">Tinggi</strong>
            </label>
        </div>
    </div>

    {{-- Catatan integrasi --}}
    <div style="margin-top: 20px; padding: 12px 14px; border-radius: 8px; background: #f0fdf4; border: 1px solid #bbf7d0;">
        <div style="font-size: 12px; color: #166534; display: flex; align-items: flex-start; gap: 8px;">
            <i class="fas fa-shield-halved" style="margin-top: 2px;"></i>
            <span>
                <strong>Integrasi otomatis tetap aktif di semua mode:</strong>
                Buzzer akan berbunyi bila <strong>PIR sensor mendeteksi gerakan</strong> dan <strong>Kamera AI mendeteksi binatang</strong> secara bersamaan, terlepas dari mode yang dipilih.
            </span>
        </div>
    </div>

    <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
        <button type="button" id="buzzer-save-btn" class="btn-primary-custom">
            <i class="fas fa-floppy-disk"></i> Simpan Pengaturan Buzzer
        </button>
    </div>

    <div id="buzzer-save-msg" style="display:none; margin-top: 10px; text-align: right; font-size: 13px; color: #3a7d5a;">
        <i class="fas fa-check-circle"></i> Pengaturan tersimpan.
    </div>
</div>

<script>
(function () {
    const apiBase    = @json(url('/api/buzzer'));
    const csrf       = document.querySelector('meta[name="csrf-token"]')?.content || '';
    let currentState = false; // true = buzzer ON

    const els = {
        mode:             document.getElementById('buzzer-mode'),
        manualPanel:      document.getElementById('buzzer-manual-panel'),
        autoPanel:        document.getElementById('buzzer-auto-panel'),
        toggleBtn:        document.getElementById('buzzer-toggle-btn'),
        toggleLabel:      document.getElementById('buzzer-toggle-label'),
        overrideBanner:   document.getElementById('override-banner'),
        overrideBtn:      document.getElementById('override-btn'),
        overrideBtnIcon:  document.getElementById('override-btn-icon'),
        overrideBtnLabel: document.getElementById('override-btn-label'),
        overrideLabel:    document.getElementById('override-label'),
        overrideIcon:     document.getElementById('override-icon'),
        liveState:        document.getElementById('buzzer-live-state'),
        liveDot:          document.getElementById('buzzer-live-dot'),
        liveTime:         document.getElementById('buzzer-live-time'),
        schedStart:       document.getElementById('buzzer-schedule-start'),
        schedEnd:         document.getElementById('buzzer-schedule-end'),
        intervalMin:      document.getElementById('buzzer-interval-min'),
        intervalSec:      document.getElementById('buzzer-interval-sec'),
        durationAuto:     document.getElementById('buzzer-duration-auto'),
        riskTrigger:      document.getElementById('buzzer-risk-trigger-auto'),
        saveBtn:          document.getElementById('buzzer-save-btn'),
        saveMsg:          document.getElementById('buzzer-save-msg'),
        autoEnabledBtn:   document.getElementById('auto-enabled-btn'),
        autoEnabledLabel: document.getElementById('auto-enabled-label'),
        autoEnabledIcon:  document.getElementById('auto-enabled-icon'),
        autoEnabledBtnLabel: document.getElementById('auto-enabled-btn-label'),
    };

    let overrideActive = false;
    let autoEnabled    = false;

    function renderOverride(active) {
        overrideActive = active;
        if (active) {
            els.overrideBanner.style.background   = '#ffebee';
            els.overrideBanner.style.borderColor  = '#e53935';
            els.overrideLabel.textContent         = 'Override OFF Aktif — Buzzer dikunci MATI';
            els.overrideLabel.style.color         = '#c62828';
            els.overrideIcon.className            = 'fas fa-lock';
            els.overrideIcon.style.color          = '#c62828';
            els.overrideBtn.style.background      = '#4caf50';
            els.overrideBtnIcon.className         = 'fas fa-lock-open';
            els.overrideBtnLabel.textContent      = 'Nonaktifkan Override';
            // Kunci tombol ON saat override aktif
            if (els.toggleBtn) {
                els.toggleBtn.disabled = true;
                els.toggleBtn.style.opacity = '0.4';
                els.toggleBtn.style.cursor  = 'not-allowed';
            }
        } else {
            els.overrideBanner.style.background   = '#fff3e0';
            els.overrideBanner.style.borderColor  = '#ff9800';
            els.overrideLabel.textContent         = 'Override OFF Tidak Aktif';
            els.overrideLabel.style.color         = '#e65100';
            els.overrideIcon.className            = 'fas fa-lock-open';
            els.overrideIcon.style.color          = '#e65100';
            els.overrideBtn.style.background      = '#e65100';
            els.overrideBtnIcon.className         = 'fas fa-lock';
            els.overrideBtnLabel.textContent      = 'Aktifkan Override';
            if (els.toggleBtn) {
                els.toggleBtn.disabled = false;
                els.toggleBtn.style.opacity = '1';
                els.toggleBtn.style.cursor  = 'pointer';
            }
        }
    }

    function renderAutoEnabled(enabled) {
        autoEnabled = enabled;
        if (enabled) {
            els.autoEnabledLabel.textContent       = 'Otomatis aktif';
            els.autoEnabledLabel.style.color       = '#2e7d32';
            els.autoEnabledBtn.style.background    = '#e53935';
            els.autoEnabledBtn.style.color         = '#fff';
            els.autoEnabledIcon.className          = 'fas fa-stop';
            els.autoEnabledBtnLabel.textContent    = 'Nonaktifkan';
        } else {
            els.autoEnabledLabel.textContent       = 'Otomatis nonaktif';
            els.autoEnabledLabel.style.color       = '#888';
            els.autoEnabledBtn.style.background    = '#4caf50';
            els.autoEnabledBtn.style.color         = '#fff';
            els.autoEnabledIcon.className          = 'fas fa-play';
            els.autoEnabledBtnLabel.textContent    = 'Aktifkan';
        }
    }

    els.autoEnabledBtn?.addEventListener('click', async () => {
        const next = !autoEnabled;
        renderAutoEnabled(next);
        // Simpan langsung ke server tanpa perlu klik Simpan
        const mode = els.mode?.value || 'auto';
        try {
            await fetch(apiBase + '/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
                body: JSON.stringify({
                    buzzer_mode:       mode,
                    enabled:           next,
                    use_interval:      next,
                    schedule_enabled:  false,
                    schedule_start:    els.schedStart?.value  || '06:00',
                    schedule_end:      els.schedEnd?.value    || '18:00',
                    interval_minutes:  parseInt(els.intervalMin?.value  || 0),
                    interval_seconds:  parseInt(els.intervalSec?.value  || 0),
                    duration_seconds:  parseInt(els.durationAuto?.value || 3),
                    pest_risk_trigger: els.riskTrigger?.checked ?? true,
                }),
            });
        } catch (_) {}
    });

    els.overrideBtn?.addEventListener('click', async () => {
        const next = !overrideActive;
        try {
            await fetch(apiBase + '/override', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
                body: JSON.stringify({ active: next }),
            });
            renderOverride(next);
            if (next) renderLive(false);
        } catch (_) {}
    });

    function applyMode(mode) {
        els.manualPanel.style.display = mode === 'manual' ? 'block' : 'none';
        els.autoPanel.style.display   = mode === 'auto'   ? 'block' : 'none';
    }

    function renderToggle(on) {
        currentState = on;
        if (on) {
            els.toggleBtn.style.background = '#4caf50';
            els.toggleBtn.style.color      = '#fff';
            els.toggleLabel.textContent    = 'Nyala';
        } else {
            els.toggleBtn.style.background = '#e53935';
            els.toggleBtn.style.color      = '#fff';
            els.toggleLabel.textContent    = 'Mati';
        }
    }

    function renderLive(on) {
        els.liveState.textContent = on ? 'AKTIF' : 'Mati';
        els.liveState.style.color = on ? '#4caf50' : '#888';
        els.liveDot.style.color   = on ? '#4caf50' : '#ccc';
        const now = new Date();
        els.liveTime.textContent  = now.toLocaleTimeString('id-ID') + ' WIB';
    }

    // Isi form hanya sekali saat halaman dimuat — tidak diulang saat polling
    async function initForm() {
        try {
            const res  = await fetch(apiBase + '/status', { cache: 'no-store' });
            if (!res.ok) return;
            const data = await res.json();
            const b    = data.buzzer || {};
            renderToggle(b.buzzer_on || false);
            renderLive(b.buzzer_on   || false);
            renderOverride(b.override_active || false);
            renderAutoEnabled((b.buzzer_mode === 'auto') && (b.enabled || false));
            if (els.mode)         els.mode.value          = b.buzzer_mode      || 'manual';
            if (els.schedStart)   els.schedStart.value    = b.schedule_start   || '06:00';
            if (els.schedEnd)     els.schedEnd.value      = b.schedule_end     || '18:00';
            if (els.intervalMin)  els.intervalMin.value   = b.interval_minutes ?? 5;
            if (els.intervalSec)  els.intervalSec.value   = b.interval_seconds ?? 0;
            if (els.durationAuto) els.durationAuto.value  = b.duration_seconds ?? 3;
            if (els.riskTrigger)  els.riskTrigger.checked = b.pest_risk_trigger ?? true;
            applyMode(b.buzzer_mode || 'manual');
        } catch (_) {}
    }

    // Polling setiap 10 detik: HANYA update override status, TIDAK sentuh toggle button
    // (buzzer_on dari server tidak reliable karena ESP32 tidak selalu report balik)
    async function pollLive() {
        try {
            const res  = await fetch(apiBase + '/status', { cache: 'no-store' });
            if (!res.ok) return;
            const data = await res.json();
            const b    = data.buzzer || {};
            renderOverride(b.override_active || false);
        } catch (_) {}
    }

    async function sendCommand(cmd) {
        try {
            await fetch(apiBase + '/' + cmd, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
            });
        } catch (_) {}
    }

    els.mode?.addEventListener('change', () => applyMode(els.mode.value));

    els.toggleBtn?.addEventListener('click', async () => {
        const next = !currentState;
        renderToggle(next);
        renderLive(next);
        await sendCommand(next ? 'on' : 'off');
    });

    els.saveBtn?.addEventListener('click', async () => {
        const mode = els.mode?.value || 'manual';
        const payload = {
            buzzer_mode:       mode,
            enabled:           mode === 'auto' ? autoEnabled : true,
            use_interval:      mode === 'auto' ? autoEnabled : false,
            schedule_enabled:  false,
            schedule_start:    els.schedStart?.value  || '06:00',
            schedule_end:      els.schedEnd?.value    || '18:00',
            interval_minutes:  parseInt(els.intervalMin?.value  || 0),
            interval_seconds:  parseInt(els.intervalSec?.value  || 0),
            duration_seconds:  parseInt(els.durationAuto?.value || 3),
            pest_risk_trigger: els.riskTrigger?.checked ?? true,
        };
        try {
            const res = await fetch(apiBase + '/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
                body: JSON.stringify(payload),
            });
            if (res.ok) {
                els.saveMsg.style.display = 'block';
                setTimeout(() => els.saveMsg.style.display = 'none', 3000);
            }
        } catch (_) {}
    });

    initForm();
    setInterval(pollLive, 10000);
})();
</script>

@endsection
