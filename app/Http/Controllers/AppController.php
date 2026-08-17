<?php

namespace App\Http\Controllers;

use App\Models\SensorData;
use Carbon\Carbon;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

class AppController extends Controller
{
    private function buildAiInsights(array $snapshot): array
    {
        $temp     = (float) ($snapshot['temperature'] ?? 0);
        $humidity = (float) ($snapshot['humidity'] ?? 0);
        $moisture = (float) ($snapshot['moisture'] ?? 0);
        $ph       = (float) ($snapshot['ph'] ?? 0);
        $motion   = (bool) ($snapshot['motion'] ?? false);

        $cameraCache    = \Illuminate\Support\Facades\Cache::get('camera_last_detection');
        $cameraDetected = (bool) ($cameraCache['detected'] ?? false);
        $animalLabel    = $cameraCache['animal_label'] ?? null;

        // Tentukan risiko hama
        $risk      = 'Rendah';
        $riskColor = '#4caf50';

        // Kondisi lingkungan mulai tidak ideal
        if (($humidity >= 75 && $temp >= 24 && $temp <= 32) || $moisture > 75 || $temp > 32) {
            $risk      = 'Sedang';
            $riskColor = '#ffb300';
        }

        // Kondisi lingkungan sangat mendukung hama
        if ($humidity >= 85 && $moisture >= 70) {
            $risk      = 'Tinggi';
            $riskColor = '#ff4757';
        }

        // Gerakan PIR saja → naik ke Sedang minimal
        if ($motion && $risk === 'Rendah') {
            $risk      = 'Sedang';
            $riskColor = '#ffb300';
        }

        // Kamera deteksi binatang saja → Sedang
        if ($cameraDetected && $risk === 'Rendah') {
            $risk      = 'Sedang';
            $riskColor = '#ffb300';
        }

        // PIR + Kamera aktif bersamaan → Tinggi (ancaman nyata)
        if ($motion && $cameraDetected) {
            $risk      = 'Tinggi';
            $riskColor = '#ff4757';
        }

        $summaryParts = [];
        $summaryParts[] = $moisture < 30 ? 'Tanah cenderung kering' : ($moisture > 70 ? 'Tanah cukup basah' : 'Kelembapan tanah stabil');
        $summaryParts[] = $temp < 20 ? 'Suhu rendah' : ($temp > 32 ? 'Suhu tinggi' : 'Suhu normal');
        $summaryParts[] = $humidity < 40 ? 'Kelembapan udara rendah' : ($humidity > 80 ? 'Kelembapan udara tinggi' : 'Kelembapan udara normal');
        if ($motion && $cameraDetected) {
            $summaryParts[] = 'Gerakan + binatang terdeteksi — kemungkinan hama tinggi';
        } elseif ($motion) {
            $summaryParts[] = 'Ada gerakan di area sensor';
        } elseif ($cameraDetected) {
            $summaryParts[] = 'Binatang terdeteksi kamera' . ($animalLabel ? " ({$animalLabel})" : '');
        }

        $recs = [];

        if ($moisture < 30) {
            $recs[] = ['title' => 'Irigasi', 'text' => 'Pertimbangkan penyiraman bertahap pagi atau sore untuk menaikkan kelembapan tanah.', 'priority' => 'high'];
        } elseif ($moisture > 80) {
            $recs[] = ['title' => 'Drainase', 'text' => 'Tanah terlalu basah, cek saluran drainase untuk mencegah busuk akar.', 'priority' => 'high'];
        } else {
            $recs[] = ['title' => 'Kelembapan Tanah', 'text' => 'Kondisi tanah relatif stabil, pertahankan jadwal irigasi seperti biasa.', 'priority' => 'low'];
        }

        if ($humidity > 80) {
            $recs[] = ['title' => 'Pencegahan Jamur', 'text' => 'Kelembapan tinggi meningkatkan risiko jamur, tingkatkan sirkulasi udara dan pantau bercak daun.', 'priority' => 'medium'];
        }

        if ($temp > 32) {
            $recs[] = ['title' => 'Stres Panas', 'text' => 'Suhu cukup tinggi, pastikan ketersediaan air dan pertimbangkan peneduh pada area rentan.', 'priority' => 'medium'];
        }

        if ($ph > 0) {
            if ($ph < 5.5) {
                $recs[] = ['title' => 'Koreksi pH', 'text' => 'pH terlalu asam, pertimbangkan pengapuran sesuai rekomendasi analisis tanah.', 'priority' => 'medium'];
            } elseif ($ph > 7.5) {
                $recs[] = ['title' => 'Koreksi pH', 'text' => 'pH terlalu basa, pertimbangkan bahan organik untuk membantu menstabilkan pH.', 'priority' => 'medium'];
            } else {
                $recs[] = ['title' => 'pH Tanah', 'text' => 'pH berada di rentang baik untuk penyerapan unsur hara.', 'priority' => 'low'];
            }
        }

        if ($motion && $cameraDetected) {
            $recs[] = [
                'title' => 'Ancaman Hama Terdeteksi',
                'text'  => 'PIR dan kamera sama-sama aktif' . ($animalLabel ? " — {$animalLabel} terdeteksi" : '') . '. Buzzer diaktifkan. Segera periksa kondisi lahan.',
                'priority' => 'high',
            ];
        } elseif ($cameraDetected) {
            $recs[] = [
                'title' => 'Binatang Terdeteksi Kamera',
                'text'  => ($animalLabel ? "{$animalLabel} terdeteksi" : 'Binatang terdeteksi') . ' oleh kamera AI. Pantau lebih lanjut, buzzer belum aktif karena PIR tidak mendeteksi gerakan.',
                'priority' => 'medium',
            ];
        } elseif ($motion) {
            $recs[] = [
                'title' => 'Gerakan Terdeteksi (PIR)',
                'text'  => 'Sensor gerak aktif namun kamera tidak mendeteksi binatang. Kemungkinan gangguan kecil atau angin.',
                'priority' => 'medium',
            ];
        }

        return [
            'risk'            => $risk,
            'riskColor'       => $riskColor,
            'summary'         => implode(' | ', $summaryParts),
            'recommendations' => $recs,
        ];
    }

