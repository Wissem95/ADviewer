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
        Schema::create('ads', function (Blueprint $table) {
            $table->id();
            $table->string('title');
            $table->text('description')->nullable();
            $table->string('video_url');
            $table->string('thumbnail_url')->nullable();
            $table->integer('duration'); // en secondes

            // Reward system
            $table->integer('points_reward')->default(10);

            // Advertiser info
            $table->string('advertiser_name');
            $table->string('advertiser_logo_url')->nullable();
            $table->string('advertiser_website')->nullable();

            // Targeting
            $table->string('category');
            $table->integer('target_age_min')->nullable();
            $table->integer('target_age_max')->nullable();
            $table->enum('target_gender', ['all', 'male', 'female'])->default('all');
            $table->json('target_countries')->nullable(); // Array of country codes
            $table->json('target_languages')->nullable(); // Array of language codes

            // Budget & economics
            $table->decimal('budget', 10, 2);
            $table->decimal('cost_per_view', 8, 4);
            $table->decimal('cost_per_completed_view', 8, 4)->nullable();
            $table->decimal('remaining_budget', 10, 2);

            // Campaign dates
            $table->timestamp('start_date');
            $table->timestamp('end_date');

            // Status and analytics
            $table->boolean('is_active')->default(true);
            $table->boolean('is_approved')->default(false);
            $table->integer('views_count')->default(0);
            $table->integer('completed_views_count')->default(0);
            $table->integer('clicks_count')->default(0);
            $table->integer('quiz_attempts_count')->default(0);
            $table->integer('quiz_success_count')->default(0);

            // Quality metrics
            $table->decimal('engagement_rate', 5, 2)->default(0);
            $table->decimal('completion_rate', 5, 2)->default(0);
            $table->decimal('quiz_success_rate', 5, 2)->default(0);

            // Content moderation
            $table->integer('reports_count')->default(0);
            $table->boolean('is_flagged')->default(false);
            $table->text('moderation_notes')->nullable();

            // Priority and algorithm
            $table->integer('priority')->default(1); // 1=low, 5=high
            $table->json('algorithm_weights')->nullable();

            $table->timestamps();

            // Indexes
            $table->index(['is_active', 'is_approved']);
            $table->index(['category']);
            $table->index(['start_date', 'end_date']);
            $table->index(['target_age_min', 'target_age_max']);
            $table->index(['priority', 'engagement_rate']);
            $table->index(['remaining_budget']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('ads');
    }
};
