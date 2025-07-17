import 'package:flutter/foundation.dart';

class AppConfig {
  static const String appName = 'AdViewer';
  static const String appVersion = '1.0.0';
  static const int buildNumber = 1;

  // API Configuration
  static const String baseUrl = kDebugMode 
    ? 'http://localhost:8000/api'
    : 'https://adviewer-api.railway.app/api';
    
  static const Duration apiTimeout = Duration(seconds: 30);
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 30);

  // Storage Keys
  static const String authTokenKey = 'auth_token';
  static const String userDataKey = 'user_data';
  static const String settingsKey = 'app_settings';
  static const String themeKey = 'theme_mode';
  static const String languageKey = 'language';
  static const String onboardingKey = 'onboarding_completed';
  static const String biometricsKey = 'biometrics_enabled';
  static const String notificationsKey = 'notifications_enabled';

  // Video Configuration
  static const Duration videoCacheSize = Duration(hours: 24);
  static const int maxCachedVideos = 5;
  static const int videoPreloadCount = 3;
  static const Duration minViewDuration = Duration(seconds: 5);
  static const Duration quizTimeout = Duration(seconds: 30);

  // Analytics Events
  static const String eventAdViewed = 'ad_viewed';
  static const String eventAdCompleted = 'ad_completed';
  static const String eventQuizStarted = 'quiz_started';
  static const String eventQuizCompleted = 'quiz_completed';
  static const String eventPointsEarned = 'points_earned';
  static const String eventWithdrawalRequested = 'withdrawal_requested';
  static const String eventUserRegistered = 'user_registered';
  static const String eventUserLogin = 'user_login';
  static const String eventAdReported = 'ad_reported';
  static const String eventAdShared = 'ad_shared';
  static const String eventAdLiked = 'ad_liked';

  // Points & Rewards
  static const int defaultAdPoints = 10;
  static const int defaultQuizPoints = 5;
  static const int shareBonus = 2;
  static const int dailyBonus = 20;
  static const int referralBonus = 50;
  static const double pointsToEuroRate = 100.0;
  static const double minWithdrawalAmount = 5.0;
  static const int dailyViewingLimit = 50;

  // UI Configuration
  static const Duration animationDuration = Duration(milliseconds: 300);
  static const Duration shortAnimationDuration = Duration(milliseconds: 150);
  static const Duration longAnimationDuration = Duration(milliseconds: 500);
  static const double borderRadius = 12.0;
  static const double cardElevation = 2.0;
  static const double iconSize = 24.0;
  static const double largeIconSize = 32.0;
  static const double smallIconSize = 16.0;

  // Error Messages
  static const String networkErrorMessage = 'Network connection failed. Please check your internet connection.';
  static const String serverErrorMessage = 'Server error occurred. Please try again later.';
  static const String authErrorMessage = 'Authentication failed. Please login again.';
  static const String validationErrorMessage = 'Please check your input and try again.';
  static const String genericErrorMessage = 'Something went wrong. Please try again.';

  // Validation Rules
  static const int minPasswordLength = 8;
  static const int maxPasswordLength = 128;
  static const int minNameLength = 2;
  static const int maxNameLength = 50;
  static const String emailPattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$';

  // Cache Configuration
  static const Duration cacheValidDuration = Duration(hours: 1);
  static const Duration imageCacheValidDuration = Duration(days: 7);
  static const int maxCacheSize = 100 * 1024 * 1024; // 100MB

  // Security
  static const int maxFailedAttempts = 5;
  static const Duration lockoutDuration = Duration(minutes: 15);
  static const bool enableCertificatePinning = !kDebugMode;
  static const Duration sessionTimeout = Duration(hours: 24);

  // Features Flags
  static const bool enableBiometrics = true;
  static const bool enablePushNotifications = true;
  static const bool enableAnalytics = true;
  static const bool enableCrashlytics = true;
  static const bool enableDeepLinking = true;
  static const bool enableOfflineMode = true;

  // Ad Configuration
  static const int adPreloadBuffer = 2;
  static const Duration adSkipDelay = Duration(seconds: 5);
  static const Duration maxAdDuration = Duration(minutes: 2);
  static const List<String> supportedVideoFormats = ['mp4', 'mov', 'avi'];
  static const List<String> adCategories = [
    'Technology',
    'Fashion',
    'Food',
    'Travel',
    'Gaming',
    'Health',
    'Education',
    'Entertainment',
    'Sports',
    'Finance',
  ];

  // Leaderboard
  static const int leaderboardSize = 100;
  static const Duration leaderboardRefreshInterval = Duration(minutes: 5);

  // Environment specific configurations
  static bool get isProduction => !kDebugMode;
  static bool get isDebug => kDebugMode;
  static String get environment => kDebugMode ? 'development' : 'production';

  // Device Information
  static const String appStoreId = '1234567890';
  static const String playStoreId = 'com.adviewer.app';
  static const String supportEmail = 'support@adviewer.com';
  static const String privacyPolicyUrl = 'https://adviewer.com/privacy';
  static const String termsOfServiceUrl = 'https://adviewer.com/terms';
  static const String faqUrl = 'https://adviewer.com/faq';

  // Social Media
  static const String twitterUrl = 'https://twitter.com/adviewer';
  static const String facebookUrl = 'https://facebook.com/adviewer';
  static const String instagramUrl = 'https://instagram.com/adviewer';
  static const String linkedinUrl = 'https://linkedin.com/company/adviewer';

  // Development Tools
  static const bool enableLogger = kDebugMode;
  static const bool enableNetworkLogger = kDebugMode;
  static const bool enablePerformanceMonitoring = true;

  // Feature Toggles (can be configured remotely)
  static Map<String, bool> featureFlags = {
    'enable_referral_program': true,
    'enable_leaderboard': true,
    'enable_achievements': true,
    'enable_daily_bonuses': true,
    'enable_push_notifications': true,
    'enable_dark_mode': true,
    'enable_biometric_auth': true,
    'enable_offline_viewing': false,
    'enable_video_preloading': true,
    'enable_auto_play': true,
  };

  // Remote Config Keys
  static const String remoteConfigMinAppVersion = 'min_app_version';
  static const String remoteConfigMaintenanceMode = 'maintenance_mode';
  static const String remoteConfigForceUpdate = 'force_update';
  static const String remoteConfigDailyLimit = 'daily_viewing_limit';
  static const String remoteConfigPointsRate = 'points_to_euro_rate';

  // Hive Box Names
  static const String userBox = 'user_box';
  static const String settingsBox = 'settings_box';
  static const String cacheBox = 'cache_box';
  static const String videoCacheBox = 'video_cache_box';
  static const String analyticsBox = 'analytics_box';
} 