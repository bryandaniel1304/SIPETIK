<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\SensorData;
use App\Services\NotificationService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;

class CameraController extends Controller
{
    private string $commandFile;

    public function __construct()
    {
        $this->commandFile = storage_path('app/buzzer_command.txt');
    }

    /**
     * Receive animal detection event from Python script.
     * Triggers ESP32 buzzer immediately via command file.
     */
    public function motion(Request $request): JsonResponse
    {
        $request->validate([
            'detected'     => 'required|boolean',
            'animal_class' => 'nullable|string|max:50',
            'confidence'   => 'nullable|numeric|min:0|max:1',
            'device_id'    => 'nullable|string|max:100',
        ]);

        $detected = (bool) $request->input('detected');
        $animal   = $request->input('animal_class', 'unknown');
        $conf     = (float) $request->input('confidence', 0.0);
        $label    = $this->animalLabel($animal);

        Cache::put('camera_last_detection', [
            'detected'       => $detected,
            'animal_class'   => $animal,
            'animal_label'   => $label,
            'confidence'     => $conf,
            'device_id'      => $request->input('device_id', 'laptop-camera'),
            'detected_at'    => now()->toIso8601String(),
            'detected_human' => now()->timezone('Asia/Jakarta')->diffForHumans(),
        ], now()->addMinutes(5));

        $buzzerTriggered = false;
        $pirActive       = false;
        $envRisky        = false;

        if ($detected) {
            $latest    = SensorData::latest('created_at')->first();
            $pirActive = (bool) ($latest?->metadata['motion'] ?? false);
            $envRisky  = $latest ? $this->hasRiskyEnvironment($latest) : false;

            // Kamera mendeteksi binatang → buzzer 3 detik (PIR tidak wajib)
            // Hanya diblokir saat override aktif
            if (!Cache::get('buzzer_override_active', false)) {
                File::put($this->commandFile, "@CMD:BUZZER:TRIGGER|3");
                $buzzerTriggered = true;

                NotificationService::sendAnimalAlert([
                    'animal_class'  => $animal,
                    'animal_label'  => $label,
                    'confidence'    => $conf,
                    'detected_at'   => now()->timezone('Asia/Jakarta')->format('d M Y, H:i:s'),
                ]);
            }
        }

        return response()->json([
            'status'           => 'ok',
            'detected'         => $detected,
            'animal_class'     => $animal,
            'animal_label'     => $label,
            'pir_active'       => $pirActive,
            'env_risky'        => $envRisky,
            'buzzer_triggered' => $buzzerTriggered,
        ]);
    }

    /**
     * Periodic heartbeat from Python script to signal it is running.
     * Cache TTL = 60s — if no heartbeat for 60s, camera shown as offline.
     */
    public function heartbeat(Request $request): JsonResponse
    {
        Cache::put('camera_heartbeat', [
            'device_id' => $request->input('device_id', 'laptop-camera'),
            'at'        => now()->toIso8601String(),
        ], now()->addSeconds(60));

        return response()->json(['status' => 'ok']);
    }

    /**
     * Dashboard polls this every 2 seconds to show camera status.
     */
    public function status(): JsonResponse
    {
        $heartbeat = Cache::get('camera_heartbeat');
        $detection = Cache::get('camera_last_detection');

        // Refresh human-readable time on each poll
        if ($detection && isset($detection['detected_at'])) {
            $detection['detected_human'] = now()
                ->timezone('Asia/Jakarta')
                ->diffForHumans(\Carbon\Carbon::parse($detection['detected_at'])->timezone('Asia/Jakarta'));
        }

        return response()->json([
            'camera_online'  => $heartbeat !== null,
            'device_id'      => $heartbeat['device_id'] ?? null,
            'last_heartbeat' => $heartbeat['at'] ?? null,
            'detection'      => $detection,
        ]);
    }

    /**
     * Cek apakah kondisi lingkungan menunjukkan risiko hama berdasarkan sensor.
     * Buzzer hanya menyala bila kondisi ini TRUE sekaligus dengan kamera + PIR.
     */
    private function hasRiskyEnvironment(SensorData $sensor): bool
    {
        $temp  = $sensor->temperature;
        $hum   = $sensor->humidity;
        $moist = $sensor->moisture;
        $meta  = is_array($sensor->metadata) ? $sensor->metadata : [];
        $ph    = $meta['ph'] ?? null;

        if ($temp  !== null && ($temp  > 32 || $temp  < 18))  return true;
        if ($hum   !== null && $hum   > 75)                    return true;
        if ($moist !== null && ($moist > 75 || $moist < 20))   return true;
        if ($ph    !== null && ($ph    < 5.5 || $ph    > 7.5)) return true;

        return false;
    }

    private function animalLabel(?string $class): string
    {
        return match ($class) {
            null, '', 'none' => '-',

            // Hama sawah — kelas custom model SIPETIK (best.pt)
            'rat', 'tikus'                    => 'Tikus',
            'walang_sangit', 'walang-sangit'  => 'Walang Sangit',
            'wereng_coklat', 'wereng-coklat',
            'brown_planthopper'               => 'Wereng Batang Coklat',
            'ulat_grayak', 'ulat-grayak',
            'armyworm'                         => 'Ulat Grayak',
            'keong_mas', 'keong-mas',
            'golden_apple_snail'               => 'Keong Mas',

            // Fallback — kelas bawaan COCO (dipakai bila best.pt tidak
            // ditemukan dan script jatuh balik ke yolov8n.pt)
            'bird'     => 'Burung',
            'cat'      => 'Kucing',
            'dog'      => 'Anjing',
            'horse'    => 'Kuda',
            'sheep'    => 'Kambing/Domba',
            'cow'      => 'Sapi',
            'elephant' => 'Gajah',
            'bear'     => 'Beruang',
            'zebra'    => 'Zebra',
            'giraffe'  => 'Jerapah',

            default    => ucfirst(str_replace(['_', '-'], ' ', $class)),
        };
    }
}
