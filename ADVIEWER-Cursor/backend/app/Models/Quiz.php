<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Quiz extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'ad_id',
        'question',
        'options',
        'correct_answer_index',
        'explanation',
        'difficulty',
        'time_limit',
        'points_reward',
        'attempts_count',
        'success_count',
        'success_rate',
        'average_time_taken',
        'question_type',
        'is_active',
        'display_order',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'ad_id' => 'integer',
        'options' => 'array',
        'correct_answer_index' => 'integer',
        'time_limit' => 'integer',
        'points_reward' => 'integer',
        'attempts_count' => 'integer',
        'success_count' => 'integer',
        'success_rate' => 'decimal:2',
        'average_time_taken' => 'decimal:2',
        'is_active' => 'boolean',
        'display_order' => 'integer',
    ];

    /**
     * Get the ad that owns this quiz
     */
    public function ad(): BelongsTo
    {
        return $this->belongsTo(Ad::class);
    }

    /**
     * Check if the given answer is correct
     */
    public function isCorrectAnswer(int $answerIndex): bool
    {
        return $answerIndex === $this->correct_answer_index;
    }

    /**
     * Record a quiz attempt
     */
    public function recordAttempt(bool $isCorrect, float $timeTaken): void
    {
        $this->increment('attempts_count');

        if ($isCorrect) {
            $this->increment('success_count');
        }

        // Update success rate
        $this->success_rate = round(($this->success_count / $this->attempts_count) * 100, 2);

        // Update average time taken
        $totalTime = $this->average_time_taken * ($this->attempts_count - 1) + $timeTaken;
        $this->average_time_taken = round($totalTime / $this->attempts_count, 2);

        $this->save();
    }

    /**
     * Get difficulty multiplier for points
     */
    public function getDifficultyMultiplier(): float
    {
        return match ($this->difficulty) {
            'easy' => 1.0,
            'medium' => 1.5,
            'hard' => 2.0,
            default => 1.0,
        };
    }

    /**
     * Get points for correct answer
     */
    public function getPointsReward(): int
    {
        return (int) round($this->points_reward * $this->getDifficultyMultiplier());
    }

    /**
     * Validate quiz options
     */
    public function validateOptions(): bool
    {
        if (!is_array($this->options) || count($this->options) < 2) {
            return false;
        }

        if ($this->correct_answer_index < 0 || $this->correct_answer_index >= count($this->options)) {
            return false;
        }

        return true;
    }
}
