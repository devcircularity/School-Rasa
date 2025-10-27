# app/api/routers/admin_users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.core.db import get_db
from app.core.security import password_manager
from app.api.deps.tenancy import require_school
from app.models.user import User, UserRole
from app.models.school import SchoolMember
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== SCHEMAS ====================

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    roles: List[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    school_count: int
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserOut]
    total: int
    page: int
    limit: int
    has_next: bool


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    roles: Optional[List[str]] = ["PARENT"]
    is_active: Optional[bool] = True


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UpdateUserRolesRequest(BaseModel):
    roles: List[str]


class UserStatsResponse(BaseModel):
    total_users: int
    active_users: int
    users_by_role: Dict[str, int]
    new_users_this_week: int
    new_users_this_month: int


class AvailableRolesResponse(BaseModel):
    roles: List[Dict[str, str]]


# ==================== HELPER FUNCTIONS ====================

def check_admin_permission(ctx: Dict[str, Any]) -> bool:
    """Check if user has admin permissions"""
    user = ctx.get("user")
    if not user:
        return False
    
    roles = user.roles if hasattr(user, 'roles') else []
    return "ADMIN" in roles or "SUPER_ADMIN" in roles


def get_user_school_count(db: Session, user_id: str) -> int:
    """Get count of schools user belongs to"""
    count = db.execute(
        select(func.count(SchoolMember.id))
        .where(SchoolMember.user_id == user_id)
    ).scalar()
    return count or 0


# ==================== ROUTES ====================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    active_only: bool = Query(False)
):
    """List all users with pagination and filters"""
    
    # Check permissions
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Build query
    query = select(User)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_term),
                User.full_name.ilike(search_term)
            )
        )
    
    if role:
        query = query.where(User.roles_csv.contains(role))
    
    if active_only:
        query = query.where(User.is_active == True)
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    users = db.execute(query).scalars().all()
    
    # Build response with school counts
    user_list = []
    for user in users:
        school_count = get_user_school_count(db, str(user.id))
        user_dict = {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "roles": user.roles,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login": user.last_login,
            "school_count": school_count
        }
        user_list.append(UserOut(**user_dict))
    
    return UserListResponse(
        users=user_list,
        total=total,
        page=page,
        limit=limit,
        has_next=(page * limit) < total
    )


