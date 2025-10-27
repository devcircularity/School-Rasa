from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

class GuardianCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=64)
    last_name: str = Field(..., min_length=1, max_length=64)
    email: EmailStr  # Mandatory
    phone: str = Field(..., max_length=32)  # Mandatory
    relationship: Optional[str] = Field(None, max_length=32)
    student_id: Optional[UUID] = None
    
    @validator('email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError('Email is required for all guardians')
        return v.lower().strip()
    
    @validator('phone')
    def validate_phone(cls, v):
        if not v or not v.strip():
            raise ValueError('Phone number is required for all guardians')
        return v.strip()

class GuardianOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    relationship: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class GuardianDetail(GuardianOut):
    is_primary: bool = False
    students: Optional[List[Dict[str, Any]]] = []  # Add this field
    
    class Config:
        from_attributes = True

class StudentGuardianLink(BaseModel):
    student_id: UUID
    guardian_id: UUID
    set_as_primary: bool = False

class GuardianUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=64)
    last_name: Optional[str] = Field(None, min_length=1, max_length=64)
    email: Optional[EmailStr] = None  # Optional for updates
    phone: Optional[str] = Field(None, max_length=32)  # Optional for updates
    relationship: Optional[str] = Field(None, max_length=32)