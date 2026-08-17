<?php

namespace App\Services;

use App\Mail\PestAlertMail;
use App\Models\User;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;

class NotificationService
{
    // Cooldown: jangan kirim email lebih dari sekali per 15 menit per jenis alert
    private const COOLDOWN_MINUTES = 15;

    public static function isEmailEnabled(): bool
    {
        return (bool) Cache::get('email_notifications_enabled', false);
    }

    public static function setEmailEnabled(bool $enabled): void
    {
        Cache::forever('email_notifications_enabled', $enabled);
    }

    public static function sendPestAlert(array $sensorData): void
    {
        if (!static::isEmailEnabled()) {
            return;
        }

        $cooldownKey = 'email_sent_pest_high';
        if (Cache::has($cooldownKey)) {
            return;
        }

        $user = User::first();
        if (!$user?->email) {
            return;
        }

        try {
            Mail::to($user->email)->send(new PestAlertMail('pest_high', $sensorData));
            Cache::put($cooldownKey, true, now()->addMinutes(static::COOLDOWN_MINUTES));
            Log::info('SIPETIK: pest alert email sent to ' . $user->email);
        } catch (\Throwable $e) {
            Log::warning('SIPETIK: failed to send pest alert email: ' . $e->getMessage());
        }
    }

    public static function sendAnimalAlert(array $detectionData): void
    {
        if (!static::isEmailEnabled()) {
            return;
        }

        $cooldownKey = 'email_sent_animal_detected';
        if (Cache::has($cooldownKey)) {
            return;
        }

        $user = User::first();
        if (!$user?->email) {
            return;
        }

        try {
            Mail::to($user->email)->send(new PestAlertMail('animal_detected', $detectionData));
            Cache::put($cooldownKey, true, now()->addMinutes(static::COOLDOWN_MINUTES));
            Log::info('SIPETIK: animal alert email sent to ' . $user->email);
        } catch (\Throwable $e) {
            Log::warning('SIPETIK: failed to send animal alert email: ' . $e->getMessage());
        }
    }

    public static function sendTestEmail(): bool
    {
        $user = User::first();
        if (!$user?->email) {
            return false;
        }

        try {
            Mail::to($user->email)->send(new PestAlertMail('test'));
            return true;
        } catch (\Throwable $e) {
            Log::warning('SIPETIK: test email failed: ' . $e->getMessage());
            return false;
        }
    }
}