    private function defaultAiInsights(): array
    {
        return [
            'risk' => 'Belum ada data',
            'riskColor' => '#616161',
            'summary' => 'Belum ada data sensor ESP32 yang masuk.',
            'recommendations' => [],
        ];
    }

    private function sensorMetadata(?SensorData $sensor): array
    {
        return $sensor && is_array($sensor->metadata) ? $sensor->metadata : [];
    }

    private function sensorBoolean(array $metadata, string $key): ?bool
    {
        if (! array_key_exists($key, $metadata)) {
            return null;
        }

        return filter_var($metadata[$key], FILTER_VALIDATE_BOOL, FILTER_NULL_ON_FAILURE);
    }

    private function rangeStatus(?float $value, float $low, float $high): array
    {
        if ($value === null) {
            return [
                'label' => 'Belum ada data',
                'color' => '#616161',
                'bg' => '#eeeeee',
            ];
        }

        if ($value < $low) {
            return [
                'label' => 'Rendah',
                'color' => '#2196f3',
                'bg' => '#e3f2fd',
            ];
        }

        if ($value > $high) {
            return [
                'label' => 'Tinggi',
                'color' => '#ff6b35',
                'bg' => '#ffe0cc',
            ];
        }

        return [
            'label' => 'Normal',
            'color' => '#2e7d32',
            'bg' => '#e8f5e9',
        ];
    }

    private function booleanStatus(?bool $value, string $activeLabel, string $inactiveLabel): array
    {
        if ($value === null) {
            return [
                'value' => '-',
                'label' => 'Belum ada data',
                'color' => '#616161',
                'bg' => '#eeeeee',
            ];
        }

        if ($value) {
            return [
                'value' => $activeLabel,
                'label' => $activeLabel,
                'color' => '#c62828',
                'bg' => '#ffebee',
            ];
        }

        return [
            'value' => $inactiveLabel,
            'label' => $inactiveLabel,
            'color' => '#2e7d32',
            'bg' => '#e8f5e9',
        ];
    }

    private function detectLanHost(): ?string
    {
        $host = gethostname();

        if (! $host) {
            return null;
        }

        $ips = gethostbynamel($host) ?: [];

        foreach ($ips as $ip) {
            if (! filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
                continue;
            }

            if (str_starts_with($ip, '127.') || str_starts_with($ip, '169.254.')) {
                continue;
            }

            return $ip;
        }

        return null;
    }

