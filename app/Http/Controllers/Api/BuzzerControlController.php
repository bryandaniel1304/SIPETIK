<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\BuzzerSetting;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;

class BuzzerControlController extends Controller
{
    private string $commandFile;

    private string $responseFile;

    public function __construct()
    {
        $this->commandFile = storage_path('app/buzzer_command.txt');
        $this->responseFile = storage_path('app/buzzer_response.txt');
    }

    public function on(): JsonResponse
    {
        if (Cache::get('buzzer_override_active', false)) {
            return response()->json([
                'status'  => 'blocked',
                'message' => 'Override aktif. Buzzer tidak bisa dinyalakan.',
            ], 403);
        }

        $this->writeCommand('BUZZER:ON');

        return response()->json([
            'status'    => 'ok',
            'command'   => 'BUZZER:ON',
            'timestamp' => now()->timezone('Asia/Jakarta')->toIso8601String(),
            'message'   => 'Buzzer dinyalakan.',
        ]);
    }

    public function off(): JsonResponse
    {
        $this->writeCommand('BUZZER:OFF');

        return response()->json([
            'status'    => 'ok',
            'command'   => 'BUZZER:OFF',
            'timestamp' => now()->timezone('Asia/Jakarta')->toIso8601String(),
            'message'   => 'Buzzer dimatikan.',
        ]);
    }

    public function trigger(): JsonResponse
    {
        if (Cache::get('buzzer_override_active', false)) {
            return response()->json([
                'status'  => 'blocked',
                'message' => 'Override aktif. Buzzer tidak bisa dinyalakan.',
            ], 403);
        }

        $this->writeCommand('BUZZER:TRIGGER');

        return response()->json([
            'status'    => 'ok',
            'command'   => 'BUZZER:TRIGGER',
            'timestamp' => now()->timezone('Asia/Jakarta')->toIso8601String(),
            'message'   => 'Buzzer dibunyikan sesuai pengaturan.',
        ]);
    }

    public function setOverride(Request $request): JsonResponse
    {
        $active = (bool) $request->input('active', false);
        Cache::put('buzzer_override_active', $active, now()->addDays(7));

        if ($active) {
            // Matikan buzzer seketika saat override diaktifkan
            $this->writeCommand('BUZZER:OFF');
        }

        return response()->json([
            'status'          => 'ok',
            'override_active' => $active,
            'message'         => $active
                ? 'Override aktif. Buzzer dimatikan dan dikunci.'
                : 'Override dinonaktifkan. Buzzer kembali normal.',
        ]);
    }

    public function status(): JsonResponse
    {
        $this->writeCommand('STATUS');

        return response()->json([
            'status' => 'ok',
            'command' => 'STATUS',
            'message' => 'Status diminta.',
        ]);
    }

    public function getStatus(): JsonResponse
    {
        $setting = BuzzerSetting::getOrCreate();
        $wibTime = now()->timezone('Asia/Jakarta');

        // Get last response from ESP32 if available
        $esp32Status = null;
        if (File::exists($this->responseFile)) {
            $content = File::get($this->responseFile);
            $esp32Status = json_decode($content, true);
            File::delete($this->responseFile);
        }

        $nextDue = null;
        if ($setting->use_interval) {
            $lastTriggered = Cache::get('buzzer_last_triggered');
            $intervalSeconds = ($setting->interval_minutes * 60) + $setting->interval_seconds;
            if ($lastTriggered) {
                $nextDue = $lastTriggered + $intervalSeconds;
            }
        }

        return response()->json([
            'status' => 'ok',
            'buzzer' => [
                'enabled'          => $setting->enabled,
                'buzzer_mode'      => $setting->buzzer_mode ?? 'manual',
                'buzzer_on'        => $esp32Status['buzzer_on'] ?? false,
                'override_active'  => (bool) Cache::get('buzzer_override_active', false),
                'interval_minutes' => $setting->interval_minutes,
                'interval_seconds' => $setting->interval_seconds,
                'use_interval'     => $setting->use_interval,
                'schedule_enabled' => $setting->schedule_enabled,
                'schedule_start'   => $setting->schedule_start ?? '06:00',
                'schedule_end'     => $setting->schedule_end   ?? '18:00',
                'pest_risk_trigger' => $setting->pest_risk_trigger,
                'duration_seconds' => $setting->duration_seconds,
                'schedule_times'   => $setting->schedule_times ?? [],
            ],
            'time' => [
                'wib' => $wibTime->format('Y-m-d H:i:s'),
                'wib_formatted' => $wibTime->format('d M Y, H:i:s').' WIB',
                'timezone' => 'Asia/Jakarta (UTC+7)',
            ],
            'next_due' => $nextDue ? date('H:i:s', $nextDue) : null,
        ]);
    }

