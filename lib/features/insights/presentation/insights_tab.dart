import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

class InsightsTab extends StatefulWidget {
  const InsightsTab({super.key});

  @override
  State<InsightsTab> createState() => _InsightsTabState();
}

class _InsightsTabState extends State<InsightsTab> {
  int _selectedDays = 7;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Insights', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 16),
          _buildTimeRangeSelector(),
          const SizedBox(height: 24),
          _buildChartCard('Compound Risk Over Time (CCRI)', 'Line chart showing CCRI score (0-100) with color bands.'),
          const SizedBox(height: 16),
          _buildChartCard('Recovery Debt Trend (RDS)', 'Bar chart showing RDS score with uncertainty band.'),
          const SizedBox(height: 16),
          _buildChartCard('Heat vs. Pollution Split', 'Stacked bar chart showing NDT vs HA-AQI driven scores.'),
          const SizedBox(height: 16),
          _buildChartCard('Check-in vs Calculated RDS', 'Scatter plot comparing self-reported sleep to RDS score.\n\n75% of your \'poor sleep\' nights matched a HIGH+ RDS score.'),
          const SizedBox(height: 16),
          _buildChartCard('Per-Member Elevated-Risk Frequency', 'Horizontal bars showing % of days flagged elevated per member.\nAmma: 40%\nYou: 5%'),
          const SizedBox(height: 24),
          _buildDataConfidenceFooter(),
        ],
      ),
    );
  }

  Widget _buildTimeRangeSelector() {
    return SegmentedButton<int>(
      segments: const [
        ButtonSegment(value: 7, label: Text('7 days')),
        ButtonSegment(value: 14, label: Text('14 days')),
        ButtonSegment(value: 30, label: Text('30 days')),
      ],
      selected: {_selectedDays},
      onSelectionChanged: (val) {
        setState(() {
          _selectedDays = val.first;
        });
      },
      style: ButtonStyle(
        backgroundColor: MaterialStateProperty.resolveWith<Color>((states) {
          if (states.contains(MaterialState.selected)) return AppTheme.primaryTeal;
          return Colors.white.withOpacity(0.1);
        }),
        foregroundColor: MaterialStateProperty.all(Colors.white),
      ),
    );
  }

  Widget _buildChartCard(String title, String description) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
            const SizedBox(height: 16),
            Container(
              height: 150,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Text(
                    description,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white54),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDataConfidenceFooter() {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.info_outline, color: Colors.white54, size: 16),
            const SizedBox(width: 8),
            const Text('Pollution data: Live (last 7 days: 98% complete)', style: TextStyle(color: Colors.white54, fontSize: 12)),
          ],
        ),
        const SizedBox(height: 8),
        const Text('Check-ins logged this month: 12', style: TextStyle(color: Colors.white54, fontSize: 12)),
      ],
    );
  }
}
