# Frontend-Backend Wiring Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `lib/` Flutter app (package name `prana`, root `c:\Users\gokul D\prana`) a working, tested HTTP client and session-state foundation so a later pass can wire real screens to the FastAPI backend.

**Architecture:** Port the already-correct `mobile_app/lib/services/api_client.dart` + `mobile_app/lib/models/user_registration.dart` into `lib/core/network/`, extend with household-member CRUD (not present in the original), add a single base-URL config constant, and extend the existing Riverpod `AppState` with a persisted `userId`/`phone` session. No screen's UI or button handlers change in this plan.

**Tech Stack:** Flutter/Dart, `http` package (new dependency), `flutter_riverpod` (existing), `shared_preferences` (existing, currently unused), `flutter_test` for unit tests.

## Global Constraints

- Dart/Flutter package name is `prana` (see `pubspec.yaml:1`); import paths are `package:prana/...`.
- Base URL is `http://100.73.57.101:8000` (Gokul's laptop Tailscale IP, port 8000 — uvicorn default per `API_CONTRACT.md`).
- Request/response field names must match `backend/main.py`'s Pydantic models exactly (snake_case JSON keys) — verified against `RiskRequest`, `HomeProfile`, `CheckinRequest`, `RegisterRequest`, `RegisterResponse`, `HouseholdMemberAdd`, `HouseholdMember`, `TagEnum` in `backend/main.py`.
- `TagEnum` values are exactly `child | teen | adult | woman | elderly` (no `pregnant` — flagged for chunk B, not resolved here).
- No retry/interceptor/offline-queue logic (YAGNI).
- Do not modify `mobile_app/` in this plan — it is read-only reference material.
- Do not modify any file under `lib/features/` in this plan — no screen wiring yet.
- Existing test `test/widget_test.dart` must keep passing (it pumps `PranaApp` inside a bare `ProviderScope`, no network involved — verify it's unaffected after each task).

---

### Task 1: Add `http` dependency and base URL config

**Files:**
- Modify: `pubspec.yaml`
- Create: `lib/core/config/api_config.dart`
- Test: `test/core/config/api_config_test.dart`

**Interfaces:**
- Produces: `ApiConfig.baseUrl` (`String`, static const) — consumed by Task 2's `PranaApiClient` default constructor argument documentation and by future chunk-B screens.

- [ ] **Step 1: Write the failing test**

Create `test/core/config/api_config_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:prana/core/config/api_config.dart';

void main() {
  test('baseUrl points at the backend host', () {
    expect(ApiConfig.baseUrl, 'http://100.73.57.101:8000');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/config/api_config_test.dart`
Expected: FAIL — `Error: Error when reading 'lib/core/config/api_config.dart': No such file or directory` (or equivalent "package doesn't exist" compile error).

- [ ] **Step 3: Add the `http` dependency**

Edit `pubspec.yaml`, in the `dependencies:` block (after `url_launcher: ^6.3.2`):

```yaml
  url_launcher: ^6.3.2
  http: ^1.2.2
```

Run: `flutter pub get`
Expected: exits 0, `pubspec.lock` updated with an `http` entry.

- [ ] **Step 4: Write minimal implementation**

Create `lib/core/config/api_config.dart`:

```dart
/// Backend base URL. Single point of change for local dev vs. deployment.
class ApiConfig {
  static const String baseUrl = 'http://100.73.57.101:8000';
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `flutter test test/core/config/api_config_test.dart`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add pubspec.yaml pubspec.lock lib/core/config/api_config.dart test/core/config/api_config_test.dart
git commit -m "feat(core): add http dependency and backend base URL config"
```

---

### Task 2: Port `HomeProfile` model

**Files:**
- Create: `lib/core/network/models/home_profile.dart`
- Test: `test/core/network/models/home_profile_test.dart`

**Interfaces:**
- Consumes: nothing.
- Produces: `HomeProfile` class with fields `ac (bool)`, `roofMaterial (String)`, `floorLevel (String)`, `fan (bool, default false)`, `windowsOpen (bool, default false)`, `occupants (int, default 1)`; methods `toJson() -> Map<String, dynamic>` and `factory HomeProfile.fromJson(Map<String, dynamic>)`. Consumed by Task 4 (`RegistrationRequest`) and Task 5 (`PranaApiClient.getCurrentRisk`).

- [ ] **Step 1: Write the failing test**

Create `test/core/network/models/home_profile_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:prana/core/network/models/home_profile.dart';

void main() {
  test('toJson emits backend-matching snake_case keys', () {
    final profile = HomeProfile(
      ac: true,
      roofMaterial: 'tin',
      floorLevel: 'top',
      fan: true,
      windowsOpen: true,
      occupants: 3,
    );
    expect(profile.toJson(), {
      'ac': true,
      'roof_material': 'tin',
      'floor_level': 'top',
      'fan': true,
      'windows_open': true,
      'occupants': 3,
    });
  });

  test('constructor defaults match backend Pydantic defaults', () {
    final profile = HomeProfile(ac: false, roofMaterial: 'concrete', floorLevel: 'ground');
    expect(profile.fan, false);
    expect(profile.windowsOpen, false);
    expect(profile.occupants, 1);
  });

  test('fromJson parses a backend response', () {
    final profile = HomeProfile.fromJson({
      'ac': false,
      'roof_material': 'brick',
      'floor_level': 'middle',
      'fan': true,
      'windows_open': false,
      'occupants': 2,
    });
    expect(profile.ac, false);
    expect(profile.roofMaterial, 'brick');
    expect(profile.floorLevel, 'middle');
    expect(profile.fan, true);
    expect(profile.windowsOpen, false);
    expect(profile.occupants, 2);
  });

  test('fromJson falls back to safe defaults on missing optional keys', () {
    final profile = HomeProfile.fromJson({});
    expect(profile.ac, false);
    expect(profile.roofMaterial, 'concrete');
    expect(profile.floorLevel, 'ground');
    expect(profile.fan, false);
    expect(profile.windowsOpen, false);
    expect(profile.occupants, 1);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/network/models/home_profile_test.dart`
Expected: FAIL — compile error, `lib/core/network/models/home_profile.dart` doesn't exist.

- [ ] **Step 3: Write minimal implementation**

Create `lib/core/network/models/home_profile.dart` (ported verbatim from `mobile_app/lib/models/user_registration.dart:1-35`):

```dart
class HomeProfile {
  HomeProfile({
    required this.ac,
    required this.roofMaterial,
    required this.floorLevel,
    this.fan = false,
    this.windowsOpen = false,
    this.occupants = 1,
  });

  final bool ac;
  final String roofMaterial;
  final String floorLevel;
  final bool fan;
  final bool windowsOpen;
  final int occupants;

  Map<String, dynamic> toJson() => {
    'ac': ac,
    'roof_material': roofMaterial,
    'floor_level': floorLevel,
    'fan': fan,
    'windows_open': windowsOpen,
    'occupants': occupants,
  };

  factory HomeProfile.fromJson(Map<String, dynamic> json) => HomeProfile(
    ac: json['ac'] as bool? ?? false,
    roofMaterial: json['roof_material'] as String? ?? 'concrete',
    floorLevel: json['floor_level'] as String? ?? 'ground',
    fan: json['fan'] as bool? ?? false,
    windowsOpen: json['windows_open'] as bool? ?? false,
    occupants: (json['occupants'] as num?)?.toInt() ?? 1,
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/core/network/models/home_profile_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/core/network/models/home_profile.dart test/core/network/models/home_profile_test.dart
git commit -m "feat(core): port HomeProfile model from mobile_app"
```

---

### Task 3: Port `RegistrationRequest` and `RegisterResult` models

**Files:**
- Create: `lib/core/network/models/registration.dart`
- Test: `test/core/network/models/registration_test.dart`

**Interfaces:**
- Consumes: `HomeProfile` (Task 2, `lib/core/network/models/home_profile.dart`).
- Produces: `RegistrationRequest { phone, locationName, lat, lon, urbanHeatOffset, onboarding }` with `toJson()`; `RegisterResult { ok, userId, verified, whatsappLink, sandboxJoinCode }` with `factory RegisterResult.fromJson(Map<String, dynamic>)`. Consumed by Task 6 (`PranaApiClient.register`).

- [ ] **Step 1: Write the failing test**

Create `test/core/network/models/registration_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:prana/core/network/models/home_profile.dart';
import 'package:prana/core/network/models/registration.dart';

void main() {
  test('RegistrationRequest.toJson emits backend-matching shape', () {
    final req = RegistrationRequest(
      phone: '+919900001111',
      locationName: 'T. Nagar, Chennai',
      lat: 13.0827,
      lon: 80.2707,
      urbanHeatOffset: 3.0,
      onboarding: HomeProfile(ac: false, roofMaterial: 'concrete', floorLevel: 'ground'),
    );
    final json = req.toJson();
    expect(json['phone'], '+919900001111');
    expect(json['location_name'], 'T. Nagar, Chennai');
    expect(json['lat'], 13.0827);
    expect(json['lon'], 80.2707);
    expect(json['urban_heat_offset'], 3.0);
    expect(json['onboarding'], {
      'ac': false,
      'roof_material': 'concrete',
      'floor_level': 'ground',
      'fan': false,
      'windows_open': false,
      'occupants': 1,
    });
  });

  test('RegisterResult.fromJson parses a successful registration response', () {
    final result = RegisterResult.fromJson({
      'ok': true,
      'user_id': '+919900001111',
      'verified': false,
      'whatsapp_link': 'https://wa.me/919900000000?text=PRANA%20START',
      'sandbox_join_code': 'able-tiger',
    });
    expect(result.ok, true);
    expect(result.userId, '+919900001111');
    expect(result.verified, false);
    expect(result.whatsappLink, 'https://wa.me/919900000000?text=PRANA%20START');
    expect(result.sandboxJoinCode, 'able-tiger');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/network/models/registration_test.dart`
Expected: FAIL — compile error, `lib/core/network/models/registration.dart` doesn't exist.

- [ ] **Step 3: Write minimal implementation**

Create `lib/core/network/models/registration.dart` (ported from `mobile_app/lib/models/user_registration.dart:37-88`):

```dart
import 'home_profile.dart';

class RegistrationRequest {
  RegistrationRequest({
    required this.phone,
    required this.locationName,
    required this.lat,
    required this.lon,
    required this.urbanHeatOffset,
    required this.onboarding,
  });

  final String phone;
  final String locationName;
  final double lat;
  final double lon;
  final double? urbanHeatOffset;
  final HomeProfile onboarding;

  Map<String, dynamic> toJson() => {
    'phone': phone,
    'location_name': locationName,
    'lat': lat,
    'lon': lon,
    'urban_heat_offset': urbanHeatOffset,
    'onboarding': onboarding.toJson(),
  };
}

class RegisterResult {
  RegisterResult({
    required this.ok,
    required this.userId,
    required this.verified,
    required this.whatsappLink,
    required this.sandboxJoinCode,
  });

  factory RegisterResult.fromJson(Map<String, dynamic> json) {
    return RegisterResult(
      ok: json['ok'] as bool,
      userId: json['user_id'] as String,
      verified: json['verified'] as bool,
      whatsappLink: json['whatsapp_link'] as String,
      sandboxJoinCode: json['sandbox_join_code'] as String,
    );
  }

  final bool ok;
  final String userId;
  final bool verified;
  final String whatsappLink;
  final String sandboxJoinCode;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/core/network/models/registration_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/core/network/models/registration.dart test/core/network/models/registration_test.dart
git commit -m "feat(core): port RegistrationRequest and RegisterResult models"
```

---

### Task 4: New `HouseholdMember` model

**Files:**
- Create: `lib/core/network/models/household_member.dart`
- Test: `test/core/network/models/household_member_test.dart`

**Interfaces:**
- Consumes: nothing.
- Produces: `HouseholdMember { id, userId, name, tag, outdoorWorker, createdAt }` with `factory HouseholdMember.fromJson(Map<String, dynamic>)` and `Map<String, dynamic> toAddJson()` (for the POST body, which omits `id`/`createdAt` — the backend generates those). Consumed by Task 7 (`PranaApiClient` household methods).

- [ ] **Step 1: Write the failing test**

Create `test/core/network/models/household_member_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:prana/core/network/models/household_member.dart';

void main() {
  test('fromJson parses a backend HouseholdMember response', () {
    final member = HouseholdMember.fromJson({
      'id': 'abc123',
      'user_id': '+919900001111',
      'name': 'Amma',
      'tag': 'elderly',
      'outdoor_worker': false,
      'created_at': '2026-07-03T10:00:00',
    });
    expect(member.id, 'abc123');
    expect(member.userId, '+919900001111');
    expect(member.name, 'Amma');
    expect(member.tag, 'elderly');
    expect(member.outdoorWorker, false);
    expect(member.createdAt, '2026-07-03T10:00:00');
  });

  test('toAddJson emits the POST body shape (no id/createdAt)', () {
    final member = HouseholdMember(
      id: '',
      userId: '+919900001111',
      name: 'Raju',
      tag: 'child',
      outdoorWorker: false,
      createdAt: '',
    );
    expect(member.toAddJson(), {
      'user_id': '+919900001111',
      'name': 'Raju',
      'tag': 'child',
      'outdoor_worker': false,
    });
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/network/models/household_member_test.dart`
Expected: FAIL — compile error, `lib/core/network/models/household_member.dart` doesn't exist.

- [ ] **Step 3: Write minimal implementation**

Create `lib/core/network/models/household_member.dart`:

```dart
/// Mirrors backend/main.py's HouseholdMember / HouseholdMemberAdd / TagEnum.
/// Valid `tag` values: child | teen | adult | woman | elderly.
/// (No "pregnant" tag exists on the backend yet -- see chunk B notes.)
class HouseholdMember {
  HouseholdMember({
    required this.id,
    required this.userId,
    required this.name,
    required this.tag,
    required this.outdoorWorker,
    required this.createdAt,
  });

  final String id;
  final String userId;
  final String name;
  final String tag;
  final bool outdoorWorker;
  final String createdAt;

  factory HouseholdMember.fromJson(Map<String, dynamic> json) => HouseholdMember(
    id: json['id'] as String,
    userId: json['user_id'] as String,
    name: json['name'] as String,
    tag: json['tag'] as String,
    outdoorWorker: json['outdoor_worker'] as bool? ?? false,
    createdAt: json['created_at'] as String,
  );

  /// POST /household/members body shape -- backend assigns id/created_at.
  Map<String, dynamic> toAddJson() => {
    'user_id': userId,
    'name': name,
    'tag': tag,
    'outdoor_worker': outdoorWorker,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/core/network/models/household_member_test.dart`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/core/network/models/household_member.dart test/core/network/models/household_member_test.dart
git commit -m "feat(core): add HouseholdMember model"
```

---

### Task 5: `PranaApiClient` — register, getCurrentRisk, recordCheckin

**Files:**
- Create: `lib/core/network/api_client.dart`
- Test: `test/core/network/api_client_test.dart`

**Interfaces:**
- Consumes: `HomeProfile` (Task 2), `RegistrationRequest`/`RegisterResult` (Task 3), `ApiConfig.baseUrl` (Task 1, used only in documentation/defaults — tests always pass an explicit `baseUrl`).
- Produces: `PranaApiClient(baseUrl: String, {http.Client? client})` with methods `register`, `getCurrentRisk`, `recordCheckin` (signatures below). Extended by Task 7 with household methods on the same class.

- [ ] **Step 1: Write the failing test**

Create `test/core/network/api_client_test.dart`:

```dart
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:prana/core/network/api_client.dart';
import 'package:prana/core/network/models/home_profile.dart';
import 'package:prana/core/network/models/registration.dart';

class _FakeHttpClient extends http.BaseClient {
  _FakeHttpClient(this.responseBody, this.statusCode);

  final String responseBody;
  final int statusCode;
  http.Request? lastRequest;
  List<int>? lastBodyBytes;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (request is http.Request) {
      lastRequest = request;
      lastBodyBytes = request.bodyBytes;
    }
    final bytes = utf8.encode(responseBody);
    return http.StreamedResponse(Stream.value(bytes), statusCode);
  }
}

void main() {
  group('register', () {
    test('POSTs to /register with the correct body and parses the response', () async {
      final fake = _FakeHttpClient(
        jsonEncode({
          'ok': true,
          'user_id': '+919900001111',
          'verified': false,
          'whatsapp_link': 'https://wa.me/919900000000?text=PRANA%20START',
          'sandbox_join_code': 'able-tiger',
        }),
        200,
      );
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      final result = await client.register(RegistrationRequest(
        phone: '+919900001111',
        locationName: 'T. Nagar, Chennai',
        lat: 13.0827,
        lon: 80.2707,
        urbanHeatOffset: 3.0,
        onboarding: HomeProfile(ac: false, roofMaterial: 'concrete', floorLevel: 'ground'),
      ));

      expect(fake.lastRequest!.method, 'POST');
      expect(fake.lastRequest!.url.toString(), 'http://test.local/register');
      final sentBody = jsonDecode(utf8.decode(fake.lastBodyBytes!)) as Map<String, dynamic>;
      expect(sentBody['phone'], '+919900001111');
      expect(result.userId, '+919900001111');
      expect(result.sandboxJoinCode, 'able-tiger');
    });

    test('throws on non-2xx response', () async {
      final fake = _FakeHttpClient('{"detail": "phone already registered"}', 409);
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      expect(
        () => client.register(RegistrationRequest(
          phone: '+919900001111',
          locationName: 'X',
          lat: 0,
          lon: 0,
          urbanHeatOffset: null,
          onboarding: HomeProfile(ac: false, roofMaterial: 'concrete', floorLevel: 'ground'),
        )),
        throwsException,
      );
    });
  });

  group('getCurrentRisk', () {
    test('POSTs to /risk/current and returns the result map', () async {
      final fake = _FakeHttpClient(
        jsonEncode({
          'result': {'ccri': 64.7, 'risk_level': 'HIGH'},
          'calculation_log': 'log text',
        }),
        200,
      );
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      final result = await client.getCurrentRisk(
        lat: 13.0827,
        lon: 80.2707,
        locationName: 'Chennai',
        userId: '+919900001111',
      );

      expect(fake.lastRequest!.method, 'POST');
      expect(fake.lastRequest!.url.toString(), 'http://test.local/risk/current');
      final sentBody = jsonDecode(utf8.decode(fake.lastBodyBytes!)) as Map<String, dynamic>;
      expect(sentBody['lat'], 13.0827);
      expect(sentBody['user_id'], '+919900001111');
      expect(result['ccri'], 64.7);
      expect(result['risk_level'], 'HIGH');
    });
  });

  group('recordCheckin', () {
    test('POSTs to /checkin and returns n_checkins', () async {
      final fake = _FakeHttpClient(
        jsonEncode({'ok': true, 'user_id': '+919900001111', 'checkin_date': '2026-07-03', 'n_checkins': 5}),
        200,
      );
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      final n = await client.recordCheckin(userId: '+919900001111', sleepQuality: 'poor');

      expect(fake.lastRequest!.method, 'POST');
      expect(fake.lastRequest!.url.toString(), 'http://test.local/checkin');
      final sentBody = jsonDecode(utf8.decode(fake.lastBodyBytes!)) as Map<String, dynamic>;
      expect(sentBody['sleep_quality'], 'poor');
      expect(n, 5);
    });

    test('throws on non-2xx response', () async {
      final fake = _FakeHttpClient('{"detail": "invalid user_id"}', 422);
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      expect(
        () => client.recordCheckin(userId: '', sleepQuality: 'poor'),
        throwsException,
      );
    });
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/network/api_client_test.dart`
Expected: FAIL — compile error, `lib/core/network/api_client.dart` doesn't exist.

- [ ] **Step 3: Write minimal implementation**

Create `lib/core/network/api_client.dart` (ported from `mobile_app/lib/services/api_client.dart:1-99`):

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models/home_profile.dart';
import 'models/registration.dart';

class PranaApiClient {
  PranaApiClient({required this.baseUrl, http.Client? client})
    : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  Future<RegisterResult> register(RegistrationRequest req) async {
    final uri = Uri.parse('$baseUrl/register');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(req.toJson()),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Registration failed ${response.statusCode}: ${response.body}');
    }

    return RegisterResult.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<Map<String, dynamic>> getCurrentRisk({
    required double lat,
    required double lon,
    required String locationName,
    double? urbanHeatOffset,
    HomeProfile? onboarding,
    Map<String, dynamic>? sleepCheckin,
    String? userId,
  }) async {
    final uri = Uri.parse('$baseUrl/risk/current');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'lat': lat,
        'lon': lon,
        'location_name': locationName,
        'urban_heat_offset': urbanHeatOffset,
        'onboarding_data': onboarding?.toJson(),
        'sleep_checkin': sleepCheckin,
        'user_id': userId,
      }),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Backend error ${response.statusCode}: ${response.body}');
    }

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    return decoded['result'] as Map<String, dynamic>;
  }

  Future<int> recordCheckin({
    required String userId,
    required String sleepQuality,
    double? outdoorTemp,
    double? humidity,
    String? checkinDate,
  }) async {
    final uri = Uri.parse('$baseUrl/checkin');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'user_id': userId,
        'sleep_quality': sleepQuality,
        'outdoor_temp': outdoorTemp,
        'humidity': humidity,
        'checkin_date': checkinDate,
      }),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Check-in failed ${response.statusCode}: ${response.body}');
    }

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    return (decoded['n_checkins'] as num?)?.toInt() ?? 0;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/core/network/api_client_test.dart`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/core/network/api_client.dart test/core/network/api_client_test.dart
git commit -m "feat(core): port PranaApiClient (register, getCurrentRisk, recordCheckin)"
```

---

### Task 6: Extend `PranaApiClient` with household-member CRUD

**Files:**
- Modify: `lib/core/network/api_client.dart`
- Modify: `test/core/network/api_client_test.dart`

**Interfaces:**
- Consumes: `HouseholdMember` (Task 4, `lib/core/network/models/household_member.dart`).
- Produces: `PranaApiClient.addHouseholdMember(...)`, `.listHouseholdMembers(String userId)`, `.deleteHouseholdMember(String id)` added to the same `PranaApiClient` class from Task 5.

- [ ] **Step 1: Write the failing tests**

Append to `test/core/network/api_client_test.dart` (add the import, then a new `group` inside `main()`):

Add import at top:
```dart
import 'package:prana/core/network/models/household_member.dart';
```

Add before the closing `}` of `main()`:
```dart
  group('household members', () {
    test('addHouseholdMember POSTs to /household/members', () async {
      final fake = _FakeHttpClient(
        jsonEncode({
          'id': 'abc123',
          'user_id': '+919900001111',
          'name': 'Amma',
          'tag': 'elderly',
          'outdoor_worker': false,
          'created_at': '2026-07-03T10:00:00',
        }),
        200,
      );
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      final member = await client.addHouseholdMember(
        userId: '+919900001111',
        name: 'Amma',
        tag: 'elderly',
        outdoorWorker: false,
      );

      expect(fake.lastRequest!.method, 'POST');
      expect(fake.lastRequest!.url.toString(), 'http://test.local/household/members');
      final sentBody = jsonDecode(utf8.decode(fake.lastBodyBytes!)) as Map<String, dynamic>;
      expect(sentBody['name'], 'Amma');
      expect(sentBody['tag'], 'elderly');
      expect(member.id, 'abc123');
      expect(member.name, 'Amma');
    });

    test('listHouseholdMembers GETs /household/members?user_id=', () async {
      final fake = _FakeHttpClient(
        jsonEncode([
          {
            'id': 'abc123',
            'user_id': '+919900001111',
            'name': 'Amma',
            'tag': 'elderly',
            'outdoor_worker': false,
            'created_at': '2026-07-03T10:00:00',
          },
        ]),
        200,
      );
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      final members = await client.listHouseholdMembers('+919900001111');

      expect(fake.lastRequest!.method, 'GET');
      expect(
        fake.lastRequest!.url.toString(),
        'http://test.local/household/members?user_id=%2B919900001111',
      );
      expect(members.length, 1);
      expect(members.first.name, 'Amma');
    });

    test('deleteHouseholdMember DELETEs /household/members/{id}', () async {
      final fake = _FakeHttpClient(jsonEncode({'ok': true}), 200);
      final client = PranaApiClient(baseUrl: 'http://test.local', client: fake);
      await client.deleteHouseholdMember('abc123');

      expect(fake.lastRequest!.method, 'DELETE');
      expect(fake.lastRequest!.url.toString(), 'http://test.local/household/members/abc123');
    });
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/network/api_client_test.dart`
Expected: FAIL — `The method 'addHouseholdMember' isn't defined for the type 'PranaApiClient'` (and similarly for the other two).

- [ ] **Step 3: Write minimal implementation**

Add import to `lib/core/network/api_client.dart`:
```dart
import 'models/household_member.dart';
```

Add methods inside the `PranaApiClient` class, after `recordCheckin`:

```dart
  Future<HouseholdMember> addHouseholdMember({
    required String userId,
    required String name,
    required String tag,
    required bool outdoorWorker,
  }) async {
    final uri = Uri.parse('$baseUrl/household/members');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'user_id': userId,
        'name': name,
        'tag': tag,
        'outdoor_worker': outdoorWorker,
      }),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Add household member failed ${response.statusCode}: ${response.body}');
    }

    return HouseholdMember.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<HouseholdMember>> listHouseholdMembers(String userId) async {
    final uri = Uri.parse('$baseUrl/household/members').replace(
      queryParameters: {'user_id': userId},
    );
    final response = await _client.get(uri);

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('List household members failed ${response.statusCode}: ${response.body}');
    }

    final decoded = jsonDecode(response.body) as List<dynamic>;
    return decoded
        .map((e) => HouseholdMember.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> deleteHouseholdMember(String id) async {
    final uri = Uri.parse('$baseUrl/household/members/$id');
    final response = await _client.delete(uri);

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Delete household member failed ${response.statusCode}: ${response.body}');
    }
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/core/network/api_client_test.dart`
Expected: PASS (8 tests total).

- [ ] **Step 5: Commit**

```bash
git add lib/core/network/api_client.dart test/core/network/api_client_test.dart
git commit -m "feat(core): add household-member CRUD to PranaApiClient"
```

---

### Task 7: Extend `AppState` with persisted session (userId/phone)

**Files:**
- Modify: `lib/core/providers/app_state_provider.dart`
- Test: `test/core/providers/app_state_provider_test.dart`

**Interfaces:**
- Consumes: `shared_preferences` package (already in `pubspec.yaml:40`, unused until now).
- Produces: `AppState.userId (String?)`, `AppState.phone (String?)` fields; `AppStateNotifier.setSession(String userId, String phone)` which updates state AND persists to `SharedPreferences`; `AppStateNotifier.build()` now attempts to restore a previously-saved session synchronously from the mock/plugin-backed store where available (see step 3 for the exact restore strategy chosen to keep `build()` synchronous, as `Notifier.build()` cannot be `async`).

- [ ] **Step 1: Write the failing test**

Create `test/core/providers/app_state_provider_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:prana/core/providers/app_state_provider.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('setSession updates AppState.userId and .phone', () async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appStateProvider.notifier).setSession(
      '+919900001111',
      '+919900001111',
    );

    final state = container.read(appStateProvider);
    expect(state.userId, '+919900001111');
    expect(state.phone, '+919900001111');
  });

  test('setSession persists to SharedPreferences', () async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appStateProvider.notifier).setSession(
      '+919900002222',
      '+919900002222',
    );

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('prana_user_id'), '+919900002222');
    expect(prefs.getString('prana_phone'), '+919900002222');
  });

  test('restoreSession loads a previously persisted session', () async {
    SharedPreferences.setMockInitialValues({
      'prana_user_id': '+919900003333',
      'prana_phone': '+919900003333',
    });
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appStateProvider.notifier).restoreSession();

    final state = container.read(appStateProvider);
    expect(state.userId, '+919900003333');
    expect(state.phone, '+919900003333');
  });

  test('AppState defaults userId/phone to null when nothing persisted', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final state = container.read(appStateProvider);
    expect(state.userId, isNull);
    expect(state.phone, isNull);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/providers/app_state_provider_test.dart`
Expected: FAIL — `The getter 'userId' isn't defined for the type 'AppState'` (and `setSession`/`restoreSession` undefined).

- [ ] **Step 3: Write minimal implementation**

Rewrite `lib/core/providers/app_state_provider.dart` in full:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kUserIdKey = 'prana_user_id';
const _kPhoneKey = 'prana_phone';

class AppState {
  final String city;
  final String ward;
  final String roofMaterial;
  final String floorLevel;
  final bool hasAC;
  final List<Map<String, String>> members;
  final String? userId;
  final String? phone;

  const AppState({
    this.city = 'No Location Selected',
    this.ward = '',
    this.roofMaterial = 'Concrete',
    this.floorLevel = 'Middle',
    this.hasAC = false,
    this.members = const [],
    this.userId,
    this.phone,
  });

  String get locationDisplay => ward.isEmpty ? city : '$city, $ward';

  AppState copyWith({
    String? city,
    String? ward,
    String? roofMaterial,
    String? floorLevel,
    bool? hasAC,
    List<Map<String, String>>? members,
    String? userId,
    String? phone,
  }) {
    return AppState(
      city: city ?? this.city,
      ward: ward ?? this.ward,
      roofMaterial: roofMaterial ?? this.roofMaterial,
      floorLevel: floorLevel ?? this.floorLevel,
      hasAC: hasAC ?? this.hasAC,
      members: members ?? this.members,
      userId: userId ?? this.userId,
      phone: phone ?? this.phone,
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

  /// Updates session state and persists it so it survives an app restart.
  Future<void> setSession(String userId, String phone) async {
    state = state.copyWith(userId: userId, phone: phone);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kUserIdKey, userId);
    await prefs.setString(_kPhoneKey, phone);
  }

  /// Loads a previously persisted session, if any. `Notifier.build()` must
  /// be synchronous, so restoration is a separate explicit call the app
  /// root triggers once at startup rather than happening inside `build()`.
  Future<void> restoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getString(_kUserIdKey);
    final phone = prefs.getString(_kPhoneKey);
    if (userId != null || phone != null) {
      state = state.copyWith(userId: userId, phone: phone);
    }
  }
}

final appStateProvider = NotifierProvider<AppStateNotifier, AppState>(
  AppStateNotifier.new,
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/core/providers/app_state_provider_test.dart`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `flutter test`
Expected: PASS — all tests including the pre-existing `test/widget_test.dart` smoke test and every test created in Tasks 1-7.

- [ ] **Step 6: Commit**

```bash
git add lib/core/providers/app_state_provider.dart test/core/providers/app_state_provider_test.dart
git commit -m "feat(core): add persisted session (userId/phone) to AppState"
```

---

## Post-plan notes (not part of this plan's scope)

- No screen (`lib/features/**`) was modified — that's chunk B.
- `AppStateNotifier.restoreSession()` is defined but not yet called from
  anywhere (e.g. `main.dart` startup) — wiring that call is chunk B's job,
  alongside the screens that will actually use `PranaApiClient`.
- The household `pregnant` tag / `TagEnum` mismatch (frontend's UI has a
  "Pregnant women" option; backend's `TagEnum` has no `pregnant` value) is
  unresolved — flagged for chunk B when `household_tab.dart` is wired.
- `mobile_app/` was not modified or deleted.
