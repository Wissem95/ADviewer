import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class ErrorHandler {
  static void logError(Object error, StackTrace? stackTrace, {
    String? context,
    Map<String, dynamic>? additionalData,
  }) {
    // Log to console in debug mode
    if (kDebugMode) {
      print('Error: $error');
      if (stackTrace != null) {
        print('Stack trace: $stackTrace');
      }
      if (context != null) {
        print('Context: $context');
      }
      if (additionalData != null) {
        print('Additional data: $additionalData');
      }
    }

    // Crashlytics logging can be added later when Firebase is configured
  }

  static void logFatalError(Object error, StackTrace? stackTrace, {
    String? context,
    Map<String, dynamic>? additionalData,
  }) {
    // Log to console in debug mode
    if (kDebugMode) {
      print('FATAL Error: $error');
      if (stackTrace != null) {
        print('Stack trace: $stackTrace');
      }
      if (context != null) {
        print('Context: $context');
      }
      if (additionalData != null) {
        print('Additional data: $additionalData');
      }
    }

    // Crashlytics logging can be added later when Firebase is configured
  }

  static String getErrorMessage(Object error) {
    if (error is Exception) {
      return error.toString().replaceFirst('Exception: ', '');
    }
    return error.toString();
  }

  static Widget buildErrorWidget(FlutterErrorDetails errorDetails) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red,
            ),
            const SizedBox(height: 16),
            const Text(
              'Something went wrong',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            if (kDebugMode) ...[
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  errorDetails.exception.toString(),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
} 