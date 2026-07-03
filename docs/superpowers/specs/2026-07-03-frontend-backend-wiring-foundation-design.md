# Frontend-backend wiring: foundation (chunk A of 3)

## Context

The repo has two Flutter apps:

- `mobile_app/` — older, plain UI, but **already fully wired** to the backend
  via `PranaApiClient` (`mobile_app/lib/services/api_client.dart`), calling
  `/register`, `/risk/current`, `/checkin` with request/response shapes that
  match the current backend models (`backend/main.py`) exactly.
- `lib/` (repo root) — newer, richer UI (onboarding, check-in, dashboard,
  household, insights, institutional, settings — ~3,557 lines), merged in
  from a diverged branch. **Zero networking code** — every screen renders
  hardcoded or purely-local Riverpod state.

Decision (Gokul, 2026-07-03): `lib/` is the frontend going forward.
`mobile_app/`'s wiring is the reference implementation to port from, not
code to keep running. `mobile_app/` itself is untouched by this work —
its removal/archival is a separate future decision.

This is chunk A of a 3-part sequence:
- **A (this doc):** HTTP client + user-id/session foundation.
- **B:** wire onboarding → `/register`, check-in → `/checkin`, household →
  `/household/members` CRUD, dashboard → `/risk/current` (one connected pass,
  since all four share the client/state built here).
- **C:** new backend endpoints for insights/institutional/settings screens
  (risk history, alert fetch, admin aggregate stats, notification prefs) —
  these have no existing backend logic to build on and are lower priority.

## Goal

Give `lib/` a working, tested path to call the backend, so chunk B can wire
each screen's real API calls without also solving networking/config/session
plumbing per-screen.

## Scope

**In scope:**
1. `http` package dependency.
2. `lib/core/config/api_config.dart` — single base-URL constant.
3. `lib/core/network/api_client.dart` — `PranaApiClient`, ported from
   `mobile_app/lib/services/api_client.dart`, extended with
   `/household/members` GET/POST/DELETE (needed for chunk B, not present in
   the old client).
4. `lib/core/network/models/` — Dart request/response models ported from
   `mobile_app/lib/models/user_registration.dart`, plus a new
   `HouseholdMember` model.
5. `AppState` (`lib/core/providers/app_state_provider.dart`) extended with
   `userId`/`phone`, persisted via `shared_preferences` (already a declared,
   currently-unused dependency) so login survives app restart.
6. Unit tests for `PranaApiClient` using a fake `http.Client`, following the
   `_FakeHttpClient extends http.BaseClient` pattern already established in
   `mobile_app/test/onboarding_screen_test.dart`.

**Out of scope (deferred to chunk B):** actually calling `PranaApiClient`
from any screen. No screen's `onPressed`/`onSubmit` changes in this chunk.

**Out of scope (deferred to chunk C):** any new backend endpoint.

## Design

### 1. Base URL (`lib/core/config/api_config.dart`)

```dart
class ApiConfig {
  static const String baseUrl = 'http://100.73.57.101:8000';
}
```

Tailscale IP of Gokul's laptop (`tailscale ip -4`), port 8000 (uvicorn
default per `API_CONTRACT.md`: `uvicorn backend.main:app --reload`). A
single constant in one file — changing environments later means editing one
line, not hunting across screens.

### 2. Models (`lib/core/network/models/`)

Ported 1:1 from `mobile_app/lib/models/user_registration.dart` (field names
and JSON keys already verified against `backend/main.py`'s Pydantic models):

- `home_profile.dart` → `HomeProfile { ac, roofMaterial, floorLevel, fan, windowsOpen, occupants }`
- `registration.dart` → `RegistrationRequest`, `RegisterResult`
- `household_member.dart` → new: `HouseholdMember { id, userId, name, tag, outdoorWorker, createdAt }`
  matching `backend/main.py`'s `HouseholdMember`/`HouseholdMemberAdd`/`TagEnum`
  (`child | teen | adult | woman | elderly` — no `pregnant` value; chunk B's
  household-screen wiring must reconcile the frontend's existing
  "Pregnant women" tag option against this, not this chunk).

### 3. API client (`lib/core/network/api_client.dart`)

`PranaApiClient` — same public shape as the reference implementation:

```dart
class PranaApiClient {
  PranaApiClient({required this.baseUrl, http.Client? client});

  Future<RegisterResult> register(RegistrationRequest req);

  Future<Map<String, dynamic>> getCurrentRisk({
    required double lat, required double lon, required String locationName,
    double? urbanHeatOffset, HomeProfile? onboarding,
    Map<String, dynamic>? sleepCheckin, String? userId,
  });

  Future<int> recordCheckin({
    required String userId, required String sleepQuality,
    double? outdoorTemp, double? humidity, String? checkinDate,
  });

  // New for chunk B (household screen):
  Future<HouseholdMember> addHouseholdMember({
    required String userId, required String name, required String tag,
    required bool outdoorWorker,
  });
  Future<List<HouseholdMember>> listHouseholdMembers(String userId);
  Future<void> deleteHouseholdMember(String id);
}
```

Error handling: throws `Exception` with status code + body on any non-2xx
response, matching the reference implementation exactly. Screens (chunk B)
are responsible for catching and displaying errors — no silent failures,
no retry logic (YAGNI for a hackathon-scale app).

### 4. Session state (`lib/core/providers/app_state_provider.dart`)

Add to `AppState`: `String? userId`, `String? phone`. Add to
`AppStateNotifier`: `setSession(String userId, String phone)`, plus
load-on-`build()`/save-on-`setSession()` via `shared_preferences` so the
session survives an app restart (the onboarding flow shouldn't have to
re-run every launch).

### 5. Tests

`test/core/network/api_client_test.dart` — one test per method, asserting
request method/path/JSON-body shape and response parsing, using a fake
`http.Client` (no live network calls). Mirrors the existing pattern in
`mobile_app/test/onboarding_screen_test.dart`.

## Testing plan

- Unit tests for `PranaApiClient` (all 6 methods: register, getCurrentRisk,
  recordCheckin, addHouseholdMember, listHouseholdMembers,
  deleteHouseholdMember) against a fake client — verify exact request shape
  and response parsing, both success and non-2xx-error paths.
- Unit test for `AppStateNotifier.setSession` persisting to and restoring
  from `shared_preferences` (using its in-memory test implementation).
- No widget/integration tests in this chunk — no screen changes yet.

## Explicitly not doing

- Not touching `mobile_app/` (deletion/archival is a separate decision).
- Not wiring any screen's button/submit handler (chunk B).
- Not building any new backend endpoint (chunk C).
- Not adding retry/offline-queue/interceptor logic (YAGNI).
- Not solving the household `pregnant` tag / `TagEnum` mismatch (flagged
  here, resolved in chunk B when the household screen is actually wired).
