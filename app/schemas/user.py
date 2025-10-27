
# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict
from datetime import datetime


class UserOut(BaseModel):
    """User output schema"""
    id: str
    email: str
    full_name: str
    roles: List[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    school_count: int = 0
    
    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """User creation schema"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    roles: Optional[List[str]] = Field(default=["PARENT"])
    is_active: Optional[bool] = True
    
    @validator('roles')
    def validate_roles(cls, v):
        """Validate that roles are from allowed list"""
        allowed_roles = ['SUPER_ADMIN', 'ADMIN', 'TESTER', 'TEACHER', 'ACCOUNTANT', 'PARENT']
        if v:
            for role in v:
                if role not in allowed_roles:
                    raise ValueError(f"Invalid role: {role}. Allowed roles: {allowed_roles}")
        return v or ["PARENT"]


class UserUpdate(BaseModel):
    """User update schema"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    
    @validator('roles')
    def validate_roles(cls, v):
        """Validate that roles are from allowed list"""
        if v is None:
            return v
        allowed_roles = ['SUPER_ADMIN', 'ADMIN', 'TESTER', 'TEACHER', 'ACCOUNTANT', 'PARENT']
        for role in v:
            if role not in allowed_roles:
                raise ValueError(f"Invalid role: {role}. Allowed roles: {allowed_roles}")
        return v


class UserRolesUpdate(BaseModel):
    """Schema for updating only user roles"""
    roles: List[str] = Field(..., min_items=1)
    
    @validator('roles')
    def validate_roles(cls, v):
        """Validate that roles are from allowed list"""
        allowed_roles = ['SUPER_ADMIN', 'ADMIN', 'TESTER', 'TEACHER', 'ACCOUNTANT', 'PARENT']
        for role in v:
            if role not in allowed_roles:
                raise ValueError(f"Invalid role: {role}. Allowed roles: {allowed_roles}")
        return v


class UserListResponse(BaseModel):
    """Response schema for user list"""
    users: List[UserOut]
    total: int
    page: int
    limit: int
    has_next: bool


class UserStatsOut(BaseModel):
    """User statistics schema"""
    total_users: int
    active_users: int
    users_by_role: Dict[str, int]
    new_users_this_week: int
    new_users_this_month: int


class RoleInfo(BaseModel):
    """Role information schema"""
    value: str
    label: str
    description: str