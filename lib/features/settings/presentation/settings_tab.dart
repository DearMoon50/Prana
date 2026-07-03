import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/providers/app_state_provider.dart';

class SettingsTab extends ConsumerStatefulWidget {
  const SettingsTab({super.key});

  @override
  ConsumerState<SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends ConsumerState<SettingsTab> {
  bool _whatsappEnabled = false;
  TimeOfDay? _whatsappTime = const TimeOfDay(hour: 8, minute: 0);
  String _whatsappOption = 'RDS';

  @override
  Widget build(BuildContext context) {
    final appState = ref.watch(appStateProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Settings', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 24),
          _buildSectionHeader('Household & Location'),
          _buildListTile(Icons.family_restroom, 'Manage Household Members: ${appState.members.length} registered'),
          _buildListTile(Icons.location_on, 'Location: ${appState.locationDisplay}'),
          const SizedBox(height: 16),
          _buildSectionHeader('Notifications'),
          _buildSwitchTile('Daily Summary', true),
          _buildWhatsAppToggle(context),
          const SizedBox(height: 16),
          _buildSectionHeader('Preferences'),
          _buildListTile(Icons.language, 'Language: English'),
          const SizedBox(height: 16),
          _buildSectionHeader('About'),
          _buildListTile(Icons.info_outline, 'About PRANA & Calculations'),
          const SizedBox(height: 24),
          Center(
            child: TextButton(
              onPressed: () {},
              child: const Text('Log Out', style: TextStyle(color: Colors.redAccent, fontSize: 16)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0, left: 4.0),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white54),
      ),
    );
  }

  Widget _buildListTile(IconData icon, String title) {
    return Card(
      margin: const EdgeInsets.only(bottom: 4),
      color: Colors.white.withValues(alpha: 0.05),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: ListTile(
        leading: Icon(icon, color: Colors.white70),
        title: Text(title, style: const TextStyle(color: Colors.white)),
        trailing: const Icon(Icons.chevron_right, color: Colors.white54),
        onTap: () {},
      ),
    );
  }

  Widget _buildSwitchTile(String title, bool value) {
    return Card(
      margin: const EdgeInsets.only(bottom: 4),
      color: Colors.white.withValues(alpha: 0.05),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: SwitchListTile(
        title: Text(title, style: const TextStyle(color: Colors.white)),
        value: value,
        onChanged: (val) {},
        activeColor: AppTheme.primaryTeal,
      ),
    );
  }

  Widget _buildWhatsAppToggle(BuildContext context) {
    final options = ['RDS', 'NDT', 'AQI', 'All'];
    return Card(
      margin: const EdgeInsets.only(bottom: 4),
      color: Colors.white.withValues(alpha: 0.05),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SwitchListTile(
            title: const Text('Whatsapp notification', style: TextStyle(color: Colors.white)),
            value: _whatsappEnabled,
            onChanged: (val) async {
              setState(() {
                _whatsappEnabled = val;
              });
              if (val && _whatsappTime == null) {
                _selectTime(context);
              }
            },
            activeColor: AppTheme.primaryTeal,
          ),
          if (_whatsappEnabled) ...[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Notification Type',
                    style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: options.map((opt) {
                      final selected = _whatsappOption == opt;
                      return ChoiceChip(
                        label: Text(opt),
                        selected: selected,
                        onSelected: (selected) {
                          if (selected) {
                            setState(() {
                              _whatsappOption = opt;
                            });
                          }
                        },
                        selectedColor: AppTheme.primaryTeal,
                        backgroundColor: Colors.white.withValues(alpha: 0.1),
                        labelStyle: TextStyle(
                          color: selected ? Colors.white : Colors.white70,
                          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                        ),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 12),
                  InkWell(
                    onTap: () => _selectTime(context),
                    borderRadius: BorderRadius.circular(8),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8.0),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.access_time, color: Colors.white70, size: 18),
                          const SizedBox(width: 8),
                          Text(
                            'Time: ${_whatsappTime!.hour.toString().padLeft(2, '0')}:${_whatsappTime!.minute.toString().padLeft(2, '0')} (Click to change)',
                            style: const TextStyle(color: Colors.white70, fontSize: 14),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _selectTime(BuildContext context) async {
    final time = await showTimePicker(
      context: context,
      initialTime: _whatsappTime ?? const TimeOfDay(hour: 8, minute: 0),
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
          child: child!,
        );
      },
    );
    if (time != null) {
      setState(() {
        _whatsappTime = time;
      });
    }
  }
}
