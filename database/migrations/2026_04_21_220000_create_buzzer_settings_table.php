<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('buzzer_settings', function (Blueprint $table) {
            $table->id();
            $table->unsignedBigInteger('user_id')->nullable();
            $table->boolean('enabled')->default(false);
            $table->integer('interval_seconds')->default(0);
            $table->integer('interval_minutes')->default(5);
            $table->boolean('use_interval')->default(true);
            $table->boolean('schedule_enabled')->default(false);
            $table->json('schedule_times')->nullable();
            $table->boolean('pest_risk_trigger')->default(true);
            $table->integer('duration_seconds')->default(3);
            $table->timestamps();

            $table->foreign('user_id')->references('id')->on('users')->onDelete('cascade');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('buzzer_settings');
    }
};
