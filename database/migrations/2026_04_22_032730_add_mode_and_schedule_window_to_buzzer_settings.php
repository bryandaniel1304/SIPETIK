<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::table('buzzer_settings', function (Blueprint $table) {
            $table->string('buzzer_mode', 10)->default('manual')->after('enabled');
            $table->string('schedule_start', 5)->nullable()->after('schedule_times');
            $table->string('schedule_end', 5)->nullable()->after('schedule_start');
        });
    }

    public function down(): void
    {
        Schema::table('buzzer_settings', function (Blueprint $table) {
            $table->dropColumn(['buzzer_mode', 'schedule_start', 'schedule_end']);
        });
    }
};
