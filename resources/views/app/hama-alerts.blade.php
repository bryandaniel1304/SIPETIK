@extends('layouts.app')

@section('title', 'Peringatan Hama')
@section('page-title', 'Peringatan Hama')
@section('breadcrumb', 'Beranda / Peringatan Hama')

@section('content')
<div style="margin-bottom: 20px;">
    <p style="color: #666; margin: 0 0 5px;">Peringatan Hama</p>
    <p style="color: #999; font-size: 14px;">Pantau tingkat risiko hama di sawah Anda berdasarkan data sensor.</p>
</div>

<x-legends type="hama" />

<!-- Filter Buttons -->
<div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
    <a href="{{ route('app.hama-alerts', ['filter' => 'all', 'search' => $search]) }}"
        style="text-decoration:none;">
        <button class="filter-btn" style="{{ $filter === 'all' ? 'background:#555;color:white;border-color:#555;' : '' }}">
            <i class="fas fa-list"></i> Semua
        </button>
    </a>
    <a href="{{ route('app.hama-alerts', ['filter' => 'high', 'search' => $search]) }}"
        style="text-decoration:none;">
        <button class="filter-btn" style="{{ $filter === 'high' ? 'background:#ff4757;color:white;border-color:#ff4757;' : '' }}">
            <i class="fas fa-exclamation-circle"></i> Risiko Tinggi
        </button>
    </a>
    <a href="{{ route('app.hama-alerts', ['filter' => 'medium', 'search' => $search]) }}"
        style="text-decoration:none;">
        <button class="filter-btn" style="{{ $filter === 'medium' ? 'background:#ffb300;color:white;border-color:#ffb300;' : '' }}">
            <i class="fas fa-triangle-exclamation"></i> Waspada
        </button>
    </a>
    <a href="{{ route('app.hama-alerts', ['filter' => 'low', 'search' => $search]) }}"
        style="text-decoration:none;">
        <button class="filter-btn" style="{{ $filter === 'low' ? 'background:#4caf50;color:white;border-color:#4caf50;' : '' }}">
            <i class="fas fa-check-circle"></i> Aman
        </button>
    </a>
</div>

<div class="table-container">
    <!-- Search -->
    <div class="table-controls">
        <form method="GET" action="{{ route('app.hama-alerts') }}" style="display:flex; gap:10px; align-items:center; width:100%;">
            <input type="hidden" name="filter" value="{{ $filter }}">
            <i class="fas fa-filter" style="color:#aaa;"></i>
            <input type="text" name="search" value="{{ $search }}"
                placeholder="Cari status, suhu, kelembapan..."
                style="flex:1; border:none; outline:none; font-size:14px; background:transparent;">
            <button type="submit" style="background:none; border:none; cursor:pointer; color:#aaa;">
                <i class="fas fa-search"></i>
            </button>
            @if($search)
                <a href="{{ route('app.hama-alerts', ['filter' => $filter]) }}"
                    style="color:#aaa; font-size:13px; text-decoration:none;">× Hapus</a>
            @endif
        </form>
    </div>

    <table style="width:100%; border-collapse:collapse;" class="table">
        <thead>
            <tr style="background:#f5f5f5; border-bottom:2px solid #eee;">
                <th style="padding:15px; text-align:left; font-weight:600; color:#333;">ID</th>
                <th style="padding:15px; text-align:left; font-weight:600; color:#333;">Timestamp</th>
                <th style="padding:15px; text-align:left; font-weight:600; color:#333;">Status</th>
                <th style="padding:15px; text-align:left; font-weight:600; color:#333;">Detail Sensor</th>
            </tr>
        </thead>
        <tbody>
            @forelse($alerts as $alert)
                @php
                    $meta    = is_array($alert->metadata) ? $alert->metadata : [];
                    $motion  = $meta['motion'] ?? null;
                    $ph      = $meta['ph']     ?? null;
                    $details = [];
                    if (!is_null($alert->temperature)) $details[] = 'Suhu ' . round($alert->temperature, 1) . '°C';
                    if (!is_null($alert->humidity))    $details[] = 'Kelembapan udara ' . round($alert->humidity, 1) . '%';
                    if (!is_null($alert->moisture))    $details[] = 'Kelembapan tanah ' . round($alert->moisture, 1) . '%';
                    if (!is_null($ph))                 $details[] = 'pH ' . number_format($ph, 1);
                    if ($motion === true)               $details[] = 'Gerakan terdeteksi';

                    $badgeClass = match($alert->pest_status) {
                        'high'   => 'badge-danger',
                        'medium' => 'badge-warning',
                        default  => 'badge-success',
                    };
                    $statusLabel = match($alert->pest_status) {
                        'high'   => 'Risiko Tinggi',
                        'medium' => 'Waspada',
                        default  => 'Aman',
                    };
                @endphp
                <tr style="border-bottom:1px solid #eee;">
                    <td style="padding:15px; color:#888; font-size:13px;">{{ $alert->id }}</td>
                    <td style="padding:15px; font-size:13px;">{{ $alert->created_at->format('d M Y, H:i') }}</td>
                    <td style="padding:15px;"><span class="{{ $badgeClass }}">{{ $statusLabel }}</span></td>
                    <td style="padding:15px; font-size:13px; color:#555;">{{ implode(' | ', $details) ?: '-' }}</td>
                </tr>
            @empty
                <tr>
                    <td colspan="4" style="padding:40px; text-align:center; color:#aaa; font-size:14px;">
                        <i class="fas fa-leaf" style="font-size:32px; display:block; margin-bottom:10px;"></i>
                        Tidak ada data
                        @if($filter !== 'all') untuk filter <strong>{{ $filter === 'high' ? 'Risiko Tinggi' : ($filter === 'medium' ? 'Waspada' : 'Aman') }}</strong>@endif
                        @if($search) dengan kata kunci "<strong>{{ $search }}</strong>"@endif
                    </td>
                </tr>
            @endforelse
        </tbody>
    </table>

    <!-- Pagination -->
    @if($alerts->hasPages())
    <div class="pagination-custom">
        @if($alerts->onFirstPage())
            <span style="opacity:.4;">←</span>
        @else
            <a href="{{ $alerts->previousPageUrl() }}">←</a>
        @endif

        @foreach($alerts->getUrlRange(1, $alerts->lastPage()) as $page => $url)
            @if($page == $alerts->currentPage())
                <span class="active">{{ $page }}</span>
            @elseif(abs($page - $alerts->currentPage()) <= 2 || $page == 1 || $page == $alerts->lastPage())
                <a href="{{ $url }}">{{ $page }}</a>
            @elseif(abs($page - $alerts->currentPage()) == 3)
                <span>...</span>
            @endif
        @endforeach

        @if($alerts->hasMorePages())
            <a href="{{ $alerts->nextPageUrl() }}">→</a>
        @else
            <span style="opacity:.4;">→</span>
        @endif
    </div>
    @endif
