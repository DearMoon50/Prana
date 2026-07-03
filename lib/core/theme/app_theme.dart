import 'package:flutter/material.dart';

class AppTheme {
  // Brand Colors
  static const Color backgroundDark = Color(0xFF050810);
  static const Color backgroundLight = Color(0xFF0A1F2E);
  static const Color primaryTeal = Color(0xFF0A7A7A);
  
  // Risk Tier Colors
  static const Color tierSafe = Color(0xFF4CAF50);
  static const Color tierElevated = Color(0xFFFFC107);
  static const Color tierHigh = Color(0xFFFF9800);
  static const Color tierCritical = Color(0xFFF44336);
  static const Color tierEmergency = Color(0xFF9C27B0);

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      useMaterial3: true,
      scaffoldBackgroundColor: backgroundDark,
      colorScheme: const ColorScheme.dark(
        primary: primaryTeal,
        background: backgroundDark,
        surface: backgroundLight,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
      ),
      cardTheme: CardThemeData(
        color: Colors.white.withOpacity(0.05),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: Colors.white.withOpacity(0.1), width: 1),
        ),
      ),
    );
  }
}
