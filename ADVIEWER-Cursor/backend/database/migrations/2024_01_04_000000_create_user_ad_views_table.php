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
        Schema::create('user_ad_views', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained('users')->onDelete('cascade');
            $table->foreignId('ad_id')->constrained('ads')->onDelete('cascade');

            // Viewing data
            $table->integer('watched_duration')->default(0); // seconds watched
            $table->boolean('completed')->default(false); // watched to end
            $table->boolean('skipped')->default(false);
            $table->integer('skip_time')->nullable(); // when user skipped (seconds)

            // Quiz interaction
            $table->boolean('quiz_attempted')->default(false);
            $table->boolean('quiz_passed')->default(false);
            $table->integer('quiz_time_taken')->nullable(); // seconds
            $table->integer('quiz_attempts')->default(0);
            $table->json('quiz_answers')->nullable(); // array of answers given

            // Points and rewards
            $table->integer('points_earned')->default(0);
            $table->decimal('advertiser_cost', 8, 4)->default(0);

            // Technical data
            $table->string('ip_address');
            $table->json('device_info')->nullable();
            $table->string('user_agent')->nullable();
            $table->string('platform'); // ios, android, web
            $table->string('app_version')->nullable();

            // Geolocation
            $table->string('country', 2)->nullable();
            $table->string('city')->nullable();
            $table->decimal('latitude', 10, 8)->nullable();
            $table->decimal('longitude', 11, 8)->nullable();

            // Engagement metrics
            $table->integer('replay_count')->default(0);
            $table->boolean('liked')->default(false);
            $table->boolean('shared')->default(false);
            $table->boolean('reported')->default(false);
            $table->string('report_reason')->nullable();

            // Fraud detection
            $table->boolean('is_suspicious')->default(false);
            $table->text('fraud_indicators')->nullable();
            $table->decimal('fraud_score', 3, 2)->default(0);

            // Session data
            $table->string('session_id')->nullable();
            $table->integer('sequence_number')->default(1); // order in viewing session

            $table->timestamp('viewed_at');
            $table->timestamps();

            // Indexes
            $table->index(['user_id', 'ad_id']);
            $table->index(['user_id', 'viewed_at']);
            $table->index(['ad_id', 'viewed_at']);
            $table->index(['completed']);
            $table->index(['quiz_passed']);
            $table->index(['ip_address']);
            $table->index(['is_suspicious']);
            $table->index(['viewed_at']);

            // Unique constraint to prevent duplicate views (same user, ad, and day)
            $table->unique(['user_id', 'ad_id', 'session_id'], 'unique_user_ad_session');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('user_ad_views');
    }
};