    /**
     * Dashboard page with sensor data metrics.
     */
    public function dashboard()
    {
        $latest = SensorData::latest('created_at')->first();
        $user = Auth::user();

        $tempStatus = 'Belum ada data';
        $tempStatusColor = '#616161';
        $tempStatusBackground = '#eeeeee';
        if ($latest) {
            if ($latest->temperature < 20) {
                $tempStatus = 'Rendah';
                $tempStatusColor = '#2196f3';
                $tempStatusBackground = '#e3f2fd';
            } elseif ($latest->temperature > 30) {
                $tempStatus = 'Tinggi';
                $tempStatusColor = '#ff6b35';
                $tempStatusBackground = '#ffe0cc';
            } else {
                $tempStatus = 'Normal';
                $tempStatusColor = '#2e7d32';
                $tempStatusBackground = '#e8f5e9';
            }
        }

        $metadata = $this->sensorMetadata($latest);
        $dummyPh = array_key_exists('ph', $metadata) ? (float) $metadata['ph'] : null;
        $dummyMotionDetected = $this->sensorBoolean($metadata, 'motion');
        $dummySoilRaw = array_key_exists('soil_raw', $metadata) ? (int) round((float) $metadata['soil_raw']) : null;
        $deviceId = $metadata['device_id'] ?? 'Perangkat belum terdeteksi';
        $lastSeen = $latest?->created_at?->diffForHumans() ?? 'Belum ada data';
        $isDeviceOnline = $latest?->created_at?->gte(now()->subMinutes(5)) ?? false;
        $moistureStatus = $this->rangeStatus($latest?->moisture, 30, 70);
        $humidityStatus = $this->rangeStatus($latest?->humidity, 30, 70);
        $phStatus = $dummyPh === null
            ? ['label' => 'Belum ada data', 'color' => '#616161', 'bg' => '#eeeeee']
            : (($dummyPh >= 6.0 && $dummyPh <= 7.0)
                ? ['label' => 'Ideal', 'color' => '#6a1b9a', 'bg' => '#f3e5f5']
                : ['label' => 'Perlu Penyesuaian', 'color' => '#ef6c00', 'bg' => '#fff3e0']);
        $motionStatus = $this->booleanStatus($dummyMotionDetected, 'TERDETEKSI', 'AMAN');
        $soilRawStatus = $dummySoilRaw === null
            ? ['label' => 'Belum ada data', 'color' => '#616161', 'bg' => '#eeeeee']
            : ['label' => 'Dari ESP32', 'color' => '#37474f', 'bg' => '#eceff1'];

        $ai = $latest
            ? $this->buildAiInsights([
                'temperature' => $latest->temperature,
                'humidity' => $latest->humidity,
                'moisture' => $latest->moisture,
                'ph' => $dummyPh,
                'motion' => $dummyMotionDetected ?? false,
            ])
            : $this->defaultAiInsights();

        $assistantLegend = $this->buildAssistantLegend();

        return view('app.dashboard', [
            'user' => $user,
            'latest' => $latest,
            'latestSensorId' => $latest?->id,
            'latestEndpoint' => url('/api/sensor/latest'),
            'tempStatus' => $tempStatus,
            'tempStatusColor' => $tempStatusColor,
            'tempStatusBackground' => $tempStatusBackground,
            'dummyPh' => $dummyPh,
            'dummyMotionDetected' => $dummyMotionDetected,
            'dummySoilRaw' => $dummySoilRaw,
            'moistureStatus' => $moistureStatus,
            'humidityStatus' => $humidityStatus,
            'phStatus' => $phStatus,
            'motionStatus' => $motionStatus,
            'soilRawStatus' => $soilRawStatus,
            'deviceId' => $deviceId,
            'lastSeen' => $lastSeen,
            'isDeviceOnline' => $isDeviceOnline,
            'ai' => $ai,
            'assistantLegend' => $assistantLegend,
        ]);
    }

