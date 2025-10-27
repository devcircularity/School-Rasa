# app/api/routers/schools.py - School management routes
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from typing import Dict, Any, List
import logging
from uuid import UUID

from app.core.db import get_db
from app.api.deps.auth import get_current_user, require_admin
from app.api.deps.tenancy import require_school
from app.models.school import School, SchoolMember
from app.models.user import User
from app.schemas.school import SchoolCreate, SchoolOut, SchoolLite, SchoolMineItem, SchoolOverview

# FIXED: Import all models at the top of the file to prevent SQLAlchemy table redefinition errors
from app.models.student import Student
from app.models.class_model import Class
from app.models.payment import Invoice, Payment
from app.models.enrollment import Enrollment
from app.models.guardian import Guardian, StudentGuardian
from app.models.academic import AcademicYear, AcademicTerm

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=SchoolOut, status_code=status.HTTP_201_CREATED)
async def create_school(
    school_data: SchoolCreate,
    ctx: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new school"""
    user = ctx["user"]
    
    # Check if short_code is unique (if provided)
    if school_data.short_code:
        existing_school = db.execute(
            select(School).where(School.short_code == school_data.short_code)
        ).scalar_one_or_none()
        
        if existing_school:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="School with this short code already exists"
            )
    
    # Create school
    new_school = School(
        name=school_data.name,
        address=school_data.address,
        contact=school_data.contact,
        short_code=school_data.short_code,
        email=school_data.email,
        phone=school_data.phone,
        currency=school_data.currency,
        academic_year_start=school_data.academic_year_start,
        boarding_type=school_data.boarding_type,  # NEW
        gender_type=school_data.gender_type,      # NEW
        created_by=user.id
    )
    
    db.add(new_school)
    
    try:
        db.flush()  # Get the school ID
        
        # Add creator as OWNER of the school
        membership = SchoolMember(
            school_id=new_school.id,
            user_id=user.id,
            role="OWNER"
        )
        db.add(membership)
        
        db.commit()
        db.refresh(new_school)
        
        logger.info(f"New school created: {new_school.name} by {user.email}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating school: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating school"
        )
    
    return SchoolOut(
        id=new_school.id,
        name=new_school.name,
        address=new_school.address,
        contact=new_school.contact
    )

@router.get("/mine", response_model=List[SchoolMineItem])
async def get_my_schools(
    ctx: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get schools the current user is a member of"""
    user = ctx["user"]
    
    # Get user's school memberships with school details
    query = (
        select(School, SchoolMember.role)
        .join(SchoolMember, School.id == SchoolMember.school_id)
        .where(SchoolMember.user_id == user.id)
        .order_by(School.name)
    )
    
    results = db.execute(query).all()
    
    schools = []
    for school, role in results:
        schools.append(SchoolMineItem(
            id=school.id,
            name=school.name,
            role=role
        ))
    
    return schools

@router.get("/{school_id}", response_model=SchoolOut)
async def get_school(
    school_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get school details"""
    try:
        school_uuid = UUID(school_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school ID format"
        )
    
    school = db.execute(
        select(School).where(School.id == school_uuid)
    ).scalar_one_or_none()
    
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    return school

@router.get("/{school_id}/overview", response_model=SchoolOverview)
async def get_school_overview(
    school_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get school overview with key metrics"""
    
    # Verify school_id matches context
    if school_id != ctx["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    try:
        school_uuid = UUID(school_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school ID format"
        )
    
    # Get school details
    school = db.get(School, school_uuid)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    # FIXED: All imports are now at the top of the file
    
    # Get counts
    students_count = db.execute(
        select(func.count(Student.id)).where(Student.school_id == school_uuid)
    ).scalar() or 0
    
    classes_count = db.execute(
        select(func.count(Class.id)).where(Class.school_id == school_uuid)
    ).scalar() or 0
    
    guardians_count = db.execute(
        select(func.count(func.distinct(Guardian.id)))
        .join(StudentGuardian, Guardian.id == StudentGuardian.guardian_id)
        .join(Student, StudentGuardian.student_id == Student.id)
        .where(Student.school_id == school_uuid)
    ).scalar() or 0
    
    # Get current academic year and term
    current_year = db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == school_uuid,
            AcademicYear.is_active == True
        )
    ).scalar_one_or_none()
    
    current_term = None
    current_term_id = None
    if current_year:
        current_term = db.execute(
            select(AcademicTerm)
            .where(
                AcademicTerm.academic_year_id == current_year.id,
                AcademicTerm.state == "ACTIVE"
            )
        ).scalar_one_or_none()
        
        if current_term:
            current_term_id = current_term.id
    
    # Get enrollment stats for current term
    enrolled_students = 0
    unassigned_students = students_count
    
    if current_term_id:
        enrolled_students = db.execute(
            select(func.count(func.distinct(Enrollment.student_id)))
            .where(Enrollment.term_id == current_term_id)
        ).scalar() or 0
        
        unassigned_students = students_count - enrolled_students
    
    # Get invoice stats
    total_invoices = db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.school_id == school_uuid)
    ).scalar() or 0
    
    issued_invoices = db.execute(
        select(func.count(Invoice.id))
        .where(
            Invoice.school_id == school_uuid,
            Invoice.status.in_(["ISSUED", "PARTIAL"])
        )
    ).scalar() or 0
    
    paid_invoices = db.execute(
        select(func.count(Invoice.id))
        .where(
            Invoice.school_id == school_uuid,
            Invoice.status == "PAID"
        )
    ).scalar() or 0
    
    pending_invoices = db.execute(
        select(func.count(Invoice.id))
        .where(
            Invoice.school_id == school_uuid,
            Invoice.status.in_(["ISSUED", "PARTIAL"])
        )
    ).scalar() or 0
    
    # Get fees collected (total payments)
    fees_collected = db.execute(
        select(func.sum(Payment.amount))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.school_id == school_uuid)
    ).scalar() or 0
    
    return {
        "school_name": school.name,
        "academic_year": current_year.year if current_year else None,
        "current_term": current_term.title if current_term else None,
        "students_total": students_count,
        "students_enrolled": enrolled_students,
        "students_unassigned": unassigned_students,
        "classes": classes_count,
        "guardians": guardians_count,
        "invoices_total": total_invoices,
        "invoices_issued": issued_invoices,
        "invoices_paid": paid_invoices,
        "invoices_pending": pending_invoices,
        "fees_collected": float(fees_collected)
    }

