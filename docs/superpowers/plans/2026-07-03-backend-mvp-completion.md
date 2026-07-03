# Backend MVP Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the PRANA backend to a coherent, single-source-of-truth MVP that runs on one laptop: unify persistence onto the framework SQLite layer, restore `/register` to its approved spec, give the proactive scheduler real RDS history + personalization, add basic alert cadence, fix the failing research test, and clean up hardening/deprecation issues.

**Architecture:** Collapse the two competing persistence systems (framework `SQLiteUserRepository`/`SQLiteCheckinRepository` on `prana.db` vs. the SQLAlchemy `prana/database.py` + `prana/models.py` on `prana_persistence.db`) into a single plain-`sqlite3` layer on one DB file. `/register` and the webhook and the scheduler and `/risk/current` all read/write the same `users`, `checkins`, `rds_states`, and `risk_evaluations` tables. The SQLAlchemy dependency and its two modules are deleted. The scheduler seeds each user's stored nightly-temp history and check-in personalization before scoring, so proactive alerts reflect multi-night RDS compounding. Alert cadence gains a per-user daily cap and a quiet-hours window on top of the existing state-change logic.

**Tech Stack:** Python 3.9, FastAPI, plain `sqlite3` (stdlib), pytest. No SQLAlchemy after this plan.

## Global Constraints

- **Python 3.9 annotations:** In Pydantic models and any runtime-evaluated annotations, use `typing.Optional[...]` / `typing.List[...]`, NOT PEP 604 (`X | None`) or PEP 585 (`list[x]`). Modules that already do `from __future__ import annotations` may keep `X | None` in function signatures (it is a string there), but do NOT add `from __future__ import annotations` to Pydantic model modules where it would break `model_rebuild`. `backend/main.py` does NOT currently import `annotations` — keep its Pydantic models on `Optional`.
- **One DB file:** the single source of truth is the path in `prana.config.DATABASE_URL` (default `sqlite:///./prana.db`). Every repository is constructed from that same URL. No module may open a second DB file.
- **No new heavy dependencies.** Everything here uses the stdlib `sqlite3` already in use. `sqlalchemy` is REMOVED from `requirements.txt` by the end.
- **Async repo methods stay async.** The framework repos expose `async def` methods that wrap sync work in `asyncio.to_thread`. New methods follow the same pattern.
- **TDD + frequent commits.** Every task: failing test → confirm fail → minimal implementation → confirm pass → commit.
- **Run tests with:** `.venv/Scripts/python.exe -m pytest` (Windows venv). Full suite baseline before starting: 238 passed, 2 failed.
- **Test DB isolation:** `build_repo()` and friends read `DATABASE_URL` from `prana.bot.bootstrap` (bound at import from `prana.config`), so monkeypatching `prana.config.DATABASE_URL` after import does NOT redirect them. Tests that must isolate the DB should construct the repo class directly with a `tmp_path` file (e.g. `SQLiteUserRepository(str(tmp_path/'t.db'))`) rather than relying on `build_repo()`. For endpoint tests that go through the module-scope singletons in `backend.main`, monkeypatch those singletons (`main.user_repo`, `main.rds_repo`, `main.risk_eval_repo`, `main.checkin_repo`) to temp-file-backed instances in a fixture. Where the plan's example tests use `build_repo()` with a monkeypatched config, adjust to direct construction if the repo does not pick up the temp path.

---

## File Structure

**New / heavily modified:**
- `framework/persistence/sqlite.py` — gains two new repositories: `SQLiteRDSStateRepository` (rolling nightly temps per user) and `SQLiteRiskEvalRepository` (risk-score history per user). Both share the one DB file.
- `prana/bot/bootstrap.py` — gains `build_rds_repo()` and `build_risk_eval_repo()` factories.
- `backend/main.py` — `/register` rewritten to the approved spec (framework repo, `verified=False`, `user_id=phone`, preserve-verified); `/risk/current` rewritten to use the new framework repos instead of SQLAlchemy sessions; SQLAlchemy imports removed; deprecated `@app.on_event` replaced with a lifespan handler.
- `prana/ai_tools/risk.py` — `get_risk` gains optional history + personalization seeding so the scheduler and agent score with the RDS ledger.
- `prana/scheduler.py` — passes the RDS + checkin repos into the scoring path.
- `prana/alerts.py` — daily-cap + quiet-hours cadence gate.
- `prana/config.py` — new cadence constants; keep single `DATABASE_URL`.
- `research/indoor_heat/adapters/south_asia/adapter.py` — fix `floor_level` mapping (`"top"` currently collapses to `"other"`).

**Deleted at the end:**
- `prana/database.py`, `prana/models.py` (SQLAlchemy layer), `scripts/ai_agent_verifier.py`, `scripts/test_persistence.py` (only consumers of the deleted layer; throwaway scripts).

**Tests:**
- `tests/framework/test_rds_state_repo.py` (new)
- `tests/framework/test_risk_eval_repo.py` (new)
- `tests/prana/test_register.py` (existing — must go green unmodified)
- `tests/prana/test_scheduler_scoring.py` (new)
- `tests/prana/test_alert_cadence.py` (new)
- `tests/prana/test_risk_current_persistence.py` (new)
- `tests/research/test_run_pipeline.py` (existing — must go green)

---

## Task 1: RDS-state repository on the framework SQLite layer

Replaces the SQLAlchemy `RDSState` model + `save_user_rds_state`/`load_user_rds_state` in `prana/database.py`. Same behavior (rolling window of `{date, temp, humidity?}` capped at `RDS_MAX_DAYS`, dates round-tripped as `date` objects), but as a plain-`sqlite3` repo on the shared DB.

**Files:**
- Modify: `framework/persistence/sqlite.py` (append new class + schema)
- Test: `tests/framework/test_rds_state_repo.py`

**Interfaces:**
- Consumes: `prana.config.RDS_MAX_DAYS` (int), `prana.config.DATABASE_URL` (str).
- Produces:
  - `SQLiteRDSStateRepository(db_path: str)`
  - `async def save(self, user_id: str, nighttime_temps: list[dict]) -> None` — each dict `{"date": date|str, "temp": float, "humidity": Optional[float]}`; stores newest-first, capped at `RDS_MAX_DAYS`.
  - `async def load(self, user_id: str) -> list[dict]` — returns dicts with `date` as a `datetime.date` object, `temp` float, and `humidity` only if present.

- [ ] **Step 1: Write the failing test**

Create `tests/framework/test_rds_state_repo.py`:

