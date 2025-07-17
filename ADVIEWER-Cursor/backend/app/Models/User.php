<?php

namespace App\Models;

use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Laravel\Sanctum\HasApiTokens;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Support\Str;

class User extends Authenticatable implements MustVerifyEmail
{
    use HasApiTokens, HasFactory, Notifiable, SoftDeletes;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'name',
        'email',
        'password',
        'points',
        'wallet_balance',
        'referral_code',
        'referred_by',
        'birth_date',
        'gender',
        'country',
        'language',
        'avatar_url',
        'is_active',
        'is_verified',
        'last_login_at',
        'last_login_ip',
        'device_info',
        'daily_ad_views',
        'last_ad_view_date',
        'notification_preferences',
        'privacy_settings',
    ];

    /**
     * The attributes that should be hidden for serialization.
     */
    protected $hidden = [
        'password',
        'remember_token',
        'device_info',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'email_verified_at' => 'datetime',
        'password' => 'hashed',
        'points' => 'integer',
        'wallet_balance' => 'decimal:2',
        'birth_date' => 'date',
        'is_active' => 'boolean',
        'is_verified' => 'boolean',
        'last_login_at' => 'datetime',
        'daily_ad_views' => 'integer',
        'last_ad_view_date' => 'date',
        'device_info' => 'array',
        'notification_preferences' => 'array',
        'privacy_settings' => 'array',
    ];

    /**
     * Boot method to generate referral code
     */
    protected static function boot()
    {
        parent::boot();

        static::creating(function ($user) {
            if (empty($user->referral_code)) {
                $user->referral_code = static::generateUniqueReferralCode();
            }
        });
    }

    /**
     * Generate unique referral code
     */
    private static function generateUniqueReferralCode(): string
    {
        do {
            $code = strtoupper(Str::random(8));
        } while (static::where('referral_code', $code)->exists());

        return $code;
    }

    /**
     * Get user's ad views
     */
    public function adViews(): HasMany
    {
        return $this->hasMany(UserAdView::class);
    }

    /**
     * Get user's transactions
     */
    public function transactions(): HasMany
    {
        return $this->hasMany(Transaction::class);
    }

    /**
     * Get user's sessions
     */
    public function sessions(): HasMany
    {
        return $this->hasMany(UserSession::class);
    }

    /**
     * Get user who referred this user
     */
    public function referrer(): BelongsTo
    {
        return $this->belongsTo(User::class, 'referred_by');
    }

    /**
     * Get users referred by this user
     */
    public function referrals(): HasMany
    {
        return $this->hasMany(User::class, 'referred_by');
    }

    /**
     * Get user's processed transactions
     */
    public function processedTransactions(): HasMany
    {
        return $this->hasMany(Transaction::class, 'processed_by');
    }

    /**
     * Check if user can view more ads today
     */
    public function canViewMoreAds(): bool
    {
        $dailyLimit = config('adviewer.daily_viewing_limit', 50);

        if ($this->last_ad_view_date?->isToday()) {
            return $this->daily_ad_views < $dailyLimit;
        }

        return true;
    }

    /**
     * Reset daily ad views if needed
     */
    public function resetDailyAdViewsIfNeeded(): void
    {
        if (!$this->last_ad_view_date?->isToday()) {
            $this->update([
                'daily_ad_views' => 0,
                'last_ad_view_date' => now()->toDateString(),
            ]);
        }
    }

    /**
     * Increment daily ad views
     */
    public function incrementDailyAdViews(): void
    {
        $this->resetDailyAdViewsIfNeeded();
        $this->increment('daily_ad_views');
    }

    /**
     * Add points to user account
     */
    public function addPoints(int $points, string $reason = 'Ad viewing', ?int $adId = null): Transaction
    {
        $this->increment('points', $points);

        return $this->transactions()->create([
            'type' => 'points_earned',
            'points_amount' => $points,
            'description' => $reason,
            'ad_id' => $adId,
            'status' => 'completed',
            'completed_at' => now(),
        ]);
    }

    /**
     * Convert points to money
     */
    public function convertPointsToMoney(int $points): bool
    {
        if ($this->points < $points) {
            return false;
        }

        $conversionRate = config('adviewer.points_to_euro_rate', 100);
        $euroAmount = $points / $conversionRate;

        $this->decrement('points', $points);
        $this->increment('wallet_balance', $euroAmount);

        $this->transactions()->create([
            'type' => 'points_converted',
            'points_amount' => -$points,
            'money_amount' => $euroAmount,
            'points_to_euro_rate' => $conversionRate,
            'status' => 'completed',
            'completed_at' => now(),
        ]);

        return true;
    }

    /**
     * Get user's level based on points
     */
    public function getLevel(): int
    {
        $totalPoints = $this->transactions()
            ->where('type', 'points_earned')
            ->where('status', 'completed')
            ->sum('points_amount');

        return min(floor($totalPoints / 1000) + 1, 100);
    }

    /**
     * Get user's engagement rate
     */
    public function getEngagementRate(): float
    {
        $totalViews = $this->adViews()->count();
        if ($totalViews === 0) return 0;

        $completedViews = $this->adViews()->where('completed', true)->count();
        return round(($completedViews / $totalViews) * 100, 2);
    }

    /**
     * Get user's quiz success rate
     */
    public function getQuizSuccessRate(): float
    {
        $totalQuizzes = $this->adViews()->where('quiz_attempted', true)->count();
        if ($totalQuizzes === 0) return 0;

        $passedQuizzes = $this->adViews()->where('quiz_passed', true)->count();
        return round(($passedQuizzes / $totalQuizzes) * 100, 2);
    }

    /**
     * Check if user is suspicious
     */
    public function isSuspicious(): bool
    {
        // Check for multiple accounts from same IP
        $sameIpUsers = static::where('last_login_ip', $this->last_login_ip)
            ->where('id', '!=', $this->id)
            ->count();

        if ($sameIpUsers >= config('adviewer.max_accounts_per_ip', 3)) {
            return true;
        }

        // Check for suspicious viewing patterns
        $recentViews = $this->adViews()
            ->where('created_at', '>=', now()->subHour())
            ->count();

        if ($recentViews > 30) {
            return true;
        }

        return false;
    }

    /**
     * Get total earnings in euros
     */
    public function getTotalEarnings(): float
    {
        return $this->transactions()
            ->whereIn('type', ['withdrawal'])
            ->where('status', 'completed')
            ->sum('money_amount');
    }

    /**
     * Get referral earnings
     */
    public function getReferralEarnings(): int
    {
        return $this->transactions()
            ->where('type', 'referral_bonus')
            ->where('status', 'completed')
            ->sum('points_amount');
    }
}
