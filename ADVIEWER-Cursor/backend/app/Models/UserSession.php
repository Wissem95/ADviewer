<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class UserSession extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'user_id',
        'session_id',
        'device_id',
        'device_fingerprint',
        'device_type',
        'platform',
        'os_version',
        'app_version',
        'user_agent',
        'ip_address',
        'country',
        'city',
        'isp',
        'is_vpn',
        'is_proxy',
        'ads_viewed',
        'quizzes_completed',
        'points_earned',
        'session_duration',
        'fraud_score',
        'fraud_indicators',
        'is_suspicious',
        'is_blocked',
        'started_at',
        'last_active_at',
        'ended_at',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'user_id' => 'integer',
        'is_vpn' => 'boolean',
        'is_proxy' => 'boolean',
        'ads_viewed' => 'integer',
        'quizzes_completed' => 'integer',
        'points_earned' => 'integer',
        'session_duration' => 'decimal:2',
        'fraud_score' => 'decimal:2',
        'fraud_indicators' => 'array',
        'is_suspicious' => 'boolean',
        'is_blocked' => 'boolean',
        'started_at' => 'datetime',
        'last_active_at' => 'datetime',
        'ended_at' => 'datetime',
    ];

    /**
     * Get the user that owns this session
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Update last active timestamp
     */
    public function updateLastActive(): void
    {
        $this->update(['last_active_at' => now()]);
        $this->updateSessionDuration();
    }

    /**
     * Update session duration
     */
    private function updateSessionDuration(): void
    {
        if ($this->started_at) {
            $duration = $this->started_at->diffInMinutes(now());
            $this->update(['session_duration' => $duration]);
        }
    }

    /**
     * End the session
     */
    public function endSession(): void
    {
        $this->update([
            'ended_at' => now(),
        ]);
        $this->updateSessionDuration();
    }

    /**
     * Increment ads viewed
     */
    public function incrementAdsViewed(): void
    {
        $this->increment('ads_viewed');
        $this->updateLastActive();
    }

    /**
     * Increment quizzes completed
     */
    public function incrementQuizzesCompleted(): void
    {
        $this->increment('quizzes_completed');
        $this->updateLastActive();
    }

    /**
     * Add points earned to session
     */
    public function addPointsEarned(int $points): void
    {
        $this->increment('points_earned', $points);
        $this->updateLastActive();
    }

    /**
     * Check if session is suspicious
     */
    public function isSuspicious(): bool
    {
        if ($this->is_suspicious) {
            return true;
        }

        // Check for abnormal activity patterns
        if ($this->ads_viewed > 50) {
            $this->markAsSuspicious('Excessive ad viewing');
            return true;
        }

        if ($this->session_duration > 0 && $this->ads_viewed / $this->session_duration > 2) {
            $this->markAsSuspicious('Unrealistic viewing rate');
            return true;
        }

        if ($this->is_vpn || $this->is_proxy) {
            $this->markAsSuspicious('VPN/Proxy usage');
            return true;
        }

        return false;
    }

    /**
     * Mark session as suspicious
     */
    public function markAsSuspicious(string $reason): void
    {
        $indicators = $this->fraud_indicators ?? [];
        $indicators[] = [
            'reason' => $reason,
            'detected_at' => now()->toISOString(),
            'ads_viewed' => $this->ads_viewed,
            'session_duration' => $this->session_duration,
        ];

        $this->update([
            'is_suspicious' => true,
            'fraud_indicators' => $indicators,
            'fraud_score' => min($this->fraud_score + 0.3, 1.0),
        ]);
    }

    /**
     * Block session
     */
    public function blockSession(string $reason): void
    {
        $this->markAsSuspicious($reason);
        $this->update(['is_blocked' => true]);
        $this->endSession();
    }

    /**
     * Get session efficiency (points per minute)
     */
    public function getEfficiency(): float
    {
        if ($this->session_duration <= 0) {
            return 0;
        }

        return round($this->points_earned / $this->session_duration, 2);
    }

    /**
     * Check if session is active
     */
    public function isActive(): bool
    {
        return is_null($this->ended_at) &&
            !$this->is_blocked &&
            $this->last_active_at->diffInMinutes(now()) < 30;
    }

    /**
     * Scope for active sessions
     */
    public function scopeActive($query)
    {
        return $query->whereNull('ended_at')
            ->where('is_blocked', false)
            ->where('last_active_at', '>=', now()->subMinutes(30));
    }

    /**
     * Scope for suspicious sessions
     */
    public function scopeSuspicious($query)
    {
        return $query->where('is_suspicious', true);
    }

    /**
     * Scope for today's sessions
     */
    public function scopeToday($query)
    {
        return $query->whereDate('started_at', today());
    }

    /**
     * Create new session for user
     */
    public static function createForUser(User $user, array $data = []): self
    {
        return static::create(array_merge([
            'user_id' => $user->id,
            'session_id' => \Str::uuid(),
            'device_id' => $data['device_id'] ?? 'unknown',
            'device_type' => $data['device_type'] ?? 'unknown',
            'platform' => $data['platform'] ?? 'unknown',
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'started_at' => now(),
            'last_active_at' => now(),
        ], $data));
    }
}