```python
import asyncio
from datetime import date

from framework.persistence.sqlite import SQLiteRDSStateRepository


def _run(coro):
    return asyncio.run(coro)


def test_save_then_load_roundtrips_dates_as_date_objects(tmp_path):
    db = str(tmp_path / "t.db")
    repo = SQLiteRDSStateRepository(db)
    temps = [
        {"date": date(2026, 7, 1), "temp": 31.0, "humidity": 70.0},
        {"date": date(2026, 7, 2), "temp": 32.5},
    ]
    _run(repo.save("+911", temps))
    loaded = _run(repo.load("+911"))

    assert len(loaded) == 2
    # newest-first ordering
    assert loaded[0]["date"] == date(2026, 7, 2)
    assert loaded[0]["temp"] == 32.5
    assert "humidity" not in loaded[0]  # was absent, stays absent
    assert loaded[1]["date"] == date(2026, 7, 1)
    assert loaded[1]["humidity"] == 70.0


def test_load_unknown_user_returns_empty_list(tmp_path):
    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    assert _run(repo.load("nobody")) == []


def test_save_caps_at_rds_max_days_newest_kept(tmp_path):
    from prana.config import RDS_MAX_DAYS
    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    temps = [{"date": date(2026, 6, d), "temp": 30.0 + d} for d in range(1, RDS_MAX_DAYS + 5)]
    _run(repo.save("+912", temps))
    loaded = _run(repo.load("+912"))
    assert len(loaded) == RDS_MAX_DAYS
    # the newest RDS_MAX_DAYS by date survive
    kept_dates = {t["date"] for t in loaded}
    assert date(2026, 6, RDS_MAX_DAYS + 4) in kept_dates
    assert date(2026, 6, 1) not in kept_dates


def test_save_is_idempotent_upsert(tmp_path):
    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    _run(repo.save("+913", [{"date": date(2026, 7, 1), "temp": 31.0}]))
    _run(repo.save("+913", [{"date": date(2026, 7, 2), "temp": 33.0}]))
    loaded = _run(repo.load("+913"))
    assert len(loaded) == 1
    assert loaded[0]["date"] == date(2026, 7, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/framework/test_rds_state_repo.py -v`
Expected: FAIL with `ImportError: cannot import name 'SQLiteRDSStateRepository'`.

- [ ] **Step 3: Write minimal implementation**

Append to `framework/persistence/sqlite.py` (after the `SQLiteCheckinRepository` class). Add the schema constant near the top with the other schemas:

```python
_RDS_STATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS rds_states (
    user_id TEXT PRIMARY KEY,
    nighttime_temps_json TEXT NOT NULL,
    last_updated TEXT
)
"""
```

```python
class SQLiteRDSStateRepository:
    """Stores each user's rolling window of nightly outdoor temps so RDS
    multi-night compounding survives across sessions. Shares the one DB file."""

    def __init__(self, db_path: str):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        with self._conn() as c:
            c.execute(_RDS_STATES_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def save(self, user_id: str, nighttime_temps: list) -> None:
        await asyncio.to_thread(self._save, user_id, nighttime_temps)

    def _save(self, user_id: str, nighttime_temps: list) -> None:
        from datetime import date as _date, datetime as _dt
        from prana.config import RDS_MAX_DAYS

        capped = sorted(nighttime_temps, key=lambda t: str(t["date"]), reverse=True)[:RDS_MAX_DAYS]
        serialized = []
        for t in capped:
            d = t["date"]
            if isinstance(d, (_date, _dt)):
                d = d.isoformat()
            entry = {"date": d, "temp": t["temp"]}
            if t.get("humidity") is not None:
                entry["humidity"] = t["humidity"]
            serialized.append(entry)

        with self._conn() as c:
            c.execute(
                """INSERT INTO rds_states (user_id, nighttime_temps_json, last_updated)
                   VALUES (?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     nighttime_temps_json=excluded.nighttime_temps_json,
                     last_updated=excluded.last_updated""",
                (user_id, json.dumps(serialized), datetime.now(timezone.utc).isoformat()),
            )

    async def load(self, user_id: str) -> list:
        return await asyncio.to_thread(self._load, user_id)

    def _load(self, user_id: str) -> list:
        from datetime import datetime as _dt
        with self._conn() as c:
            row = c.execute(
                "SELECT nighttime_temps_json FROM rds_states WHERE user_id=?", (user_id,)
            ).fetchone()
        if not row:
            return []
        temps = json.loads(row["nighttime_temps_json"])
        for t in temps:
            t["date"] = _dt.fromisoformat(t["date"]).date()
        return temps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/framework/test_rds_state_repo.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add framework/persistence/sqlite.py tests/framework/test_rds_state_repo.py
git commit -m "feat(persistence): SQLiteRDSStateRepository on the shared DB"
```

---

## Task 2: Risk-evaluation history repository on the framework SQLite layer

Replaces the SQLAlchemy `RiskEvaluation` model. Append-only per-user risk-score history.

**Files:**
- Modify: `framework/persistence/sqlite.py`
- Test: `tests/framework/test_risk_eval_repo.py`

**Interfaces:**
- Produces:
  - `SQLiteRiskEvalRepository(db_path: str)`
  - `async def add(self, user_id: str, *, outdoor_temp: Optional[float], outdoor_humidity: Optional[float], base_aqi: Optional[float], ndt: Optional[float], rds_mid: Optional[float], ccri: Optional[float]) -> None`
  - `async def list_for_user(self, user_id: str, limit: int = 30) -> list[dict]` — newest-first, each dict has keys `timestamp, outdoor_temp, outdoor_humidity, base_aqi, ndt, rds_mid, ccri`.

- [ ] **Step 1: Write the failing test**

Create `tests/framework/test_risk_eval_repo.py`:

```python
import asyncio

from framework.persistence.sqlite import SQLiteRiskEvalRepository


def _run(coro):
    return asyncio.run(coro)


def test_add_then_list_returns_row(tmp_path):
    repo = SQLiteRiskEvalRepository(str(tmp_path / "t.db"))
    _run(repo.add("+911", outdoor_temp=31.0, outdoor_humidity=70.0,
                  base_aqi=120.0, ndt=34.6, rds_mid=66.1, ccri=64.7))
    rows = _run(repo.list_for_user("+911"))
    assert len(rows) == 1
    r = rows[0]
    assert r["outdoor_temp"] == 31.0
    assert r["ndt"] == 34.6
    assert r["rds_mid"] == 66.1
    assert r["ccri"] == 64.7
    assert r["timestamp"]  # ISO string present


def test_list_newest_first_and_limit(tmp_path):
    repo = SQLiteRiskEvalRepository(str(tmp_path / "t.db"))
    for c in (10.0, 20.0, 30.0):
        _run(repo.add("+912", outdoor_temp=None, outdoor_humidity=None,
                      base_aqi=None, ndt=None, rds_mid=None, ccri=c))
    rows = _run(repo.list_for_user("+912", limit=2))
    assert len(rows) == 2
    assert rows[0]["ccri"] == 30.0  # newest first


def test_list_unknown_user_empty(tmp_path):
    repo = SQLiteRiskEvalRepository(str(tmp_path / "t.db"))
    assert _run(repo.list_for_user("nobody")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/framework/test_risk_eval_repo.py -v`
Expected: FAIL with `ImportError: cannot import name 'SQLiteRiskEvalRepository'`.

- [ ] **Step 3: Write minimal implementation**

