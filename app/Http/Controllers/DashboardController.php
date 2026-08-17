<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Models\SensorData;
use Carbon\Carbon;

class DashboardController extends Controller
{
    public function index(Request $request)
    {
        $latest = SensorData::latest('created_at')->first();

        $labels = [];
        $temps = [];
        $moistures = [];

        // Prepare 7 days labels (including today)
        $days = collect();
        for ($i = 6; $i >= 0; $i--) {
            $days->push(Carbon::today()->subDays($i));
        }

        foreach ($days as $day) {
            $labels[] = $day->format('Y-m-d');

            $dayStart = $day->copy()->startOfDay();
            $dayEnd = $day->copy()->endOfDay();

            $dayRecords = SensorData::whereBetween('created_at', [$dayStart, $dayEnd])->get();

            if ($dayRecords->isEmpty()) {
                $temps[] = null;
                $moistures[] = null;
            } else {
                $temps[] = round($dayRecords->avg('temperature'), 2);
                $moistures[] = round($dayRecords->avg('moisture'), 2);
            }
        }

        return view('dashboard', [
            'latest' => $latest,
            'chartLabels' => json_encode($labels),
            'chartTemps' => json_encode($temps),
            'chartMoistures' => json_encode($moistures),
        ]);
    }
}
