<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use App\Models\SensorData;
use Carbon\Carbon;

class SensorDataSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $dates = [];
        for ($i = 6; $i >= 0; $i--) {
            $dates[] = Carbon::today()->subDays($i);
        }

        foreach ($dates as $date) {
            for ($j = 0; $j < 3; $j++) {
                SensorData::create([
                    'temperature' => 20 + rand(0, 100) / 10,
                    'moisture' => 40 + rand(0, 300) / 10,
                    'humidity' => 60 + rand(0, 300) / 10,
                    'pest_status' => ['low', 'medium', 'high'][rand(0, 2)],
                    'metadata' => ['source' => 'seeder', 'day_offset' => $i],
                    'created_at' => $date->copy()->addHours(rand(6, 18))->addMinutes(rand(0, 59)),
                    'updated_at' => $date->copy()->addHours(rand(6, 18))->addMinutes(rand(0, 59)),
                ]);
            }
        }

        echo "✓ Inserted 21 sensor data rows (3 per day for 7 days)\n";
    }
}
