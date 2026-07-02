
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    evaluations = relationship("RiskEvaluation", back_populates="user")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    city_name = Column(String(100))
    resolved_climate_zone = Column(String(50), default="default")
    
    roof_material = Column(String(50), default="brick")
    floor_level = Column(String(50), default="other")
    has_ac = Column(Boolean, default=False)
    has_fan = Column(Boolean, default=False)
    windows_open = Column(Boolean, default=False)
    occupants = Column(Float, default=1.0)
    
    user = relationship("User", back_populates="profile")

class RiskEvaluation(Base):
    __tablename__ = "risk_evaluations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    outdoor_temp = Column(Float)
    outdoor_humidity = Column(Float)
    base_aqi = Column(Float)
    calculated_ndt = Column(Float)
    calculated_rds = Column(Float)
    ccri = Column(Float)
    
    user = relationship("User", back_populates="evaluations")

class RDSState(Base):
    __tablename__ = "rds_states"
    
    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    # Stores the JSON serialized nighttime_temps list to reconstruct RDSCalculator
    nighttime_temps = Column(JSON, default=list)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
