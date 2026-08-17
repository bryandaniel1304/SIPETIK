<?php

namespace App\Mail;

use Illuminate\Mail\Mailable;
use Illuminate\Mail\Mailables\Content;
use Illuminate\Mail\Mailables\Envelope;

class PestAlertMail extends Mailable
{
    public function __construct(
        public readonly string $alertType,   // 'pest_high' | 'animal_detected' | 'test'
        public readonly array  $data = [],
    ) {}

    public function envelope(): Envelope
    {
        $subject = match ($this->alertType) {
            'pest_high'       => '⚠️ SIPETIK — Risiko Hama Tinggi Terdeteksi!',
            'animal_detected' => '🐾 SIPETIK — Binatang Terdeteksi di Lahan!',
            default           => '🔔 SIPETIK — Notifikasi Sistem',
        };

        return new Envelope(subject: $subject);
    }

    public function content(): Content
    {
        return new Content(markdown: 'mail.pest-alert');
    }
}