    public function updateSettings(Request $request): JsonResponse
    {
        $request->validate([
            'enabled'          => 'boolean',
            'buzzer_mode'      => 'string|in:manual,auto',
            'interval_minutes' => 'integer|min:0|max:1440',
            'interval_seconds' => 'integer|min:0|max:59',
            'use_interval'     => 'boolean',
            'schedule_enabled' => 'boolean',
            'schedule_times'   => 'array',
            'schedule_start'   => 'nullable|string|regex:/^\d{2}:\d{2}$/',
            'schedule_end'     => 'nullable|string|regex:/^\d{2}:\d{2}$/',
            'pest_risk_trigger' => 'boolean',
            'duration_seconds' => 'integer|min:1|max:60',
        ]);

        $setting = BuzzerSetting::getOrCreate();
        $setting->update($request->only([
            'enabled',
            'buzzer_mode',
            'interval_minutes',
            'interval_seconds',
            'use_interval',
            'schedule_enabled',
            'schedule_times',
            'schedule_start',
            'schedule_end',
            'pest_risk_trigger',
            'duration_seconds',
        ]));

        return response()->json([
            'status' => 'ok',
            'message' => 'Pengaturan buzzer berhasil diperbarui.',
            'settings' => [
                'enabled' => $setting->enabled,
                'interval_minutes' => $setting->interval_minutes,
                'interval_seconds' => $setting->interval_seconds,
                'use_interval' => $setting->use_interval,
                'schedule_enabled' => $setting->schedule_enabled,
                'pest_risk_trigger' => $setting->pest_risk_trigger,
                'duration_seconds' => $setting->duration_seconds,
                'schedule_times' => $setting->schedule_times ?? [],
            ],
        ]);
    }

    /**
     * ESP32 polls this endpoint to receive pending commands.
     * Returns one command (manual or auto-scheduled) then clears it.
     */
    public function getCommand(): JsonResponse
    {
        $command  = null;
        $duration = null;
        $override = (bool) Cache::get('buzzer_override_active', false);

        // 1. Manual command written by dashboard buttons or camera detector
        if (File::exists($this->commandFile)) {
            $raw = trim(File::get($this->commandFile));
            File::delete($this->commandFile);

            if (str_starts_with($raw, '@CMD:')) {
                $cmdPart = substr($raw, 5);
                if (str_contains($cmdPart, '|')) {
                    [$parsedCmd, $durStr] = explode('|', $cmdPart, 2);
                    $duration = (int) $durStr;
                } else {
                    $parsedCmd = $cmdPart;
                }

                // Override aktif: buang semua perintah NYALA, izinkan MATI
                if ($override && in_array($parsedCmd, ['BUZZER:ON', 'BUZZER:TRIGGER'], true)) {
                    $command  = 'BUZZER:OFF';
                    $duration = null;
                } else {
                    $command = $parsedCmd;
                }
            }
        }

        // 2. Auto-trigger (interval / schedule / pest risk) jika tidak ada perintah manual
        if ($command === null) {
            if ($override) {
                // Override aktif → selalu kirim OFF agar ESP32 tetap mati
                $command = 'BUZZER:OFF';
            } else {
                $setting = BuzzerSetting::getActive();
                if ($setting) {
                    $latest   = \App\Models\SensorData::latest('created_at')->first();
                    $pestRisk = $latest?->pest_status;

                    if ($setting->shouldTrigger($pestRisk)) {
                        $command  = 'BUZZER:TRIGGER';
                        $duration = $setting->duration_seconds;
                        $setting->markTriggered();
                    }
                }
            }
        }

        // Resolve duration untuk TRIGGER
        if ($command === 'BUZZER:TRIGGER' && $duration === null) {
            $duration = BuzzerSetting::getActive()?->duration_seconds ?? 3;
        }

        return response()->json([
            'command'  => $command,
            'duration' => $duration,
        ]);
    }

    private function writeCommand(string $command): void
    {
        $cmd = "@CMD:{$command}";
        File::put($this->commandFile, $cmd);
    }
}
