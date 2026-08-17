
@props(['type' => 'dashboard'])

<div class="card shadow-sm border-0 mb-4 bg-light">
    <div class="card-body py-3">
        <div class="d-flex align-items-center gap-2 mb-2 text-dark">
            <i class="fas fa-info-circle text-primary"></i>
            <span class="small fw-bold text-uppercase tracking-wider">Keterangan Status</span>
        </div>
        
        @if($type === 'dashboard' || $type === 'sensor' || $type === 'settings' || $type === 'status')
        <div class="row g-3">
            <div class="col-md-3 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-success-subtle text-success border border-success px-2 py-1" style="min-width: 60px;">Aman</span>
                    <span class="small text-muted">Kondisi ideal / normal</span>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-warning-subtle text-warning border border-warning px-2 py-1" style="min-width: 60px;">Sedang</span>
                    <span class="small text-muted">Waspada / Perlu pantauan</span>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-danger-subtle text-danger border border-danger px-2 py-1" style="min-width: 60px;">Bahaya</span>
                    <span class="small text-muted">Risiko tinggi / Serangan</span>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-danger-subtle text-danger border border-danger px-2 py-1" style="min-width: 60px;">Gerak</span>
                    <span class="small text-muted">Aktivitas terdeteksi</span>
                </div>
            </div>
            <div class="col-md-3 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <i class="fas fa-seedling text-success"></i>
                    <span class="small text-muted">Smart Agriculture Monitor</span>
                </div>
            </div>
        </div>
        @endif

        @if($type === 'hama')
        <div class="row g-3">
            <div class="col-md-4 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-success-subtle text-success border border-success px-3 py-1">Rendah</span>
                    <span class="small text-muted">Aman (Tidak ada indikasi)</span>
                </div>
            </div>
            <div class="col-md-4 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-warning-subtle text-warning border border-warning px-3 py-1">Sedang</span>
                    <span class="small text-muted">Waspada (Indikasi awal)</span>
                </div>
            </div>
            <div class="col-md-4 col-sm-6">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge rounded-pill bg-danger-subtle text-danger border border-danger px-3 py-1">Tinggi</span>
                    <span class="small text-muted">Bahaya (Serangan tinggi)</span>
                </div>
            </div>
        </div>
        @endif
    </div>
</div>
