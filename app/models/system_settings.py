# app/models/system_settings.py
from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.sql import func
from app.models.base import Base

class SystemSetting(Base):
    __tablename__ = "system_settings"
    
    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(String)
    updated_by = Column(String)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemSetting(key={self.key}, value={self.value})>"