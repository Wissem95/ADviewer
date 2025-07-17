<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\ValidationException;
use Laravel\Sanctum\PersonalAccessToken;

class AuthController extends Controller
{
    /**
     * Register a new user
     */
    public function register(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'name' => 'required|string|max:255',
            'email' => 'required|string|email|max:255|unique:users',
            'password' => 'required|string|min:8|confirmed',
            'birth_date' => 'nullable|date|before:today',
            'gender' => 'nullable|in:male,female,other',
            'country' => 'nullable|string|size:2',
            'language' => 'nullable|string|size:2',
            'referral_code' => 'nullable|string|exists:users,referral_code',
            'device_info' => 'nullable|array',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation errors',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            // Check for referral
            $referredBy = null;
            if ($request->referral_code) {
                $referrer = User::where('referral_code', $request->referral_code)->first();
                if ($referrer) {
                    $referredBy = $referrer->id;
                }
            }

            // Create user
            $user = User::create([
                'name' => $request->name,
                'email' => $request->email,
                'password' => Hash::make($request->password),
                'birth_date' => $request->birth_date,
                'gender' => $request->gender,
                'country' => $request->country ?? $this->getCountryFromIP($request->ip()),
                'language' => $request->language ?? 'en',
                'referred_by' => $referredBy,
                'device_info' => $request->device_info,
                'last_login_ip' => $request->ip(),
                'last_login_at' => now(),
            ]);

            // Award referral bonus if applicable
            if ($referredBy) {
                $referrer = User::find($referredBy);
                $bonusPoints = config('adviewer.referral_bonus_points', 50);
                $referrer->addPoints($bonusPoints, 'Referral bonus', null);
            }

            // Create access token
            $token = $user->createToken('AdViewer App')->plainTextToken;

            return response()->json([
                'success' => true,
                'message' => 'User registered successfully',
                'data' => [
                    'user' => $this->formatUserData($user),
                    'token' => $token,
                ],
            ], 201);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Registration failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Login user
     */
    public function login(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'email' => 'required|email',
            'password' => 'required|string',
            'device_info' => 'nullable|array',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation errors',
                'errors' => $validator->errors(),
            ], 422);
        }

        $user = User::where('email', $request->email)->first();

        if (!$user || !Hash::check($request->password, $user->password)) {
            return response()->json([
                'success' => false,
                'message' => 'Invalid credentials',
            ], 401);
        }

        if (!$user->is_active) {
            return response()->json([
                'success' => false,
                'message' => 'Account is deactivated',
            ], 403);
        }

        // Check for suspicious activity
        if ($user->isSuspicious()) {
            return response()->json([
                'success' => false,
                'message' => 'Account temporarily restricted',
            ], 403);
        }

        // Update last login info
        $user->update([
            'last_login_at' => now(),
            'last_login_ip' => $request->ip(),
            'device_info' => $request->device_info,
        ]);

        // Revoke existing tokens for security
        $user->tokens()->delete();

        // Create new token
        $token = $user->createToken('AdViewer App')->plainTextToken;

        return response()->json([
            'success' => true,
            'message' => 'Login successful',
            'data' => [
                'user' => $this->formatUserData($user),
                'token' => $token,
            ],
        ]);
    }

    /**
     * Logout user
     */
    public function logout(Request $request): JsonResponse
    {
        try {
            $request->user()->currentAccessToken()->delete();

            return response()->json([
                'success' => true,
                'message' => 'Logged out successfully',
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Logout failed',
            ], 500);
        }
    }

    /**
     * Refresh token
     */
    public function refreshToken(Request $request): JsonResponse
    {
        try {
            $user = $request->user();

            // Delete current token
            $request->user()->currentAccessToken()->delete();

            // Create new token
            $token = $user->createToken('AdViewer App')->plainTextToken;

            return response()->json([
                'success' => true,
                'message' => 'Token refreshed successfully',
                'data' => [
                    'token' => $token,
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Token refresh failed',
            ], 500);
        }
    }

    /**
     * Get user profile
     */
    public function getProfile(Request $request): JsonResponse
    {
        try {
            $user = $request->user();
            $user->load(['transactions' => function ($query) {
                $query->latest()->limit(10);
            }]);

            return response()->json([
                'success' => true,
                'data' => [
                    'user' => $this->formatUserData($user),
                    'stats' => [
                        'level' => $user->getLevel(),
                        'total_points_earned' => $user->transactions()
                            ->where('type', 'points_earned')
                            ->where('status', 'completed')
                            ->sum('points_amount'),
                        'total_earnings' => $user->getTotalEarnings(),
                        'referral_earnings' => $user->getReferralEarnings(),
                        'engagement_rate' => $user->getEngagementRate(),
                        'quiz_success_rate' => $user->getQuizSuccessRate(),
                        'days_active' => $user->created_at->diffInDays(now()),
                        'referrals_count' => $user->referrals()->count(),
                    ],
                    'recent_transactions' => $user->transactions,
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get profile',
            ], 500);
        }
    }

    /**
     * Update user profile
     */
    public function updateProfile(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'name' => 'sometimes|string|max:255',
            'birth_date' => 'sometimes|date|before:today',
            'gender' => 'sometimes|in:male,female,other',
            'country' => 'sometimes|string|size:2',
            'language' => 'sometimes|string|size:2',
            'avatar_url' => 'sometimes|url',
            'notification_preferences' => 'sometimes|array',
            'privacy_settings' => 'sometimes|array',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation errors',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            $user = $request->user();
            $user->update($validator->validated());

            return response()->json([
                'success' => true,
                'message' => 'Profile updated successfully',
                'data' => [
                    'user' => $this->formatUserData($user),
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Profile update failed',
            ], 500);
        }
    }

    /**
     * Delete user account
     */
    public function deleteAccount(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'password' => 'required|string',
            'confirmation' => 'required|in:DELETE',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation errors',
                'errors' => $validator->errors(),
            ], 422);
        }

        $user = $request->user();

        if (!Hash::check($request->password, $user->password)) {
            return response()->json([
                'success' => false,
                'message' => 'Invalid password',
            ], 401);
        }

        try {
            // Soft delete user
            $user->delete();

            // Revoke all tokens
            $user->tokens()->delete();

            return response()->json([
                'success' => true,
                'message' => 'Account deleted successfully',
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Account deletion failed',
            ], 500);
        }
    }

    /**
     * Change password
     */
    public function changePassword(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'current_password' => 'required|string',
            'new_password' => 'required|string|min:8|confirmed',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation errors',
                'errors' => $validator->errors(),
            ], 422);
        }

        $user = $request->user();

        if (!Hash::check($request->current_password, $user->password)) {
            return response()->json([
                'success' => false,
                'message' => 'Current password is incorrect',
            ], 401);
        }

        try {
            $user->update([
                'password' => Hash::make($request->new_password),
            ]);

            // Revoke all tokens for security
            $user->tokens()->delete();

            return response()->json([
                'success' => true,
                'message' => 'Password changed successfully. Please login again.',
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Password change failed',
            ], 500);
        }
    }

    /**
     * Format user data for API response
     */
    private function formatUserData(User $user): array
    {
        return [
            'id' => $user->id,
            'name' => $user->name,
            'email' => $user->email,
            'points' => $user->points,
            'wallet_balance' => $user->wallet_balance,
            'referral_code' => $user->referral_code,
            'birth_date' => $user->birth_date?->format('Y-m-d'),
            'gender' => $user->gender,
            'country' => $user->country,
            'language' => $user->language,
            'avatar_url' => $user->avatar_url,
            'is_verified' => $user->is_verified,
            'created_at' => $user->created_at->toISOString(),
            'last_login_at' => $user->last_login_at?->toISOString(),
        ];
    }

    /**
     * Get country from IP address (placeholder)
     */
    private function getCountryFromIP(string $ip): string
    {
        // TODO: Implement IP geolocation service
        return 'FR'; // Default to France
    }
}
