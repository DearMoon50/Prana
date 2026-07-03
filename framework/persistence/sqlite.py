from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone

from framework.context.user import UserContext

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    phone TEXT,
    location_name TEXT,
    lat REAL,
    lon REAL,
    urban_heat_offset REAL,
    onboarding_json TEXT,
    role TEXT,
    locale TEXT,
    created_at TEXT,
    verified INTEGER DEFAULT 0
)
"""

_CHECKINS_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    checkin_date TEXT NOT NULL,
    sleep_quality TEXT,
    outdoor_temp REAL,
    humidity REAL,
    created_at TEXT,
    UNIQUE(user_id, checkin_date)
)
"""

_RDS_STATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS rds_states (
    user_id TEXT PRIMARY KEY,
    nighttime_temps_json TEXT NOT NULL,
    last_updated TEXT
)
"""

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

_HOUSEHOLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS household_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    tag TEXT NOT NULL,
    outdoor_worker INTEGER DEFAULT 0,
    created_at TEXT
)
"""


class SQLiteUserRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        with self._conn() as c:
            c.execute(_SCHEMA)
            for ddl in (
                "ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN last_alert_level TEXT",
                "ALTER TABLE users ADD COLUMN last_alert_at TEXT",
            ):
                try:
                    c.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # column already exists (fresh DB or prior migration)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency (multiple readers, one writer)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @staticmethod
    def _to_user(row: sqlite3.Row) -> UserContext:
        return UserContext(
            user_id=row["user_id"],
            phone=row["phone"],
            role=row["role"] or "user",
            locale=row["locale"] or "en",
            metadata={
                "lat": row["lat"],
                "lon": row["lon"],
                "location_name": row["location_name"],
                "urban_heat_offset": row["urban_heat_offset"],
                "onboarding": json.loads(row["onboarding_json"]) if row["onboarding_json"] else None,
                "verified": bool(row["verified"]) if row["verified"] is not None else False,
                "last_alert_level": (
                    row["last_alert_level"] if "last_alert_level" in row.keys() else None
                ),
                "last_alert_at": (
                    row["last_alert_at"] if "last_alert_at" in row.keys() else None
                ),
            },
        )

    async def get_by_phone(self, phone: str) -> UserContext | None:
        return await asyncio.to_thread(self._query, "phone", phone)

    async def get(self, user_id: str) -> UserContext | None:
        return await asyncio.to_thread(self._query, "user_id", user_id)

    def _query(self, column: str, value: str) -> UserContext | None:
        with self._conn() as c:
            row = c.execute(f"SELECT * FROM users WHERE {column}=?", (value,)).fetchone()
        return self._to_user(row) if row else None

    async def upsert(self, user: UserContext) -> None:
        await asyncio.to_thread(self._upsert, user)

    def _upsert(self, user: UserContext) -> None:
        m = user.metadata
        with self._conn() as c:
            c.execute(
                """INSERT INTO users
                   (user_id, phone, location_name, lat, lon, urban_heat_offset,
                    onboarding_json, role, locale, created_at, verified, last_alert_level,
                    last_alert_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     phone=excluded.phone, location_name=excluded.location_name,
                     lat=excluded.lat, lon=excluded.lon,
                     urban_heat_offset=excluded.urban_heat_offset,
                     onboarding_json=excluded.onboarding_json,
                     role=excluded.role, locale=excluded.locale,
                     verified=excluded.verified,
                     last_alert_level=excluded.last_alert_level,
                     last_alert_at=excluded.last_alert_at""",
                (user.user_id, user.phone, m.get("location_name"), m.get("lat"), m.get("lon"),
                 m.get("urban_heat_offset"),
                 json.dumps(m.get("onboarding")) if m.get("onboarding") is not None else None,
                 user.role, user.locale, datetime.now(timezone.utc).isoformat(),
                 1 if m.get("verified") else 0, m.get("last_alert_level"),
                 m.get("last_alert_at")),
            )

    async def list_all(self) -> list[UserContext]:
        return await asyncio.to_thread(self._list_all)

    def _list_all(self) -> list[UserContext]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM users").fetchall()
        return [self._to_user(r) for r in rows]


