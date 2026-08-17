<?php

use App\Http\Controllers\Api\BuzzerControlController;
use App\Http\Controllers\Api\SensorController;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
|
| These routes are loaded by the RouteServiceProvider and use the "api"
| middleware group (no CSRF protection, ideal for IoT devices).
|
*/

Route::post('/sensor', [SensorController::class, 'store']);
Route::get('/sensor/latest', [SensorController::class, 'latest']);
Route::get('/sensor/test', [SensorController::class, 'storeTest']);
Route::get('/sensor/schema', [SensorController::class, 'schema']);

// Buzzer Control Routes (v2 - dengan settings & schedule)
Route::post('/buzzer/on', [BuzzerControlController::class, 'on']);
Route::post('/buzzer/off', [BuzzerControlController::class, 'off']);
Route::post('/buzzer/trigger', [BuzzerControlController::class, 'trigger']);
Route::get('/buzzer/status', [BuzzerControlController::class, 'getStatus']);
Route::put('/buzzer/settings', [BuzzerControlController::class, 'updateSettings']);
