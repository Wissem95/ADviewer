<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class UserAdView extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'user_id',
        'ad_id',
        'watched_duration',
        'completed',
        'skipped',
        'skip_time',
        'quiz_attempted',
        'quiz_passed',
        'quiz_time_taken',
        'quiz_attempts',
        'quiz_answers',
        'points_earned',
        'advertiser_cost',
        'ip_address',
        'device_info',
        'user_agent',
        'platform',
        'app_version',
        'country',
        'city',
        'latitude',
        'longitude',
        'replay_count',
        'liked',
        'shared',
        'reported',
        'report_reason',
        'is_suspicious',
        'fraud_indicators',
        'fraud_score',
        'session_id',
        'sequence_number',
        'viewed_at',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'user_id' => 'integer',
        'ad_id' => 'integer',
        'watched_duration' => 'integer',
        'completed' => 'boolean',
        'skipped' => 'boolean',
        'skip_time' => 'integer',
        'quiz_attempted' => 'boolean',
        'quiz_passed' => 'boolean',
        'quiz_time_taken' => 'integer',
        'quiz_attempts' => 'integer',
        'quiz_answers' => 'array',
        'points_earned' => 'integer',
        'advertiser_cost' => 'decimal:4',
        'device_info' => 'array',
        'latitude' => 'decimal:8',
        'longitude' => 'decimal:8',
        'replay_count' => 'integer',
        'liked' => 'boolean',
        'shared' => 'boolean',
        'reported' => 'boolean',
        'is_suspicious' => 'boolean',
        'fraud_indicators' => 'array',
        'fraud_score' => 'decimal:2',
        'sequence_number' => 'integer',
        'viewed_at' => 'datetime',
    ];

    /**
     * Get the user that owns this view
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Get the ad that was viewed
     */
    public function ad(): BelongsTo
    {
        return $this->belongsTo(Ad::class);
    }

    /**
     * Check if view is completed (watched to end)
     */
    public function isCompleted(): bool
    {
        return $this->completed;
    }

    /**
     * Get completion percentage
     */
    public function getCompletionPercentage(): float
    {
        if (!$this->ad || $this->ad->duration <= 0) {
            return 0;
        }

        return min(round(($this->watched_duration / $this->ad->duration) * 100, 2), 100);
    }

    /**
     * Mark as completed and award points
     */
    public function markAsCompleted(): void
    {
        if ($this->completed) {
            return; // Already completed
        }

        $this->update(['completed' => true]);

        // Award points for completing the ad
        $points = $this->ad->points_reward;
        $this->user->addPoints($points, 'Ad completion', $this->ad_id);

        $this->update(['points_earned' => $points]);
    }

    /**
     * Process quiz answer
     */
    public function processQuizAnswer(int $answerIndex, float $timeTaken): bool
    {
        $quiz = $this->ad->quiz;
        if (!$quiz) {
            return false;
        }

        $this->increment('quiz_attempts');
        $isCorrect = $quiz->isCorrectAnswer($answerIndex);

        // Store answer
        $answers = $this->quiz_answers ?? [];
        $answers[] = [
            'answer_index' => $answerIndex,
            'time_taken' => $timeTaken,
            'is_correct' => $isCorrect,
            'attempted_at' => now()->toISOString(),
        ];

        $updateData = [
            'quiz_attempted' => true,
            'quiz_answers' => $answers,
            'quiz_time_taken' => $timeTaken,
        ];

        if ($isCorrect) {
            $updateData['quiz_passed'] = true;

            // Award quiz points
            $quizPoints = $quiz->getPointsReward();
            $this->user->addPoints($quizPoints, 'Quiz completion', $this->ad_id);
            $this->increment('points_earned', $quizPoints);
        }

        $this->update($updateData);

        // Update quiz statistics
        $quiz->recordAttempt($isCorrect, $timeTaken);

        return $isCorrect;
    }

    /**
     * Calculate engagement score
     */
    public function getEngagementScore(): float
    {
        $score = 0;

        // Completion bonus
        if ($this->completed) {
            $score += 50;
        } else {
            $score += $this->getCompletionPercentage() * 0.5;
        }

        // Quiz bonus
        if ($this->quiz_attempted) {
            $score += 20;
            if ($this->quiz_passed) {
                $score += 30;
            }
        }

        // Interaction bonuses
        if ($this->liked) $score += 5;
        if ($this->shared) $score += 10;
        if ($this->replay_count > 0) $score += min($this->replay_count * 2, 10);

        return min($score, 100);
    }

    /**
     * Check if view is suspicious
     */
    public function isSuspicious(): bool
    {
        if ($this->is_suspicious) {
            return true;
        }

        // Check for rapid succession views
        $recentViews = static::where('user_id', $this->user_id)
            ->where('created_at', '>=', now()->subMinutes(5))
            ->count();

        if ($recentViews > 10) {
            $this->markAsSuspicious('Rapid succession views');
            return true;
        }

        // Check for unrealistic completion time
        if ($this->completed && $this->watched_duration < ($this->ad->duration * 0.8)) {
            $this->markAsSuspicious('Unrealistic completion time');
            return true;
        }

        return false;
    }

    /**
     * Mark view as suspicious
     */
    public function markAsSuspicious(string $reason): void
    {
        $indicators = $this->fraud_indicators ?? [];
        $indicators[] = [
            'reason' => $reason,
            'detected_at' => now()->toISOString(),
            'ip_address' => $this->ip_address,
        ];

        $this->update([
            'is_suspicious' => true,
            'fraud_indicators' => $indicators,
            'fraud_score' => min($this->fraud_score + 0.2, 1.0),
        ]);
    }

    /**
     * Get watch time formatted
     */
    public function getFormattedWatchTime(): string
    {
        $minutes = floor($this->watched_duration / 60);
        $seconds = $this->watched_duration % 60;

        if ($minutes > 0) {
            return sprintf('%dm %ds', $minutes, $seconds);
        }

        return sprintf('%ds', $seconds);
    }

    /**
     * Scope for completed views
     */
    public function scopeCompleted($query)
    {
        return $query->where('completed', true);
    }

    /**
     * Scope for quiz passed views
     */
    public function scopeQuizPassed($query)
    {
        return $query->where('quiz_passed', true);
    }

    /**
     * Scope for suspicious views
     */
    public function scopeSuspicious($query)
    {
        return $query->where('is_suspicious', true);
    }
}
