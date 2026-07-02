
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

# Database path
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = str(BASE_DIR / "data" / "prana_persistence.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    from prana.models import Base
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions for RDS persistence
def save_user_rds_state(db: Session, user_id: str, nighttime_temps: list):
    from prana.models import RDSState
    from prana.config import RDS_MAX_DAYS
    from datetime import datetime, date
    
    # Enforce window limit at persistence layer
    nighttime_temps = sorted(nighttime_temps, key=lambda x: x['date'], reverse=True)[:RDS_MAX_DAYS]
    
    # Serialize dates
    serialized = []
    for t in nighttime_temps:
        d = t['date']
        if isinstance(d, (date, datetime)):
            d = d.isoformat()
        entry = {"date": d, "temp": t['temp']}
        if t.get('humidity') is not None:
            entry['humidity'] = t['humidity']
        serialized.append(entry)
        
    state = db.query(RDSState).filter(RDSState.user_id == user_id).first()
    if not state:
        state = RDSState(user_id=user_id, nighttime_temps=serialized)
        db.add(state)
    else:
        state.nighttime_temps = serialized
    db.commit()

def load_user_rds_state(db: Session, user_id: str) -> list:
    from prana.models import RDSState
    from datetime import datetime
    
    state = db.query(RDSState).filter(RDSState.user_id == user_id).first()
    if not state:
        return []
    
    temps = state.nighttime_temps
    for t in temps:
        # Convert back to date object (keeping just the date part for RDS)
        t['date'] = datetime.fromisoformat(t['date']).date()
    return temps
