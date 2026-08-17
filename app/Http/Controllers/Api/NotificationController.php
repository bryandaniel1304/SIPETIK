<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use App\Services\NotificationService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class NotificationController extends Controller
{
    public function status(): JsonResponse
    {
        $user = User::first();

        return response()->json([
            'email_enabled' => NotificationService::isEmailEnabled(),
            'email'         => $user?->email,
        ]);
    }

    public function toggle(Request $request): JsonResponse
    {
        $enabled = (bool) $request->input('enabled', false);
        NotificationService::setEmailEnabled($enabled);

        return response()->json([
            'status'        => 'ok',
            'email_enabled' => $enabled,
        ]);
    }

    public function sendTest(): JsonResponse
    {
        $user = User::first();
        if (!$user?->email) {
            return response()->json(['status' => 'error', 'message' => 'Tidak ada email user terdaftar.'], 422);
        }

        $ok = NotificationService::sendTestEmail();

        return response()->json([
            'status'  => $ok ? 'ok' : 'error',
            'message' => $ok
                ? "Email percobaan berhasil dikirim ke {$user->email}."
                : 'Gagal mengirim email. Periksa konfigurasi SMTP di .env.',
        ]);
    }
}

