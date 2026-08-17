<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

class ProfileController extends Controller
{
    /**
     * Get current user profile data (for modal/display)
     */
    public function show()
    {
        return response()->json(Auth::user());
    }

    /**
     * Show edit profile form
     */
    public function edit()
    {
        return response()->json(Auth::user());
    }

    /**
     * Update user profile
     */
    public function update(Request $request)
    {
        try {
            $validated = $request->validate([
                'name' => 'required|string|max:255',
                'email' => 'required|email|max:255|unique:users,email,' . Auth::id(),
                'phone' => 'nullable|string|max:20',
                'address' => 'nullable|string|max:255',
                'farm_name' => 'nullable|string|max:255',
                'farm_area' => 'nullable|string|max:50',
                'crop_type' => 'nullable|string|max:100',
            ]);

            Auth::user()->update($validated);

            return response()->json([
                'status' => 'success',
                'message' => 'Profil berhasil diperbarui',
                'user' => Auth::user(),
            ], 200);
        } catch (\Illuminate\Validation\ValidationException $e) {
            return response()->json([
                'status' => 'error',
                'message' => 'Validasi gagal',
                'errors' => $e->errors(),
            ], 422);
        } catch (\Exception $e) {
            return response()->json([
                'status' => 'error',
                'message' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Logout user
     */
    public function logout(Request $request)
    {
        Auth::logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();
        return redirect()->route('login')->with('success', 'Berhasil keluar');
    }
}
