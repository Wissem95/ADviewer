import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/app_config.dart';
import 'storage_service.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  late Dio _dio;

  void initialize() {
    _dio = Dio(BaseOptions(
      baseUrl: AppConfig.baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    // Add auth interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await StorageService.getSecure('auth_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) {
        if (error.response?.statusCode == 401) {
          // Token expired, logout user
          _handleUnauthorized();
        }
        handler.next(error);
      },
    ));
  }

  Future<void> _handleUnauthorized() async {
    await StorageService.deleteSecure('auth_token');
    // Navigate to login screen - implement this in your app
  }

  // Wallet endpoints
  Future<Map<String, dynamic>> getWalletBalance() async {
    try {
      final response = await _dio.get('/wallet');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> convertPoints(int pointsAmount) async {
    try {
      final response = await _dio.post('/wallet/convert-points', data: {
        'points_amount': pointsAmount,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getTransactions({
    String? type,
    int page = 1,
    int perPage = 20,
  }) async {
    try {
      final response = await _dio.get('/wallet/transactions', queryParameters: {
        if (type != null) 'type': type,
        'page': page,
        'per_page': perPage,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getEarningsHistory({String period = 'week'}) async {
    try {
      final response = await _dio.get('/wallet/earnings-history', queryParameters: {
        'period': period,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getWithdrawalMethods() async {
    try {
      final response = await _dio.get('/wallet/withdrawal-methods');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> requestWithdrawal({
    required double amount,
    required String method,
    required Map<String, dynamic> paymentDetails,
  }) async {
    try {
      final response = await _dio.post('/wallet/withdraw', data: {
        'amount': amount,
        'method': method,
        'payment_details': paymentDetails,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Ad and Quiz endpoints
  Future<Map<String, dynamic>> getAdsFeed() async {
    try {
      final response = await _dio.get('/ads/feed');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> recordAdView(int adId) async {
    try {
      final response = await _dio.post('/ads/$adId/view');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> completeAdView(int viewId, int watchedDuration) async {
    try {
      final response = await _dio.post('/ads/view/$viewId/complete', data: {
        'watched_duration': watchedDuration,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getQuizForAd(int adId) async {
    try {
      final response = await _dio.get('/quizzes/ad/$adId');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> submitQuizAnswer({
    required int quizId,
    required int answerIndex,
    required double timeTaken,
  }) async {
    try {
      final response = await _dio.post('/quizzes/$quizId/answer', data: {
        'answer_index': answerIndex,
        'time_taken': timeTaken,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getQuizResult(int quizId) async {
    try {
      final response = await _dio.get('/quizzes/$quizId/result');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getQuizStats() async {
    try {
      final response = await _dio.get('/quizzes/stats');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Auth endpoints
  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _dio.post('/auth/login', data: {
        'email': email,
        'password': password,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> register({
    required String name,
    required String email,
    required String password,
    String? referralCode,
  }) async {
    try {
      final response = await _dio.post('/auth/register', data: {
        'name': name,
        'email': email,
        'password': password,
        'password_confirmation': password,
        if (referralCode != null) 'referral_code': referralCode,
      });
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> getProfile() async {
    try {
      final response = await _dio.get('/auth/me');
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<void> logout() async {
    try {
      await _dio.post('/auth/logout');
    } catch (e) {
      // Ignore logout errors
    } finally {
      await StorageService.deleteSecure('auth_token');
    }
  }

  ApiException _handleError(dynamic error) {
    if (error is DioException) {
      if (error.response != null) {
        final data = error.response!.data;
        final message = data is Map ? (data['message'] ?? 'Une erreur est survenue') : 'Une erreur est survenue';
        return ApiException(
          message: message,
          statusCode: error.response!.statusCode,
          data: data,
        );
      } else {
        return ApiException(
          message: 'Erreur de connexion',
          statusCode: 0,
        );
      }
    }
    return ApiException(
      message: error.toString(),
      statusCode: 0,
    );
  }
}

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;

  ApiException({
    required this.message,
    this.statusCode,
    this.data,
  });

  @override
  String toString() => message;
}

// Provider for dependency injection
final apiServiceProvider = Provider<ApiService>((ref) {
  final apiService = ApiService();
  apiService.initialize();
  return apiService;
}); 