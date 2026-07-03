import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/providers/app_state_provider.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  // Dynamic location data
  final Map<String, List<String>> _cityWards = {
    'Chennai': ['Adyar (Zone 13)', 'Teynampet (Zone 9)', 'Velachery'],
    'Ho Chi Minh City': ['District 1', 'District 3', 'District 7'],
    'Dhaka': ['Gulshan', 'Banani', 'Mirpur'],
    'Karachi': ['Clifton', 'DHA', 'Gulshan-e-Iqbal'],
    'Manila': ['Ermita', 'Malate', 'Tondo'],
    'Jakarta': ['Central Jakarta', 'South Jakarta', 'West Jakarta'],
  };

  String? _selectedCity;
  String? _selectedWard;
  bool _isLoadingLocation = false;

  // Phone consent state
  bool _agreedToAlerts = true;

  // Housing details state
  String _roofMaterial = 'Concrete';
  String _floorLevel = 'Middle';
  bool _hasAC = false;

  // Household members state
  final List<Map<String, String>> _members = [];

  // Phone
  final TextEditingController _phoneController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _phoneController.addListener(() {
      setState(() {});
    });
  }

  @override
  void dispose() {
    _pageController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  bool _canProceed() {
    if (_currentPage == 0) {
      return _phoneController.text.trim().isNotEmpty && _agreedToAlerts;
    }
    if (_currentPage == 1) {
      return _selectedCity != null && _selectedWard != null;
    }
    return true;
  }

  void _nextPage() {
    if (_currentPage < 4) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      context.go('/app');
    }
  }

  void _showAddMemberDialog() {
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
      builder: (sheetContext) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.only(
            left: 24,
            right: 24,
            top: 24,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
          ),
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
                    setState(() {
                      _members.add({'name': nameController.text.trim(), 'tag': selectedTag});
                    });
                    Navigator.pop(sheetContext);
                  }
                },
                child: const Text('Add Member', style: TextStyle(fontSize: 15)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openWhatsApp() async {
    const twilioNumber = '14155238886';
    const message = 'start prana';
    final waUri = Uri.parse('whatsapp://send?phone=$twilioNumber&text=${Uri.encodeComponent(message)}');
    final webUri = Uri.parse('https://wa.me/$twilioNumber?text=${Uri.encodeComponent(message)}');
    try {
      if (await canLaunchUrl(waUri)) {
        await launchUrl(waUri);
      } else {
        await launchUrl(webUri, mode: LaunchMode.externalApplication);
      }
    } catch (_) {
      await launchUrl(webUri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              AppTheme.backgroundDark,
              AppTheme.backgroundLight,
              AppTheme.primaryTeal,
            ],
            stops: [0.0, 0.5, 1.0],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // Progress indicator
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                child: Row(
                  children: List.generate(5, (i) => Expanded(
                    child: Container(
                      height: 3,
                      margin: const EdgeInsets.symmetric(horizontal: 2),
                      decoration: BoxDecoration(
                        color: i <= _currentPage
                            ? AppTheme.primaryTeal
                            : Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  )),
                ),
              ),
              Expanded(
                child: PageView(
                  controller: _pageController,
                  physics: const NeverScrollableScrollPhysics(),
                  onPageChanged: (index) => setState(() => _currentPage = index),
                  children: [
                    _buildPhoneConsentStep(),
                    _buildLocationStep(),
                    _buildHousingDetailsStep(),
                    _buildHouseholdMembersStep(),
                    _buildConfirmationStep(),
                  ],
                ),
              ),
              // Bottom nav buttons — hidden on last page (WhatsApp step)
              if (_currentPage < 4)
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      if (_currentPage > 0)
                        TextButton(
                          onPressed: () => _pageController.previousPage(
                            duration: const Duration(milliseconds: 300),
                            curve: Curves.easeInOut,
                          ),
                          child: const Text('Back', style: TextStyle(color: Colors.white70)),
                        )
                      else
                        const SizedBox.shrink(),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.primaryTeal,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        onPressed: _canProceed() ? _nextPage : null,
                        child: const Text('Next'),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhoneConsentStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Welcome to PRANA',
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 8),
          const Text(
            'Enter your phone number to receive critical alerts.',
            style: TextStyle(fontSize: 16, color: Colors.white70),
          ),
          const SizedBox(height: 32),
          TextField(
            controller: _phoneController,
            keyboardType: TextInputType.phone,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'Phone Number (e.g. +91 98765 43210)',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.white.withOpacity(0.1),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
              prefixIcon: const Icon(Icons.phone, color: Colors.white54),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Checkbox(
                value: _agreedToAlerts,
                onChanged: (val) {
                  if (val != null) {
                    setState(() => _agreedToAlerts = val);
                  }
                },
                fillColor: WidgetStateProperty.all(AppTheme.primaryTeal),
              ),
              const Expanded(
                child: Text(
                  'I agree to receive WhatsApp alerts from PRANA',
                  style: TextStyle(color: Colors.white),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLocationStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Where are you located?',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 32),
          ElevatedButton.icon(
            onPressed: _isLoadingLocation ? null : () async {
              setState(() => _isLoadingLocation = true);
              await Future.delayed(const Duration(seconds: 2));
              if (mounted) {
                setState(() {
                  _selectedCity = 'Ho Chi Minh City';
                  _selectedWard = _cityWards['Ho Chi Minh City']!.first;
                  _isLoadingLocation = false;
                });
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Location detected: Ho Chi Minh City')),
                );
              }
            },
            icon: _isLoadingLocation
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                : const Icon(Icons.my_location),
            label: Text(_isLoadingLocation ? 'Locating...' : 'Use my current location'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white.withOpacity(0.1),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.all(16),
            ),
          ),
          const SizedBox(height: 24),
          const Row(
            children: [
              Expanded(child: Divider(color: Colors.white24)),
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Text('OR', style: TextStyle(color: Colors.white54)),
              ),
              Expanded(child: Divider(color: Colors.white24)),
            ],
          ),
          const SizedBox(height: 24),
          const Text('City', style: TextStyle(color: Colors.white70, fontSize: 13)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                dropdownColor: AppTheme.backgroundLight,
                value: _selectedCity,
                hint: const Text('Select City', style: TextStyle(color: Colors.white54)),
                isExpanded: true,
                style: const TextStyle(color: Colors.white, fontSize: 16),
                items: _cityWards.keys
                    .map((city) => DropdownMenuItem(value: city, child: Text(city)))
                    .toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() {
                      _selectedCity = val;
                      _selectedWard = null; // Reset ward on city change so user must select a new one
                    });
                  }
                },
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Text('District / Ward', style: TextStyle(color: Colors.white70, fontSize: 13)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                dropdownColor: AppTheme.backgroundLight,
                value: _selectedWard,
                hint: const Text('Select District / Ward', style: TextStyle(color: Colors.white54)),
                isExpanded: true,
                style: const TextStyle(color: Colors.white, fontSize: 16),
                items: _selectedCity == null
                    ? []
                    : _cityWards[_selectedCity]!
                        .map((ward) => DropdownMenuItem(value: ward, child: Text(ward)))
                        .toList(),
                onChanged: (val) {
                  if (val != null) setState(() => _selectedWard = val);
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHousingDetailsStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Housing Details',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 8),
          const Text(
            'This helps us calculate your indoor heat risks more accurately.',
            style: TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 32),
          const Text('Roof Material', style: TextStyle(color: Colors.white, fontSize: 16)),
          const SizedBox(height: 10),
          Row(
            children: ['Tin', 'Concrete', 'Other'].map((option) {
              final selected = _roofMaterial == option;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _roofMaterial = option),
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: selected ? AppTheme.primaryTeal : Colors.white.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: selected ? AppTheme.primaryTeal : Colors.white.withOpacity(0.2),
                      ),
                    ),
                    child: Center(
                      child: Text(
                        option,
                        style: TextStyle(
                          color: selected ? Colors.white : Colors.white70,
                          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 28),
          const Text('Floor Level', style: TextStyle(color: Colors.white, fontSize: 16)),
          const SizedBox(height: 10),
          Row(
            children: ['Ground', 'Middle', 'Top'].map((option) {
              final selected = _floorLevel == option;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _floorLevel = option),
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: selected ? AppTheme.primaryTeal : Colors.white.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: selected ? AppTheme.primaryTeal : Colors.white.withOpacity(0.2),
                      ),
                    ),
                    child: Center(
                      child: Text(
                        option,
                        style: TextStyle(
                          color: selected ? Colors.white : Colors.white70,
                          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 28),
          const Text('AC Available', style: TextStyle(color: Colors.white, fontSize: 16)),
          const SizedBox(height: 10),
          Row(
            children: ['Yes', 'No'].map((option) {
              final selected = (option == 'Yes') == _hasAC;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _hasAC = option == 'Yes'),
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: selected ? AppTheme.primaryTeal : Colors.white.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: selected ? AppTheme.primaryTeal : Colors.white.withOpacity(0.2),
                      ),
                    ),
                    child: Center(
                      child: Text(
                        option,
                        style: TextStyle(
                          color: selected ? Colors.white : Colors.white70,
                          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildHouseholdMembersStep() {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Household Members',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 8),
          const Text(
            'Add members to get personalized risk alerts.',
            style: TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _members.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.group_add, size: 48, color: Colors.white.withOpacity(0.3)),
                        const SizedBox(height: 12),
                        Text('No members added yet', style: TextStyle(color: Colors.white.withOpacity(0.4))),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: _members.length,
                    itemBuilder: (context, index) {
                      final member = _members[index];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 10),
                        color: Colors.white.withOpacity(0.1),
                        child: ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppTheme.primaryTeal,
                            child: Text(member['name']![0].toUpperCase(), style: const TextStyle(color: Colors.white)),
                          ),
                          title: Text(member['name']!, style: const TextStyle(color: Colors.white)),
                          subtitle: Text(member['tag']!, style: const TextStyle(color: Colors.white54)),
                          trailing: IconButton(
                            icon: const Icon(Icons.close, color: Colors.white54),
                            onPressed: () => setState(() => _members.removeAt(index)),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _showAddMemberDialog,
            icon: const Icon(Icons.add),
            label: const Text('Add Household Member'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              padding: const EdgeInsets.all(16),
              side: BorderSide(color: Colors.white.withOpacity(0.3)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfirmationStep() {
    final memberCount = _members.length;
    final acText = _hasAC ? 'Yes' : 'No';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Icon(Icons.check_circle_outline, size: 80, color: AppTheme.tierSafe),
          const SizedBox(height: 24),
          const Text(
            'Setup Complete!',
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 8),
          const Text(
            'Your profile is ready. We will now monitor risks tailored to your household.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 15, color: Colors.white70),
          ),
          const SizedBox(height: 28),
          Card(
            color: Colors.white.withOpacity(0.08),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _confirmRow(Icons.location_on, 'Location', '${_selectedCity ?? "Not Selected"}, ${_selectedWard ?? ""}'),
                  const Divider(color: Colors.white12, height: 20),
                  _confirmRow(Icons.home, 'Housing', '$_roofMaterial roof · $_floorLevel floor · AC: $acText'),
                  const Divider(color: Colors.white12, height: 20),
                  _confirmRow(Icons.group, 'Members', memberCount == 0 ? 'None added' : '$memberCount member${memberCount > 1 ? 's' : ''}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 28),
          _buildWhatsAppSection(),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryTeal,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () {
                ref.read(appStateProvider.notifier).setLocation(_selectedCity ?? '', _selectedWard ?? '');
                ref.read(appStateProvider.notifier).setHousing(_roofMaterial, _floorLevel, _hasAC);
                ref.read(appStateProvider.notifier).setMembers(List.from(_members));
                context.go('/app');
              },
              child: const Text('Go to Dashboard', style: TextStyle(fontSize: 16)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWhatsAppSection() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF25D366).withValues(alpha: 0.15),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(15)),
            ),
            child: const Row(
              children: [
                Icon(Icons.chat_bubble_outline, color: Color(0xFF25D366), size: 18),
                SizedBox(width: 8),
                Text('Activate WhatsApp Alerts',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14)),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Send a message to our bot to register and receive heat alerts.',
                  style: TextStyle(color: Colors.white70, fontSize: 13),
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.07),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.send, color: AppTheme.primaryTeal, size: 16),
                      SizedBox(width: 8),
                      Text('"start prana"',
                          style: TextStyle(color: AppTheme.primaryTeal, fontFamily: 'monospace', fontSize: 14, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                ElevatedButton(
                  onPressed: _openWhatsApp,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF25D366),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    elevation: 0,
                  ),
                  child: const Text('Open WhatsApp', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _confirmRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppTheme.primaryTeal, size: 20),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(color: Colors.white, fontSize: 14)),
            ],
          ),
        ),
      ],
    );
  }
}