class SQLiteCheckinRepository:
    """Stores per-user nightly sleep check-ins, the evidence the personalization
    layer consumes. Shares the same SQLite file as the user repository."""

    def __init__(self, db_path: str):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        with self._conn() as c:
            c.execute(_CHECKINS_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency (multiple readers, one writer)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def add(self, user_id: str, checkin_date: str, sleep_quality: str | None,
                  outdoor_temp: float | None, humidity: float | None) -> None:
        await asyncio.to_thread(
            self._add, user_id, checkin_date, sleep_quality, outdoor_temp, humidity
        )

    def _add(self, user_id: str, checkin_date: str, sleep_quality: str | None,
             outdoor_temp: float | None, humidity: float | None) -> None:
        # One check-in per user per night; a later report for the same date
        # overwrites the earlier one (last write wins).
        with self._conn() as c:
            c.execute(
                """INSERT INTO checkins
                   (user_id, checkin_date, sleep_quality, outdoor_temp, humidity, created_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(user_id, checkin_date) DO UPDATE SET
                     sleep_quality=excluded.sleep_quality,
                     outdoor_temp=excluded.outdoor_temp,
                     humidity=excluded.humidity,
                     created_at=excluded.created_at""",
                (user_id, checkin_date, sleep_quality, outdoor_temp, humidity,
                 datetime.now(timezone.utc).isoformat()),
            )

    async def list_for_user(self, user_id: str, limit: int = 30) -> list[dict]:
        return await asyncio.to_thread(self._list_for_user, user_id, limit)

    def _list_for_user(self, user_id: str, limit: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT checkin_date, sleep_quality, outdoor_temp, humidity
                   FROM checkins WHERE user_id=?
                   ORDER BY checkin_date DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [
            {
                "checkin_date": r["checkin_date"],
                "sleep_quality": r["sleep_quality"],
                "outdoor_temp": r["outdoor_temp"],
                "humidity": r["humidity"],
            }
            for r in rows
        ]


class SQLiteRDSStateRepository:
    """Stores each user's rolling window of nightly outdoor temps so RDS
    multi-night compounding survives across sessions. Shares the one DB file."""

    def __init__(self, db_path: str, max_days: int = 4):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        self.max_days = max_days
        with self._conn() as c:
            c.execute(_RDS_STATES_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency (multiple readers, one writer)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def save(self, user_id: str, nighttime_temps: list) -> None:
        await asyncio.to_thread(self._save, user_id, nighttime_temps)

    def _save(self, user_id: str, nighttime_temps: list) -> None:
        from datetime import date as _date, datetime as _dt

        capped = sorted(nighttime_temps, key=lambda t: str(t["date"]), reverse=True)[:self.max_days]
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


class SQLiteRiskEvalRepository:
    """Append-only per-user risk-score history. Shares the one DB file."""

    def __init__(self, db_path: str):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        with self._conn() as c:
            c.execute(_RISK_EVALS_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency (multiple readers, one writer)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
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


class SQLiteHouseholdRepository:
    """Stores household members for a user. Shares the one DB file."""

    def __init__(self, db_path: str):
        self.db_path = db_path.replace("sqlite:///", "").replace("sqlite://", "")
        with self._conn() as c:
            c.execute(_HOUSEHOLD_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency (multiple readers, one writer)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def add(self, user_id: str, name: str, tag: str, outdoor_worker: bool) -> int:
        return await asyncio.to_thread(self._add, user_id, name, tag, outdoor_worker)

    def _add(self, user_id: str, name: str, tag: str, outdoor_worker: bool) -> int:
        with self._conn() as c:
            cursor = c.execute(
                """INSERT INTO household_members (user_id, name, tag, outdoor_worker, created_at)
                   VALUES (?,?,?,?,?)""",
                (user_id, name, tag, 1 if outdoor_worker else 0, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.lastrowid

    async def list_for_user(self, user_id: str) -> list[dict]:
        return await asyncio.to_thread(self._list_for_user, user_id)

    def _list_for_user(self, user_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM household_members WHERE user_id=? ORDER BY id ASC", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    async def update(self, member_id: int, name: str, tag: str, outdoor_worker: bool) -> bool:
        return await asyncio.to_thread(self._update, member_id, name, tag, outdoor_worker)

    def _update(self, member_id: int, name: str, tag: str, outdoor_worker: bool) -> bool:
        with self._conn() as c:
            cursor = c.execute(
                """UPDATE household_members SET name=?, tag=?, outdoor_worker=?
                   WHERE id=?""",
                (name, tag, 1 if outdoor_worker else 0, member_id),
            )
            return cursor.rowcount > 0

    async def delete(self, member_id: int) -> bool:
        return await asyncio.to_thread(self._delete, member_id)

    def _delete(self, member_id: int) -> bool:
        with self._conn() as c:
            cursor = c.execute("DELETE FROM household_members WHERE id=?", (member_id,))
            return cursor.rowcount > 0
