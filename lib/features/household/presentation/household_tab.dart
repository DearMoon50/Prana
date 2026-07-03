import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/providers/app_state_provider.dart';

class HouseholdTab extends ConsumerWidget {
  const HouseholdTab({super.key});

  void _showAddMemberDialog(BuildContext context, WidgetRef ref) {
    final nameController = TextEditingController();
    String selectedTag = 'Adults (18–55): 32°C';

    final memberOptions = [
      'Children (0–12): 30°C',
      'Teenagers (13–17): 31°C',
      'Adults (18–55): 32°C',
      'Women (18–55): 31°C',
      'Pregnant women: 30°C',
      'Elderly (55+): 30°C',
    ];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.backgroundLight,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => Padding(
        padding: MediaQuery.of(sheetContext).viewInsets,
        child: StatefulBuilder(
          builder: (ctx, setSheetState) => Padding(
            padding: const EdgeInsets.all(24),
            child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Add Household Member',
                      style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white54),
                    onPressed: () => Navigator.pop(sheetContext),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: nameController,
                autofocus: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Name',
                  hintStyle: const TextStyle(color: Colors.white54),
                  filled: true,
                  fillColor: Colors.white.withValues(alpha: 0.1),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text('Member Type & Alert Threshold', style: TextStyle(color: Colors.white70, fontSize: 13)),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: memberOptions
                    .map((tag) => GestureDetector(
                          onTap: () => setSheetState(() => selectedTag = tag),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: selectedTag == tag ? AppTheme.primaryTeal : Colors.white.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: selectedTag == tag ? AppTheme.primaryTeal : Colors.white.withValues(alpha: 0.2),
                              ),
                            ),
                            child: Text(tag,
                                style: TextStyle(
                                  color: selectedTag == tag ? Colors.white : Colors.white70,
                                  fontSize: 12,
                                )),
                          ),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryTeal,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () {
                  if (nameController.text.trim().isNotEmpty) {
                    final currentMembers = List<Map<String, String>>.from(ref.read(appStateProvider).members);
                    currentMembers.add({
                      'name': nameController.text.trim(),
                      'tag': selectedTag,
                    });
                    ref.read(appStateProvider.notifier).setMembers(currentMembers);
                    Navigator.pop(sheetContext);
                  }
                },
                child: const Text('Add Member', style: TextStyle(fontSize: 15)),
              ),
            ],
          ),
        ),
        ),
        ),
      ),
    );
  }

  void _showEditMemberDialog(BuildContext context, WidgetRef ref, int index, Map<String, String> member) {
    final nameController = TextEditingController(text: member['name']);
    String selectedTag = member['tag'] ?? 'Adults (18–55): 32°C';

    final memberOptions = [
      'Children (0–12): 30°C',
      'Teenagers (13–17): 31°C',
      'Adults (18–55): 32°C',
      'Women (18–55): 31°C',
      'Pregnant women: 30°C',
      'Elderly (55+): 30°C',
    ];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.backgroundLight,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => Padding(
        padding: MediaQuery.of(sheetContext).viewInsets,
        child: StatefulBuilder(
          builder: (ctx, setSheetState) => Padding(
            padding: const EdgeInsets.all(24),
            child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Edit Household Member',
                      style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white54),
                    onPressed: () => Navigator.pop(sheetContext),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: nameController,
                autofocus: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Name',
                  hintStyle: const TextStyle(color: Colors.white54),
                  filled: true,
                  fillColor: Colors.white.withValues(alpha: 0.1),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text('Member Type & Alert Threshold', style: TextStyle(color: Colors.white70, fontSize: 13)),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: memberOptions
                    .map((tag) => GestureDetector(
                          onTap: () => setSheetState(() => selectedTag = tag),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: selectedTag == tag ? AppTheme.primaryTeal : Colors.white.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: selectedTag == tag ? AppTheme.primaryTeal : Colors.white.withValues(alpha: 0.2),
                              ),
                            ),
                            child: Text(tag,
                                style: TextStyle(
                                  color: selectedTag == tag ? Colors.white : Colors.white70,
                                  fontSize: 12,
                                )),
                          ),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryTeal,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () {
                  if (nameController.text.trim().isNotEmpty) {
                    final currentMembers = List<Map<String, String>>.from(ref.read(appStateProvider).members);
                    currentMembers[index] = {
                      'name': nameController.text.trim(),
                      'tag': selectedTag,
                    };
                    ref.read(appStateProvider.notifier).setMembers(currentMembers);
                    Navigator.pop(sheetContext);
                  }
                },
                child: const Text('Save Changes', style: TextStyle(fontSize: 15)),
              ),
            ],
          ),
        ),
        ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appStateProvider);
    final members = appState.members;

    return Container(
      constraints: BoxConstraints(minHeight: MediaQuery.of(context).size.height),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Household', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
              IconButton(
                icon: const Icon(Icons.person_add, color: AppTheme.primaryTeal, size: 28),
                onPressed: () => _showAddMemberDialog(context, ref),
              ),
            ],
          ),
          const SizedBox(height: 24),
          if (members.isEmpty)
            Card(
              color: Colors.white.withValues(alpha: 0.05),
              child: Padding(
                padding: const EdgeInsets.all(32.0),
                child: Column(
                  children: [
                    Icon(Icons.people_outline, size: 48, color: Colors.white.withValues(alpha: 0.3)),
                    const SizedBox(height: 16),
                    const Text(
                      'No members registered yet',
                      style: TextStyle(color: Colors.white70, fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Add members to calculate dynamic threshold alerts tailored to their vulnerability.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white54, fontSize: 13),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton.icon(
                      onPressed: () => _showAddMemberDialog(context, ref),
                      icon: const Icon(Icons.add),
                      label: const Text('Add First Member'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryTeal,
                        foregroundColor: Colors.white,
                      ),
                    )
                  ],
                ),
              ),
            )
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: members.length,
              itemBuilder: (context, index) {
                final member = members[index];
                final name = member['name'] ?? 'Unknown';
                final tag = member['tag'] ?? 'Adult';

                // Determine risk color based on tag
                Color riskColor = AppTheme.tierSafe;
                String instruction = 'Keep active and stay hydrated.';
                if (tag.contains('Elderly') || tag.contains('Pregnant') || tag.contains('Children')) {
                  riskColor = AppTheme.tierHigh;
                  instruction = 'Avoid direct heat exposure. Max safety threshold is 30°C.';
                } else if (tag.contains('Women') || tag.contains('Teenagers')) {
                  riskColor = AppTheme.tierElevated;
                  instruction = 'Limit strenuous activity. Alert threshold is 31°C.';
                }

                return Card(
                  margin: const EdgeInsets.only(bottom: 16),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                CircleAvatar(
                                  backgroundColor: AppTheme.primaryTeal,
                                  child: Text(name.isNotEmpty ? name[0].toUpperCase() : '?',
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                ),
                                const SizedBox(width: 12),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(name,
                                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                                    const SizedBox(height: 2),
                                    Text(tag, style: const TextStyle(color: Colors.white54, fontSize: 13)),
                                  ],
                                ),
                              ],
                            ),
                            Row(
                              children: [
                                IconButton(
                                  icon: const Icon(Icons.edit, color: Colors.white54),
                                  onPressed: () => _showEditMemberDialog(context, ref, index, member),
                                ),
                                IconButton(
                                  icon: const Icon(Icons.delete, color: Colors.white54),
                                  onPressed: () {
                                    final currentMembers = List<Map<String, String>>.from(members);
                                    currentMembers.removeAt(index);
                                    ref.read(appStateProvider.notifier).setMembers(currentMembers);
                                  },
                                ),
                              ],
                            )
                          ],
                        ),
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(8),
                            border: Border(left: BorderSide(color: riskColor, width: 4)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Dynamic Status Instruction', style: TextStyle(fontSize: 12, color: Colors.white54)),
                              const SizedBox(height: 4),
                              Text(instruction, style: const TextStyle(color: Colors.white, fontSize: 14)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
        ],
      ),
      ),
    );
  }
}
