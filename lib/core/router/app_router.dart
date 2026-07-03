import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/onboarding/presentation/onboarding_screen.dart';
import '../../features/home/presentation/main_scaffold.dart';
import '../../features/institutional/presentation/institutional_dashboard.dart';
import '../../features/check_in/presentation/check_in_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/onboarding',
    routes: [
      GoRoute(
        path: '/onboarding',
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        path: '/app',
        builder: (context, state) => const MainScaffold(),
      ),
      GoRoute(
        path: '/check-in',
        pageBuilder: (context, state) => const MaterialPage(
          fullscreenDialog: true,
          child: CheckInScreen(),
        ),
      ),
      GoRoute(
        path: '/institutional',
        builder: (context, state) => const InstitutionalDashboard(),
      ),
    ],
  );
});
