import 'package:firebase_analytics/firebase_analytics.dart';

class AnalyticsService {
  static FirebaseAnalytics? _analytics;

  static Future<void> init() async {
    try {
      _analytics = FirebaseAnalytics.instance;
    } catch (e) {
      // Firebase not configured, continue without analytics
      print('Analytics not available: $e');
    }
  }

  static Future<void> logEvent(String name, [Map<String, dynamic>? parameters]) async {
    try {
      await _analytics?.logEvent(name: name, parameters: parameters);
    } catch (e) {
      print('Error logging event: $e');
    }
  }

  static Future<void> logScreenView(String screenName) async {
    await logEvent('screen_view', {'screen_name': screenName});
  }

  static Future<void> logAdView(String adId) async {
    await logEvent('ad_view', {
      'ad_id': adId,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    });
  }

  static Future<void> logAdCompletion(String adId, int pointsEarned) async {
    await logEvent('ad_completion', {
      'ad_id': adId,
      'points_earned': pointsEarned,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    });
  }

  static Future<void> logQuizAnswer(String quizId, bool correct) async {
    await logEvent('quiz_answer', {
      'quiz_id': quizId,
      'correct': correct,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    });
  }

  static Future<void> logPointsEarned(int points, String source) async {
    await logEvent('points_earned', {
      'points': points,
      'source': source,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    });
  }

  static Future<void> logWithdrawal(double amount, String method) async {
    await logEvent('withdrawal', {
      'amount': amount,
      'method': method,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    });
  }

  static Future<void> setUserId(String userId) async {
    try {
      await _analytics?.setUserId(id: userId);
    } catch (e) {
      print('Error setting user ID: $e');
    }
  }

  static Future<void> setUserProperties(Map<String, String> properties) async {
    try {
      for (final entry in properties.entries) {
        await _analytics?.setUserProperty(name: entry.key, value: entry.value);
      }
    } catch (e) {
      print('Error setting user properties: $e');
    }
  }
} 