import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'src/core/app_fonts.dart';
import 'src/core/app_controller.dart';
import 'src/features/auth/auth_page.dart';
import 'src/features/chat/chat_page.dart';
import 'src/l10n/app_localizations.dart';

void main() {
  runApp(const ProviderScope(child: VaeAgentApp()));
}

class VaeAgentApp extends ConsumerWidget {
  const VaeAgentApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(appControllerProvider);
    final router = GoRouter(
      initialLocation: state.isAuthenticated ? '/chat' : '/auth',
      redirect: (context, routerState) {
        final authed = ref.read(appControllerProvider).isAuthenticated;
        final isAuth = routerState.matchedLocation == '/auth';
        if (!authed && !isAuth) return '/auth';
        if (authed && isAuth) return '/chat';
        return null;
      },
      routes: [
        GoRoute(path: '/auth', builder: (_, __) => const AuthPage()),
        GoRoute(path: '/chat', builder: (_, __) => const ChatPage()),
      ],
    );

    return MaterialApp.router(
      title: 'VAEAGENT',
      debugShowCheckedModeBanner: false,
      locale: LocaleParser.parse(state.locale),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      themeMode: state.themeMode,
      theme: _theme(Brightness.light),
      darkTheme: _theme(Brightness.dark),
      routerConfig: router,
    );
  }

  ThemeData _theme(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      fontFamily: AppFonts.ui,
      fontFamilyFallback: AppFonts.fallback,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF111827),
        brightness: brightness,
        surface: isDark ? const Color(0xFF111827) : Colors.white,
      ),
      scaffoldBackgroundColor: isDark ? const Color(0xFF111827) : Colors.white,
      textTheme: AppFonts.themedTextTheme(
        brightness: brightness,
        platform: TargetPlatform.windows,
      ),
      cardTheme: const CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(8))),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: isDark ? const Color(0xFF1F2937) : Colors.white,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(
              color:
                  isDark ? const Color(0xFF374151) : const Color(0xFFE5E7EB)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(
              color:
                  isDark ? const Color(0xFF374151) : const Color(0xFFE5E7EB)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(
              color:
                  isDark ? const Color(0xFF9CA3AF) : const Color(0xFF111827)),
        ),
      ),
    );
  }
}
