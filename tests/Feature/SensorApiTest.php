<?php

use App\Models\SensorData;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;

uses(RefreshDatabase::class);

test('esp32 payload is stored and raw soil is converted to moisture percentage', function () {
    $response = $this->postJson('/api/sensor', [
        'device_id' => 'esp32-sawah-01',
        'temperature' => 29.4,
        'humidity' => 82.1,
        'soil_raw' => 2200,
        'motion' => false,
        'ph' => 6.4,
    ]);

    $response
        ->assertCreated()
        ->assertJsonPath('device_id', 'esp32-sawah-01')
        ->assertJsonPath('stored_moisture', 50);

    $sensor = SensorData::firstOrFail();

    expect($sensor->temperature)->toEqual(29.4)
        ->and($sensor->humidity)->toEqual(82.1)
        ->and($sensor->moisture)->toEqual(50.0)
        ->and($sensor->pest_status)->toBe('medium')
        ->and($sensor->metadata['device_id'])->toBe('esp32-sawah-01')
        ->and($sensor->metadata['motion'])->toBeFalse()
        ->and($sensor->metadata['soil_raw'])->toBe(2200);
});

test('latest sensor endpoint returns normalized dashboard fields', function () {
    SensorData::create([
        'temperature' => 27.2,
        'moisture' => 61.3,
        'humidity' => 78.4,
        'pest_status' => 'low',
        'metadata' => [
            'device_id' => 'esp32-dashboard',
            'ph' => 6.8,
            'motion' => false,
            'soil_raw' => 1750,
        ],
    ]);

    $response = $this->getJson('/api/sensor/latest');

    $response
        ->assertOk()
        ->assertJsonPath('device_id', 'esp32-dashboard')
        ->assertJsonPath('temperature', 27.2)
        ->assertJsonPath('moisture', 61.3)
        ->assertJsonPath('ph', 6.8)
        ->assertJsonPath('soil_raw', 1750)
        ->assertJsonPath('is_online', true);
});

test('sensor endpoint accepts common esp32 alias fields', function () {
    $response = $this->postJson('/api/sensor', [
        'deviceId' => 'esp32-alias',
        'temp' => 30.1,
        'hum' => 79.2,
        'soil_adc' => 1800,
        'motion_detected' => 1,
        'ph_value' => 6.7,
    ]);

    $response
        ->assertCreated()
        ->assertJsonPath('device_id', 'esp32-alias');

    $sensor = SensorData::firstOrFail();

    expect($sensor->moisture)->toBeFloat()
        ->and($sensor->metadata['motion'])->toBeTrue()
        ->and($sensor->metadata['ph'])->toEqual(6.7);
});

test('schema endpoint exposes supported field aliases', function () {
    $this->getJson('/api/sensor/schema')
        ->assertOk()
        ->assertJsonPath('aliases.temperature.0', 'temperature')
        ->assertJsonPath('aliases.temperature.1', 'temp');
});

test('dashboard page renders successfully with no sensor data for authenticated user', function () {
    $user = User::factory()->create();

    $this->actingAs($user)
        ->get('/app/dashboard')
        ->assertOk();
});
