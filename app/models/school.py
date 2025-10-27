# app/models/school.py - Add new fields to School model

from __future__ import annotations
import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, DateTime, Date, Boolean, ForeignKey, CheckConstraint, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import enum

# Add enums for the new fields
class BoardingType(str, enum.Enum):
    DAY = "DAY"
    BOARDING = "BOARDING"
    BOTH = "BOTH"

class GenderType(str, enum.Enum):
    BOYS = "BOYS"
    GIRLS = "GIRLS"
    MIXED = "MIXED"

class School(Base):
    __tablename__ = "schools"

    # Use proper UUID type
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str | None] = mapped_column(String(256))
    contact: Mapped[str | None] = mapped_column(String(128))
    short_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    email: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(8), default="KES")
    
    # NEW FIELDS
    boarding_type: Mapped[BoardingType] = mapped_column(
        SQLEnum(BoardingType, native_enum=False),
        default=BoardingType.DAY,
        nullable=False
    )
    gender_type: Mapped[GenderType] = mapped_column(
        SQLEnum(GenderType, native_enum=False),
        default=GenderType.MIXED,
        nullable=False
    )
    
    # Academic year start as proper Date field
    academic_year_start: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Foreign key to users table
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Add required timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (unchanged)
    members: Mapped[list["SchoolMember"]] = relationship("SchoolMember", back_populates="school")
    whatsapp_settings: Mapped["SchoolWhatsAppSettings | None"] = relationship(
        "SchoolWhatsAppSettings", 
        back_populates="school", 
        uselist=False
    )
    mobile_device_statuses: Mapped[list["MobileDeviceStatus"]] = relationship(
        "MobileDeviceStatus", 
        back_populates="school"
    )


class SchoolMember(Base):
    __tablename__ = "schoolmember"

    # Use proper UUID type
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # OWNER|ADMIN|TEACHER|ACCOUNTANT|PARENT
    
    # Add required timestamp fields
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="members")
    # user: Mapped["User"] = relationship("User", back_populates="school_memberships")
    
    __table_args__ = (
        CheckConstraint("role IN ('OWNER','ADMIN','TEACHER','ACCOUNTANT','PARENT')", name="ck_schoolmember_role"),
    )


class SchoolWhatsAppSettings(Base):
    __tablename__ = "school_whatsapp_settings"

    # Primary key - school_id (one record per school)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("schools.id"), 
        primary_key=True
    )
    
    # WhatsApp configuration
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bridge_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    connection_token: Mapped[str | None] = mapped_column(String(128))
    
    # QR Code storage fields
    qr_code: Mapped[str | None] = mapped_column(String(10000))  # Store base64 QR code
    qr_generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Status tracking
    last_connection_check: Mapped[datetime | None] = mapped_column(DateTime)
    last_successful_message: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Optional: Store bridge URL if different per school
    bridge_url: Mapped[str | None] = mapped_column(String(256))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to school
    school: Mapped["School"] = relationship("School", back_populates="whatsapp_settings")


class MobileDeviceStatus(Base):
    __tablename__ = "mobile_device_status"

    # Composite primary key: school_id + user_id + device_id
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)  # "android-<random-or-androidId>"
    
    # Device information
    app_version: Mapped[str | None] = mapped_column(String(32))
    device_model: Mapped[str | None] = mapped_column(String(128))
    android_version: Mapped[str | None] = mapped_column(String(32))
    
    # Permission and connection status
    notification_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_permission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    listener_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Last operation status
    last_forward_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)  # Store error messages
    last_sms_received_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Network and connectivity info
    network_status: Mapped[str | None] = mapped_column(String(32))  # "wifi", "mobile", "offline"
    battery_optimized: Mapped[bool | None] = mapped_column(Boolean)  # If app is battery optimized
    
    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_update_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="mobile_device_statuses")
    # user: Mapped["User"] = relationship("User")
    
    # Ensure unique device per user per school
    __table_args__ = (
        # Unique constraint on school_id + user_id + device_id
        # This allows the same user to have multiple devices, but each device is unique per school
        CheckConstraint("device_id != ''", name="ck_mobile_device_status_device_id_not_empty"),
    )
    
    @property
    def is_online(self) -> bool:
        """Check if device is considered online (heartbeat within last 5 minutes)"""
        if not self.last_heartbeat_at:
            return False
        return (datetime.utcnow() - self.last_heartbeat_at).total_seconds() < 300  # 5 minutes
    
    @property
    def is_healthy(self) -> bool:
        """Check if device is healthy (all permissions granted and no recent errors)"""
        return (
            self.notification_access and 
            self.sms_permission and 
            self.listener_connected and 
            self.last_forward_ok
        )
    
    @property
    def status_summary(self) -> str:
        """Get human-readable status summary"""
        if not self.is_online:
            return "offline"
        elif not self.is_healthy:
            return "issues"
        else:
            return "connected"