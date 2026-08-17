<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;

class Esp32SerialBridge extends Command
{
    protected $signature = 'esp32:serial-bridge {port=COM14} {baud=115200}';

    protected $description = 'Membaca data JSON dari ESP32 (USB Serial) dan mengirimnya ke API dasbor';

    private string $commandFile;

    private string $responseFile;

    private $handle;

    public function handle(): int
    {
        $port = strtoupper($this->argument('port'));
        $baud = (int) $this->argument('baud');
        $apiUrl = url('/api/sensor');
        $this->commandFile = storage_path('app/buzzer_command.txt');
        $this->responseFile = storage_path('app/buzzer_response.txt');

        $actualPort = (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN' && preg_match('/^COM\d+$/', $port))
            ? '\\\\.\\'.$port
            : $port;

        $this->info('🚀 SIPETIK Serial Bridge v2.2');
        $this->info("📡 Port  : {$port} @ {$baud} baud");
        $this->info("🔗 API   : {$apiUrl}");
        $this->info('🔔 Buzzer: Aktif (cek command file)');
        $this->line(str_repeat('-', 52));

        // Configure baud rate on Windows
        if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
            exec("mode {$port} BAUD={$baud} PARITY=n DATA=8 STOP=1 2>&1", $modeOut, $modeCode);
            if ($modeCode !== 0) {
                $this->warn("⚠️  'mode' command gagal, lanjut buka port...");
            }
        }

        $this->handle = @fopen($actualPort, 'r+');

        if (! $this->handle) {
            $this->error("❌ Gagal membuka {$port}.");
            $this->line('   • Pastikan COM port benar (cek Device Manager).');
            $this->line('   • Tutup Arduino IDE Serial Monitor jika sedang terbuka.');
            $this->line('   • Coba jalankan terminal sebagai Administrator.');

            return 1;
        }

        // Flush stale buffer, switch to non-blocking briefly
        stream_set_blocking($this->handle, false);
        fread($this->handle, 8192);
        stream_set_blocking($this->handle, true);
        stream_set_timeout($this->handle, 3);

        $this->info('✅ Port terbuka! Menunggu data dari ESP32...');
        $this->warn('   Tekan Ctrl+C untuk berhenti.');
        $this->line(str_repeat('-', 52));

        while (true) {
            // Check for command file first
            $this->checkCommandFile();

            // Read from serial
            $line = fgets($this->handle, 2048);

            if ($line === false || trim($line) === '') {
                usleep(5000);

                continue;
            }

            $line = trim($line);

            // Handle buzzer status response from ESP32
            if (str_starts_with($line, '{')) {
                if ($this->isValidJson($line)) {
                    $payload = json_decode($line, true);

                    // Check if this is a buzzer status response
                    if (isset($payload['buzzer_on'])) {
                        File::put($this->responseFile, $line);
                        $this->info('   🔔 Status buzzer diterima: '.($payload['buzzer_on'] ? 'ON' : 'OFF'));
                    } else {
                        $preview = substr($line, 0, 80).(strlen($line) > 80 ? '…' : '');
                        $this->comment("📥 JSON: {$preview}");
                        $this->forwardToApi($apiUrl, $line);
                    }
                }
            }
            // Skip debug lines
            elseif (! str_starts_with($line, '[') && ! str_starts_with($line, '[CMD]')) {
                // Silently skip debug output
            }
        }

        fclose($this->handle);

        return 0;
    }

    private function checkCommandFile(): void
    {
        if (! File::exists($this->commandFile)) {
            return;
        }

        $command = trim(File::get($this->commandFile));
        File::delete($this->commandFile);

        if (empty($command)) {
            return;
        }

        $this->info("📤 Mengirim command: {$command}");

        // Send command to ESP32 via serial (append newline)
        fwrite($this->handle, $command."\n");

        // Small delay to ensure command is sent
        usleep(100000);
    }

    private function isValidJson(string $s): bool
    {
        json_decode($s);

        return json_last_error() === JSON_ERROR_NONE;
    }

    private function forwardToApi(string $url, string $json): void
    {
        try {
            $payload = json_decode($json, true);

            if (! isset($payload['temperature'])) {
                return;
            }

            $response = Http::timeout(5)->post($url, $payload);

            if ($response->successful()) {
                $id = $response->json('id') ?? '-';
                $this->info("   ✅ Tersimpan (ID: {$id})  suhu={$payload['temperature']}°C  tanah={$payload['soil_raw']}");
            } else {
                $this->error("   ❌ API error {$response->status()}: ".$response->body());
            }
        } catch (\Exception $e) {
            $this->error("   💥 {$e->getMessage()}");
        }
    }
}