@router.get("/users/stats", response_model=UserStatsResponse)
async def get_user_stats(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get user statistics"""
    
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Total users
    total_users = db.execute(select(func.count(User.id))).scalar()
    
    # Active users
    active_users = db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    ).scalar()
    
    # Users by role
    all_users = db.execute(select(User)).scalars().all()
    users_by_role = {}
    for role in ["SUPER_ADMIN", "ADMIN", "TESTER", "TEACHER", "ACCOUNTANT", "PARENT"]:
        count = sum(1 for user in all_users if role in user.roles)
        users_by_role[role] = count
    
    # New users this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_this_week = db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    ).scalar()
    
    # New users this month
    month_ago = datetime.utcnow() - timedelta(days=30)
    new_users_this_month = db.execute(
        select(func.count(User.id)).where(User.created_at >= month_ago)
    ).scalar()
    
    return UserStatsResponse(
        total_users=total_users or 0,
        active_users=active_users or 0,
        users_by_role=users_by_role,
        new_users_this_week=new_users_this_week or 0,
        new_users_this_month=new_users_this_month or 0
    )


@router.get("/users/roles/available", response_model=AvailableRolesResponse)
async def get_available_roles(
    ctx: Dict[str, Any] = Depends(require_school)
):
    """Get list of available user roles"""
    
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    roles = [
        {
            "value": "SUPER_ADMIN",
            "label": "Super Admin",
            "description": "Full system access, can manage all schools and users"
        },
        {
            "value": "ADMIN",
            "label": "Administrator",
            "description": "Can manage specific schools and users"
        },
        {
            "value": "TESTER",
            "label": "Tester",
            "description": "Can review and suggest intent improvements"
        },
        {
            "value": "TEACHER",
            "label": "Teacher",
            "description": "Can manage classes and students"
        },
        {
            "value": "ACCOUNTANT",
            "label": "Accountant",
            "description": "Can manage fees and payments"
        },
        {
            "value": "PARENT",
            "label": "Parent",
            "description": "Basic user access"
        }
    ]
    
    return AvailableRolesResponse(roles=roles)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get user by ID"""
    
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(
        select(User).where(User.id == user_uuid)
    ).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    school_count = get_user_school_count(db, str(user.id))
    
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "roles": user.roles,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
        "school_count": school_count
    }
    
    return UserOut(**user_dict)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: CreateUserRequest,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new user"""
    
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Check if user already exists
    existing_user = db.execute(
        select(User).where(User.email == user_data.email.lower())
    ).scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Validate password
    validation = password_manager.validate_password_strength(user_data.password)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(validation["feedback"])
        )
    
    # Validate roles
    valid_roles = [r.value for r in UserRole]
    for role in user_data.roles:
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}"
            )
    
    # Create user
    hashed_password = password_manager.hash_password(user_data.password)
    new_user = User(
        email=user_data.email.lower(),
        full_name=user_data.full_name,
        password_hash=hashed_password,
        is_active=user_data.is_active,
        is_verified=False
    )
    new_user.set_roles(user_data.roles)
    
    db.add(new_user)
    
    try:
        db.commit()
        db.refresh(new_user)
        logger.info(f"User created: {new_user.email} by admin {ctx['user'].email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )
    
    school_count = get_user_school_count(db, str(new_user.id))
    
    user_dict = {
        "id": str(new_user.id),
        "email": new_user.email,
        "full_name": new_user.full_name,
        "roles": new_user.roles,
        "is_active": new_user.is_active,
        "is_verified": new_user.is_verified,
        "created_at": new_user.created_at,
        "updated_at": new_user.updated_at,
        "last_login": new_user.last_login,
        "school_count": school_count
    }
    
    return UserOut(**user_dict)


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    user_data: UpdateUserRequest,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update user information"""
    
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(
        select(User).where(User.id == user_uuid)
    ).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.is_verified is not None:
        user.is_verified = user_data.is_verified
    
    if user_data.roles is not None:
        # Validate roles
        valid_roles = [r.value for r in UserRole]
        for role in user_data.roles:
            if role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role}"
                )
        user.set_roles(user_data.roles)
    
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"User {user.email} updated by admin {ctx['user'].email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )
    
    school_count = get_user_school_count(db, str(user.id))
    
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "roles": user.roles,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
        "school_count": school_count
    }
    
    return UserOut(**user_dict)


@router.put("/users/{user_id}/roles", response_model=UserOut)
async def update_user_roles(
    user_id: str,
    roles_data: UpdateUserRolesRequest,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update user roles specifically"""
    
    if not check_admin_permission(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(
        select(User).where(User.id == user_uuid)
    ).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate roles
    valid_roles = [r.value for r in UserRole]
    for role in roles_data.roles:
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}"
            )
    
    user.set_roles(roles_data.roles)
    
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"User {user.email} roles updated to {roles_data.roles} by admin {ctx['user'].email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user roles"
        )
    
    school_count = get_user_school_count(db, str(user.id))
    
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "roles": user.roles,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
        "school_count": school_count
    }
    
    return UserOut(**user_dict)


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def deactivate_user(
    user_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Deactivate a user (soft delete)"""
    
    # Only super admins can deactivate users
    user = ctx.get("user")
    if not user or "SUPER_ADMIN" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    target_user = db.execute(
        select(User).where(User.id == user_uuid)
    ).scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deactivation
    if str(target_user.id) == str(user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    
    target_user.is_active = False
    
    try:
        db.commit()
        logger.info(f"User {target_user.email} deactivated by super admin {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deactivating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating user"
        )
    
    return {"message": f"User {target_user.email} has been deactivated"}