    private function buildAssistantLegend(): array
    {
        $provider = strtolower((string) config('services.assistant.provider', 'openai'));
        $openAiKey = trim((string) config('services.openai.api_key', ''));
        $openRouterKey = trim((string) config('services.openrouter.api_key', ''));

        $legend = [
            'provider' => $provider,
            'provider_label' => 'Tidak diketahui',
            'chat_endpoint' => url('/api/assistant/ask'),
            'key_status_label' => 'Tidak dikonfigurasi',
            'has_provider_key' => false,
            'api_name' => '-',
            'model' => '-',
            'api_target' => '-',
            'note' => 'Gunakan OpenRouter atau OpenAI untuk fitur asisten pintar.',
            'setup_url' => 'https://openrouter.ai/keys',
            'activation_hint' => 'Atur ASSISTANT_PROVIDER dan API_KEY di .env Anda.',
        ];

        if ($provider === 'openrouter') {
            $legend['provider_label'] = 'OpenRouter AI';
            $legend['api_name'] = 'OpenRouter';
            $legend['model'] = config('services.openrouter.model', 'openrouter/free');
            $legend['api_target'] = 'https://openrouter.ai/api/v1';
            $legend['setup_url'] = 'https://openrouter.ai/keys';
            
            if ($openRouterKey !== '') {
                $legend['key_status_label'] = 'Aktif (OpenRouter)';
                $legend['has_provider_key'] = true;
                $legend['note'] = 'Asisten AI aktif menggunakan model OpenRouter.';
            } else {
                $legend['key_status_label'] = 'Key Kosong';
                $legend['note'] = 'OpenRouter dipilih tetapi API key belum diatur.';
            }
        } elseif ($provider === 'openai') {
            $legend['provider_label'] = 'OpenAI';
            $legend['api_name'] = 'OpenAI';
            $legend['model'] = config('services.openai.model', 'gpt-4o-mini');
            $legend['api_target'] = 'https://api.openai.com/v1';
            $legend['setup_url'] = 'https://platform.openai.com/api-keys';

            if ($openAiKey !== '') {
                $legend['key_status_label'] = 'Aktif (OpenAI)';
                $legend['has_provider_key'] = true;
                $legend['note'] = 'Asisten AI aktif menggunakan model OpenAI.';
            } else {
                $legend['key_status_label'] = 'Key Kosong';
                $legend['note'] = 'OpenAI dipilih tetapi API key belum diatur.';
            }
        }

        return $legend;
    }

