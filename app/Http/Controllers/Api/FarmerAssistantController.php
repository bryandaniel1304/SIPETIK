<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class FarmerAssistantController extends Controller
{
    public function ask(Request $request)
    {
        $data = $request->validate([
            'question' => 'required|string|min:2|max:2000',
            'locale' => 'nullable|string|max:10',
            'context' => 'nullable|array',
        ]);

        $question = trim($data['question']);
        $context = $data['context'] ?? [];

        $provider = strtolower((string) config('services.assistant.provider', 'openai'));
        $provider = in_array($provider, ['openai', 'openrouter', 'rules'], true) ? $provider : 'rules';
        $openAiApiKey = trim((string) config('services.openai.api_key', ''));
        $openRouterApiKey = trim((string) config('services.openrouter.api_key', ''));
        $locale = $this->normalizeLocale($data['locale'] ?? null);

        if ($provider === 'openai' && $openAiApiKey !== '') {
            return $this->askOpenAi(
                $question,
                $context,
                $locale,
                $openAiApiKey,
                (string) config('services.openai.model', 'gpt-4.1-mini'),
                (string) config('services.openai.base_url', 'https://api.openai.com/v1'),
                trim((string) config('services.openai.organization', '')),
                trim((string) config('services.openai.project', '')),
                (bool) config('services.openai.verify_tls', true),
                trim((string) config('services.openai.ca_bundle', ''))
            );
        }

        if ($provider === 'openrouter' && $openRouterApiKey !== '') {
            return $this->askOpenRouter(
                $question,
                $context,
                $locale,
                $openRouterApiKey,
                (string) config('services.openrouter.model', 'openrouter/free'),
                (string) config('services.openrouter.base_url', 'https://openrouter.ai/api/v1'),
                trim((string) config('services.openrouter.site_url', '')),
                trim((string) config('services.openrouter.app_name', 'SIPETIK Dashboard')),
                (bool) config('services.openrouter.verify_tls', true),
                trim((string) config('services.openrouter.ca_bundle', ''))
            );
        }

        $reason = match ($provider) {
            'openai' => 'missing_openai_key',
            'openrouter' => 'missing_openrouter_key',
            default => 'rules_provider',
        };

        return $this->askRules($locale, $reason);
    }

    private function askRules(string $locale, string $reason = 'fallback')
    {
        $isEnglish = $locale === 'en';

        $openAiHintEn = 'Set ASSISTANT_PROVIDER=openai and OPENAI_API_KEY in .env, then run php artisan optimize:clear.';
        $openAiHintId = 'Set ASSISTANT_PROVIDER=openai dan OPENAI_API_KEY di .env, lalu jalankan php artisan optimize:clear.';
        $openRouterHintEn = 'Set ASSISTANT_PROVIDER=openrouter and OPENROUTER_API_KEY in .env (model can be OPENROUTER_MODEL=openrouter/free), then run php artisan optimize:clear.';
        $openRouterHintId = 'Set ASSISTANT_PROVIDER=openrouter dan OPENROUTER_API_KEY di .env (model bisa OPENROUTER_MODEL=openrouter/free), lalu jalankan php artisan optimize:clear.';

        $setupMessageEn = match ($reason) {
            'missing_openai_key' => "OpenAI is selected but OPENAI_API_KEY is empty. {$openAiHintEn}",
            'missing_openrouter_key' => "OpenRouter is selected but OPENROUTER_API_KEY is empty. {$openRouterHintEn}",
            default => "Enable AI provider in .env. {$openRouterHintEn} {$openAiHintEn}",
        };
        $setupMessageId = match ($reason) {
            'missing_openai_key' => "OpenAI dipilih tetapi OPENAI_API_KEY masih kosong. {$openAiHintId}",
            'missing_openrouter_key' => "OpenRouter dipilih tetapi OPENROUTER_API_KEY masih kosong. {$openRouterHintId}",
            default => "Aktifkan provider AI di .env. {$openRouterHintId} {$openAiHintId}",
        };

        $answer = $isEnglish
            ? "I can help with many topics in English or Indonesian. {$setupMessageEn}"
            : "Saya bisa membantu banyak topik dalam Bahasa Indonesia maupun English. {$setupMessageId}";

        $followUps = $isEnglish
            ? [
                'What would you like to ask?',
                'Should I answer in English or Indonesian?',
                'Use OpenRouter free model by setting OPENROUTER_MODEL=openrouter/free.',
            ]
            : [
                'Topik apa yang ingin Anda tanyakan?',
                'Anda ingin jawaban dalam Bahasa Indonesia atau English?',
                'Gunakan model gratis OpenRouter dengan OPENROUTER_MODEL=openrouter/free.',
            ];

        return response()->json([
            'answer' => $answer,
            'tags' => ['general', 'fallback'],
            'follow_up_questions' => $followUps,
            'provider' => 'rules',
            'reason' => $reason,
        ]);
    }

    private function askOpenAi(
        string $question,
        array $context,
        string $locale,
        string $apiKey,
        string $model,
        string $baseUrl,
        string $organization = '',
        string $project = '',
        bool $verifyTls = true,
        string $caBundle = ''
    )
    {
        $languageInstruction = $locale === 'en'
            ? 'Always answer in English unless the user explicitly asks for Indonesian.'
            : ($locale === 'id'
                ? 'Selalu jawab dalam Bahasa Indonesia kecuali user secara eksplisit meminta English.'
                : 'Detect the language of the user message and answer in the same language (Indonesian or English).');

        $system = 'You are a helpful general-purpose AI assistant for a Laravel dashboard chatbot. '
            . 'You can answer questions on any topic, not only agriculture. '
            . 'Keep answers clear, concise, and practical. '
            . 'If a request is ambiguous, ask 1-2 short clarifying questions. '
            . 'If you are uncertain, say so briefly and provide the best next step. '
            . $languageInstruction;

        $payload = [
            'model' => $model,
            'input' => [
                [
                    'role' => 'system',
                    'content' => $system,
                ],
                [
                    'role' => 'user',
                    'content' => 'User question: ' . $question . "\n\nOptional dashboard context: " . json_encode($context, JSON_UNESCAPED_UNICODE),
                ],
            ],
        ];

        $endpoint = rtrim($baseUrl, '/').'/responses';
        $requestBuilder = Http::withToken($apiKey)->connectTimeout(8)->timeout(20);

        $headers = [];
        if ($organization !== '') {
            $headers['OpenAI-Organization'] = $organization;
        }
        if ($project !== '') {
            $headers['OpenAI-Project'] = $project;
        }
        if ($headers !== []) {
            $requestBuilder = $requestBuilder->withHeaders($headers);
        }

        if ($caBundle !== '') {
            $requestBuilder = $requestBuilder->withOptions(['verify' => $caBundle]);
        } elseif (! $verifyTls) {
            $requestBuilder = $requestBuilder->withOptions(['verify' => false]);
        }

        try {
            $resp = $requestBuilder->post($endpoint, $payload);
        } catch (\Throwable $e) {
            $message = $e->getMessage();
            $isSslIssue = str_contains(strtolower($message), 'ssl certificate') || str_contains(strtolower($message), 'curl error 60');

            return response()->json([
                'answer' => $isSslIssue
                    ? 'Koneksi ke OpenAI gagal karena sertifikat SSL lokal. Untuk dev lokal, atur OPENAI_VERIFY_TLS=false atau isi OPENAI_CA_BUNDLE.'
                    : 'Maaf, koneksi ke layanan AI gagal. Coba lagi beberapa saat.',
                'provider' => 'openai',
                'error' => [
                    'type' => 'connection_error',
                    'message' => $message,
                ],
            ], 502);
        }

        if (! $resp->successful()) {
            $status = $resp->status();
            $errorMessage = (string) data_get($resp->json(), 'error.message', 'Unknown OpenAI error');
            $errorMessageLower = strtolower($errorMessage);

            $userFriendlyAnswer = 'Maaf, layanan AI sedang bermasalah. Coba lagi beberapa saat.';

            if ($status === 401 || str_contains($errorMessageLower, 'invalid api key')) {
                $userFriendlyAnswer = 'API key OpenAI tidak valid atau tidak aktif. Cek OPENAI_API_KEY di .env, buat key baru jika perlu, lalu jalankan php artisan optimize:clear.';
            } elseif ($status === 429 && str_contains($errorMessageLower, 'quota')) {
                $userFriendlyAnswer = 'Kuota OpenAI habis atau billing project belum aktif. Tambahkan credit/aktifkan billing di OpenAI, lalu coba lagi beberapa menit.';
            } elseif ($status === 429) {
                $userFriendlyAnswer = 'Permintaan ke OpenAI terlalu banyak (rate limit). Tunggu sebentar lalu coba lagi.';
            } elseif ($status === 403) {
                $userFriendlyAnswer = 'Akses OpenAI ditolak untuk project ini. Periksa organisasi/project API key dan permission model.';
            }

            return response()->json([
                'answer' => $userFriendlyAnswer,
                'provider' => 'openai',
                'error' => [
                    'status' => $status,
                    'message' => $errorMessage,
                ],
            ], 502);
        }

        $json = $resp->json();
        $text = $json['output_text'] ?? null;

        return response()->json([
            'answer' => $text ?: 'Maaf, saya belum bisa menghasilkan jawaban saat ini.',
            'provider' => 'openai',
        ]);
    }

    private function askOpenRouter(
        string $question,
        array $context,
        string $locale,
        string $apiKey,
        string $model,
        string $baseUrl,
        string $siteUrl = '',
        string $appName = 'SIPETIK Dashboard',
        bool $verifyTls = true,
        string $caBundle = ''
    )
    {
        $languageInstruction = $locale === 'en'
            ? 'Always answer in English unless the user explicitly asks for Indonesian.'
            : ($locale === 'id'
                ? 'Selalu jawab dalam Bahasa Indonesia kecuali user secara eksplisit meminta English.'
                : 'Detect the language of the user message and answer in the same language (Indonesian or English).');

        $system = 'You are a helpful general-purpose AI assistant for a Laravel dashboard chatbot. '
            . 'You can answer questions on any topic, not only agriculture. '
            . 'Keep answers clear, concise, and practical. '
            . 'If a request is ambiguous, ask 1-2 short clarifying questions. '
            . 'If you are uncertain, say so briefly and provide the best next step. '
            . $languageInstruction;

        $payload = [
            'model' => $model,
            'messages' => [
                [
                    'role' => 'system',
                    'content' => $system,
                ],
                [
                    'role' => 'user',
                    'content' => 'User question: ' . $question . "\n\nOptional dashboard context: " . json_encode($context, JSON_UNESCAPED_UNICODE),
                ],
            ],
        ];

        $endpoint = rtrim($baseUrl, '/').'/chat/completions';
        $requestBuilder = Http::withToken($apiKey)->connectTimeout(8)->timeout(20);

        $headers = [];
        if ($siteUrl !== '') {
            $headers['HTTP-Referer'] = $siteUrl;
        }
        if ($appName !== '') {
            $headers['X-Title'] = $appName;
        }
        if ($headers !== []) {
            $requestBuilder = $requestBuilder->withHeaders($headers);
        }

        if ($caBundle !== '') {
            $requestBuilder = $requestBuilder->withOptions(['verify' => $caBundle]);
        } elseif (! $verifyTls) {
            $requestBuilder = $requestBuilder->withOptions(['verify' => false]);
        }

        try {
            $resp = $requestBuilder->post($endpoint, $payload);
        } catch (\Throwable $e) {
            $message = $e->getMessage();
            $isSslIssue = str_contains(strtolower($message), 'ssl certificate') || str_contains(strtolower($message), 'curl error 60');

            return response()->json([
                'answer' => $isSslIssue
                    ? 'Koneksi ke OpenRouter gagal karena sertifikat SSL lokal. Untuk dev lokal, atur OPENROUTER_VERIFY_TLS=false atau isi OPENROUTER_CA_BUNDLE.'
                    : 'Maaf, koneksi ke layanan OpenRouter gagal. Coba lagi beberapa saat.',
                'provider' => 'openrouter',
                'error' => [
                    'type' => 'connection_error',
                    'message' => $message,
                ],
            ], 502);
        }

        if (! $resp->successful()) {
            $status = $resp->status();
            $errorMessage = (string) data_get($resp->json(), 'error.message', 'Unknown OpenRouter error');
            $errorMessageLower = strtolower($errorMessage);

            $userFriendlyAnswer = 'Maaf, layanan AI OpenRouter sedang bermasalah. Coba lagi beberapa saat.';

            if ($status === 401 || str_contains($errorMessageLower, 'invalid')) {
                $userFriendlyAnswer = 'API key OpenRouter tidak valid atau tidak aktif. Cek OPENROUTER_API_KEY di .env lalu jalankan php artisan optimize:clear.';
            } elseif ($status === 429 && str_contains($errorMessageLower, 'quota')) {
                $userFriendlyAnswer = 'Kuota OpenRouter habis atau batas gratis harian tercapai. Coba lagi nanti atau ganti model free lain.';
            } elseif ($status === 429) {
                $userFriendlyAnswer = 'Permintaan terlalu banyak (rate limit OpenRouter). Tunggu sebentar lalu coba lagi.';
            } elseif ($status === 403) {
                $userFriendlyAnswer = 'Akses OpenRouter ditolak untuk model ini. Coba model free lain seperti openrouter/free.';
            }

            return response()->json([
                'answer' => $userFriendlyAnswer,
                'provider' => 'openrouter',
                'error' => [
                    'status' => $status,
                    'message' => $errorMessage,
                ],
            ], 502);
        }

        $json = $resp->json();
        $text = data_get($json, 'choices.0.message.content');
        if (is_array($text)) {
            $text = collect($text)
                ->map(fn ($item) => is_array($item) ? (string) ($item['text'] ?? '') : (string) $item)
                ->implode('');
        }

        return response()->json([
            'answer' => is_string($text) && trim($text) !== ''
                ? $text
                : 'Maaf, saya belum bisa menghasilkan jawaban saat ini.',
            'provider' => 'openrouter',
        ]);
    }

    private function normalizeLocale(?string $locale): string
    {
        if (! $locale) {
            return 'auto';
        }

        $value = strtolower(trim($locale));

        if (str_starts_with($value, 'en')) {
            return 'en';
        }

        if (str_starts_with($value, 'id')) {
            return 'id';
        }

        return 'auto';
    }
}
