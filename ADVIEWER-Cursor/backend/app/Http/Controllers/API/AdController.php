<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Models\Ad;
use App\Models\User;
use App\Models\UserAdView;
use App\Models\UserSession;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Validator;

class AdController extends Controller
{
    /**
     * Get next ad for user with intelligent algorithm
     */
    public function getNextAd(Request $request): JsonResponse
    {
        try {
            $user = $request->user();

            // Check if user can view more ads today
            if (!$user->canViewMoreAds()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Daily viewing limit reached',
                    'data' => [
                        'limit_reached' => true,
                        'reset_time' => now()->addDay()->startOfDay()->toISOString(),
                    ],
                ], 429);
            }

            // Get user preferences and history
            $userPreferences = $this->getUserPreferences($user);

            // Get recommended ad using intelligent algorithm
            $ad = $this->getRecommendedAd($user, $userPreferences);

            if (!$ad) {
                return response()->json([
                    'success' => false,
                    'message' => 'No ads available at the moment',
                    'data' => [
                        'retry_after' => 300, // 5 minutes
                    ],
                ], 404);
            }

            // Load quiz if exists
            $ad->load('quiz');

            return response()->json([
                'success' => true,
                'data' => [
                    'ad' => $this->formatAdData($ad),
                    'user_stats' => [
                        'daily_views' => $user->daily_ad_views,
                        'daily_limit' => config('adviewer.daily_viewing_limit', 50),
                        'points' => $user->points,
                        'level' => $user->getLevel(),
                    ],
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get next ad',
                'error' => $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Get ads by category
     */
    public function getAdsByCategory(Request $request, string $category): JsonResponse
    {
        $validator = Validator::make(['category' => $category], [
            'category' => 'required|string|max:50',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Invalid category',
                'errors' => $validator->errors(),
            ], 422);
        }

        try {
            $user = $request->user();
            $ads = Ad::active()
                ->inCampaignPeriod()
                ->withBudget()
                ->where('category', $category)
                ->targetingUser($user)
                ->prioritized()
                ->paginate(20);

            return response()->json([
                'success' => true,
                'data' => [
                    'ads' => $ads->items(),
                    'pagination' => [
                        'current_page' => $ads->currentPage(),
                        'last_page' => $ads->lastPage(),
                        'per_page' => $ads->perPage(),
                        'total' => $ads->total(),
                    ],
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get ads',
            ], 500);
        }
    }

    /**
     * Mark ad as viewed
     */
    public function markAsViewed(Request $request, int $adId): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'session_id' => 'required|string',
            'device_info' => 'nullable|array',
            'platform' => 'required|string',
            'app_version' => 'nullable|string',
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
            $ad = Ad::find($adId);

            if (!$ad || !$ad->canBeViewedBy($user)) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad not available',
                ], 404);
            }

