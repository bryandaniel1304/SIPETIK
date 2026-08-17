@extends('layouts.app')

@section('title', 'Data Sensor')
@section('page-title', 'Data Sensor')
@section('breadcrumb', 'Beranda / Data Sensor')

@section('content')
<div class="container-fluid py-4">

    {{-- Page Header --}}
    <div class="mb-4">
        <h2 class="h4 fw-normal text-dark">Data Sensor</h2>
        <p class="text-muted small">Riwayat data yang terekam dari perangkat sensor ESP32.</p>
    </div>

    {{-- Legends (sesuai TODO.md) --}}
    <div class="mb-4">
        @include('components.legends', ['type' => 'status'])
    </div>

    {{-- Filters and Actions --}}
    <div class="card shadow-sm border-0 mb-4">
        <div class="card-body">
            <form action="{{ url('/app/sensor-data') }}" method="GET">
                <div class="row g-3 align-items-end">
                    {{-- Search Input --}}
                    <div class="col-md-3">
                        <label for="q" class="form-label small fw-bold text-muted">Pencarian</label>
                        <input type="text" name="q" id="q" value="{{ request('q') }}" placeholder="Cari ID, status, nilai..." class="form-control">
                    </div>

                    {{-- Status Filter --}}
                    <div class="col-md-2">
                        <label for="status" class="form-label small fw-bold text-muted">Status Hama</label>
                        <select name="status" id="status" class="form-select">
                            <option value="all" @if(request('status', 'all') == 'all') selected @endif>Semua</option>
                            <option value="safe" @if(request('status') == 'safe') selected @endif>Rendah</option>
                            <option value="medium" @if(request('status') == 'medium') selected @endif>Sedang</option>
                            <option value="high" @if(request('status') == 'high') selected @endif>Tinggi</option>
                        </select>
                    </div>

                    {{-- Date Filters --}}
                    <div class="col-md-2">
                        <label for="start" class="form-label small fw-bold text-muted">Dari Tanggal</label>
                        <input type="date" name="start" id="start" value="{{ request('start') }}" class="form-control">
                    </div>
                    <div class="col-md-2">
                        <label for="end" class="form-label small fw-bold text-muted">Sampai Tanggal</label>
                        <input type="date" name="end" id="end" value="{{ request('end') }}" class="form-control">
                    </div>

                    {{-- Action Buttons --}}
                    <div class="col-md-3 d-flex gap-2">
                        <button type="submit" class="btn btn-primary flex-grow-1">
                            <i class="fas fa-filter me-1"></i> Filter
                        </button>
                        <a href="{{ url('/app/sensor-data') }}" class="btn btn-outline-secondary">
                            Reset
                        </a>
                        <button type="submit" name="export" value="true" class="btn btn-success">
                            <i class="fas fa-file-export me-1"></i> Ekspor
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </div>

    {{-- Table Container --}}
    <div class="card shadow-sm border-0">
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead class="table-light">
                    <tr>
                        <th class="px-4 py-3 text-muted small text-uppercase">Waktu</th>
                        <th class="px-3 py-3 text-muted small text-uppercase">Suhu (°C)</th>
                        <th class="px-3 py-3 text-muted small text-uppercase">Tanah (%)</th>
                        <th class="px-3 py-3 text-muted small text-uppercase">Udara (%)</th>
                        <th class="px-3 py-3 text-muted small text-uppercase">pH</th>
                        <th class="px-3 py-3 text-muted small text-uppercase">Gerakan</th>
                        <th class="px-3 py-3 text-muted small text-uppercase text-center">Status Hama</th>
                        <th class="px-4 py-3 text-muted small text-uppercase text-end">ID</th>
                    </tr>
                </thead>
                <tbody>
                    @if($showDummySensors)
                        @foreach($dummySensors as $sensor)
                            <tr class="opacity-75">
                                <td class="px-4 py-3 small text-muted">{{ $sensor['created_at']->format('d M Y, H:i') }}</td>
                                <td class="px-3 py-3 fw-bold">{{ $sensor['temperature'] }}</td>
                                <td class="px-3 py-3 fw-bold">{{ $sensor['moisture'] }}</td>
                                <td class="px-3 py-3 fw-bold">{{ $sensor['humidity'] }}</td>
                                <td class="px-3 py-3 fw-bold">{{ $sensor['ph'] }}</td>
                                <td class="px-3 py-3">
                                    @if($sensor['motion'])
                                        <span class="badge rounded-pill bg-danger-subtle text-danger">TERDETEKSI</span>
                                    @else
                                        <span class="badge rounded-pill bg-success-subtle text-success">AMAN</span>
                                    @endif
                                </td>
                                <td class="px-3 py-3 text-center">
                                    @php
                                        $badgeClass  = 'bg-success-subtle text-success';
                                        $badgeLabel  = 'Rendah';
                                        if ($sensor['pest_status'] == 'medium') { $badgeClass = 'bg-warning-subtle text-warning'; $badgeLabel = 'Sedang'; }
                                        if ($sensor['pest_status'] == 'high')   { $badgeClass = 'bg-danger-subtle text-danger';  $badgeLabel = 'Tinggi'; }
                                    @endphp
                                    <span class="badge rounded-pill {{ $badgeClass }} px-3">{{ $badgeLabel }}</span>
                                </td>
                                <td class="px-4 py-3 text-end text-muted small">{{ $sensor['id'] }}</td>
                            </tr>
                        @endforeach
                        <tr>
                            <td colspan="8" class="text-center py-5">
                                <div class="text-muted">
                                    <i class="fas fa-info-circle mb-2 d-block fs-3"></i>
                                    <p class="mb-0 fw-bold">Menampilkan data contoh.</p>
                                    <p class="small">Belum ada data sensor yang masuk. Pastikan perangkat ESP32 Anda online.</p>
                                </div>
                            </td>
                        </tr>
                    @else
                        @forelse($sensors as $sensor)
                            @php
                                $metadata = is_array($sensor->metadata) ? $sensor->metadata : [];
                                $ph = $metadata['ph'] ?? null;
                                $motion = isset($metadata['motion']) ? filter_var($metadata['motion'], FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE) : null;
                            @endphp
                            <tr>
                                <td class="px-4 py-3 small text-muted">{{ $sensor->created_at->format('d M Y, H:i') }}</td>
                                <td class="px-3 py-3 fw-bold">{{ number_format($sensor->temperature, 1) }}</td>
                                <td class="px-3 py-3 fw-bold">{{ number_format($sensor->moisture, 1) }}</td>
                                <td class="px-3 py-3 fw-bold">{{ number_format($sensor->humidity, 1) }}</td>
                                <td class="px-3 py-3 fw-bold">{{ $ph !== null ? number_format($ph, 1) : '-' }}</td>
                                <td class="px-3 py-3">
                                    @if($motion === null)
                                        <span class="text-muted small">-</span>
                                    @elseif($motion)
                                        <span class="badge rounded-pill bg-danger-subtle text-danger">TERDETEKSI</span>
                                    @else
                                        <span class="badge rounded-pill bg-success-subtle text-success">AMAN</span>
                                    @endif
                                </td>
                                <td class="px-3 py-3 text-center">
                                    @php
                                        $badgeClass = 'bg-secondary-subtle text-secondary';
                                        $badgeLabel = 'N/A';
                                        if ($sensor->pest_status == 'low')    { $badgeClass = 'bg-success-subtle text-success'; $badgeLabel = 'Rendah'; }
                                        if ($sensor->pest_status == 'medium') { $badgeClass = 'bg-warning-subtle text-warning'; $badgeLabel = 'Sedang'; }
                                        if ($sensor->pest_status == 'high')   { $badgeClass = 'bg-danger-subtle text-danger';   $badgeLabel = 'Tinggi'; }
                                    @endphp
                                    <span class="badge rounded-pill {{ $badgeClass }} px-3">{{ $badgeLabel }}</span>
                                </td>
                                <td class="px-4 py-3 text-end text-muted small">{{ $sensor->id }}</td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="8" class="text-center py-5 text-muted">
                                    <i class="fas fa-search mb-2 d-block fs-3"></i>
                                    <p class="mb-0">Tidak ada data sensor yang cocok.</p>
                                    <p class="small">Coba sesuaikan filter atau <a href="{{ url('/app/sensor-data') }}" class="text-primary text-decoration-none fw-bold">reset filter</a>.</p>
                                </td>
                            </tr>
                        @endforelse
                    @endif
                </tbody>
            </table>
        </div>
    </div>

    {{-- Pagination --}}
    @if(!$showDummySensors && $sensors->hasPages())
    <div class="mt-5 d-flex justify-content-center pagination-wrapper">
        <div class="shadow-sm p-2 bg-white rounded-pill px-4">
            {{ $sensors->links() }}
        </div>
    </div>
    @endif

    <style>
        .pagination {
            margin-bottom: 0;
            gap: 5px;
        }
        .page-item .page-link {
            border-radius: 50% !important;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            color: #3a7d5a;
            font-weight: 600;
            transition: all 0.3s;
        }
        .page-item.active .page-link {
            background-color: #3a7d5a;
            color: white;
            box-shadow: 0 4px 10px rgba(58, 125, 90, 0.3);
        }
        .page-item .page-link:hover {
            background-color: #e8f5e9;
            color: #2d5f47;
        }
        .page-item.disabled .page-link {
            background-color: transparent;
            color: #ccc;
        }
        /* Hide "Showing X to Y of Z results" text if it's too much */
        .pagination-wrapper nav > div:first-child {
            display: none !important;
        }
        .pagination-wrapper nav > div:last-child {
            margin-bottom: 0 !important;
        }
    </style>
</div>
@endsection