@router.get("/{school_id}/members")
async def get_school_members(
    school_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get school members list (admin only)"""
    
    # Verify school_id matches context
    if school_id != ctx["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    user = ctx["user"]
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        school_uuid = UUID(school_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school ID format"
        )
    
    # Get members with user details
    query = (
        select(User, SchoolMember.role, SchoolMember.created_at)
        .join(SchoolMember, User.id == SchoolMember.user_id)
        .where(SchoolMember.school_id == school_uuid)
        .order_by(User.full_name)
    )
    
    results = db.execute(query).all()
    
    members = []
    for user, role, joined_at in results:
        members.append({
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "role": role,
            "is_active": user.is_active,
            "joined_at": joined_at,
            "last_login": user.last_login
        })
    
    return {"members": members}

@router.put("/{school_id}")
async def update_school(
    school_id: str,
    school_data: SchoolCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update school details (admin only)"""
    
    # Verify school_id matches context
    if school_id != ctx["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    user = ctx["user"]
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        school_uuid = UUID(school_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school ID format"
        )
    
    school = db.get(School, school_uuid)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    # Check if short_code is unique (if changed)
    if school_data.short_code and school_data.short_code != school.short_code:
        existing_school = db.execute(
            select(School).where(
                School.short_code == school_data.short_code,
                School.id != school_uuid
            )
        ).scalar_one_or_none()
        
        if existing_school:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="School with this short code already exists"
            )
    
    # Update school fields
    school.name = school_data.name
    school.address = school_data.address
    school.contact = school_data.contact
    school.short_code = school_data.short_code
    school.email = school_data.email
    school.phone = school_data.phone
    school.currency = school_data.currency
    school.academic_year_start = school_data.academic_year_start
    school.boarding_type = school_data.boarding_type      # NEW
    school.gender_type = school_data.gender_type 
    
    try:
        db.commit()
        logger.info(f"School updated: {school.name} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating school: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating school"
        )
    
    return {"message": "School updated successfully"}

@router.delete("/{school_id}")
async def delete_school(
    school_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete school (owner only)"""
    
    # Verify school_id matches context
    if school_id != ctx["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this school"
        )
    
    user = ctx["user"]
    
    try:
        school_uuid = UUID(school_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school ID format"
        )
    
    # Check if user is owner of the school
    membership = db.execute(
        select(SchoolMember).where(
            SchoolMember.school_id == school_uuid,
            SchoolMember.user_id == user.id,
            SchoolMember.role == "OWNER"
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school owners can delete schools"
        )
    
    school = db.get(School, school_uuid)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    try:
        # Delete school (this will cascade delete members due to FK constraints)
        db.delete(school)
        db.commit()
        
        logger.info(f"School deleted: {school.name} by {user.email}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting school: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting school. Make sure all related data is removed first."
        )
    
    return {"message": "School deleted successfully"}