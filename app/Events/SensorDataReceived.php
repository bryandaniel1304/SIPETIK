<?php

namespace App\Events;

use App\Models\SensorData;
use Illuminate\Broadcasting\Channel;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class SensorDataReceived implements ShouldBroadcastNow
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    public function __construct(public SensorData $sensorData)
    {
    }

    /**
     * Broadcast on a public channel so the dashboard can subscribe without auth flow.
     */
    public function broadcastOn(): array
    {
        return [new Channel('sensor-data')];
    }

    public function broadcastAs(): string
    {
        return 'SensorDataReceived';
    }

    public function broadcastWith(): array
    {
        $metadata = is_array($this->sensorData->metadata) ? $this->sensorData->metadata : [];

        return [
            'id' => $this->sensorData->id,
            'device_id' => $metadata['device_id'] ?? null,
            'temperature' => $this->sensorData->temperature,
            'humidity' => $this->sensorData->humidity,
            'moisture' => $this->sensorData->moisture,
            'ph' => $metadata['ph'] ?? null,
            'motion' => $metadata['motion'] ?? null,
            'soil_raw' => $metadata['soil_raw'] ?? null,
            'pest_status' => $this->sensorData->pest_status,
            'created_at' => $this->sensorData->created_at?->toIso8601String(),
        ];
    }
}
