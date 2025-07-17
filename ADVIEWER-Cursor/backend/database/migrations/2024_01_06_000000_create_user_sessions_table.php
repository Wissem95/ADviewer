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
        Schema::create('user_sessions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained('users')->onDelete('cascade');

            // Session identification
            $table->string('session_id')->unique();
            $table->string('device_id');
            $table->string('device_fingerprint')->nullable();

            // Device information
            $table->string('device_type'); // mobile, tablet, desktop
            $table->string('platform'); // ios, android, web
            $table->string('os_version')->nullable();
            $table->string('app_version')->nullable();
            $table->string('user_agent')->nullable();

            // Network information
            $table->string('ip_address');
            $table->string('country', 2)->nullable();
            $table->string('city')->nullable();
            $table->string('isp')->nullable();
            $table->boolean('is_vpn')->default(false);
            $table->boolean('is_proxy')->default(false);

            // Session analytics
            $table->integer('ads_viewed')->default(0);
            $table->integer('quizzes_completed')->default(0);
            $table->integer('points_earned')->default(0);
            $table->decimal('session_duration', 8, 2)->default(0); // minutes

            // Anti-fraud metrics
            $table->decimal('fraud_score', 3, 2)->default(0);
            $table->json('fraud_indicators')->nullable();
            $table->boolean('is_suspicious')->default(false);
            $table->boolean('is_blocked')->default(false);

            // Timestamps
            $table->timestamp('started_at');
            $table->timestamp('last_active_at');
            $table->timestamp('ended_at')->nullable();
            $table->timestamps();

            // Indexes
            $table->index(['user_id']);
            $table->index(['device_id']);
            $table->index(['ip_address']);
            $table->index(['is_suspicious']);
            $table->index(['started_at']);
            $table->index(['last_active_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('user_sessions');
    }
};