Add the schema constant near the other schemas in `framework/persistence/sqlite.py`:

```python
_RISK_EVALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS risk_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    outdoor_temp REAL,
    outdoor_humidity REAL,
    base_aqi REAL,
    ndt REAL,
    rds_mid REAL,
    ccri REAL
)
"""
```

Append the class:

```python
class SQLiteRiskEvalRepository:
    """Append-only per-user risk-score history. Shares the one DB file."""

    def __init__(self, db_path: str):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        with self._conn() as c:
            c.execute(_RISK_EVALS_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def add(self, user_id: str, *, outdoor_temp, outdoor_humidity,
                  base_aqi, ndt, rds_mid, ccri) -> None:
        await asyncio.to_thread(
            self._add, user_id, outdoor_temp, outdoor_humidity, base_aqi, ndt, rds_mid, ccri
        )

    def _add(self, user_id, outdoor_temp, outdoor_humidity, base_aqi, ndt, rds_mid, ccri) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO risk_evaluations
                   (user_id, timestamp, outdoor_temp, outdoor_humidity,
                    base_aqi, ndt, rds_mid, ccri)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (user_id, datetime.now(timezone.utc).isoformat(),
                 outdoor_temp, outdoor_humidity, base_aqi, ndt, rds_mid, ccri),
            )

    async def list_for_user(self, user_id: str, limit: int = 30) -> list:
        return await asyncio.to_thread(self._list_for_user, user_id, limit)

    def _list_for_user(self, user_id: str, limit: int) -> list:
        with self._conn() as c:
            rows = c.execute(
                """SELECT timestamp, outdoor_temp, outdoor_humidity, base_aqi,
                          ndt, rds_mid, ccri
                   FROM risk_evaluations WHERE user_id=?
                   ORDER BY id DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/framework/test_risk_eval_repo.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add framework/persistence/sqlite.py tests/framework/test_risk_eval_repo.py
git commit -m "feat(persistence): SQLiteRiskEvalRepository on the shared DB"
```

---

## Task 3: Bootstrap factories for the two new repos

**Files:**
- Modify: `prana/bot/bootstrap.py`
- Test: `tests/prana/test_bootstrap_repos.py`

**Interfaces:**
- Consumes: `prana.config.DATABASE_URL`, the two classes from Tasks 1–2.
- Produces: `build_rds_repo() -> SQLiteRDSStateRepository`, `build_risk_eval_repo() -> SQLiteRiskEvalRepository`.

- [ ] **Step 1: Write the failing test**

Create `tests/prana/test_bootstrap_repos.py`:

```python
from framework.persistence.sqlite import (
    SQLiteRDSStateRepository, SQLiteRiskEvalRepository,
)
from prana.bot.bootstrap import build_rds_repo, build_risk_eval_repo


def test_build_rds_repo_returns_rds_state_repo():
    assert isinstance(build_rds_repo(), SQLiteRDSStateRepository)


def test_build_risk_eval_repo_returns_risk_eval_repo():
    assert isinstance(build_risk_eval_repo(), SQLiteRiskEvalRepository)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_bootstrap_repos.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_rds_repo'`.

- [ ] **Step 3: Write minimal implementation**

In `prana/bot/bootstrap.py`, extend the import and add two factories:

```python
from framework.persistence.sqlite import (
    SQLiteUserRepository, SQLiteCheckinRepository,
    SQLiteRDSStateRepository, SQLiteRiskEvalRepository,
)
```

```python
def build_rds_repo() -> SQLiteRDSStateRepository:
    return SQLiteRDSStateRepository(DATABASE_URL)


def build_risk_eval_repo() -> SQLiteRiskEvalRepository:
    return SQLiteRiskEvalRepository(DATABASE_URL)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_bootstrap_repos.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add prana/bot/bootstrap.py tests/prana/test_bootstrap_repos.py
git commit -m "feat(bootstrap): factories for RDS-state and risk-eval repos"
```

---

## Task 4: Restore `/register` to the approved spec (fixes pending items 1–3)

Rewrite `/register` to write through `user_repo` (framework `SQLiteUserRepository`), return `user_id == phone`, `verified=False`, and preserve `verified` on re-registration. This makes the existing `tests/prana/test_register.py` pass unmodified. The onboarding profile is stored in `UserContext.metadata["onboarding"]` (dict), exactly what `get_risk` already reads.

**Files:**
- Modify: `backend/main.py` (the `register` handler + `RegisterResponse`/imports)
- Test: `tests/prana/test_register.py` (existing — do NOT edit; it is the contract)

**Interfaces:**
- Consumes: `user_repo` (module-scope `SQLiteUserRepository` already built at `backend/main.py:31`), `framework.context.user.UserContext`, `prana.config.WHATSAPP_BOT_NUMBER`, `settings.whatsapp_sandbox_join_code`.
- Produces: `POST /register` returning `{ok, user_id (==phone), verified (False for new), whatsapp_link, sandbox_join_code}`.

- [ ] **Step 1: Confirm the target tests currently fail**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_register.py -v`
Expected: `test_register_valid_payload_returns_200_and_unverified` FAILS (currently returns a UUID + `verified=True`). Some others already pass.

- [ ] **Step 2: Rewrite the `register` handler**

In `backend/main.py`, replace the entire `register` function (currently ~L272–L311) with:

```python
@app.post("/register", response_model=RegisterResponse)
async def register(payload: RegisterRequest) -> RegisterResponse:
    """Register a phone + location + home profile through the single shared user
    repository, so the webhook and scheduler see the same record. Verification is
    completed later by the user's own inbound WhatsApp message; re-registering an
    already-verified phone must NOT reset it to unverified."""
    existing = await user_repo.get_by_phone(payload.phone)
    verified = bool(existing.metadata.get("verified")) if existing else False

    user = UserContext(
        user_id=payload.phone,
        phone=payload.phone,
        metadata={
            "lat": payload.lat,
            "lon": payload.lon,
            "location_name": payload.location_name,
            "urban_heat_offset": payload.urban_heat_offset,
            "onboarding": payload.onboarding.model_dump(),
            "verified": verified,
            "last_alert_level": existing.metadata.get("last_alert_level") if existing else None,
        },
    )
    await user_repo.upsert(user)

    return RegisterResponse(
        ok=True,
        user_id=payload.phone,
        verified=verified,
        whatsapp_link=f"https://wa.me/{WHATSAPP_BOT_NUMBER}?text=PRANA%20START",
        sandbox_join_code=settings.whatsapp_sandbox_join_code,
    )
```

Remove the now-unused SQLAlchemy import of `User`/`UserProfile` from this handler (the full import cleanup happens in Task 8; for now leave the module-level imports, they still resolve).

- [ ] **Step 3: Run the register tests**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_register.py -v`
Expected: all 6 tests PASS, including `test_register_valid_payload_returns_200_and_unverified`, `test_register_saves_user_with_onboarding_metadata`, and `test_register_twice_preserves_verified_true`.

