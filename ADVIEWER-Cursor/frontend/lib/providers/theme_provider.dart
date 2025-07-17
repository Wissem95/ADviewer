import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

enum AppThemeMode { light, dark, system }

class ThemeNotifier extends StateNotifier<ThemeMode> {
  ThemeNotifier() : super(ThemeMode.system);

  void setTheme(AppThemeMode themeMode) {
    switch (themeMode) {
      case AppThemeMode.light:
        state = ThemeMode.light;
        break;
      case AppThemeMode.dark:
        state = ThemeMode.dark;
        break;
      case AppThemeMode.system:
        state = ThemeMode.system;
        break;
    }
  }

  void toggleTheme() {
    if (state == ThemeMode.light) {
      state = ThemeMode.dark;
    } else {
      state = ThemeMode.light;
    }
  }
}

final themeProvider = StateNotifierProvider<ThemeNotifier, ThemeMode>((ref) {
  return ThemeNotifier();
}); 