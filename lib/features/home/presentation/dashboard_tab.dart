import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';

class DashboardTab extends StatelessWidget {
  const DashboardTab({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildHeader(),
          const SizedBox(height: 24),
          _buildHeroCard(),
          const SizedBox(height: 16),
          _buildSubScores(),
          const SizedBox(height: 16),
          _buildRDS(),
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
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Chennai, Adyar', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
            Text('Updated just now', style: TextStyle(fontSize: 12, color: Colors.white70)),
          ],
        ),
        IconButton(
          icon: const Icon(Icons.refresh, color: Colors.white),
          onPressed: () {},
        ),
      ],
    );
  }

  Widget _buildHeroCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            const Text('Compound Risk (CCRI)', style: TextStyle(fontSize: 16, color: Colors.white70)),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.tierElevated.withOpacity(0.2),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: AppTheme.tierElevated),
              ),
              child: const Text('ELEVATED', style: TextStyle(color: AppTheme.tierElevated, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 24),
            Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 120,
                  height: 120,
                  child: CircularProgressIndicator(
                    value: 0.62,
                    strokeWidth: 12,
                    backgroundColor: Colors.white.withOpacity(0.1),
                    valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.tierElevated),
                  ),
                ),
                const Column(
                  children: [
                    Text('62/100', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
                  ],
                ),
              ],
            ),
          ],
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
              child: Column(
                children: [
                  const Icon(Icons.thermostat, color: AppTheme.tierHigh),
                  const SizedBox(height: 8),
                  const Text('34°C', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
                  const Text('HIGH', style: TextStyle(color: AppTheme.tierHigh, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  const Icon(Icons.air, color: AppTheme.tierElevated),
                  const SizedBox(height: 8),
                  const Text('112', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text('PM2.5', style: TextStyle(color: Colors.white70)),
                      const SizedBox(width: 4),
                      Icon(Icons.warning_amber, size: 14, color: Colors.yellow[700]),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRDS() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Recovery Debt (RDS)', style: TextStyle(fontSize: 16, color: Colors.white70)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.tierHigh.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text('HIGH', style: TextStyle(color: AppTheme.tierHigh, fontSize: 12, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: List.generate(7, (index) {
                // Mock heights for past 7 days
                final heights = [20.0, 30.0, 25.0, 45.0, 60.0, 80.0, 70.0];
                final colors = [
                  AppTheme.tierSafe,
                  AppTheme.tierSafe,
                  AppTheme.tierSafe,
                  AppTheme.tierElevated,
                  AppTheme.tierElevated,
                  AppTheme.tierHigh,
                  AppTheme.tierHigh,
                ];
                return Container(
                  width: 30,
                  height: heights[index],
                  decoration: BoxDecoration(
                    color: colors[index],
                    borderRadius: BorderRadius.circular(4),
                  ),
                );
              }),
            ),
            const SizedBox(height: 16),
            const Text(
              'Confidence range: 65–75 (uncertainty band)',
              style: TextStyle(fontSize: 12, color: Colors.white54, fontStyle: FontStyle.italic),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () {
                  // This context needs to go to a route. But since DashboardTab is in the app, we can use context.go()
                  // Wait, check_in needs the GoRouter context
                },
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: BorderSide(color: Colors.white.withOpacity(0.3)),
                ),
                child: const Text('Log last night\'s sleep'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHouseholdChecklist() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Household Checklist', style: TextStyle(fontSize: 16, color: Colors.white70)),
            const SizedBox(height: 16),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const CircleAvatar(backgroundColor: AppTheme.primaryTeal, child: Text('A', style: TextStyle(color: Colors.white))),
              title: const Text('Amma', style: TextStyle(color: Colors.white)),
              subtitle: const Text('Keep hydrated. 34°C is high for 60+.', style: TextStyle(color: Colors.white70)),
              trailing: Container(
                width: 12,
                height: 12,
                decoration: const BoxDecoration(
                  color: AppTheme.tierHigh,
                  shape: BoxShape.circle,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
