# app/schemas/class_stream.py
from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID
from typing import List

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