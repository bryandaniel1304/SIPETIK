<?php

use Illuminate\Support\Facades\Route;
use Illuminate\Foundation\Http\Middleware\ValidateCsrfToken;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\Api\SensorController as ApiSensorController;
use App\Http\Controllers\Api\FarmerAssistantController as ApiFarmerAssistantController;
use App\Http\Controllers\AppController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\Api\BuzzerControlController;
use App\Http\Controllers\Api\CameraController;
use App\Http\Controllers\Api\NotificationController;

use App\Http\Controllers\AuthController;

Route::get('/', function () {
    return redirect()->route('app.dashboard');
});

Route::get('/dashboard', function () {
    return redirect()->route('app.dashboard');
})->middleware('auth')->name('dashboard');

// Auth Routes
Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthController::class, 'login']);
Route::get('/register', [AuthController::class, 'showRegister'])->name('register');
Route::post('/register', [AuthController::class, 'register']);
Route::post('/logout', [AuthController::class, 'logout'])->name('logout');

// Smart Agriculture App Routes
Route::prefix('app')->name('app.')->middleware('auth')->group(function () {
    Route::get('/dashboard', [AppController::class, 'dashboard'])->name('dashboard');
    Route::get('/sensor-data', [AppController::class, 'sensorData'])->name('sensor-data');
    Route::get('/hama-alerts', [AppController::class, 'hamaAlerts'])->name('hama-alerts');
    Route::get('/settings', [AppController::class, 'settings'])->name('settings');
});

// Profile Routes
Route::prefix('profile')->name('profile.')->middleware('auth')->group(function () {
    Route::get('/show', [ProfileController::class, 'show'])->name('show');
    Route::get('/edit', [ProfileController::class, 'edit'])->name('edit');
    Route::post('/update', [ProfileController::class, 'update'])->name('update');
});

// Endpoint for IoT devices to post sensor data. Disable CSRF for IoT POSTs.
Route::post('/api/sensor', [ApiSensorController::class, 'store'])->withoutMiddleware([
    ValidateCsrfToken::class,
    App\Http\Middleware\VerifyCsrfToken::class,
]);

// Lightweight GET test endpoint to insert sample data (useful for testing without CSRF)
Route::get('/api/sensor/test', [ApiSensorController::class, 'storeTest'])->name('api.sensor.test');

// Simple JSON endpoint to see the latest sensor reading (for debugging/live check)
Route::get('/api/sensor/latest', [ApiSensorController::class, 'latest']);
Route::get('/api/sensor/schema', [ApiSensorController::class, 'schema']);

// Farmer Q&A assistant API (for plugin/chat UI)
Route::post('/api/assistant/ask', [ApiFarmerAssistantController::class, 'ask']);

// Buzzer control — dashboard buttons send X-CSRF-TOKEN header so standard middleware is fine
Route::get('/api/buzzer/status',   [BuzzerControlController::class, 'getStatus']);
Route::post('/api/buzzer/on',      [BuzzerControlController::class, 'on'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
Route::post('/api/buzzer/off',     [BuzzerControlController::class, 'off'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
Route::post('/api/buzzer/trigger', [BuzzerControlController::class, 'trigger'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
Route::put('/api/buzzer/settings', [BuzzerControlController::class, 'updateSettings'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
Route::post('/api/buzzer/override', [BuzzerControlController::class, 'setOverride'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);

// ESP32 polls this to receive pending commands (no auth, no CSRF — device request)
Route::get('/api/esp32/command', [BuzzerControlController::class, 'getCommand']);

// Camera animal detection — called by Python script on laptop (no CSRF)
Route::post('/api/camera/motion',    [CameraController::class, 'motion'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
Route::get('/api/camera/heartbeat',  [CameraController::class, 'heartbeat']);
Route::get('/api/camera/status',     [CameraController::class, 'status']);

// Email notification settings
Route::get('/api/notifications/status',   [NotificationController::class, 'status']);
Route::post('/api/notifications/toggle',  [NotificationController::class, 'toggle'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
Route::post('/api/notifications/test',    [NotificationController::class, 'sendTest'])->withoutMiddleware([ValidateCsrfToken::class, App\Http\Middleware\VerifyCsrfToken::class]);
