import 'package:flutter_riverpod/flutter_riverpod.dart';

class AppState {
  final String city;
  final String ward;
  final String roofMaterial;
  final String floorLevel;
  final bool hasAC;
  final List<Map<String, String>> members;

  const AppState({
    this.city = 'No Location Selected',
    this.ward = '',
    this.roofMaterial = 'Concrete',
    this.floorLevel = 'Middle',
    this.hasAC = false,
    this.members = const [],
  });

  String get locationDisplay => ward.isEmpty ? city : '$city, $ward';

  AppState copyWith({
    String? city,
    String? ward,
    String? roofMaterial,
    String? floorLevel,
    bool? hasAC,
    List<Map<String, String>>? members,
  }) {
    return AppState(
      city: city ?? this.city,
      ward: ward ?? this.ward,
      roofMaterial: roofMaterial ?? this.roofMaterial,
      floorLevel: floorLevel ?? this.floorLevel,
      hasAC: hasAC ?? this.hasAC,
      members: members ?? this.members,
    );
  }
}

class AppStateNotifier extends Notifier<AppState> {
  @override
  AppState build() => const AppState();

  void setLocation(String city, String ward) {
    state = state.copyWith(city: city, ward: ward);
  }

  void setHousing(String roofMaterial, String floorLevel, bool hasAC) {
    state = state.copyWith(
      roofMaterial: roofMaterial,
      floorLevel: floorLevel,
      hasAC: hasAC,
    );
  }

  void setMembers(List<Map<String, String>> members) {
    state = state.copyWith(members: members);
  }
}

final appStateProvider = NotifierProvider<AppStateNotifier, AppState>(
  AppStateNotifier.new,
);
