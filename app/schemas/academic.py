# app/schemas/academic.py - Fixed schema
from datetime import date
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID

# Academic Year schemas
class AcademicYearCreate(BaseModel):
    year: int
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class AcademicYearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    year: int
    title: str
    state: str
    start_date: Optional[date]
    end_date: Optional[date]

# Academic Term schemas
class AcademicTermCreate(BaseModel):
    term: int
    title: str
    academic_year: int  # This is correct - used for input
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class AcademicTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    term: int
    title: str
    state: str
    start_date: Optional[date]
    end_date: Optional[date]
    academic_year_id: UUID  # FIXED: Changed from year_id to match the model

# Enrollment schemas
class EnrollmentCreate(BaseModel):
    student_id: UUID
    class_id: UUID
    term_id: UUID
    joined_on: Optional[date] = None

class EnrollmentStatusUpdate(BaseModel):
    new_status: str
    reason: Optional[str] = None
    event_date: Optional[date] = None

class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    student_id: UUID
    class_id: UUID
    term_id: UUID
    status: str
    joined_on: Optional[date]
    left_on: Optional[date]

class EnrollmentStatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    enrollment_id: UUID
    prev_status: Optional[str]
    new_status: str
    reason: Optional[str]
    event_date: date

# Monitoring schemas
class ClassRosterItem(BaseModel):
    student_id: UUID
    student_name: str
    admission_no: str
    status: str
    joined_on: Optional[date]

class ClassRoster(BaseModel):
    class_id: UUID
    class_name: str
    students: List[ClassRosterItem]

class TermSummary(BaseModel):
    term_id: UUID
    term_title: str
    total_enrolled: int
    transferred_out: int
    suspended: int
    dropped: int
    graduated: int