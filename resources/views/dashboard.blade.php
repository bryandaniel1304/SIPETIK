<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard Sensor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
    <h1 class="mb-4">Dashboard Sensor</h1>

    <div class="row g-3 mb-4">
        <div class="col-md-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Suhu</h6>
                    <h2 class="card-title">{{ $latest ? $latest->temperature . ' °C' : '-' }}</h2>
                </div>
            </div>
        </div>

        <div class="col-md-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Kelembapan Tanah</h6>
                    <h2 class="card-title">{{ $latest ? $latest->moisture . ' %' : '-' }}</h2>
                </div>
            </div>
        </div>

        <div class="col-md-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Status Hama</h6>
                    @php
                        $status = $latest->pest_status ?? null;
                        $color = 'secondary';
                        if ($status) {
                            $s = strtolower($status);
                            if (in_array($s, ['high','danger','red'])) $color = 'danger';
                            elseif (in_array($s, ['medium','yellow'])) $color = 'warning';
                            else $color = 'success';
                        }
                    @endphp
                    <span class="badge bg-{{ $color }} p-3 fs-5">{{ $status ?? 'Unknown' }}</span>
                </div>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-body">
            <h5 class="card-title">Grafik 7 Hari Terakhir</h5>
            <canvas id="sensorChart" height="100"></canvas>
        </div>
    </div>
    
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
    const labels = {!! $chartLabels !!};
    const temps = {!! $chartTemps !!};
    const moistures = {!! $chartMoistures !!};

    const ctx = document.getElementById('sensorChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Suhu (°C)',
                    data: temps,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255,99,132,0.2)',
                    tension: 0.2
                },
                {
                    label: 'Kelembapan (%)',
                    data: moistures,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54,162,235,0.2)',
                    tension: 0.2
                }
            ]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: false
                }
            },
            responsive: true,
            maintainAspectRatio: false
        }
    });
</script>

</body>
</html>
