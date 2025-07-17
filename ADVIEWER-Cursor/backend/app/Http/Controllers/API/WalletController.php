<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Models\Transaction;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Facades\DB;

class WalletController extends Controller
{
    /**
     * Get wallet balance and overview
     */
    public function getBalance(Request $request): JsonResponse
    {
        try {
            $user = $request->user();

            $pointsEarned = $user->transactions()
                ->where('type', 'points_earned')
                ->where('status', 'completed')
                ->sum('points_amount');

            $pointsConverted = $user->transactions()
                ->where('type', 'points_converted')
                ->where('status', 'completed')
                ->sum('points_amount'); // This is negative

            $totalPointsConverted = abs($pointsConverted);
            $conversionRate = config('adviewer.points_to_euro_rate', 100);

            return response()->json([
                'success' => true,
                'data' => [
                    'points' => [
                        'current_balance' => $user->points,
                        'total_earned' => $pointsEarned,
                        'total_converted' => $totalPointsConverted,
                        'available_for_conversion' => $user->points,
                    ],
                    'money' => [
                        'current_balance' => (float) $user->wallet_balance,
                        'total_earned' => (float) $user->transactions()
                            ->where('type', 'points_converted')
                            ->where('status', 'completed')
                            ->sum('money_amount'),
                        'total_withdrawn' => (float) $user->transactions()
                            ->where('type', 'withdrawal')
                            ->where('status', 'completed')
                            ->sum('money_amount'),
                    ],
                    'conversion' => [
                        'rate' => $conversionRate,
                        'rate_display' => "1€ = {$conversionRate} points",
                        'minimum_conversion' => 50, // Minimum 50 points to convert
                        'estimated_euro_value' => round($user->points / $conversionRate, 2),
                    ],
                    'statistics' => [
                        'total_transactions' => $user->transactions()->count(),
                        'level' => $user->getLevel(),
                        'achievements_unlocked' => $this->getUnlockedAchievements($user),
                    ],
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get wallet balance',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Convert points to money
     */
    public function convertPoints(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'points_amount' => 'required|integer|min:50|max:10000',
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
            $pointsToConvert = $request->points_amount;

            // Check if user has enough points
            if ($user->points < $pointsToConvert) {
                return response()->json([
                    'success' => false,
                    'message' => 'Insufficient points balance',
                    'data' => [
                        'current_points' => $user->points,
                        'requested_points' => $pointsToConvert,
                    ],
                ], 400);
            }

            // Check daily conversion limit (example: max 500 points per day)
            $todayConversions = $user->transactions()
                ->where('type', 'points_converted')
                ->whereDate('created_at', today())
                ->sum('points_amount');

            $dailyLimit = 500; // points
            if (abs($todayConversions) + $pointsToConvert > $dailyLimit) {
                return response()->json([
                    'success' => false,
                    'message' => 'Daily conversion limit exceeded',
                    'data' => [
                        'daily_limit' => $dailyLimit,
                        'already_converted_today' => abs($todayConversions),
                        'available_today' => $dailyLimit - abs($todayConversions),
                    ],
                ], 429);
            }

            DB::beginTransaction();

            try {
                // Perform the conversion
                $success = $user->convertPointsToMoney($pointsToConvert);

                if (!$success) {
                    DB::rollBack();
                    return response()->json([
                        'success' => false,
                        'message' => 'Conversion failed',
                    ], 400);
                }

                DB::commit();

                $conversionRate = config('adviewer.points_to_euro_rate', 100);
                $euroAmount = $pointsToConvert / $conversionRate;

                return response()->json([
                    'success' => true,
                    'message' => 'Points converted successfully',
                    'data' => [
                        'points_converted' => $pointsToConvert,
                        'euro_received' => round($euroAmount, 2),
                        'conversion_rate' => $conversionRate,
                        'new_points_balance' => $user->fresh()->points,
                        'new_money_balance' => (float) $user->fresh()->wallet_balance,
                    ],
                ]);
            } catch (\Exception $e) {
                DB::rollBack();
                throw $e;
            }
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Conversion failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Get transaction history
     */
    public function getTransactions(Request $request): JsonResponse
    {
        try {
            $user = $request->user();
            $perPage = $request->get('per_page', 20);
            $type = $request->get('type'); // 'points_earned', 'points_converted', 'withdrawal'

            $query = $user->transactions()->latest();

            if ($type) {
                $query->where('type', $type);
            }

            $transactions = $query->paginate($perPage);

            $formattedTransactions = $transactions->map(function ($transaction) {
                return [
                    'id' => $transaction->id,
                    'type' => $transaction->type,
                    'type_display' => $this->getTransactionTypeDisplay($transaction->type),
                    'points_amount' => $transaction->points_amount,
                    'money_amount' => $transaction->money_amount ? (float) $transaction->money_amount : null,
                    'status' => $transaction->status,
                    'description' => $transaction->description,
                    'created_at' => $transaction->created_at->toISOString(),
                    'completed_at' => $transaction->completed_at?->toISOString(),
                    'points_to_euro_rate' => $transaction->points_to_euro_rate ? (float) $transaction->points_to_euro_rate : null,
                ];
            });

            return response()->json([
                'success' => true,
                'data' => [
                    'transactions' => $formattedTransactions,
                    'pagination' => [
                        'current_page' => $transactions->currentPage(),
                        'last_page' => $transactions->lastPage(),
                        'per_page' => $transactions->perPage(),
                        'total' => $transactions->total(),
                    ],
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get transactions',
            ], 500);
        }
    }

    /**
     * Get earnings history with detailed breakdown
     */
    public function getEarningsHistory(Request $request): JsonResponse
    {
        try {
            $user = $request->user();
            $period = $request->get('period', 'week'); // day, week, month, year

            $startDate = match ($period) {
                'day' => now()->startOfDay(),
                'week' => now()->startOfWeek(),
                'month' => now()->startOfMonth(),
                'year' => now()->startOfYear(),
                default => now()->startOfWeek(),
            };

            $earnings = $user->transactions()
                ->where('created_at', '>=', $startDate)
                ->where('status', 'completed')
                ->get()
                ->groupBy(function ($transaction) use ($period) {
                    return match ($period) {
                        'day' => $transaction->created_at->format('H:00'),
                        'week' => $transaction->created_at->format('l'),
                        'month' => $transaction->created_at->format('Y-m-d'),
                        'year' => $transaction->created_at->format('Y-m'),
                        default => $transaction->created_at->format('Y-m-d'),
                    };
                });

            $chartData = [];
            foreach ($earnings as $period => $transactions) {
                $pointsEarned = $transactions->where('type', 'points_earned')->sum('points_amount');
                $pointsConverted = abs($transactions->where('type', 'points_converted')->sum('points_amount'));
                $moneyEarned = $transactions->where('type', 'points_converted')->sum('money_amount');

                $chartData[] = [
                    'period' => $period,
                    'points_earned' => $pointsEarned,
                    'points_converted' => $pointsConverted,
                    'money_earned' => (float) $moneyEarned,
                ];
            }

            return response()->json([
                'success' => true,
                'data' => [
                    'period' => $period,
                    'chart_data' => $chartData,
                    'summary' => [
                        'total_points_earned' => $user->transactions()
                            ->where('created_at', '>=', $startDate)
                            ->where('type', 'points_earned')
                            ->where('status', 'completed')
                            ->sum('points_amount'),
                        'total_money_earned' => (float) $user->transactions()
                            ->where('created_at', '>=', $startDate)
                            ->where('type', 'points_converted')
                            ->where('status', 'completed')
                            ->sum('money_amount'),
                    ],
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get earnings history',
            ], 500);
        }
    }

    /**
     * Get withdrawal methods
     */
    public function getWithdrawalMethods(Request $request): JsonResponse
    {
        return response()->json([
            'success' => true,
            'data' => [
                'methods' => [
                    [
                        'id' => 'paypal',
                        'name' => 'PayPal',
                        'description' => 'Retrait via PayPal',
                        'min_amount' => 5.00,
                        'max_amount' => 1000.00,
                        'processing_time' => '1-3 jours',
                        'fee_percentage' => 0.0,
                        'is_available' => true,
                    ],
                    [
                        'id' => 'bank_transfer',
                        'name' => 'Virement bancaire',
                        'description' => 'Virement sur compte bancaire',
                        'min_amount' => 10.00,
                        'max_amount' => 5000.00,
                        'processing_time' => '3-5 jours',
                        'fee_percentage' => 0.0,
                        'is_available' => true,
                    ],
                    [
                        'id' => 'crypto',
                        'name' => 'Cryptomonnaie',
                        'description' => 'Bitcoin, Ethereum, etc.',
                        'min_amount' => 5.00,
                        'max_amount' => 10000.00,
                        'processing_time' => '1-24 heures',
                        'fee_percentage' => 1.0,
                        'is_available' => false, // Coming soon
                    ],
                ],
                'user_balance' => (float) $request->user()->wallet_balance,
            ],
        ]);
    }

    /**
     * Request withdrawal
     */
    public function withdraw(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'amount' => 'required|numeric|min:5|max:1000',
            'method' => 'required|string|in:paypal,bank_transfer',
            'payment_details' => 'required|array',
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
            $amount = $request->amount;

            if ($user->wallet_balance < $amount) {
                return response()->json([
                    'success' => false,
                    'message' => 'Insufficient balance',
                    'data' => [
                        'current_balance' => (float) $user->wallet_balance,
                        'requested_amount' => $amount,
                    ],
                ], 400);
            }

            // Create withdrawal transaction
            $transaction = $user->transactions()->create([
                'type' => 'withdrawal',
                'money_amount' => -$amount,
                'status' => 'pending',
                'payment_method' => $request->method,
                'payment_details' => $request->payment_details,
                'description' => 'Withdrawal request',
            ]);

            // Deduct from wallet balance
            $user->decrement('wallet_balance', $amount);

            return response()->json([
                'success' => true,
                'message' => 'Withdrawal request submitted',
                'data' => [
                    'transaction_id' => $transaction->id,
                    'amount' => $amount,
                    'method' => $request->method,
                    'status' => 'pending',
                    'estimated_processing_time' => $request->method === 'paypal' ? '1-3 jours' : '3-5 jours',
                    'new_balance' => (float) $user->fresh()->wallet_balance,
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Withdrawal request failed',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Get transaction type display name
     */
    private function getTransactionTypeDisplay(string $type): string
    {
        return match ($type) {
            'points_earned' => 'Points gagnés',
            'points_converted' => 'Points convertis',
            'withdrawal' => 'Retrait',
            'referral_bonus' => 'Bonus parrainage',
            'daily_bonus' => 'Bonus quotidien',
            'achievement_bonus' => 'Bonus achievement',
            'penalty' => 'Pénalité',
            'refund' => 'Remboursement',
            default => ucfirst($type),
        };
    }

    /**
     * Get unlocked achievements
     */
    private function getUnlockedAchievements(User $user): array
    {
        $achievements = [];

        $totalPoints = $user->transactions()
            ->where('type', 'points_earned')
            ->where('status', 'completed')
            ->sum('points_amount');

        if ($totalPoints >= 100) $achievements[] = 'Premier 100 points';
        if ($totalPoints >= 500) $achievements[] = 'Collectionneur (500 points)';
        if ($totalPoints >= 1000) $achievements[] = 'Expert (1000 points)';
        if ($totalPoints >= 5000) $achievements[] = 'Maître (5000 points)';

        $conversions = $user->transactions()
            ->where('type', 'points_converted')
            ->where('status', 'completed')
            ->count();

        if ($conversions >= 1) $achievements[] = 'Première conversion';
        if ($conversions >= 5) $achievements[] = 'Convertisseur régulier';

        return $achievements;
    }
}
