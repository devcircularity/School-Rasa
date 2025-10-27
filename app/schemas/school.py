# app/schemas/school.py - Updated with boarding_type and gender_type
from datetime import date
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import uuid

# Add enums for validation
class BoardingTypeEnum(str, Enum):
    DAY = "DAY"
    BOARDING = "BOARDING"
    BOTH = "BOTH"

class GenderTypeEnum(str, Enum):
    BOYS = "BOYS"
    GIRLS = "GIRLS"
    MIXED = "MIXED"

class SchoolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="School name (required)")
    address: Optional[str] = Field(None, max_length=500, description="School address")
    contact: Optional[str] = Field(None, max_length=255, description="Contact information")
    short_code: Optional[str] = Field(None, max_length=32, description="Short code for reports/IDs")
    email: Optional[str] = Field(None, max_length=255, description="Official school email")
    phone: Optional[str] = Field(None, max_length=32, description="School phone number")
    currency: Optional[str] = Field("KES", max_length=8, description="Default currency")
    
    # Academic year start date
    academic_year_start: str = Field(..., description="Academic year start date (YYYY-MM-DD format)")
    
    # NEW FIELDS
    boarding_type: BoardingTypeEnum = Field(
        default=BoardingTypeEnum.DAY,
        description="School type: DAY, BOARDING, or BOTH"
    )
    gender_type: GenderTypeEnum = Field(
        default=GenderTypeEnum.MIXED,
        description="Gender type: BOYS, GIRLS, or MIXED"
    )
    
    @field_validator('academic_year_start')
    @classmethod
    def validate_academic_year_start(cls, v: str) -> date:
        """Convert date string to date object"""
        try:
            if isinstance(v, str):
                # Parse YYYY-MM-DD format
                return date.fromisoformat(v)
            elif isinstance(v, date):
                # Already a date object
                return v
            else:
                raise ValueError("Invalid date format")
        except ValueError:
            raise ValueError("academic_year_start must be in YYYY-MM-DD format (e.g., '2024-01-15')")

class SchoolOut(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    contact: Optional[str] = None
    short_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    currency: Optional[str] = None
    academic_year_start: Optional[date] = None
    
    # NEW FIELDS
    boarding_type: Optional[str] = None
    gender_type: Optional[str] = None
    
    class Config:
        from_attributes = True

class SchoolLite(BaseModel):
    id: uuid.UUID
    name: str
    
    class Config:
        from_attributes = True

class SchoolMineItem(BaseModel):
    id: uuid.UUID
    name: str
    role: Optional[str] = None
    
    class Config:
        from_attributes = True

class SchoolOverview(BaseModel):
    school_name: str
    academic_year: int | None
    current_term: str | None
    students_total: int
    students_enrolled: int
    students_unassigned: int
    classes: int
    guardians: int
    invoices_total: int
    invoices_issued: int
    invoices_paid: int
    invoices_pending: int
    fees_collected: float
    
    # OPTIONAL: You could add these to overview too
    # boarding_type: Optional[str] = None
    # gender_type: Optional[str] = None