<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('transactions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained('users')->onDelete('cascade');

            // Transaction type and details
            $table->enum('type', [
                'points_earned',        // Points gagnés en regardant des pubs
                'points_converted',     // Points convertis en euros
                'withdrawal',           // Retrait d'argent
                'referral_bonus',       // Bonus de parrainage
                'daily_bonus',          // Bonus quotidien
                'achievement_bonus',    // Bonus pour achievements
                'penalty',              // Pénalité pour fraude
                'refund'               // Remboursement
            ]);

            // Amounts
            $table->integer('points_amount')->nullable(); // Points involved
            $table->decimal('money_amount', 10, 2)->nullable(); // Money involved (EUR)

            // Transaction status
            $table->enum('status', ['pending', 'processing', 'completed', 'failed', 'cancelled'])->default('pending');
            $table->text('status_message')->nullable();

            // Related records
            $table->foreignId('ad_id')->nullable()->constrained('ads')->onDelete('set null');
            $table->foreignId('user_ad_view_id')->nullable()->constrained('user_ad_views')->onDelete('set null');
            $table->foreignId('referral_user_id')->nullable()->constrained('users')->onDelete('set null');

            // Payment details
            $table->string('payment_method')->nullable(); // paypal, bank_transfer, crypto
            $table->json('payment_details')->nullable(); // Payment gateway response
            $table->string('payment_reference')->nullable(); // External payment ID
            $table->string('payment_gateway')->nullable(); // paypal, stripe, etc.

            // Conversion rate (at time of transaction)
            $table->decimal('points_to_euro_rate', 8, 4)->nullable();

            // Fees
            $table->decimal('platform_fee', 8, 4)->default(0);
            $table->decimal('payment_fee', 8, 4)->default(0);
            $table->decimal('net_amount', 10, 2)->nullable(); // Amount after fees

            // Administrative
            $table->text('description')->nullable();
            $table->json('metadata')->nullable(); // Additional data
            $table->string('admin_note')->nullable();
            $table->foreignId('processed_by')->nullable()->constrained('users')->onDelete('set null');

            // Timestamps
            $table->timestamp('processed_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->timestamps();

            // Indexes
            $table->index(['user_id', 'type']);
            $table->index(['user_id', 'status']);
            $table->index(['type', 'status']);
            $table->index(['created_at']);
            $table->index(['payment_reference']);
            $table->index(['ad_id']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('transactions');
    }
};