            // Check for duplicate view
            $existingView = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $ad->id)
                ->where('session_id', $request->session_id)
                ->first();

            if ($existingView) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad already viewed in this session',
                ], 409);
            }

            // Get or create user session
            $session = UserSession::where('session_id', $request->session_id)
                ->where('user_id', $user->id)
                ->first();

            if (!$session) {
                $session = UserSession::createForUser($user, [
                    'session_id' => $request->session_id,
                    'platform' => $request->platform,
                    'app_version' => $request->app_version,
                    'device_info' => $request->device_info,
                ]);
            }

            // Record the view
            $view = $ad->recordView($user, [
                'session_id' => $request->session_id,
                'platform' => $request->platform,
                'app_version' => $request->app_version,
                'device_info' => $request->device_info,
                'country' => $user->country,
            ]);

            // Update user and session stats
            $user->incrementDailyAdViews();
            $session->incrementAdsViewed();

            return response()->json([
                'success' => true,
                'message' => 'Ad view recorded',
                'data' => [
                    'view_id' => $view->id,
                    'points_pending' => $ad->points_reward,
                    'has_quiz' => !is_null($ad->quiz),
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to record ad view',
            ], 500);
        }
    }

    /**
     * Mark ad as completed
     */
    public function markAsCompleted(Request $request, int $viewId): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'watched_duration' => 'required|integer|min:1',
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
            $view = UserAdView::where('id', $viewId)
                ->where('user_id', $user->id)
                ->with('ad')
                ->first();

            if (!$view) {
                return response()->json([
                    'success' => false,
                    'message' => 'View not found',
                ], 404);
            }

            if ($view->completed) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad already completed',
                ], 409);
            }

            // Update view details
            $view->update([
                'watched_duration' => $request->watched_duration,
                'completed' => true,
            ]);

            // Award points and update ad stats
            $points = $view->ad->points_reward;
            $user->addPoints($points, 'Ad completion', $view->ad_id);
            $view->update(['points_earned' => $points]);

            // Update ad metrics
            $view->ad->recordCompletedView($view);

            return response()->json([
                'success' => true,
                'message' => 'Ad completed successfully',
                'data' => [
                    'points_earned' => $points,
                    'total_points' => $user->fresh()->points,
                    'has_quiz' => !is_null($view->ad->quiz),
                    'quiz_points' => $view->ad->quiz?->getPointsReward() ?? 0,
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to complete ad',
            ], 500);
        }
    }

    /**
     * Report ad
     */
    public function reportAd(Request $request, int $adId): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'reason' => 'required|string|in:inappropriate,misleading,spam,offensive,other',
            'description' => 'nullable|string|max:500',
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
            $ad = Ad::find($adId);

            if (!$ad) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad not found',
                ], 404);
            }

            // Check if user already reported this ad
            $existingReport = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $ad->id)
                ->where('reported', true)
                ->exists();

            if ($existingReport) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad already reported',
                ], 409);
            }

            // Report the ad
            $ad->report($user, $request->reason);

            // Update user's view record if exists
            UserAdView::where('user_id', $user->id)
                ->where('ad_id', $ad->id)
                ->update([
                    'reported' => true,
                    'report_reason' => $request->reason,
                ]);

            return response()->json([
                'success' => true,
                'message' => 'Ad reported successfully',
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to report ad',
            ], 500);
        }
    }

    /**
     * Like/Unlike ad
     */
    public function toggleLike(Request $request, int $adId): JsonResponse
    {
        try {
            $user = $request->user();
            $ad = Ad::find($adId);

            if (!$ad) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad not found',
                ], 404);
            }

            $view = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $ad->id)
                ->first();

            if (!$view) {
                return response()->json([
                    'success' => false,
                    'message' => 'You must view the ad first',
                ], 404);
            }

            $liked = !$view->liked;
            $view->update(['liked' => $liked]);

            return response()->json([
                'success' => true,
                'message' => $liked ? 'Ad liked' : 'Ad unliked',
                'data' => [
                    'liked' => $liked,
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to toggle like',
            ], 500);
        }
    }

    /**
     * Share ad
     */
    public function shareAd(Request $request, int $adId): JsonResponse
    {
        try {
            $user = $request->user();
            $ad = Ad::find($adId);

            if (!$ad) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ad not found',
                ], 404);
            }

            $view = UserAdView::where('user_id', $user->id)
                ->where('ad_id', $ad->id)
                ->first();

            if ($view) {
                $view->update(['shared' => true]);
                $view->increment('replay_count');
            }

            // Award bonus points for sharing
            $sharePoints = 2;
            $user->addPoints($sharePoints, 'Ad sharing', $ad->id);

            return response()->json([
                'success' => true,
                'message' => 'Ad shared successfully',
                'data' => [
                    'points_earned' => $sharePoints,
                    'share_url' => url("/ads/{$ad->id}/share"),
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to share ad',
            ], 500);
        }
    }

    /**
     * Get user viewing history
     */
    public function getViewingHistory(Request $request): JsonResponse
    {
        try {
            $user = $request->user();

            $history = UserAdView::where('user_id', $user->id)
                ->with(['ad:id,title,advertiser_name,category,points_reward'])
                ->orderByDesc('viewed_at')
                ->paginate(20);

            return response()->json([
                'success' => true,
                'data' => [
                    'history' => $history->items(),
                    'pagination' => [
                        'current_page' => $history->currentPage(),
                        'last_page' => $history->lastPage(),
                        'per_page' => $history->perPage(),
                        'total' => $history->total(),
                    ],
                ],
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to get viewing history',
            ], 500);
        }
    }

    /**
     * Get user preferences based on viewing history
     */
    private function getUserPreferences(User $user): array
    {
        $views = UserAdView::where('user_id', $user->id)
            ->where('completed', true)
            ->with('ad')
            ->get();

        if ($views->isEmpty()) {
            return [
                'preferred_categories' => [],
                'average_engagement' => 0,
                'quiz_success_rate' => 0,
            ];
        }

        // Calculate category preferences
        $categories = $views->groupBy('ad.category')
            ->map(function ($categoryViews) {
                return [
                    'count' => $categoryViews->count(),
                    'engagement' => $categoryViews->avg(function ($view) {
                        return $view->getEngagementScore();
                    }),
                ];
            })
            ->sortByDesc('engagement')
            ->take(5);

        return [
            'preferred_categories' => $categories->keys()->toArray(),
            'average_engagement' => $views->avg(function ($view) {
                return $view->getEngagementScore();
            }),
            'quiz_success_rate' => $user->getQuizSuccessRate(),
        ];
    }

    /**
     * Get recommended ad using intelligent algorithm
     */
    private function getRecommendedAd(User $user, array $preferences): ?Ad
    {
        $query = Ad::active()
            ->inCampaignPeriod()
            ->withBudget()
            ->targetingUser($user)
            ->notViewedByUser($user);

        // Apply category preferences if available
        if (!empty($preferences['preferred_categories'])) {
            $query->where(function ($q) use ($preferences) {
                foreach ($preferences['preferred_categories'] as $category) {
                    $q->orWhere('category', $category);
                }
            });
        }

        // Weight by engagement and priority
        $query->orderByRaw('
            (priority * 0.4 + 
             engagement_rate * 0.3 + 
             (100 - views_count) * 0.2 + 
             RAND() * 0.1) DESC
        ');

        return $query->first();
    }

    /**
     * Format ad data for API response
     */
    private function formatAdData(Ad $ad): array
    {
        return [
            'id' => $ad->id,
            'title' => $ad->title,
            'description' => $ad->description,
            'video_url' => $ad->video_url,
            'thumbnail_url' => $ad->thumbnail_url,
            'duration' => $ad->duration,
            'points_reward' => $ad->points_reward,
            'advertiser' => [
                'name' => $ad->advertiser_name,
                'logo_url' => $ad->advertiser_logo_url,
                'website' => $ad->advertiser_website,
            ],
            'category' => $ad->category,
            'quiz' => $ad->quiz ? [
                'id' => $ad->quiz->id,
                'question' => $ad->quiz->question,
                'options' => $ad->quiz->options,
                'difficulty' => $ad->quiz->difficulty,
                'time_limit' => $ad->quiz->time_limit,
                'points_reward' => $ad->quiz->getPointsReward(),
            ] : null,
        ];
    }
}
