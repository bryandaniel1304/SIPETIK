<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class BuzzerSetting extends Model
{
    protected $table = 'buzzer_settings';

    protected $fillable = [
        'user_id',
        'enabled',
        'buzzer_mode',
        'interval_seconds',
        'interval_minutes',
        'use_interval',
        'schedule_enabled',
        'schedule_times',
        'schedule_start',
        'schedule_end',
        'pest_risk_trigger',
        'duration_seconds',
    ];

    protected $casts = [
        'enabled' => 'boolean',
        'use_interval' => 'boolean',
        'schedule_enabled' => 'boolean',
        'pest_risk_trigger' => 'boolean',
        'schedule_times' => 'array',
    ];

    public static function getActive(): ?self
    {
        return static::first();
    }

    public function isDue(): bool
    {
        if (!$this->enabled) {
            return false;
        }

        // Check interval-based trigger
        if ($this->use_interval) {
            $lastTriggered = cache()->get('buzzer_last_triggered');
            $intervalSeconds = ($this->interval_minutes ?? 0) * 60 + ($this->interval_seconds ?? 0);
            
            if ($lastTriggered === null) {
                return true;
            }

            return (time() - $lastTriggered) >= $intervalSeconds;
        }

        return false;
    }

    public function isScheduledTime(): bool
    {
        if (!$this->schedule_enabled || !$this->schedule_times) {
            return false;
        }

        $now = now()->timezone('Asia/Jakarta');
        $currentTime = $now->format('H:i');
        $currentDay = $now->dayOfWeek;

        foreach ($this->schedule_times as $schedule) {
            if (!isset($schedule['time'])) {
                continue;
            }

            if ($schedule['time'] === $currentTime) {
                if (empty($schedule['days'])) {
                    return true;
                }

                $days = is_array($schedule['days']) ? $schedule['days'] : json_decode((string) $schedule['days'], true);
                if (in_array($currentDay, $days)) {
                    return true;
                }
            }
        }

        return false;
    }

    public function isWithinScheduleWindow(): bool
    {
        if (!$this->schedule_start || !$this->schedule_end) {
            return true; // no window restriction
        }

        $now   = now()->timezone('Asia/Jakarta')->format('H:i');
        $start = $this->schedule_start;
        $end   = $this->schedule_end;

        // Handle overnight windows (e.g. 22:00 – 06:00)
        if ($start <= $end) {
            return $now >= $start && $now <= $end;
        }

        return $now >= $start || $now <= $end;
    }

    public function shouldTrigger(?string $pestRisk = null): bool
    {
        if (!$this->enabled) {
            return false;
        }

        // Manual mode: user controls buzzer sepenuhnya, tidak ada auto-trigger
        if (($this->buzzer_mode ?? 'manual') === 'manual') {
            return false;
        }

        if ($this->pest_risk_trigger && $pestRisk === 'high') {
            return true;
        }

        if ($this->use_interval && $this->isDue() && $this->isWithinScheduleWindow()) {
            return true;
        }

        // Prevent multiple triggers within the same scheduled minute
        if ($this->schedule_enabled && $this->isScheduledTime()) {
            $minuteKey = 'buzzer_sched_fired_' . now()->timezone('Asia/Jakarta')->format('YmdHi');
            if (!cache()->has($minuteKey)) {
                return true;
            }
        }

        return false;
    }

    public function markTriggered(): void
    {
        cache()->put('buzzer_last_triggered', time(), now()->addHours(24));
        $minuteKey = 'buzzer_sched_fired_' . now()->timezone('Asia/Jakarta')->format('YmdHi');
        cache()->put($minuteKey, true, now()->addMinutes(2));
    }

    public static function getDefaultSettings(): array
    {
        return [
            'enabled'          => false,
            'buzzer_mode'      => 'manual',
            'interval_minutes' => 5,
            'interval_seconds' => 0,
            'use_interval'     => false,
            'schedule_enabled' => false,
            'schedule_times'   => [],
            'schedule_start'   => '06:00',
            'schedule_end'     => '18:00',
            'pest_risk_trigger' => true,
            'duration_seconds' => 3,
        ];
    }

    public static function getOrCreate(): self
    {
        $setting = static::getActive();
        
        if (!$setting) {
            $setting = static::create([
                'user_id' => auth()->id(),
                ...static::getDefaultSettings(),
            ]);
        }

        return $setting;
    }
}