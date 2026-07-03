import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/providers/app_state_provider.dart';
import '../../insights/presentation/insights_tab.dart';
import '../../household/presentation/household_tab.dart';
import '../../settings/presentation/settings_tab.dart';
import 'widgets/water_wave_circle.dart';

class MainScaffold extends ConsumerStatefulWidget {
  const MainScaffold({super.key});

  @override
  ConsumerState<MainScaffold> createState() => _MainScaffoldState();
}

class _MainScaffoldState extends ConsumerState<MainScaffold> {
  int _currentIndex = 0;

  final List<String> _tabTitles = ['Home', 'Insights', 'Household', 'Settings'];
  final List<IconData> _tabIcons = [Icons.home, Icons.analytics, Icons.family_restroom, Icons.settings];

  @override
  Widget build(BuildContext context) {
    final appState = ref.watch(appStateProvider);

    final tabs = [
      DashboardContent(location: appState.locationDisplay),
      const InsightsTab(),
      const HouseholdTab(),
      const SettingsTab(),
    ];

    return Scaffold(
      backgroundColor: AppTheme.backgroundDark,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: Builder(
          builder: (ctx) => IconButton(
            icon: const Icon(Icons.menu, color: Colors.white, size: 26),
            onPressed: () => Scaffold.of(ctx).openDrawer(),
          ),
        ),
        title: Text(
          _tabTitles[_currentIndex],
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 18),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined, color: Colors.white),
            onPressed: () {},
          ),
        ],
      ),
      drawer: _buildDrawer(context, appState.locationDisplay),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppTheme.backgroundDark, AppTheme.backgroundLight, AppTheme.primaryTeal],
            stops: [0.0, 0.6, 1.0],
          ),
        ),
        child: tabs[_currentIndex],
      ),
    );
  }

  Widget _buildDrawer(BuildContext context, String location) {
    return Drawer(
      backgroundColor: AppTheme.backgroundLight,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(24),
              width: double.infinity,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppTheme.primaryTeal.withValues(alpha: 0.8), AppTheme.backgroundDark],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const CircleAvatar(
                    radius: 28,
                    backgroundColor: AppTheme.primaryTeal,
                    child: Text('P', style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(height: 12),
                  const Text('PRANA',
                      style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: 4)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.location_on, color: Colors.white54, size: 14),
                      const SizedBox(width: 4),
                      Text(location, style: const TextStyle(color: Colors.white70, fontSize: 13)),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            // Nav items
            for (int i = 0; i < _tabTitles.length; i++)
              _drawerItem(_tabIcons[i], _tabTitles[i], i, context),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.all(16),
              child: TextButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.logout, color: Colors.redAccent),
                label: const Text('Log Out', style: TextStyle(color: Colors.redAccent)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _drawerItem(IconData icon, String title, int index, BuildContext context) {
    final selected = _currentIndex == index;
    return ListTile(
      leading: Icon(icon, color: selected ? AppTheme.primaryTeal : Colors.white70),
      title: Text(title, style: TextStyle(color: selected ? AppTheme.primaryTeal : Colors.white)),
      selected: selected,
      selectedTileColor: AppTheme.primaryTeal.withValues(alpha: 0.1),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      onTap: () {
        Navigator.pop(context);
        setState(() => _currentIndex = index);
      },
    );
  }

  Widget _drawerItemCustom(IconData icon, String title, BuildContext context, {required VoidCallback onTap}) {
    return ListTile(
      leading: Icon(icon, color: Colors.white70),
      title: Text(title, style: const TextStyle(color: Colors.white)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      onTap: onTap,
    );
  }
}

// Dashboard content widget — reads location from prop
class DashboardContent extends StatelessWidget {
  final String location;
  const DashboardContent({super.key, required this.location});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildHeader(context, location),
          const SizedBox(height: 20),
          _buildHeroCard(),
          const SizedBox(height: 16),
          _buildSubScores(),
          const SizedBox(height: 16),
          _buildRDS(context),
          const SizedBox(height: 16),
          _buildHouseholdChecklist(),
          const SizedBox(height: 24),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryTeal,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.all(16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () {},
            child: const Text('View Latest Alert'),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context, String loc) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(loc, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
            const Text('Updated just now', style: TextStyle(fontSize: 12, color: Colors.white70)),
          ],
        ),
        IconButton(
          icon: const Icon(Icons.refresh, color: Colors.white),
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Data refreshed')),
            );
          },
        ),
      ],
    );
  }

  Widget _buildHeroCard() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
        child: Container(
          padding: const EdgeInsets.all(24.0),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.15),
            ),
          ),
          child: Column(
            children: [
              const Text(
                'Compound Climate Risk Index',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.blue.shade500.withValues(alpha: 0.3),
                      Colors.cyan.shade500.withValues(alpha: 0.3),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: Colors.cyan.shade400.withValues(alpha: 0.5),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: const BoxDecoration(
                        color: Colors.cyanAccent,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text(
                      'ELEVATED STATUS',
                      style: TextStyle(
                        color: Colors.cyanAccent,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.0,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              const WaterWaveCircle(score: 62),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSubScores() {
    return Row(
      children: [
        Expanded(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(children: [
                const Icon(Icons.thermostat, color: AppTheme.tierHigh),
                const SizedBox(height: 8),
                const Text('34°C', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
                const Text('HIGH', style: TextStyle(color: AppTheme.tierHigh, fontWeight: FontWeight.bold)),
              ]),
            ),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(children: [
                const Icon(Icons.air, color: AppTheme.tierElevated),
                const SizedBox(height: 8),
                const Text('112', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Text('PM2.5', style: TextStyle(color: Colors.white70)),
                  const SizedBox(width: 4),
                  Icon(Icons.warning_amber, size: 14, color: Colors.yellow[700]),
                ]),
              ]),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRDS(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            const Text('Recovery Debt (RDS)', style: TextStyle(fontSize: 16, color: Colors.white70)),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.tierHigh.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text('HIGH', style: TextStyle(color: AppTheme.tierHigh, fontSize: 12, fontWeight: FontWeight.bold)),
            ),
          ]),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: List.generate(7, (index) {
              final heights = [20.0, 30.0, 25.0, 45.0, 60.0, 80.0, 70.0];
              final colors = [
                AppTheme.tierSafe, AppTheme.tierSafe, AppTheme.tierSafe,
                AppTheme.tierElevated, AppTheme.tierElevated,
                AppTheme.tierHigh, AppTheme.tierHigh,
              ];
              return Container(
                width: 30,
                height: heights[index],
                decoration: BoxDecoration(color: colors[index], borderRadius: BorderRadius.circular(4)),
              );
            }),
          ),
          const SizedBox(height: 12),
          const Text(
            'Confidence range: 65–75 (uncertainty band)',
            style: TextStyle(fontSize: 12, color: Colors.white54, fontStyle: FontStyle.italic),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () => context.push('/check-in'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: BorderSide(color: Colors.white.withValues(alpha: 0.3)),
              ),
              child: const Text('Log last night\'s sleep'),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _buildHouseholdChecklist() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Household Checklist', style: TextStyle(fontSize: 16, color: Colors.white70)),
          const SizedBox(height: 16),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const CircleAvatar(
              backgroundColor: AppTheme.primaryTeal,
              child: Text('A', style: TextStyle(color: Colors.white)),
            ),
            title: const Text('Amma', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Keep hydrated. 34°C is high for 60+.', style: TextStyle(color: Colors.white70)),
            trailing: Container(
              width: 12, height: 12,
              decoration: const BoxDecoration(color: AppTheme.tierHigh, shape: BoxShape.circle),
            ),
          ),
        ]),
      ),
    );
  }
}
