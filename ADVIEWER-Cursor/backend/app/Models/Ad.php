<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Database\Eloquent\Builder;
use Carbon\Carbon;

class Ad extends Model
{
    use HasFactory, SoftDeletes;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'title',
        'description',
        'video_url',
        'thumbnail_url',
        'duration',
        'points_reward',
        'advertiser_name',
        'advertiser_logo_url',
        'advertiser_website',
        'category',
        'target_age_min',
        'target_age_max',
        'target_gender',
        'target_countries',
        'target_languages',
        'budget',
        'cost_per_view',
        'cost_per_completed_view',
        'remaining_budget',
        'start_date',
        'end_date',
        'is_active',
        'is_approved',
        'views_count',
        'completed_views_count',
        'clicks_count',
        'quiz_attempts_count',
        'quiz_success_count',
        'engagement_rate',
        'completion_rate',
        'quiz_success_rate',
        'reports_count',
        'is_flagged',
        'moderation_notes',
        'priority',
        'algorithm_weights',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'duration' => 'integer',
        'points_reward' => 'integer',
        'target_age_min' => 'integer',
        'target_age_max' => 'integer',
        'target_countries' => 'array',
        'target_languages' => 'array',
        'budget' => 'decimal:2',
        'cost_per_view' => 'decimal:4',
        'cost_per_completed_view' => 'decimal:4',
        'remaining_budget' => 'decimal:2',
        'start_date' => 'datetime',
        'end_date' => 'datetime',
        'is_active' => 'boolean',
        'is_approved' => 'boolean',
        'views_count' => 'integer',
        'completed_views_count' => 'integer',
        'clicks_count' => 'integer',
        'quiz_attempts_count' => 'integer',
        'quiz_success_count' => 'integer',
        'engagement_rate' => 'decimal:2',
        'completion_rate' => 'decimal:2',
        'quiz_success_rate' => 'decimal:2',
        'reports_count' => 'integer',
        'is_flagged' => 'boolean',
        'priority' => 'integer',
        'algorithm_weights' => 'array',
    ];

    /**
     * Get the quiz for this ad
     */
    public function quiz(): HasOne
    {
        return $this->hasOne(Quiz::class);
    }

    /**
     * Get all user views for this ad
     */
    public function userViews(): HasMany
    {
        return $this->hasMany(UserAdView::class);
    }

    /**
     * Get all transactions related to this ad
     */
    public function transactions(): HasMany
    {
        return $this->hasMany(Transaction::class);
    }

    /**
     * Scope for active ads
     */
    public function scopeActive(Builder $query): Builder
    {
        return $query->where('is_active', true)
            ->where('is_approved', true)
            ->where('is_flagged', false);
    }

    /**
     * Scope for ads within campaign period
     */
    public function scopeInCampaignPeriod(Builder $query): Builder
    {
        $now = now();
        return $query->where('start_date', '<=', $now)
            ->where('end_date', '>=', $now);
    }

    /**
     * Scope for ads with remaining budget
     */
    public function scopeWithBudget(Builder $query): Builder
    {
        return $query->where('remaining_budget', '>', 0);
    }

    /**
     * Scope for ads targeting specific user
     */
    public function scopeTargetingUser(Builder $query, User $user): Builder
    {
        return $query->where(function ($q) use ($user) {
            // Age targeting
            if ($user->birth_date) {
                $age = $user->birth_date->age;
                $q->where(function ($ageQuery) use ($age) {
                    $ageQuery->whereNull('target_age_min')
                        ->orWhere('target_age_min', '<=', $age);
                })->where(function ($ageQuery) use ($age) {
                    $ageQuery->whereNull('target_age_max')
                        ->orWhere('target_age_max', '>=', $age);
                });
            }

            // Gender targeting
            if ($user->gender) {
                $q->where(function ($genderQuery) use ($user) {
                    $genderQuery->where('target_gender', 'all')
                        ->orWhere('target_gender', $user->gender);
                });
            }

            // Country targeting
            if ($user->country) {
                $q->where(function ($countryQuery) use ($user) {
                    $countryQuery->whereNull('target_countries')
                        ->orWhereJsonContains('target_countries', $user->country);
                });
            }

            // Language targeting
            if ($user->language) {
                $q->where(function ($langQuery) use ($user) {
                    $langQuery->whereNull('target_languages')
                        ->orWhereJsonContains('target_languages', $user->language);
                });
            }
        });
    }

    /**
     * Scope for ads not viewed by user
     */
    public function scopeNotViewedByUser(Builder $query, User $user): Builder
    {
        return $query->whereNotExists(function ($q) use ($user) {
            $q->select('id')
                ->from('user_ad_views')
                ->whereColumn('user_ad_views.ad_id', 'ads.id')
                ->where('user_ad_views.user_id', $user->id)
                ->where('user_ad_views.completed', true);
        });
    }

    /**
     * Scope for prioritized ads
     */
    public function scopePrioritized(Builder $query): Builder
    {
        return $query->orderByDesc('priority')
            ->orderByDesc('engagement_rate')
            ->orderBy('views_count');
    }

    /**
     * Check if ad is currently available
     */
    public function isAvailable(): bool
    {
        return $this->is_active
            && $this->is_approved
            && !$this->is_flagged
            && $this->remaining_budget > 0
            && $this->start_date <= now()
            && $this->end_date >= now();
    }

    /**
     * Check if user can view this ad
     */
    public function canBeViewedBy(User $user): bool
    {
        if (!$this->isAvailable()) {
            return false;
        }

        // Check if user already viewed this ad today
        $hasViewedToday = $this->userViews()
            ->where('user_id', $user->id)
            ->where('completed', true)
            ->whereDate('viewed_at', today())
            ->exists();

        if ($hasViewedToday) {
            return false;
        }

        // Check targeting criteria
        return $this->matchesTargeting($user);
    }

    /**
     * Check if ad matches user targeting
     */
    private function matchesTargeting(User $user): bool
    {
        // Age targeting
        if ($this->target_age_min || $this->target_age_max) {
            if (!$user->birth_date) return false;

            $age = $user->birth_date->age;
            if ($this->target_age_min && $age < $this->target_age_min) return false;
            if ($this->target_age_max && $age > $this->target_age_max) return false;
        }

        // Gender targeting
        if ($this->target_gender !== 'all' && $this->target_gender !== $user->gender) {
            return false;
        }

        // Country targeting
        if ($this->target_countries && !in_array($user->country, $this->target_countries)) {
            return false;
        }

        // Language targeting
        if ($this->target_languages && !in_array($user->language, $this->target_languages)) {
            return false;
        }

        return true;
    }

    /**
     * Record a view for this ad
     */
    public function recordView(User $user, array $data = []): UserAdView
    {
        $view = $this->userViews()->create(array_merge([
            'user_id' => $user->id,
            'watched_duration' => 0,
            'completed' => false,
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'viewed_at' => now(),
        ], $data));

        $this->increment('views_count');
        return $view;
    }

    /**
     * Record a completed view
     */
    public function recordCompletedView(UserAdView $view): void
    {
        $view->update(['completed' => true]);
        $this->increment('completed_views_count');

        // Deduct from budget
        $cost = $this->cost_per_completed_view ?? $this->cost_per_view;
        $this->decrement('remaining_budget', $cost);

        // Update metrics
        $this->updateMetrics();
    }

    /**
     * Record a quiz attempt
     */
    public function recordQuizAttempt(UserAdView $view, bool $passed, int $timeTaken): void
    {
        $view->update([
            'quiz_attempted' => true,
            'quiz_passed' => $passed,
            'quiz_time_taken' => $timeTaken,
        ]);

        $this->increment('quiz_attempts_count');
        if ($passed) {
            $this->increment('quiz_success_count');
        }

        $this->updateMetrics();
    }

    /**
     * Update ad metrics
     */
    private function updateMetrics(): void
    {
        // Completion rate
        if ($this->views_count > 0) {
            $this->completion_rate = round(($this->completed_views_count / $this->views_count) * 100, 2);
        }

        // Quiz success rate
        if ($this->quiz_attempts_count > 0) {
            $this->quiz_success_rate = round(($this->quiz_success_count / $this->quiz_attempts_count) * 100, 2);
        }

        // Engagement rate (completion + quiz success)
        $this->engagement_rate = round(($this->completion_rate + $this->quiz_success_rate) / 2, 2);

        $this->save();
    }

    /**
     * Get recommended ads for user
     */
    public static function getRecommendedForUser(User $user, int $limit = 10): Collection
    {
        return static::active()
            ->inCampaignPeriod()
            ->withBudget()
            ->targetingUser($user)
            ->notViewedByUser($user)
            ->prioritized()
            ->limit($limit)
            ->get();
    }

    /**
     * Get ads by category
     */
    public static function getByCategory(string $category, int $limit = 20): Collection
    {
        return static::active()
            ->inCampaignPeriod()
            ->withBudget()
            ->where('category', $category)
            ->prioritized()
            ->limit($limit)
            ->get();
    }

    /**
     * Report this ad
     */
    public function report(User $user, string $reason): void
    {
        $this->increment('reports_count');

        // Flag ad if too many reports
        if ($this->reports_count >= 10) {
            $this->update(['is_flagged' => true]);
        }

        // Log the report
        activity()
            ->performedOn($this)
            ->causedBy($user)
            ->withProperties(['reason' => $reason])
            ->log('ad_reported');
    }

    /**
     * Get performance summary
     */
    public function getPerformanceSummary(): array
    {
        return [
            'views' => $this->views_count,
            'completed_views' => $this->completed_views_count,
            'completion_rate' => $this->completion_rate,
            'quiz_attempts' => $this->quiz_attempts_count,
            'quiz_success_rate' => $this->quiz_success_rate,
            'engagement_rate' => $this->engagement_rate,
            'total_cost' => $this->budget - $this->remaining_budget,
            'ctr' => $this->views_count > 0 ? round(($this->clicks_count / $this->views_count) * 100, 2) : 0,
        ];
    }
}