- [ ] **Step 4: Run the webhook regression tests**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_whatsapp_webhook.py -v`
Expected: PASS — the webhook now finds registered users in the same repo.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "fix(register): restore approved spec — shared repo, verified=False, user_id=phone"
```

---

## Task 5: `/risk/current` uses the framework repos (drop SQLAlchemy sessions)

Rewrite `/risk/current` so profile lookup, RDS-history seed, and result persistence all go through the framework repos instead of a SQLAlchemy `SessionLocal`. Behavior preserved: when `user_id` is given, load that user's onboarding + RDS history, personalize from check-ins, run the pipeline, persist the new RDS window and a risk-eval row.

**Files:**
- Modify: `backend/main.py` (`calculate_current_risk`, `_run_prana_pipeline`, module-scope repo singletons)
- Test: `tests/prana/test_risk_current_persistence.py`

**Interfaces:**
- Consumes: `user_repo`, `checkin_repo` (existing singletons), plus new module-scope `rds_repo = build_rds_repo()` and `risk_eval_repo = build_risk_eval_repo()`.
- Produces: `/risk/current` behavior unchanged from the client's perspective; side effects now land in `prana.db` tables `rds_states` and `risk_evaluations`.

- [ ] **Step 1: Write the failing test**

Create `tests/prana/test_risk_current_persistence.py`. It monkeypatches the pipeline so no live network call happens, and asserts persistence side-effects land in the framework repos:

```python
import asyncio

from fastapi.testclient import TestClient

import backend.main as main
from backend.main import app


def _register(client, phone="+919900010001"):
    return client.post("/register", json={
        "phone": phone, "location_name": "Chennai",
        "lat": 13.08, "lon": 80.27, "urban_heat_offset": None,
        "onboarding": {"ac": True, "roof_material": "concrete", "floor_level": "top"},
    })


def test_risk_current_persists_rds_window_and_eval(monkeypatch, tmp_path):
    from datetime import date

    def fake_pipeline(payload, personalization=None, historical_temps=None):
        result = {
            "raw_temp": 31.0, "raw_humidity": 70.0,
            "aqi": {"base_aqi": 120.0}, "ndt": 34.6,
            "rds": {"rds_mid": 66.1}, "ccri": 64.7,
            "rds_historical_temps": [{"date": date(2026, 7, 2), "temp": 31.0}],
        }
        return result, "log"

    monkeypatch.setattr(main, "_run_prana_pipeline", fake_pipeline)

    client = TestClient(app)
    phone = "+919900010002"
    _register(client, phone)

    resp = client.post("/risk/current", json={
        "lat": 13.08, "lon": 80.27, "location_name": "Chennai",
        "user_id": phone,
    })
    assert resp.status_code == 200

    async def loads():
        window = await main.rds_repo.load(phone)
        evals = await main.risk_eval_repo.list_for_user(phone)
        return window, evals

    window, evals = asyncio.run(loads())
    assert len(window) == 1
    assert window[0]["temp"] == 31.0
    assert len(evals) == 1
    assert evals[0]["ccri"] == 64.7
    assert evals[0]["rds_mid"] == 66.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_risk_current_persistence.py -v`
Expected: FAIL — `main` has no `rds_repo` / `risk_eval_repo`, and `/risk/current` still uses SQLAlchemy.

- [ ] **Step 3: Add repo singletons and rewrite the handler**

In `backend/main.py`, after the existing `user_repo`/`checkin_repo` singletons (near L31), add:

```python
from prana.bot.bootstrap import (
    build_repo, build_checkin_repo, build_rds_repo, build_risk_eval_repo, settings,
)  # replace the existing bootstrap import line

rds_repo = build_rds_repo()
risk_eval_repo = build_risk_eval_repo()
```

Replace the body of `calculate_current_risk` (currently ~L188–L250) with:

```python
@app.post("/risk/current", response_model=RiskResponse)
async def calculate_current_risk(payload: RiskRequest) -> RiskResponse:
    """Calculate current PRANA climate risk. When user_id is supplied, seed the
    RDS ledger + check-in personalization for that user and persist the result."""
    personalization = None
    onb_data = payload.onboarding_data or {}
    loc_name = payload.location_name
    historical_temps = []

    if payload.user_id:
        user = await user_repo.get_by_phone(payload.user_id)
        if user and user.metadata.get("onboarding"):
            onb_data = user.metadata["onboarding"]
            loc_name = user.metadata.get("location_name") or loc_name

        checkins = await checkin_repo.list_for_user(payload.user_id, limit=30)
        if checkins:
            prior_mean = _onboarding_prior_mean(onb_data, loc_name)
            prior_sd = _onboarding_prior_sd(onb_data)
            post = personalize_offset(prior_mean, prior_sd, checkins, RDS_NIGHTTIME_THRESHOLD)
            personalization = {"offset": post.mean, "band": post.sd, "n_checkins": post.n_checkins}

        historical_temps = await rds_repo.load(payload.user_id)

    result, logs = await run_in_threadpool(
        _run_prana_pipeline, payload, personalization, historical_temps
    )
    if not result:
        raise HTTPException(status_code=502, detail="Risk calculation failed.")

    if payload.user_id:
        await risk_eval_repo.add(
            payload.user_id,
            outdoor_temp=result.get("raw_temp"),
            outdoor_humidity=result.get("raw_humidity"),
            base_aqi=(result.get("aqi") or {}).get("base_aqi"),
            ndt=result.get("ndt"),
            rds_mid=(result.get("rds") or {}).get("rds_mid"),
            ccri=result.get("ccri"),
        )
        await rds_repo.save(payload.user_id, result.get("rds_historical_temps", []))

    return RiskResponse(result=_serialize_result(result), calculation_log=logs)
```

Note: `_run_prana_pipeline`, `_onboarding_prior_mean`, `_onboarding_prior_sd`, and the `RDS_NIGHTTIME_THRESHOLD`/`personalize_offset` imports already exist and are unchanged.

- [ ] **Step 4: Run the test**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_risk_current_persistence.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/prana/test_risk_current_persistence.py
git commit -m "refactor(risk): /risk/current uses framework repos, drops SQLAlchemy session"
```

---

## Task 6: Scheduler scores with RDS history + personalization (fixes pending item 4)

`get_risk` currently ignores stored history. Give it optional `historical_temps` and `personalization` params (default `None` → identical to today's behavior for the agent), and have the scheduler load them per user before scoring.

**Files:**
- Modify: `prana/ai_tools/risk.py` (`get_risk` signature + seeding)
- Modify: `prana/scheduler.py` (`_score_user` loads history/personalization)
- Test: `tests/prana/test_scheduler_scoring.py`

**Interfaces:**
- Consumes: `SQLiteRDSStateRepository.load`, `SQLiteCheckinRepository.list_for_user`, `personalize_offset`.
- Produces:
  - `get_risk(*, ctx, historical_temps: Optional[list] = None, personalization: Optional[dict] = None) -> dict` — when `historical_temps` given, seeds `PRANASystem.rds_calculator.nighttime_temps`; when `personalization` given, passes it to `update_all`.
  - Scheduler's per-user scoring now async-loads both before calling `get_risk`.

- [ ] **Step 1: Write the failing test**

Create `tests/prana/test_scheduler_scoring.py`:

```python
from datetime import date

