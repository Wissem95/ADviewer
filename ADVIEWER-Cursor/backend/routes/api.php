<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\API\AuthController;
use App\Http\Controllers\API\AdController;
use App\Http\Controllers\API\QuizController;
use App\Http\Controllers\API\WalletController;
use App\Http\Controllers\API\LeaderboardController;
use App\Http\Controllers\API\UserController;

// Health check
Route::get('/health', function () {
    return response()->json([
        'status' => 'ok',
        'message' => 'AdViewer API is running',
        'timestamp' => now(),
        'version' => '1.0.0'
    ]);
});

// Public routes
Route::prefix('auth')->group(function () {
    Route::post('/register', [AuthController::class, 'register']);
    Route::post('/login', [AuthController::class, 'login']);
    Route::post('/refresh', [AuthController::class, 'refresh']);
    Route::post('/forgot-password', [AuthController::class, 'forgotPassword']);
    Route::post('/reset-password', [AuthController::class, 'resetPassword']);
    Route::post('/verify-referral', [AuthController::class, 'verifyReferral']);
});

// Protected routes
Route::middleware(['auth:sanctum', 'anti.fraud'])->group(function () {

    // Auth routes
    Route::prefix('auth')->group(function () {
        Route::post('/logout', [AuthController::class, 'logout']);
        Route::get('/me', [AuthController::class, 'me']);
        Route::put('/profile', [AuthController::class, 'updateProfile']);
        Route::post('/change-password', [AuthController::class, 'changePassword']);
        Route::delete('/account', [AuthController::class, 'deleteAccount']);
    });

    // User routes
    Route::prefix('user')->group(function () {
        Route::get('/stats', [UserController::class, 'getStats']);
        Route::get('/referrals', [UserController::class, 'getReferrals']);
        Route::post('/generate-referral-code', [UserController::class, 'generateReferralCode']);
        Route::get('/achievements', [UserController::class, 'getAchievements']);
        Route::get('/activity-log', [UserController::class, 'getActivityLog']);
    });

    // Ad routes with rate limiting
    Route::middleware(['rate.limit.viewing'])->prefix('ads')->group(function () {
        Route::get('/feed', [AdController::class, 'getFeed']);
        Route::get('/{id}', [AdController::class, 'show']);
        Route::post('/{id}/view', [AdController::class, 'recordView']);
        Route::post('/{id}/complete', [AdController::class, 'recordCompletion']);
        Route::post('/{id}/report', [AdController::class, 'reportAd']);
    });

    // Quiz routes
    Route::prefix('quizzes')->group(function () {
        Route::get('/ad/{adId}', [QuizController::class, 'getQuizForAd']);
        Route::post('/{id}/answer', [QuizController::class, 'submitAnswer']);
        Route::get('/{id}/result', [QuizController::class, 'getResult']);
    });

    // Wallet routes
    Route::prefix('wallet')->group(function () {
        Route::get('/', [WalletController::class, 'getBalance']);
        Route::get('/transactions', [WalletController::class, 'getTransactions']);
        Route::post('/withdraw', [WalletController::class, 'withdraw']);
        Route::get('/withdrawal-methods', [WalletController::class, 'getWithdrawalMethods']);
        Route::post('/convert-points', [WalletController::class, 'convertPoints']);
        Route::get('/earnings-history', [WalletController::class, 'getEarningsHistory']);
    });

    // Leaderboard routes
    Route::prefix('leaderboard')->group(function () {
        Route::get('/daily', [LeaderboardController::class, 'daily']);
        Route::get('/weekly', [LeaderboardController::class, 'weekly']);
        Route::get('/monthly', [LeaderboardController::class, 'monthly']);
        Route::get('/all-time', [LeaderboardController::class, 'allTime']);
        Route::get('/friends', [LeaderboardController::class, 'friends']);
    });
});

// Admin routes (will be implemented later)
Route::middleware(['auth:sanctum', 'admin'])->prefix('admin')->group(function () {
    Route::get('/dashboard', function () {
        return response()->json(['message' => 'Admin dashboard - Coming soon']);
    });
});
