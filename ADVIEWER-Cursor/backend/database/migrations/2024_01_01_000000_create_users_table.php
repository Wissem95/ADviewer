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
        Schema::create('users', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('email')->unique();
            $table->timestamp('email_verified_at')->nullable();
            $table->string('password');

            // Points and wallet
            $table->integer('points')->default(0);
            $table->decimal('wallet_balance', 10, 2)->default(0);

            // Referral system
            $table->string('referral_code', 10)->unique()->nullable();
            $table->foreignId('referred_by')->nullable()->constrained('users')->onDelete('set null');

            // User profile
            $table->date('birth_date')->nullable();
            $table->enum('gender', ['male', 'female', 'other'])->nullable();
            $table->string('country', 2)->nullable();
            $table->string('language', 2)->default('en');
            $table->string('avatar_url')->nullable();

            // Account status
            $table->boolean('is_active')->default(true);
            $table->boolean('is_verified')->default(false);
            $table->timestamp('last_login_at')->nullable();
            $table->string('last_login_ip')->nullable();

            // Anti-fraud
            $table->json('device_info')->nullable();
            $table->integer('daily_ad_views')->default(0);
            $table->date('last_ad_view_date')->nullable();

            // Preferences
            $table->json('notification_preferences')->nullable();
            $table->json('privacy_settings')->nullable();

            $table->rememberToken();
            $table->timestamps();

            // Indexes
            $table->index(['referral_code']);
            $table->index(['is_active', 'is_verified']);
            $table->index(['last_ad_view_date']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('users');
    }
};
