import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';

class CheckInScreen extends StatefulWidget {
  const CheckInScreen({super.key});

  @override
  State<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends State<CheckInScreen> {
  String? _selectedSleep;
  String? _selectedCooling;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Check-in', style: TextStyle(color: Colors.white)),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      backgroundColor: AppTheme.backgroundDark,
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'How did last night\'s sleep feel?',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 16),
            _buildOptionCard('😀 Fine', _selectedSleep, (val) {
              setState(() => _selectedSleep = val);
            }),
            _buildOptionCard('😐 A bit restless', _selectedSleep, (val) {
              setState(() => _selectedSleep = val);
            }),
            _buildOptionCard('😣 Poor', _selectedSleep, (val) {
              setState(() => _selectedSleep = val);
            }),
            _buildOptionCard('😫 Very poor', _selectedSleep, (val) {
              setState(() => _selectedSleep = val);
            }),
            const SizedBox(height: 32),
            const Text(
              'Any cooling issues last night?',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 16),
            _buildOptionCard('⚡ Power cut', _selectedCooling, (val) {
              setState(() => _selectedCooling = val);
            }),
            _buildOptionCard('🌀 Fan only', _selectedCooling, (val) {
              setState(() => _selectedCooling = val);
            }),
            _buildOptionCard('❄️ AC worked fine', _selectedCooling, (val) {
              setState(() => _selectedCooling = val);
            }),
            _buildOptionCard('— None', _selectedCooling, (val) {
              setState(() => _selectedCooling = val);
            }),
            const SizedBox(height: 32),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryTeal,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: (_selectedSleep == null || _selectedCooling == null)
                  ? null
                  : () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Thanks — this helps personalize your recovery score')),
                      );
                      context.pop();
                    },
              child: const Text('Submit Check-in', style: TextStyle(fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOptionCard(String text, String? selectedVal, ValueChanged<String> onSelected) {
    final isSelected = selectedVal == text;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      color: isSelected
          ? AppTheme.primaryTeal.withValues(alpha: 0.3)
          : Colors.white.withValues(alpha: 0.05),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isSelected ? AppTheme.primaryTeal : Colors.white.withValues(alpha: 0.1),
          width: 2,
        ),
      ),
      child: InkWell(
        onTap: () => onSelected(text),
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(text, style: const TextStyle(fontSize: 16, color: Colors.white)),
              if (isSelected)
                const Icon(Icons.check_circle, color: AppTheme.primaryTeal, size: 20)
              else
                Icon(Icons.circle_outlined, color: Colors.white.withValues(alpha: 0.3), size: 20),
            ],
          ),
        ),
      ),
    );
  }
}
