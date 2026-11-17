import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData light() {
    const primaryDark = Color(0xFF103020);
    const primary = Color(0xFF207050);
    const background = Color(0xFFF0F0E0);
    final scheme = ColorScheme.fromSeed(
      seedColor: primary,
      primary: primary,
      secondary: primaryDark,
      surface: Colors.white,
    );
    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      appBarTheme: const AppBarTheme(
        backgroundColor: primaryDark,
        foregroundColor: Colors.white,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      useMaterial3: true,
    );
  }
}