</div>

<!-- Notification Settings -->
<div class="settings-section" style="margin-top: 30px;">
    <h5>Pengaturan Notifikasi Email</h5>
    <p style="margin-top: 4px; color: #999; font-size: 12px;">
        Email dikirim ke akun yang Anda gunakan untuk login saat risiko hama tinggi atau binatang terdeteksi.
    </p>

    <div class="settings-row" style="margin-top: 16px;">
        <div>
            <h6 style="margin-bottom: 5px; color: #333;">Notifikasi Email</h6>
            <p style="margin: 0; color: #999; font-size: 12px;">
                Kirim email ke <strong id="notif-email-display" style="color: #3a7d5a;">memuat...</strong>
                saat risiko hama tinggi atau binatang terdeteksi.
            </p>
        </div>
        <div id="email-toggle" class="toggle-switch" onclick="toggleEmailNotif(this)"></div>
    </div>

    <div style="margin-top: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <button type="button" id="test-email-btn" onclick="sendTestEmail()"
            style="padding: 8px 16px; border-radius: 8px; border: 1px solid #3a7d5a; background: white; color: #3a7d5a; font-size: 13px; font-weight: 600; cursor: pointer;">
            <i class="fas fa-paper-plane"></i> Kirim Email Percobaan
        </button>
        <span id="test-email-msg" style="font-size: 13px; color: #3a7d5a; display: none;"></span>
    </div>
</div>

<script>
(function () {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';

    async function loadStatus() {
        try {
            const res  = await fetch('/api/notifications/status', { cache: 'no-store' });
            const data = await res.json();
            const toggle = document.getElementById('email-toggle');
            if (data.email_enabled) toggle.classList.add('active');
            else toggle.classList.remove('active');
            const emailEl = document.getElementById('notif-email-display');
            if (emailEl) emailEl.textContent = data.email || '-';
        } catch (_) {}
    }

    window.toggleEmailNotif = async function (el) {
        el.classList.toggle('active');
        const enabled = el.classList.contains('active');
        try {
            await fetch('/api/notifications/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
                body: JSON.stringify({ enabled }),
            });
        } catch (_) {}
    };

    window.sendTestEmail = async function () {
        const btn = document.getElementById('test-email-btn');
        const msg = document.getElementById('test-email-msg');
        btn.disabled = true;
        btn.textContent = 'Mengirim...';
        try {
            const res  = await fetch('/api/notifications/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
            });
            const data = await res.json();
            msg.textContent = data.message;
            msg.style.color = data.status === 'ok' ? '#3a7d5a' : '#e53935';
            msg.style.display = 'inline';
            setTimeout(() => msg.style.display = 'none', 6000);
        } catch (_) {
            msg.textContent = 'Gagal terhubung ke server.';
            msg.style.color = '#e53935';
            msg.style.display = 'inline';
        }
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane"></i> Kirim Email Percobaan';
    };

    loadStatus();
})();
</script>
@endsection
