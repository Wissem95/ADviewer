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
        Schema::create('quizzes', function (Blueprint $table) {
            $table->id();
            $table->foreignId('ad_id')->constrained('ads')->onDelete('cascade');

            // Question content
            $table->text('question');
            $table->json('options'); // Array of possible answers
            $table->integer('correct_answer_index'); // Index of correct answer in options array
            $table->text('explanation')->nullable(); // Explanation of the correct answer

            // Quiz settings
            $table->enum('difficulty', ['easy', 'medium', 'hard'])->default('easy');
            $table->integer('time_limit')->default(30); // seconds
            $table->integer('points_reward')->default(5);

            // Analytics
            $table->integer('attempts_count')->default(0);
            $table->integer('success_count')->default(0);
            $table->decimal('success_rate', 5, 2)->default(0);
            $table->decimal('average_time_taken', 5, 2)->default(0); // seconds

            // Question metadata
            $table->string('question_type')->default('multiple_choice'); // Future: true/false, fill_blank
            $table->boolean('is_active')->default(true);
            $table->integer('display_order')->default(1);

            $table->timestamps();

            // Indexes
            $table->index(['ad_id']);
            $table->index(['difficulty']);
            $table->index(['is_active']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('quizzes');
    }
};
