<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Models\Quiz;
use App\Models\UserAdView;
use App\Models\Ad;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Validator;

class QuizController extends Controller
{
    /**
     * Get quiz for a specific ad
     */
    public function getQuizForAd(Request $request, int $adId): JsonResponse
    {
        try {
            $user = $request->user();

            // Check if user has viewed the ad
            $adView = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $adId)
                ->where('completed', true)
                ->first();

            if (!$adView) {
                return response()->json([
                    'success' => false,
                    'message' => 'You must complete watching the ad first',
                ], 403);
            }

            // Check if quiz already attempted
            if ($adView->quiz_attempted && $adView->quiz_passed) {
                return response()->json([
                    'success' => false,
                    'message' => 'Quiz already completed for this ad',
                ], 409);
            }

            $quiz = Quiz::where('ad_id', $adId)
                ->where('is_active', true)
                ->first();

            if (!$quiz) {
                return response()->json([
                    'success' => false,
                    'message' => 'No quiz available for this ad',
                ], 404);
            }

            return response()->json([
                'success' => true,
                'data' => [
                    'quiz' => [
                        'id' => $quiz->id,
                        'question' => $quiz->question,
                        'options' => $quiz->options,
                        'difficulty' => $quiz->difficulty,
                        'time_limit' => $quiz->time_limit,
                        'points_reward' => $quiz->getPointsReward(),
                        'explanation' => null, // Don't show explanation before answering
                    ],
                    'attempts_remaining' => max(0, 3 - $adView->quiz_attempts), // Max 3 attempts
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to load quiz',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Submit quiz answer
     */
    public function submitAnswer(Request $request, int $quizId): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'answer_index' => 'required|integer|min:0',
            'time_taken' => 'required|numeric|min:0',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation errors',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            $user = $request->user();
            $quiz = Quiz::where('id', $quizId)
                ->where('is_active', true)
                ->first();

            if (!$quiz) {
                return response()->json([
                    'success' => false,
                    'message' => 'Quiz not found',
                ], 404);
            }

            // Find the user's ad view for this quiz
            $adView = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $quiz->ad_id)
                ->where('completed', true)
                ->first();

            if (!$adView) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad must be completed first',
                ], 403);
            }

            // Check if quiz already passed
            if ($adView->quiz_passed) {
                return response()->json([
                    'success' => false,
                    'message' => 'Quiz already completed successfully',
                ], 409);
            }

            // Check attempts limit
            if ($adView->quiz_attempts >= 3) {
                return response()->json([
                    'success' => false,
                    'message' => 'Maximum attempts reached',
                ], 429);
            }

            // Validate answer index
            if ($request->answer_index >= count($quiz->options)) {
                return response()->json([
                    'success' => false,
                    'message' => 'Invalid answer index',
                ], 422);
            }

            // Process the answer
            $isCorrect = $adView->processQuizAnswer($request->answer_index, $request->time_taken);

            $response = [
                'success' => true,
                'data' => [
                    'is_correct' => $isCorrect,
                    'correct_answer_index' => $quiz->correct_answer_index,
                    'explanation' => $quiz->explanation,
                    'points_earned' => $isCorrect ? $quiz->getPointsReward() : 0,
                    'total_points' => $user->fresh()->points,
                    'attempts_remaining' => max(0, 3 - $adView->fresh()->quiz_attempts),
                ],
            ];

            if ($isCorrect) {
                $response['message'] = 'Correct answer! Points awarded.';
            } else {
                $response['message'] = 'Incorrect answer. Try again!';
            }

            return response()->json($response);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to submit answer',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Get quiz result
     */
    public function getResult(Request $request, int $quizId): JsonResponse
    {
        try {
            $user = $request->user();
            $quiz = Quiz::findOrFail($quizId);

            $adView = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $quiz->ad_id)
                ->first();

            if (!$adView || !$adView->quiz_attempted) {
                return response()->json([
                    'success' => false,
                    'message' => 'Quiz not attempted yet',
                ], 404);
            }

            return response()->json([
                'success' => true,
                'data' => [
                    'quiz_passed' => $adView->quiz_passed,
                    'attempts_used' => $adView->quiz_attempts,
                    'time_taken' => $adView->quiz_time_taken,
                    'points_earned' => $adView->points_earned,
                    'answers' => $adView->quiz_answers,
                    'explanation' => $quiz->explanation,
                    'correct_answer_index' => $quiz->correct_answer_index,
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get quiz result',
            ], 500);
        }
    }

    /**
     * Get user's quiz statistics
     */
    public function getUserStats(Request $request): JsonResponse
    {
        try {
            $user = $request->user();

            $totalQuizzes = UserAdView::where('user_id', $user->id)
                ->where('quiz_attempted', true)
                ->count();

            $passedQuizzes = UserAdView::where('user_id', $user->id)
                ->where('quiz_passed', true)
                ->count();

            $totalQuizPoints = UserAdView::where('user_id', $user->id)
                ->where('quiz_passed', true)
                ->sum('points_earned') - UserAdView::where('user_id', $user->id)
                ->where('completed', true)
                ->sum('points_earned'); // Subtract ad viewing points

            return response()->json([
                'success' => true,
                'data' => [
                    'total_quizzes_attempted' => $totalQuizzes,
                    'quizzes_passed' => $passedQuizzes,
                    'success_rate' => $totalQuizzes > 0 ? round(($passedQuizzes / $totalQuizzes) * 100, 2) : 0,
                    'total_quiz_points' => max(0, $totalQuizPoints),
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get quiz statistics',
            ], 500);
        }
    }
}
