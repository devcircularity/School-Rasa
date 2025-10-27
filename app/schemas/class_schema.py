# app/schemas/class_schema.py
import re
from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

def normalize_class_name(name: str) -> str:
    """Normalize class name for consistency"""
    if not name:
        return name
    
    name = name.strip()
    
    # Handle grade/form patterns with letter suffixes: "8a" -> "8A", "form 1a" -> "Form 1A"
    grade_pattern = r'^(grade|form|jss|pp|class)\s*(\d+)([a-zA-Z])$'
    match = re.match(grade_pattern, name, re.IGNORECASE)
    if match:
        prefix, number, letter = match.groups()
        return f"{prefix.title()} {number}{letter.upper()}"
    
    # Handle simple patterns like "8a" -> "8A"
    simple_pattern = r'^(\d+)([a-zA-Z])$'
    match = re.match(simple_pattern, name, re.IGNORECASE)
    if match:
        number, letter = match.groups()
        return f"{number}{letter.upper()}"
    
    # Default: title case
    return name.title()

class ClassCreate(BaseModel):
    name: str
    level: str
    academic_year: int
    stream: Optional[str] = None
    
    @validator('name', 'level')
    def validate_and_normalize_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('This field cannot be empty')
        return normalize_class_name(v)
    
    @validator('stream')
    def normalize_stream(cls, v):
        if v:
            return v.strip().upper()
        return v
    
    @validator('academic_year')
    def validate_academic_year(cls, v):
        if v < 2020 or v > 2030:
            raise ValueError('Academic year must be between 2020 and 2030')
        return v

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[str] = None
    academic_year: Optional[int] = None
    stream: Optional[str] = None
    
    @validator('name', 'level')
    def normalize_text_fields(cls, v):
        if v is not None:
            return normalize_class_name(v)
        return v
    
    @validator('stream')
    def normalize_stream(cls, v):
        if v is not None:
            return v.strip().upper()
        return v

class ClassOut(BaseModel):
    id: UUID
    name: str
    level: str
    academic_year: int
    stream: Optional[str]
    student_count: int
    streams: List[str] = []  # NEW: List of stream names
    created_at: datetime
    
    class Config:
        from_attributes = True

class ClassDetail(ClassOut):
    students: List[Dict[str, Any]]
    updated_at: datetime

class ClassList(BaseModel):
    classes: List[ClassOut]
    total: int
    page: int
    limit: int
    has_next: bool

# NEW: Stream-specific schemas
class ClassStreamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    
    @validator('name')
    def normalize_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Stream name cannot be empty')
        # Normalize to title case: "red" -> "Red", "BLUE" -> "Blue"
        return v.strip().title()

class ClassStreamOut(BaseModel):
    id: UUID
    class_id: UUID
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ClassStreamList(BaseModel):
    streams: List[ClassStreamOut]
    total: int