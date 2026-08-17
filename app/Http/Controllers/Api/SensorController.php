<?php

namespace App\Http\Controllers\Api;

use App\Events\SensorDataReceived;
use App\Http\Controllers\Controller;
use App\Models\SensorData;
use App\Services\NotificationService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class SensorController extends Controller
{
    /**
     * Accept JSON payload from ESP32 and store normalized sensor data.
     */
    public function store(Request $request): JsonResponse
    {
        $normalized = $this->normalizePayload($request);

        $data = validator($normalized, [
            'device_id' => 'nullable|string|max:100',
            'temperature' => 'required|numeric',
            'humidity' => 'nullable|numeric',
            'moisture' => 'nullable|numeric',
            'soil' => 'nullable|numeric',
            'soil_percent' => 'nullable|numeric',
            'soil_raw' => 'nullable|numeric',
            'motion' => 'nullable',
            'pir' => 'nullable',
            'ph' => 'nullable|numeric',
            'pest_status' => 'nullable|string|max:50',
            'metadata' => 'nullable|array',
        ])->validate();

        $moisture = $this->resolveMoistureValue($data);

        if ($moisture === null) {
            return response()->json([
                'message' => 'Field moisture/soil/soil_percent/soil_raw wajib dikirim.',
            ], 422);
        }

        $motion = $this->resolveBoolean($data['motion'] ?? ($data['pir'] ?? null));
        $soilRaw = $this->resolveSoilRaw($data);
        $deviceId = trim((string) ($data['device_id'] ?? 'esp32'));
        $metadata = $data['metadata'] ?? [];

        $sensor = SensorData::create([
            'temperature' => (float) $data['temperature'],
            'moisture' => $moisture,
            'humidity' => array_key_exists('humidity', $data) ? (float) $data['humidity'] : null,
            'pest_status' => $data['pest_status'] ?? $this->inferPestStatus(
                (float) $data['temperature'],
                isset($data['humidity']) ? (float) $data['humidity'] : null,
                $moisture,
                $motion
            ),
            'metadata' => array_merge($metadata, array_filter([
                'source' => 'esp32',
                'device_id' => $deviceId !== '' ? $deviceId : null,
                'motion' => $motion,
                'ph' => array_key_exists('ph', $data) ? (float) $data['ph'] : null,
                'soil_raw' => $soilRaw,
            ], static fn ($value) => ! is_null($value))),
        ]);

        $this->dispatchRealtimeEvent($sensor);

        // Kirim email notifikasi jika risiko hama tinggi
        if ($sensor->pest_status === 'high') {
            NotificationService::sendPestAlert([
                'temperature' => $sensor->temperature,
                'humidity'    => $sensor->humidity,
                'moisture'    => $sensor->moisture,
                'ph'          => $sensor->metadata['ph'] ?? null,
                'motion'      => $sensor->metadata['motion'] ?? false,
                'pest_status' => $sensor->pest_status,
            ]);
        }

        return response()->json([
            'status' => 'created',
            'id' => $sensor->id,
            'device_id' => $deviceId,
            'stored_moisture' => $sensor->moisture,
            'pest_status' => $sensor->pest_status,
        ], 201);
    }

    /**
     * Helper GET endpoint for quick local testing.
     */
    public function storeTest(Request $request): JsonResponse
    {
        $sensor = SensorData::create([
            'temperature' => (float) $request->query('temperature', 25.0),
            'moisture' => (float) $request->query('moisture', 50.0),
            'humidity' => (float) $request->query('humidity', 70.0),
            'pest_status' => $request->query('pest_status', 'low'),
            'metadata' => [
                'test' => true,
                'source' => 'test-endpoint',
                'device_id' => $request->query('device_id', 'esp32-demo'),
                'motion' => false,
                'ph' => (float) $request->query('ph', 6.5),
                'soil_raw' => (int) $request->query('soil_raw', 1840),
            ],
        ]);

        $this->dispatchRealtimeEvent($sensor);

        return response()->json([
            'status' => 'created',
            'id' => $sensor->id,
        ], 201);
    }

    /**
     * Return latest sensor record in a dashboard-friendly format.
     */
    public function latest(): JsonResponse
    {
        $sensor = SensorData::latest('created_at')->first();

        if (! $sensor) {
            return response()->json(['message' => 'No data yet'], 404);
        }

        $metadata = is_array($sensor->metadata) ? $sensor->metadata : [];
        $motion = $this->resolveBoolean($metadata['motion'] ?? null);
        $isOnline = $sensor->created_at?->gte(now()->subMinutes(5)) ?? false;

        return response()->json([
            'id' => $sensor->id,
            'device_id' => $metadata['device_id'] ?? null,
            'temperature' => $sensor->temperature,
            'moisture' => $sensor->moisture,
            'humidity' => $sensor->humidity,
            'pest_status' => $sensor->pest_status,
            'ph' => $metadata['ph'] ?? null,
            'motion' => $motion,
            'soil_raw' => $metadata['soil_raw'] ?? null,
            'created_at' => $sensor->created_at?->toIso8601String(),
            'last_seen_human' => $sensor->created_at?->diffForHumans(),
            'is_online' => $isOnline,
            'metadata' => $metadata,
        ]);
    }

    /**
     * Return payload schema and aliases to simplify ESP32 integration.
     */
    public function schema(): JsonResponse
    {
        return response()->json([
            'required' => ['temperature', 'moisture/soil/soil_raw/soil_percent'],
            'optional' => ['humidity', 'motion', 'pir', 'ph', 'device_id', 'metadata'],
            'aliases' => [
                'device_id' => ['device_id', 'deviceId'],
                'temperature' => ['temperature', 'temp'],
                'humidity' => ['humidity', 'hum'],
                'moisture' => ['moisture', 'soil_moisture'],
                'soil' => ['soil', 'soil_value'],
                'soil_percent' => ['soil_percent', 'soilPercentage'],
                'soil_raw' => ['soil_raw', 'soil_adc', 'adc'],
                'motion' => ['motion', 'motion_detected'],
                'pir' => ['pir', 'pir_state'],
                'ph' => ['ph', 'ph_value'],
            ],
            'example_payload' => [
                'device_id' => 'esp32-sawah-01',
                'temperature' => 29.4,
                'humidity' => 82.1,
                'soil_raw' => 1870,
                'motion' => false,
                'ph' => 6.4,
            ],
        ]);
    }

    private function normalizePayload(Request $request): array
    {
        return [
            'device_id' => $this->firstPresent($request, ['device_id', 'deviceId']),
            'temperature' => $this->firstPresent($request, ['temperature', 'temp']),
            'humidity' => $this->firstPresent($request, ['humidity', 'hum']),
            'moisture' => $this->firstPresent($request, ['moisture', 'soil_moisture']),
            'soil' => $this->firstPresent($request, ['soil', 'soil_value']),
            'soil_percent' => $this->firstPresent($request, ['soil_percent', 'soilPercentage']),
            'soil_raw' => $this->firstPresent($request, ['soil_raw', 'soil_adc', 'adc']),
            'motion' => $this->firstPresent($request, ['motion', 'motion_detected']),
            'pir' => $this->firstPresent($request, ['pir', 'pir_state']),
            'ph' => $this->firstPresent($request, ['ph', 'ph_value']),
            'pest_status' => $this->firstPresent($request, ['pest_status', 'pestStatus']),
            'metadata' => $request->input('metadata'),
        ];
    }

    private function firstPresent(Request $request, array $keys): mixed
    {
        foreach ($keys as $key) {
            if ($request->has($key)) {
                return $request->input($key);
            }
        }

        return null;
    }

    private function resolveMoistureValue(array $data): ?float
    {
        if (array_key_exists('moisture', $data) && $data['moisture'] !== null) {
            return $this->clampPercentage((float) $data['moisture']);
        }

        if (array_key_exists('soil_percent', $data) && $data['soil_percent'] !== null) {
            return $this->clampPercentage((float) $data['soil_percent']);
        }

        if (array_key_exists('soil_raw', $data) && $data['soil_raw'] !== null) {
            return $this->rawSoilToPercent((float) $data['soil_raw']);
        }

        if (array_key_exists('soil', $data) && $data['soil'] !== null) {
            $soil = (float) $data['soil'];

            return $soil <= 100
                ? $this->clampPercentage($soil)
                : $this->rawSoilToPercent($soil);
        }

        return null;
    }

    private function resolveSoilRaw(array $data): ?int
    {
        if (array_key_exists('soil_raw', $data) && $data['soil_raw'] !== null) {
            return (int) round((float) $data['soil_raw']);
        }

        if (array_key_exists('soil', $data) && $data['soil'] !== null && (float) $data['soil'] > 100) {
            return (int) round((float) $data['soil']);
        }

        return null;
    }

    private function rawSoilToPercent(float $rawValue): float
    {
        $wet = (float) config('esp32.soil_raw_wet', 1200);
        $dry = (float) config('esp32.soil_raw_dry', 3200);

        if ($dry <= $wet) {
            return $this->clampPercentage($rawValue);
        }

        $percent = (($dry - $rawValue) / ($dry - $wet)) * 100;

        return $this->clampPercentage($percent);
    }

    private function clampPercentage(float $value): float
    {
        return round(max(0, min(100, $value)), 2);
    }

    private function resolveBoolean(mixed $value): ?bool
    {
        if ($value === null || $value === '') {
            return null;
        }

        if (is_bool($value)) {
            return $value;
        }

        if (is_numeric($value)) {
            return (int) $value === 1;
        }

        $normalized = strtolower(trim((string) $value));

        return match ($normalized) {
            '1', 'true', 'yes', 'on', 'high', 'detected' => true,
            '0', 'false', 'no', 'off', 'low', 'clear' => false,
            default => null,
        };
    }

    private function inferPestStatus(
        float $temperature,
        ?float $humidity,
        float $moisture,
        ?bool $motion
    ): string {
        $cameraDetected = (bool) (\Illuminate\Support\Facades\Cache::get('camera_last_detection.detected')
            ?? (\Illuminate\Support\Facades\Cache::get('camera_last_detection')['detected'] ?? false));

        // PIR aktif + kamera deteksi binatang → risiko hama sangat tinggi
        if ($motion === true && $cameraDetected) {
            return 'high';
        }

        // Kondisi lingkungan mendukung hama (lembap + basah) atau gerakan saja
        if ($motion === true || ($humidity !== null && $humidity >= 85 && $moisture >= 70)) {
            return 'high';
        }

        // Kondisi lingkungan mulai tidak ideal
        if (($humidity !== null && $humidity >= 75) || $temperature > 32 || $moisture > 75 || $cameraDetected) {
            return 'medium';
        }

        return 'low';
    }

    private function dispatchRealtimeEvent(SensorData $sensor): void
    {
        try {
            event(new SensorDataReceived($sensor));
        } catch (\Throwable $e) {
            // Keep ingestion resilient even if broadcast driver is not configured yet.
            Log::warning('Sensor broadcast failed: '.$e->getMessage(), [
                'sensor_id' => $sensor->id,
            ]);
        }
    }
}
