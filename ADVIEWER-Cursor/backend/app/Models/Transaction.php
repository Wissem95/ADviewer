<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Transaction extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'user_id',
        'type',
        'points_amount',
        'money_amount',
        'status',
        'status_message',
        'ad_id',
        'user_ad_view_id',
        'referral_user_id',
        'payment_method',
        'payment_details',
        'payment_reference',
        'payment_gateway',
        'points_to_euro_rate',
        'platform_fee',
        'payment_fee',
        'net_amount',
        'description',
        'metadata',
        'admin_note',
        'processed_by',
        'processed_at',
        'completed_at',
    ];

    /**
     * The attributes that should be cast.
     */
    protected $casts = [
        'user_id' => 'integer',
        'points_amount' => 'integer',
        'money_amount' => 'decimal:2',
        'ad_id' => 'integer',
        'user_ad_view_id' => 'integer',
        'referral_user_id' => 'integer',
        'payment_details' => 'array',
        'points_to_euro_rate' => 'decimal:4',
        'platform_fee' => 'decimal:4',
        'payment_fee' => 'decimal:4',
        'net_amount' => 'decimal:2',
        'metadata' => 'array',
        'processed_by' => 'integer',
        'processed_at' => 'datetime',
        'completed_at' => 'datetime',
    ];

    /**
     * Get the user that owns this transaction
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Get the ad related to this transaction
     */
    public function ad(): BelongsTo
    {
        return $this->belongsTo(Ad::class);
    }

    /**
     * Get the user ad view related to this transaction
     */
    public function userAdView(): BelongsTo
    {
        return $this->belongsTo(UserAdView::class);
    }

    /**
     * Get the referral user
     */
    public function referralUser(): BelongsTo
    {
        return $this->belongsTo(User::class, 'referral_user_id');
    }

    /**
     * Get the user who processed this transaction
     */
    public function processedByUser(): BelongsTo
    {
        return $this->belongsTo(User::class, 'processed_by');
    }

    /**
     * Scope for points earnings
     */
    public function scopePointsEarned($query)
    {
        return $query->where('type', 'points_earned');
    }

    /**
     * Scope for withdrawals
     */
    public function scopeWithdrawals($query)
    {
        return $query->where('type', 'withdrawal');
    }

    /**
     * Scope for completed transactions
     */
    public function scopeCompleted($query)
    {
        return $query->where('status', 'completed');
    }

    /**
     * Scope for pending transactions
     */
    public function scopePending($query)
    {
        return $query->where('status', 'pending');
    }

    /**
     * Check if transaction is completed
     */
    public function isCompleted(): bool
    {
        return $this->status === 'completed';
    }

    /**
     * Check if transaction is pending
     */
    public function isPending(): bool
    {
        return $this->status === 'pending';
    }

    /**
     * Mark transaction as completed
     */
    public function markAsCompleted(): void
    {
        $this->update([
            'status' => 'completed',
            'completed_at' => now(),
        ]);
    }

    /**
     * Mark transaction as failed
     */
    public function markAsFailed(string $reason = ''): void
    {
        $this->update([
            'status' => 'failed',
            'status_message' => $reason,
        ]);
    }

    /**
     * Get formatted amount
     */
    public function getFormattedAmount(): string
    {
        if ($this->points_amount) {
            return number_format($this->points_amount) . ' points';
        }

        if ($this->money_amount) {
            return '€' . number_format($this->money_amount, 2);
        }

        return 'N/A';
    }

    /**
     * Get transaction description
     */
    public function getDescription(): string
    {
        if ($this->description) {
            return $this->description;
        }

        return match ($this->type) {
            'points_earned' => 'Points earned from ad viewing',
            'points_converted' => 'Points converted to euros',
            'withdrawal' => 'Money withdrawal',
            'referral_bonus' => 'Referral bonus',
            'daily_bonus' => 'Daily login bonus',
            'achievement_bonus' => 'Achievement bonus',
            'penalty' => 'Account penalty',
            'refund' => 'Transaction refund',
            default => 'Transaction',
        };
    }
}
