import 'package:flutter/material.dart';

class AppFonts {
  const AppFonts._();

  static const global = 'LXGW WenKai';
  static const ui = global;
  static const message = global;
  static const heading = global;
  static const code = 'LXGW WenKai Mono';

  static const fallback = [
    'Microsoft YaHei UI',
    'Microsoft YaHei',
    'Segoe UI',
    'Noto Sans CJK SC',
    'PingFang SC',
    'Arial',
  ];

  static TextTheme themedTextTheme({
    required Brightness brightness,
    required TargetPlatform platform,
  }) {
    final base = brightness == Brightness.dark
        ? Typography.material2021(platform: platform).white
        : Typography.material2021(platform: platform).black;
    final textColor = brightness == Brightness.dark
        ? const Color(0xFFE5E7EB)
        : const Color(0xFF111827);
    return base.apply(
      fontFamily: ui,
      fontFamilyFallback: fallback,
      bodyColor: textColor,
      displayColor: textColor,
    );
  }

  static TextStyle messageStyle(BuildContext context) {
    return DefaultTextStyle.of(context).style.copyWith(
          fontFamily: message,
          fontFamilyFallback: fallback,
          height: 1.58,
        );
  }

  static TextStyle codeStyle(BuildContext context) {
    return DefaultTextStyle.of(context).style.copyWith(
          fontFamily: code,
          fontFamilyFallback: fallback,
          fontSize: 14,
          height: 1.55,
        );
  }
}