from framework.context.user import UserContext
from prana.ai_tools import risk as risk_mod


def test_get_risk_seeds_historical_temps(monkeypatch):
    captured = {}

    class FakeSystem:
        def __init__(self, **kwargs):
            self.rds_calculator = type("RC", (), {"nighttime_temps": []})()

        def update_all(self, lat, lon, personalization=None):
            captured["seeded"] = list(self.rds_calculator.nighttime_temps)
            captured["personalization"] = personalization
            return {
                "ccri": 50.0, "risk_level": "HIGH", "ndt": 30.0,
                "rds": {"rds_mid": 40.0, "consecutive_nights": 3},
                "alert_message": "x", "timestamp": "2026-07-03T00:00:00",
            }

    monkeypatch.setattr(risk_mod, "PRANASystem", FakeSystem)

    ctx = UserContext(user_id="+911", phone="+911",
                      metadata={"lat": 13.0, "lon": 80.0, "location_name": "Chennai"})
    hist = [{"date": date(2026, 7, 1), "temp": 33.0}]
    out = risk_mod.get_risk(ctx=ctx, historical_temps=hist,
                            personalization={"offset": -3.0, "band": 2.0, "n_checkins": 5})

    assert out["risk_level"] == "HIGH"
    assert captured["seeded"] == hist
    assert captured["personalization"] == {"offset": -3.0, "band": 2.0, "n_checkins": 5}


def test_get_risk_without_history_matches_old_behavior(monkeypatch):
    class FakeSystem:
        def __init__(self, **kwargs):
            self.rds_calculator = type("RC", (), {"nighttime_temps": []})()

        def update_all(self, lat, lon, personalization=None):
            return {
                "ccri": 10.0, "risk_level": "SAFE", "ndt": 20.0,
                "rds": {"rds_mid": 0.0, "consecutive_nights": 0},
                "alert_message": "ok", "timestamp": "2026-07-03T00:00:00",
            }

    monkeypatch.setattr(risk_mod, "PRANASystem", FakeSystem)
    ctx = UserContext(user_id="+912", phone="+912",
                      metadata={"lat": 1.0, "lon": 2.0})
    out = risk_mod.get_risk(ctx=ctx)
    assert out["risk_level"] == "SAFE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_scheduler_scoring.py -v`
Expected: FAIL — `get_risk` does not accept `historical_temps`.

- [ ] **Step 3: Update `get_risk`**

In `prana/ai_tools/risk.py`, replace the `get_risk` function with:

```python
def get_risk(*, ctx: UserContext, historical_temps=None, personalization=None) -> dict:
    meta = ctx.metadata
    system = PRANASystem(
        api_key=OPENWEATHER_API_KEY,
        location_name=meta.get("location_name", "Current location"),
        urban_heat_offset=meta.get("urban_heat_offset"),
        openaq_api_key=OPENAQ_API_KEY,
        onboarding_data=meta.get("onboarding"),
    )
    if historical_temps:
        system.rds_calculator.nighttime_temps = historical_temps

    result = system.update_all(meta["lat"], meta["lon"], personalization=personalization)
    if not result:
        return {"error": "Risk data is temporarily unavailable."}
    rds = result["rds"]
    ts = result["timestamp"]
    return {
        "ccri": result["ccri"],
        "risk_level": result["risk_level"],
        "ndt": result["ndt"],
        "rds_mid": rds["rds_mid"],
        "consecutive_nights": rds["consecutive_nights"],
        "alert_message": result["alert_message"],
        "as_of": ts.isoformat() if hasattr(ts, "isoformat") else ts,
    }
```

Note: verify `PRANASystem.update_all` accepts `personalization=` (it does — `backend/main.py` already calls it with that kwarg). The `risk_tool` definition below `get_risk` is unchanged (its `fn=get_risk` still works; the agent calls it with only `ctx`).

- [ ] **Step 4: Run the risk test**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_scheduler_scoring.py -v`
Expected: PASS.

- [ ] **Step 5: Wire the scheduler to load history + personalization**

In `prana/scheduler.py`, replace the imports and `_score_user`/`_cycle_once` region with:

```python
import asyncio
import logging

from prana.alerts import run_alert_cycle
from prana.ai_tools.risk import get_risk
from prana.bot.bootstrap import (
    build_messaging, build_repo, build_checkin_repo, build_rds_repo,
)
from prana.config import UPDATE_INTERVAL, RDS_NIGHTTIME_THRESHOLD
from prana.personalization import personalize_offset
from prana.rds_calculator import RDSCalculator
from prana.prana_system import PRANASystem

logger = logging.getLogger(__name__)


async def _cycle_once() -> int:
    repo = build_repo()
    messaging = build_messaging()
    rds_repo = build_rds_repo()
    checkin_repo = build_checkin_repo()

    async def score(user):
        historical = await rds_repo.load(user.user_id)
        personalization = None
        checkins = await checkin_repo.list_for_user(user.user_id, limit=30)
        onb = user.metadata.get("onboarding") or {}
        if checkins:
            dummy = PRANASystem(location_name=user.metadata.get("location_name") or "default")
            prior_mean = RDSCalculator.compute_onboarding_temp_offset(onb, climate_zone=dummy.climate_zone)
            prior_sd = RDSCalculator.compute_band_width(onb)
            post = personalize_offset(prior_mean, prior_sd, checkins, RDS_NIGHTTIME_THRESHOLD)
            personalization = {"offset": post.mean, "band": post.sd, "n_checkins": post.n_checkins}
        # get_risk is sync (blocking network); run it off the event loop.
        return await asyncio.to_thread(
            get_risk, ctx=user, historical_temps=historical, personalization=personalization
        )

    return await run_alert_cycle(repo, messaging, score)
