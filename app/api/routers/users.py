# app/api/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID
import logging

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.user import User, UserRole
from app.models.school import SchoolMember
from app.schemas.user import (
    UserOut, UserCreate, UserUpdate, UserRolesUpdate,
    UserListResponse, UserStatsOut, RoleInfo
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== USER MANAGEMENT ====================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    active_only: bool = Query(False),
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """List all users with pagination and filtering"""
    user = ctx["user"]
    
    # Check if user has permission to manage users
    if not (user.has_role("ADMIN") or user.has_role("SUPER_ADMIN")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view users"
        )
    
    # Build query
    query = select(User)
    
    # Apply filters
    if active_only:
        query = query.where(User.is_active == True)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_term),
                User.full_name.ilike(search_term)
            )
        )
    
    if role:
        # Filter by role (stored as CSV in roles_csv field)
        query = query.where(User.roles_csv.like(f"%{role}%"))
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(User.created_at.desc())
    
    # Execute query
    users = db.execute(query).scalars().all()
    
    # Get school count for each user
    user_list = []
    for u in users:
        # Count schools for this user
        school_count = db.execute(
            select(func.count(SchoolMember.id))
            .where(SchoolMember.user_id == u.id)
        ).scalar()
        
        user_dict = {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "roles": u.roles,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat(),
            "updated_at": u.updated_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "school_count": school_count
        }
        user_list.append(user_dict)
    
    return {
        "users": user_list,
        "total": total,
        "page": page,
        "limit": limit,
        "has_next": (page * limit) < total
    }


@router.get("/users/stats", response_model=UserStatsOut)
async def get_user_stats(
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get user statistics"""
    user = ctx["user"]
    
    if not (user.has_role("ADMIN") or user.has_role("SUPER_ADMIN")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view user statistics"
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
    for u in all_users:
        for role in u.roles:
            users_by_role[role] = users_by_role.get(role, 0) + 1
    
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
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "users_by_role": users_by_role,
        "new_users_this_week": new_users_this_week,
        "new_users_this_month": new_users_this_month
    }


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get user by ID"""
    current_user = ctx["user"]
    
    if not (current_user.has_role("ADMIN") or current_user.has_role("SUPER_ADMIN")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view users"
        )
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get school count
    school_count = db.execute(
        select(func.count(SchoolMember.id)).where(SchoolMember.user_id == user.id)
    ).scalar()
    
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        roles=user.roles,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        school_count=school_count
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new user"""
    current_user = ctx["user"]
    
    if not (current_user.has_role("ADMIN") or current_user.has_role("SUPER_ADMIN")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create users"
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
    
    # Import here to avoid circular imports
    from app.core.security import password_manager
    
    # Hash password
    hashed_password = password_manager.hash_password(user_data.password)
    
    # Create user
    new_user = User(
        email=user_data.email.lower(),
        full_name=user_data.full_name,
        password_hash=hashed_password,
        is_active=user_data.is_active if user_data.is_active is not None else True
    )
    
    # Set roles
    roles = user_data.roles if user_data.roles else ["PARENT"]
    new_user.set_roles(roles)
    
    db.add(new_user)
    
    try:
        db.commit()
        db.refresh(new_user)
        logger.info(f"User created: {new_user.email} by {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )
    
    return UserOut(
        id=str(new_user.id),
        email=new_user.email,
        full_name=new_user.full_name,
        roles=new_user.roles,
        is_active=new_user.is_active,
        is_verified=new_user.is_verified,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        last_login=new_user.last_login,
        school_count=0
    )


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update user"""
    current_user = ctx["user"]
    
    if not (current_user.has_role("ADMIN") or current_user.has_role("SUPER_ADMIN")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update users"
        )
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent users from deactivating themselves
    if str(user.id) == str(current_user.id) and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    
    # Update fields
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.is_verified is not None:
        user.is_verified = user_data.is_verified
    if user_data.roles is not None:
        user.set_roles(user_data.roles)
    
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"User updated: {user.email} by {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )
    
    school_count = db.execute(
        select(func.count(SchoolMember.id)).where(SchoolMember.user_id == user.id)
    ).scalar()
    
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        roles=user.roles,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        school_count=school_count
    )


@router.put("/users/{user_id}/roles", response_model=UserOut)
async def update_user_roles(
    user_id: str,
    roles_data: UserRolesUpdate,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update user roles specifically"""
    current_user = ctx["user"]
    
    # Only super admins can update roles
    if not current_user.has_role("SUPER_ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can update user roles"
        )
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update roles
    user.set_roles(roles_data.roles)
    
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"User roles updated: {user.email} -> {roles_data.roles} by {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user roles"
        )
    
    school_count = db.execute(
        select(func.count(SchoolMember.id)).where(SchoolMember.user_id == user.id)
    ).scalar()
    
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        roles=user.roles,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        school_count=school_count
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Deactivate user (soft delete)"""
    current_user = ctx["user"]
    
    if not current_user.has_role("SUPER_ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can deactivate users"
        )
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent users from deactivating themselves
    if str(user.id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    
    user.is_active = False
    
    try:
        db.commit()
        logger.info(f"User deactivated: {user.email} by {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deactivating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating user"
        )
    
    return {"message": "User deactivated successfully"}


@router.get("/users/roles/available", response_model=dict)
async def get_available_roles(
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get available user roles"""
    roles = [
        {
            "value": "SUPER_ADMIN",
            "label": "Super Admin",
            "description": "Full system access and user management"
        },
        {
            "value": "ADMIN",
            "label": "Administrator",
            "description": "School management and user administration"
        },
        {
            "value": "TESTER",
            "label": "Tester",
            "description": "Can test chatbot and submit suggestions"
        },
        {
            "value": "TEACHER",
            "label": "Teacher",
            "description": "Manage classes and students"
        },
        {
            "value": "ACCOUNTANT",
            "label": "Accountant",
            "description": "Manage fees and payments"
        },
        {
            "value": "PARENT",
            "label": "Parent",
            "description": "View student information and chat with assistant"
        }
    ]
    
    return {"roles": roles}