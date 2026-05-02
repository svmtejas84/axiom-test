"""
SQLAlchemy ORM Models for PostgreSQL

Defines the persistent data models for:
- User profiles
- Credit score history
- Verification records
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()


class UserProfile(Base):
    """User profile model."""

    __tablename__ = "user_profiles"

    id = Column(String(50), primary_key=True)  # user_id
    kyc_hash = Column(String(256), nullable=True)  # Hashed KYC document
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AxiomScoreHistory(Base):
    """Credit score history model."""

    __tablename__ = "axiom_score_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True)
    score = Column(Integer, nullable=False)  # 300-900
    confidence = Column(Float, nullable=False)  # 0-1
    tier = Column(String(20), nullable=False)  # Low, Medium, High, Prime
    signal_count = Column(Integer, nullable=False)
    s_b = Column(Float, nullable=True)  # Baseline component
    s_t = Column(Float, nullable=True)  # Transitive component
    r_f = Column(Float, nullable=True)  # Fraud component
    task_id = Column(String(255), nullable=True)  # Associated Celery Task ID
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class VerificationRecord(Base):
    """Rent verification record model."""

    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True)
    landlord_vpa_hash = Column(String(256), nullable=False)  # Hashed for privacy
    months_consistent = Column(Integer, nullable=False)
    trust_coefficient = Column(Float, nullable=False)
    verified_at = Column(DateTime, default=datetime.utcnow)


class StudentVerification(Base):
    """Student verification record model."""

    __tablename__ = "student_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True)
    edu_email = Column(String(255), nullable=False)
    parents_vpa_hash = Column(String(256), nullable=False)  # Hashed for privacy
    sheerid_verification_id = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # 'pending', 'verified', 'rejected'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