```

Change `run_alert_cycle`'s `risk_fn` call site in `prana/alerts.py` to `await` the risk function (Task 7 covers alerts.py; if executing strictly in order, make the minimal change here: in `alerts.py`, `check_and_alert_user` currently calls `risk = risk_fn(user)` synchronously — change to `risk = await risk_fn(user)` and adjust the type hint `RiskFn = Callable[[UserContext], Awaitable[dict]]`). Add a test-covering step in Task 7.

- [ ] **Step 6: Run scheduler + full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_scheduler_scoring.py tests/prana/ -v`
Expected: PASS (scheduler scoring green; alert tests may need Task 7's async change — run Task 7 next).

- [ ] **Step 7: Commit**

```bash
git add prana/ai_tools/risk.py prana/scheduler.py
git commit -m "feat(scheduler): seed RDS history + personalization into proactive scoring"
```

---

## Task 7: Alert cadence — daily cap + quiet hours (fixes pending item 5)

Add a per-user daily cap (max one alert per 24h) and a quiet-hours window on top of the existing state-change logic. Make `run_alert_cycle`/`check_and_alert_user` `await` the (now async) risk function.

**Files:**
- Modify: `prana/config.py` (cadence constants)
- Modify: `prana/alerts.py` (async risk_fn + cadence gate)
- Test: `tests/prana/test_alert_cadence.py`

**Interfaces:**
- Consumes: `user.metadata["last_alert_at"]` (ISO str, new), `user.metadata["last_alert_level"]` (existing).
- Produces: `check_and_alert_user(user, risk_fn, repo, messaging, now=None) -> bool` where `risk_fn` is `async`, and an alert fires only if level is risky AND changed AND ≥ `ALERT_MIN_HOURS_BETWEEN` since `last_alert_at` AND `now` is outside quiet hours.

- [ ] **Step 1: Add config constants**

In `prana/config.py`, add:

```python
# --- Proactive alert cadence ---
ALERT_MIN_HOURS_BETWEEN = 24          # at most one proactive alert per user per day
ALERT_QUIET_HOURS_START = 22          # local hour [0-23]; no alerts at/after this
ALERT_QUIET_HOURS_END = 7             # local hour [0-23]; no alerts before this
```

- [ ] **Step 2: Write the failing test**

Create `tests/prana/test_alert_cadence.py`:

```python
import asyncio
from datetime import datetime

from framework.context.user import UserContext
from prana.alerts import check_and_alert_user


class FakeMessaging:
    def __init__(self):
        self.sent = []

    async def send(self, *, channel, recipient, body):
        self.sent.append((recipient, body))


class FakeRepo:
    async def upsert(self, user):
        pass


def _run(coro):
    return asyncio.run(coro)


async def _risk_high(user):
    return {"risk_level": "HIGH", "alert_message": "hot"}


def _user(**meta):
    m = {"verified": True}
    m.update(meta)
    return UserContext(user_id="+911", phone="+911", metadata=m)


def test_fires_when_risky_changed_daytime_and_no_recent_alert():
    msg = FakeMessaging()
    user = _user()
    sent = _run(check_and_alert_user(user, _risk_high, FakeRepo(), msg,
                                     now=datetime(2026, 7, 3, 12, 0)))
    assert sent is True
    assert len(msg.sent) == 1
    assert user.metadata["last_alert_level"] == "HIGH"
    assert user.metadata["last_alert_at"] is not None


def test_suppressed_during_quiet_hours():
    msg = FakeMessaging()
    user = _user()
    sent = _run(check_and_alert_user(user, _risk_high, FakeRepo(), msg,
                                     now=datetime(2026, 7, 3, 23, 0)))
    assert sent is False
    assert msg.sent == []


def test_suppressed_when_alerted_within_24h():
    msg = FakeMessaging()
    user = _user(last_alert_level="SAFE",
                 last_alert_at=datetime(2026, 7, 3, 6, 0).isoformat())
    sent = _run(check_and_alert_user(user, _risk_high, FakeRepo(), msg,
                                     now=datetime(2026, 7, 3, 12, 0)))
    assert sent is False


def test_suppressed_when_level_unchanged():
    msg = FakeMessaging()
    user = _user(last_alert_level="HIGH",
                 last_alert_at=datetime(2026, 7, 1, 12, 0).isoformat())
    sent = _run(check_and_alert_user(user, _risk_high, FakeRepo(), msg,
                                     now=datetime(2026, 7, 3, 12, 0)))
    assert sent is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_alert_cadence.py -v`
Expected: FAIL — `check_and_alert_user` is sync and has no cadence/quiet-hours logic or `now` param.

- [ ] **Step 4: Rewrite `alerts.py`**

Replace `prana/alerts.py` in full:

```python
"""Proactive climate-risk alerting.

An alert fires only when ALL hold:
  - risk level is risky (HIGH / CRITICAL / COMPOUND EMERGENCY),
  - the level CHANGED since the last recorded level (state-change semantics),
  - it has been at least ALERT_MIN_HOURS_BETWEEN since the last alert (daily cap),
  - the current local time is outside the quiet-hours window.
Non-risky levels are still recorded so a drop to SAFE then a rise re-alerts.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

from framework.context.user import UserContext
from framework.messaging.registry import MessagingRegistry
from prana.config import (
    ALERT_MIN_HOURS_BETWEEN, ALERT_QUIET_HOURS_START, ALERT_QUIET_HOURS_END,
)

logger = logging.getLogger(__name__)

RISKY_LEVELS = frozenset({"HIGH", "CRITICAL", "COMPOUND EMERGENCY"})

RiskFn = Callable[[UserContext], Awaitable[dict]]


def _in_quiet_hours(now: datetime) -> bool:
    """Quiet hours wrap past midnight (e.g. 22:00–07:00)."""
    h = now.hour
    if ALERT_QUIET_HOURS_START <= ALERT_QUIET_HOURS_END:
        return ALERT_QUIET_HOURS_START <= h < ALERT_QUIET_HOURS_END
    return h >= ALERT_QUIET_HOURS_START or h < ALERT_QUIET_HOURS_END


def _hours_since(iso_ts: Optional[str], now: datetime) -> float:
    if not iso_ts:
        return float("inf")
    try:
        return (now - datetime.fromisoformat(iso_ts)).total_seconds() / 3600.0
    except ValueError:
        return float("inf")


async def check_and_alert_user(
    user: UserContext,
    risk_fn: RiskFn,
    repo,
    messaging: MessagingRegistry,
    now: Optional[datetime] = None,
) -> bool:
    """Score one user and send a WhatsApp alert if their risk turned dangerous,
    respecting the daily cap and quiet hours. Returns True iff an alert was sent."""
    now = now or datetime.now()
    try:
        risk = await risk_fn(user)
    except Exception:  # noqa: BLE001 - one user's failure must not stop the cycle
        logger.exception("Risk scoring failed for %s", user.phone)
        return False

    level = risk.get("risk_level")
    if risk.get("error") or level is None:
        return False

    last = user.metadata.get("last_alert_level")

    if last != level:
        user.metadata["last_alert_level"] = level
        await repo.upsert(user)

    if level not in RISKY_LEVELS or level == last:
        return False
    if _in_quiet_hours(now):
        return False
    if _hours_since(user.metadata.get("last_alert_at"), now) < ALERT_MIN_HOURS_BETWEEN:
        return False

    body = risk.get("alert_message") or f"PRANA alert: your climate risk is {level}."
    await messaging.send(channel="whatsapp", recipient=user.phone, body=body)
    user.metadata["last_alert_at"] = now.isoformat()
    await repo.upsert(user)
    logger.info("Sent %s alert to %s", level, user.phone)
    return True


async def run_alert_cycle(
    repo,
    messaging: MessagingRegistry,
    risk_fn: RiskFn,
) -> int:
    """Score every verified user and alert those whose risk turned dangerous."""
    users = await repo.list_all()
    sent = 0
    for user in users:
        if not user.metadata.get("verified"):
            continue
        if await check_and_alert_user(user, risk_fn, repo, messaging):
            sent += 1
    logger.info("Alert cycle complete: %d alert(s) sent across %d users", sent, len(users))
    return sent
```

Persist `last_alert_at`: add it to the framework repo. In `framework/persistence/sqlite.py`, add to the migration loop in `SQLiteUserRepository.__init__`:

```python
"ALTER TABLE users ADD COLUMN last_alert_at TEXT",
```

Add to `_to_user`'s metadata dict:

```python
"last_alert_at": row["last_alert_at"] if "last_alert_at" in row.keys() else None,
```

And extend `_upsert`'s column list, placeholders, `ON CONFLICT` set, and values tuple to include `last_alert_at=excluded.last_alert_at` / `m.get("last_alert_at")` (mirror exactly how `last_alert_level` is already threaded).

- [ ] **Step 5: Run the cadence tests + webhook/scheduler regression**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_alert_cadence.py tests/prana/test_scheduler_scoring.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add prana/config.py prana/alerts.py framework/persistence/sqlite.py tests/prana/test_alert_cadence.py
git commit -m "feat(alerts): daily cap + quiet hours cadence; async risk_fn"
```

---

## Task 8: Delete the SQLAlchemy layer and its dependency (completes item 1 cleanup)

Nothing runtime depends on `prana/database.py` / `prana/models.py` after Tasks 4–5 (only `backend/llm.py`'s import — verify — and two throwaway scripts). Remove them, remove the `sqlalchemy` requirement, and delete the stale scripts and second DB file.

**Files:**
- Delete: `prana/database.py`, `prana/models.py`, `scripts/ai_agent_verifier.py`, `scripts/test_persistence.py`
- Modify: `backend/main.py` (remove SQLAlchemy imports), `backend/llm.py` (remove any SQLAlchemy import if present), `requirements.txt`
- Test: full suite

- [ ] **Step 1: Find every remaining reference**

Run: `.venv/Scripts/python.exe - <<'PY'`... or simply:
`grep -rn "prana.database\|prana.models\|sqlalchemy\|SessionLocal\|init_db\|save_user_rds_state\|load_user_rds_state\|RiskEvaluation\|RDSState\|UserProfile" --include=*.py prana backend tests`
Expected remaining hits: only `backend/main.py` import lines (L24–L25), `backend/llm.py`, and the two scripts. Note each.

- [ ] **Step 2: Remove imports from `backend/main.py`**

Delete these lines from `backend/main.py`:

```python
from prana.database import init_db, SessionLocal, save_user_rds_state, load_user_rds_state  # noqa: E402
from prana.models import User, UserProfile, RiskEvaluation  # noqa: E402
```

In the startup handler, remove the `init_db()` call (the framework repos create their own tables on construction, which already happened when the module-scope singletons were built). Replace the deprecated `@app.on_event("startup")`/`@app.on_event("shutdown")` pair with a lifespan handler (this also fixes pending item 10 for the app events):

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("DISABLE_ALERT_SCHEDULER") != "1":
        _scheduler.start()
    yield
    await _scheduler.stop()
```

and pass `lifespan=lifespan` to the `FastAPI(...)` constructor, deleting the two `@app.on_event` functions. Note: `_scheduler = AlertScheduler()` must be defined *above* `lifespan`; move the `FastAPI(...)` construction to after `_scheduler` is defined, or define `_scheduler` before the app. Keep imports ordered.

- [ ] **Step 3: Migrate `backend/llm.py`'s profile-override block to the framework user repo**

`backend/llm.py` (~L122–L138) is NOT unused — it applies LLM-extracted `profile_updates` (`floor_level`, `fan`, `windows_open`, `ac`) into the SQLAlchemy `UserProfile`. Under the unified design, onboarding lives in `UserContext.metadata["onboarding"]` in the framework user repo. Replace the `--- DYNAMIC PROFILE OVERRIDE ---` block with a repo-based update.

First write a failing test, `tests/prana/test_llm_profile_override.py`:

```python
import asyncio

from framework.context.user import UserContext
from prana.bot.bootstrap import build_repo
from backend.llm import apply_profile_updates  # new helper


def test_apply_profile_updates_merges_into_onboarding(tmp_path, monkeypatch):
    import prana.config as cfg
    db = f"sqlite:///{tmp_path/'t.db'}"
    monkeypatch.setattr(cfg, "DATABASE_URL", db)
    repo = build_repo()

    async def seed():
        await repo.upsert(UserContext(
            user_id="+911", phone="+911",
            metadata={"onboarding": {"ac": False, "roof_material": "tin",
                                     "floor_level": "ground", "fan": False,
                                     "windows_open": False, "occupants": 1},
                      "verified": True}))

    asyncio.run(seed())
    asyncio.run(apply_profile_updates(repo, "+911",
                                      {"floor_level": "top", "ac": True}))

    async def read():
        return await repo.get_by_phone("+911")

    user = asyncio.run(read())
    assert user.metadata["onboarding"]["floor_level"] == "top"
    assert user.metadata["onboarding"]["ac"] is True
    assert user.metadata["onboarding"]["roof_material"] == "tin"  # untouched
```

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_llm_profile_override.py -v` → FAIL (`apply_profile_updates` undefined).

Add the helper to `backend/llm.py` (module level, near the class) and remove the SQLAlchemy import block:

```python
async def apply_profile_updates(user_repo, user_id: str, updates: dict) -> None:
    """Merge LLM-extracted onboarding fields into the user's stored profile."""
    user = await user_repo.get_by_phone(user_id)
    if not user:
        return
    onb = dict(user.metadata.get("onboarding") or {})
    for key in ("floor_level", "fan", "windows_open", "ac"):
        if key in updates:
            onb[key] = updates[key]
    user.metadata["onboarding"] = onb
    await user_repo.upsert(user)
```

Then replace the old `if user_id and result.get("profile_updates"):` SQLAlchemy block. Because the surrounding method may be sync, guard the call: if the LLM method is synchronous, dispatch via `asyncio.run(apply_profile_updates(build_repo(), user_id, result["profile_updates"]))` (import `build_repo` from `prana.bot.bootstrap` and `asyncio` at top of llm.py); if it is already async, `await` it directly. Read the enclosing method's `def`/`async def` before choosing.

Run the test again → PASS. Then this module no longer imports `prana.database`/`prana.models`.

- [ ] **Step 4: Delete the dead modules, scripts, and second DB**

```bash
git rm prana/database.py prana/models.py scripts/ai_agent_verifier.py scripts/test_persistence.py
rm -f data/prana_persistence.db
```

- [ ] **Step 5: Remove the sqlalchemy dependency**

Edit `requirements.txt`: delete the `sqlalchemy>=2.0.0` line. Edit `pyproject.toml`: remove `sqlalchemy` if it appears in `dependencies` (it may not — check).

- [ ] **Step 6: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: no import errors; `tests/prana/test_register.py`, `test_risk_current_persistence.py`, `test_scheduler_scoring.py`, `test_alert_cadence.py` all green. Only the research test (Task 9) may still fail.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(persistence): delete SQLAlchemy layer + dependency; lifespan events; single DB"
```

---

## Task 9: Fix the research pipeline `floor_level` mapping (fixes item 6)

`tests/research/test_run_pipeline.py::test_run_site_produces_canonical_rows` fails: `floor_level` `"top"` maps to `"other"`. Fix the South Asia adapter's value mapping.

**Files:**
- Modify: `research/indoor_heat/adapters/south_asia/adapter.py`
- Test: `tests/research/test_run_pipeline.py` (existing)

- [ ] **Step 1: Reproduce the failure**

Run: `.venv/Scripts/python.exe -m pytest tests/research/test_run_pipeline.py::test_run_site_produces_canonical_rows -v`
Expected: FAIL `assert 'other' == 'top'` at line 37.

- [ ] **Step 2: Locate the mapping**

Run: `grep -n "floor_level\|top\|middle\|ground\|other" research/indoor_heat/adapters/south_asia/adapter.py`
Identify the dict/branch that normalizes floor level. The bug is a missing/incorrect `"top"` case (it falls through to the `"other"` default).

- [ ] **Step 3: Fix the mapping**

In `research/indoor_heat/adapters/south_asia/adapter.py`, ensure the floor-level normalizer maps the raw source value for a top floor to `"top"` (mirror the existing `"ground"`/`"middle"` handling). Concretely, the mapping must satisfy: a top-floor raw value → `"top"`, not `"other"`. (Read the surrounding cases and add the missing key so it matches the canonical vocabulary `ground | middle | top | other`.)

- [ ] **Step 4: Run the test**

Run: `.venv/Scripts/python.exe -m pytest tests/research/test_run_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/indoor_heat/adapters/south_asia/adapter.py
git commit -m "fix(research): map top-floor to 'top' in South Asia adapter"
```

---

## Task 10: Rate limiter hardening + remaining deprecations (items 7, 10)

Bound the in-memory rate limiter so idle client IPs are evicted (stop the slow leak), and clear the remaining `datetime.utcnow()` deprecations in backend code. CORS default (`*`) and "no Alembic" (item 8, 9) are intentionally left as documented laptop-MVP limitations — recorded in a short note, not changed.

**Files:**
- Modify: `backend/main.py` (rate-limit eviction, `datetime.utcnow()` → `datetime.now(timezone.utc)`)
- Modify: `README.md` (document the two accepted limitations)
- Test: `tests/prana/test_rate_limit.py`

**Interfaces:**
- Produces: rate-limit middleware that evicts IPs whose entire window has expired, so `_window_store` does not grow unbounded.

- [ ] **Step 1: Write the failing test**

Create `tests/prana/test_rate_limit.py`:

```python
import backend.main as main


def test_expired_ip_entries_are_evicted(monkeypatch):
    # Simulate an IP that made requests over a minute ago, then time advances.
    main._window_store.clear()
    fake_now = [1000.0]
    monkeypatch.setattr(main.time, "time", lambda: fake_now[0])

    # Directly exercise the eviction helper the middleware uses.
    main._window_store["1.2.3.4"] = [900.0, 905.0]  # both older than 60s at t=1000
    main._evict_stale_windows(now=1000.0)
    assert "1.2.3.4" not in main._window_store
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/prana/test_rate_limit.py -v`
Expected: FAIL — `_evict_stale_windows` does not exist.

- [ ] **Step 3: Add eviction and call it from the middleware**

In `backend/main.py`, add near the rate-limit state:

```python
def _evict_stale_windows(now: float) -> None:
    """Drop client IPs whose entire request window has expired, so the
    in-memory store does not grow unbounded on a long-running process."""
    cutoff = now - 60
    stale = [ip for ip, times in _window_store.items() if not times or times[-1] <= cutoff]
    for ip in stale:
        del _window_store[ip]
```

In `rate_limit_middleware`, after computing `now`, call `_evict_stale_windows(now)` before the per-IP window logic. Keep the existing per-request trimming.

- [ ] **Step 4: Clear `datetime.utcnow()` in backend**

Run: `grep -rn "utcnow" backend prana`
Replace each `datetime.utcnow()` with `datetime.now(timezone.utc)` (add `from datetime import timezone` where needed). In `record_checkin`, `datetime.utcnow().date().isoformat()` becomes `datetime.now(timezone.utc).date().isoformat()`.

- [ ] **Step 5: Document accepted limitations**

Append to `README.md` under "Current Status" a short subsection:

```markdown
### Known MVP limitations (single-laptop scope)

- **CORS** defaults to `*` for local development. Restrict `CORS_ORIGINS` before any network-exposed deployment.
- **Rate limiting** is in-memory and per-process (fine for one local Uvicorn worker; not shared across workers).
- **Schema migrations** are handled by idempotent `CREATE TABLE IF NOT EXISTS` + guarded `ALTER TABLE` in the SQLite repositories; there is no Alembic. Adequate for the single local SQLite file.
```

- [ ] **Step 6: Run the rate-limit test + full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all green (0 failed).

- [ ] **Step 7: Commit**

```bash
git add backend/main.py README.md tests/prana/test_rate_limit.py
git commit -m "fix(api): evict stale rate-limit windows; clear utcnow deprecations; document MVP limits"
```

---

## Final verification (run after all tasks)

- [ ] Full suite green:

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `0 failed` (was 2 failed at baseline; the two target failures — `test_register` and the research pipeline — are now green, plus the new tests).

- [ ] App boots and single DB is used:

Run: `.venv/Scripts/python.exe -c "import backend.main; print('import ok')"`
Expected: `import ok`, no SQLAlchemy import error.

Run: `.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000` (Ctrl-C after startup logs)
Expected: startup logs show the scheduler starting; only `prana.db` is created/touched (no `prana_persistence.db`).

- [ ] End-to-end sanity (no live keys needed for the register→lookup path):

Register a phone via `POST /register`, then confirm the webhook path would find it — covered by `tests/prana/test_register.py::test_register_saves_user_with_onboarding_metadata` and `test_whatsapp_webhook.py`.

---

## Spec-coverage self-check

| Pending item | Task(s) |
|---|---|
| 1. Two DBs → one source of truth | 1, 2, 3, 4, 5, 8 |
| 2. `/register` `verified=True` hardcoded | 4 |
| 3. `user_id` UUID vs phone | 4 |
| 4. Scheduler no RDS history/personalization | 6 |
| 5. Alert cadence (daily cap + quiet hours) | 7 |
| 6. Failing research test (`floor_level`) | 9 |
| 7. Rate-limiter unbounded growth | 10 |
| 8. CORS `*` | 10 (documented, intentionally not changed) |
| 9. No migrations | 10 (documented; SQLite `IF NOT EXISTS`/`ALTER` accepted) |
| 10. Deprecated `@app.on_event` / `datetime.utcnow()` | 8 (on_event→lifespan), 10 (utcnow) |