    /**
     * Sensor Data page.
     */
    public function sensorData()
    {
        $user = Auth::user();
        $query = SensorData::query()->orderBy('created_at', 'desc');

        $q = request('q');
        $start = request('start');
        $end = request('end');
        $status = request('status', 'all');
        $export = request('export');

        // Cek apakah ada filter yang aktif untuk membedakan antara "tidak ada data" dan "hasil filter kosong"
        $isFiltered = $q || $start || $end || ($status !== 'all');

        $dummySensors = [
            [
                'id' => 'D-001',
                'created_at' => now()->subMinutes(15),
                'temperature' => 27.4,
                'moisture' => 41.0,
                'humidity' => 78.0,
                'ph' => 6.5,
                'motion' => false,
                'pest_status' => 'low',
            ],
            [
                'id' => 'D-002',
                'created_at' => now()->subMinutes(5),
                'temperature' => 30.2,
                'moisture' => 29.0,
                'humidity' => 84.0,
                'ph' => 5.6,
                'motion' => true,
                'pest_status' => 'medium',
            ],
        ];

        if ($q) {
            $query->where(function ($sub) use ($q) {
                $sub->where('id', $q)
                    ->orWhere('pest_status', 'like', "%{$q}%")
                    ->orWhereRaw('CAST(temperature AS CHAR) LIKE ?', ["%{$q}%"])
                    ->orWhereRaw('CAST(moisture AS CHAR) LIKE ?', ["%{$q}%"])
                    ->orWhereRaw('CAST(humidity AS CHAR) LIKE ?', ["%{$q}%"])
                    ->orWhere('metadata', 'like', "%{$q}%");
            });
        }

        if ($start) {
            try {
                $startDt = Carbon::parse($start)->startOfDay();
                $query->where('created_at', '>=', $startDt);
            } catch (\Exception $e) {
                // Ignore invalid date.
            }
        }

        if ($end) {
            try {
                $endDt = Carbon::parse($end)->endOfDay();
                $query->where('created_at', '<=', $endDt);
            } catch (\Exception $e) {
                // Ignore invalid date.
            }
        }

        if ($status && $status !== 'all') {
            if ($status === 'safe') {
                $query->where('pest_status', 'low');
            } elseif ($status === 'medium') {
                $query->where('pest_status', 'medium');
            } elseif ($status === 'high') {
                $query->where('pest_status', 'high');
            }
        }

        if ($export) {
            $items = $query->get();
            $filename = 'sensor-data-'.now()->format('YmdHis').'.xls';
            $headers = [
                'Content-Type' => 'application/vnd.ms-excel; charset=UTF-8',
                'Content-Disposition' => "attachment; filename=\"{$filename}\"",
            ];

            $callback = function () use ($items, $dummySensors) {
                echo "\xEF\xBB\xBF";
                echo '<table border="1">';
                echo '<thead><tr>';
                foreach (['ID', 'Waktu', 'Suhu (C)', 'Kelembapan Tanah (%)', 'Kelembapan Udara (%)', 'pH', 'Gerakan', 'Status', 'Metadata'] as $h) {
                    echo '<th>'.htmlspecialchars($h, ENT_QUOTES, 'UTF-8').'</th>';
                }
                echo '</tr></thead><tbody>';

                foreach ($items as $row) {
                    $meta = is_array($row->metadata) ? $row->metadata : [];
                    $ph = $meta['ph'] ?? null;
                    $motion = array_key_exists('motion', $meta) ? (bool) $meta['motion'] : null;
                    echo '<tr>';
                    echo '<td>'.htmlspecialchars((string) $row->id, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars((string) $row->created_at, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars((string) $row->temperature, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars((string) $row->moisture, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars(is_null($row->humidity) ? '' : (string) $row->humidity, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars(is_null($ph) ? '' : (string) $ph, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars(is_null($motion) ? '' : ($motion ? 'GERAK' : 'AMAN'), ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars((string) $row->pest_status, ENT_QUOTES, 'UTF-8').'</td>';
                    echo '<td>'.htmlspecialchars(json_encode($row->metadata, JSON_UNESCAPED_UNICODE), ENT_QUOTES, 'UTF-8').'</td>';
                    echo '</tr>';
                }

                if ($items->isEmpty()) {
                    foreach ($dummySensors as $d) {
                        echo '<tr>';
                        echo '<td>'.htmlspecialchars((string) $d['id'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars((string) $d['created_at'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars((string) $d['temperature'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars((string) $d['moisture'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars((string) $d['humidity'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars((string) $d['ph'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars($d['motion'] ? 'GERAK' : 'AMAN', ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td>'.htmlspecialchars((string) $d['pest_status'], ENT_QUOTES, 'UTF-8').'</td>';
                        echo '<td></td>';
                        echo '</tr>';
                    }
                }

                echo '</tbody></table>';
            };

            return response()->stream($callback, 200, $headers);
        }

        // Tambahkan withQueryString() agar filter tetap terbawa saat paginasi
        $sensors = $query->paginate(10)->withQueryString();

        // Tampilkan data dummy hanya jika tidak ada filter dan tabel benar-benar kosong
        $showDummySensors = !$isFiltered && $sensors->total() === 0;

        return view('app.sensor-data', [
            'user' => $user,
            'sensors' => $sensors,
            'dummySensors' => $dummySensors,
            'showDummySensors' => $showDummySensors,
        ]);
    }

    /**
     * Hama Alerts page.
     */
    public function hamaAlerts(Request $request)
    {
        $user   = Auth::user();
        $filter = $request->query('filter', 'all');   // all | high | medium | low
        $search = trim($request->query('search', '')); // free text

        $query = SensorData::orderBy('created_at', 'desc')
            ->whereNotNull('pest_status');

        if (in_array($filter, ['high', 'medium', 'low'])) {
            $query->where('pest_status', $filter);
        }

        if ($search !== '') {
            $query->where(function ($q) use ($search) {
                $q->where('pest_status', 'like', "%{$search}%")
                  ->orWhereRaw('CAST(temperature AS CHAR) LIKE ?', ["%{$search}%"])
                  ->orWhereRaw('CAST(moisture AS CHAR) LIKE ?', ["%{$search}%"]);
            });
        }

        $alerts = $query->paginate(15)->withQueryString();

        return view('app.hama-alerts', [
            'user'   => $user,
            'alerts' => $alerts,
            'filter' => $filter,
            'search' => $search,
        ]);
    }

    /**
     * Settings page.
     */
    public function settings(Request $request)
    {
        $user = Auth::user();

        $irrigationConfig = [
            'mode' => 'auto_interval',
            'interval_hours' => 12,
            'interval_days' => 0,
            'duration_minutes' => 15,
            'moisture_threshold' => 35,
        ];

        $baseUrl = rtrim(url('/'), '/');
        $postUrl = $baseUrl.'/api/sensor';
        $latestUrl = $baseUrl.'/api/sensor/latest';
        $testUrl = $baseUrl.'/api/sensor/test';
        $schemaUrl = $baseUrl.'/api/sensor/schema';

        $parsed = parse_url($baseUrl);
        $host = $parsed['host'] ?? null;
        $scheme = $parsed['scheme'] ?? $request->getScheme();
        $port = isset($parsed['port']) ? ':'.$parsed['port'] : '';
        $path = isset($parsed['path']) ? rtrim($parsed['path'], '/') : '';
        $lanHost = $this->detectLanHost();
        $lanBaseUrl = $lanHost ? "{$scheme}://{$lanHost}{$port}{$path}" : null;
        $lanPostUrl = $lanBaseUrl ? "{$lanBaseUrl}/api/sensor" : null;
        $lanLatestUrl = $lanBaseUrl ? "{$lanBaseUrl}/api/sensor/latest" : null;
        $usesLocalhost = in_array($host, ['localhost', '127.0.0.1', '::1'], true);

        $recommendedPostUrl = ($usesLocalhost && $lanPostUrl) ? $lanPostUrl : $postUrl;
        $recommendedLatestUrl = ($usesLocalhost && $lanLatestUrl) ? $lanLatestUrl : $latestUrl;

        $esp32Guide = [
            'post_url' => $postUrl,
            'latest_url' => $latestUrl,
            'test_url' => $testUrl,
            'schema_url' => $schemaUrl,
            'lan_post_url' => $lanPostUrl,
            'lan_latest_url' => $lanLatestUrl,
            'recommended_post_url' => $recommendedPostUrl,
            'recommended_latest_url' => $recommendedLatestUrl,
            'serial_command' => 'php artisan esp32:serial-bridge [PORT] 115200',
            'soil_raw_wet' => config('esp32.soil_raw_wet'),
            'soil_raw_dry' => config('esp32.soil_raw_dry'),
            'sample_payload' => json_encode([
                'device_id' => 'esp32-sawah-01',
                'temperature' => 29.4,
                'humidity' => 82.1,
                'soil_raw' => 1870,
                'motion' => false,
                'ph' => 6.4,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES),
            'sample_code' => implode("\n", [
                '#include <WiFi.h>',
                '#include <HTTPClient.h>',
                '#include <ArduinoJson.h>',
                '',
                'const char* serverUrl = "'.$recommendedPostUrl.'";',
                '',
                'void sendData(float temperature, float humidity, int soilRaw, bool motion, float ph) {',
                '  HTTPClient http;',
                '  http.begin(serverUrl);',
                '  http.addHeader("Content-Type", "application/json");',
                '',
                '  StaticJsonDocument<256> doc;',
                '  doc["device_id"] = "esp32-sawah-01";',
                '  doc["temperature"] = temperature;',
                '  doc["humidity"] = humidity;',
                '  doc["soil_raw"] = soilRaw;',
                '  doc["motion"] = motion;',
                '  doc["ph"] = ph;',
                '',
                '  String body;',
                '  serializeJson(doc, body);',
                '  int statusCode = http.POST(body);',
                '  http.end();',
                '}',
            ]),
            'uses_localhost' => $usesLocalhost,
            'sensors_used' => [
                'temperature',
                'humidity',
                'soil_raw atau moisture',
                'motion (PIR)',
                'ph',
            ],
        ];

        return view('app.settings', [
            'user' => $user,
            'irrigation' => $irrigationConfig,
            'esp32Guide' => $esp32Guide,
        ]);
    }
}
