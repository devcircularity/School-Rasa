# app/api/routers/academic.py - Fixed imports
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from typing import Dict, Any, List, Optional
from uuid import UUID
import logging
from datetime import datetime, date

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.academic import AcademicYear, AcademicTerm, EnrollmentStatusEvent
# FIXED: Import Enrollment from enrollment.py, not academic.py
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.class_model import Class
from app.schemas.academic import (
    AcademicYearCreate, AcademicYearOut,
    AcademicTermCreate, AcademicTermOut,
    EnrollmentCreate, EnrollmentOut,
    EnrollmentStatusUpdate, EnrollmentStatusEventOut
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== ACADEMIC YEARS ====================

@router.post("/years", response_model=AcademicYearOut, status_code=status.HTTP_201_CREATED)
async def create_academic_year(
    year_data: AcademicYearCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new academic year"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Check if academic year already exists for this school
    existing_year = db.execute(
        select(AcademicYear).where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.year == year_data.year
        )
    ).scalar_one_or_none()
    
    if existing_year:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Academic year {year_data.year} already exists"
        )
    
    # Create academic year
    new_year = AcademicYear(
        school_id=UUID(school_id),
        year=year_data.year,
        title=year_data.title,
        start_date=year_data.start_date,
        end_date=year_data.end_date
    )
    
    db.add(new_year)
    
    try:
        db.commit()
        db.refresh(new_year)
        logger.info(f"Academic year created: {new_year.year} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating academic year: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating academic year"
        )
    
    return AcademicYearOut.model_validate(new_year)

@router.get("/years", response_model=List[AcademicYearOut])
async def get_academic_years(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get all academic years for the school"""
    school_id = ctx["school_id"]
    
    years = db.execute(
        select(AcademicYear)
        .where(AcademicYear.school_id == UUID(school_id))
        .order_by(AcademicYear.year.desc())
    ).scalars().all()
    
    return [AcademicYearOut.model_validate(year) for year in years]

@router.get("/years/current", response_model=AcademicYearOut)
async def get_current_academic_year(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get the current/active academic year"""
    school_id = ctx["school_id"]
    
    # BUG WAS HERE: Using .first() instead of .scalars().first()
    current_year = db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
        .order_by(AcademicYear.year.desc())
    ).scalars().first()  # FIXED: Added .scalars()
    
    # If no active year, get the most recent one
    if not current_year:
        current_year = db.execute(
            select(AcademicYear)
            .where(AcademicYear.school_id == UUID(school_id))
            .order_by(AcademicYear.year.desc())
        ).scalars().first()  # FIXED: Added .scalars()
    
    if not current_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No academic year found. Please create one first."
        )
    
    return AcademicYearOut.model_validate(current_year)

# In academic.py - make sure this exists and works properly

@router.put("/years/{year_id}/activate")
async def activate_academic_year(
    year_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Activate an academic year (set as current)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        year_uuid = UUID(year_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid academic year ID format"
        )
    
    # Find the year
    year = db.execute(
        select(AcademicYear).where(
            AcademicYear.id == year_uuid,
            AcademicYear.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found"
        )
    
    # Deactivate ALL other years for this school FIRST
    all_years = db.execute(
        select(AcademicYear).where(AcademicYear.school_id == UUID(school_id))
    ).scalars().all()
    
    for y in all_years:
        if y.id != year_uuid:
            y.state = "INACTIVE" if y.state == "ACTIVE" else "DRAFT"
    
    # Activate the target year
    year.state = "ACTIVE"
    
    try:
        db.commit()
        logger.info(f"Academic year {year.year} activated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error activating academic year: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating academic year"
        )
    
    return {"message": f"Academic year {year.year} activated successfully"}

# ==================== ACADEMIC TERMS ====================

@router.post("/years/{year_id}/terms", response_model=AcademicTermOut, status_code=status.HTTP_201_CREATED)
async def create_academic_term(
    year_id: str,
    term_data: AcademicTermCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new academic term"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        year_uuid = UUID(year_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid academic year ID format"
        )
    
    # Verify academic year exists
    year = db.execute(
        select(AcademicYear).where(
            AcademicYear.id == year_uuid,
            AcademicYear.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found"
        )
    
    # Check if term already exists for this year
    existing_term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == year_uuid,  # FIXED
            AcademicTerm.term == term_data.term
        )
    ).scalar_one_or_none()
    
    if existing_term:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Term {term_data.term} already exists for {year.year}"
        )
    
    # Create academic term
    new_term = AcademicTerm(
        school_id=UUID(school_id),
        academic_year_id=year_uuid,  # FIXED
        term=term_data.term,
        title=term_data.title,
        start_date=term_data.start_date,
        end_date=term_data.end_date
    )
    
    db.add(new_term)
    
    try:
        db.commit()
        db.refresh(new_term)
        logger.info(f"Academic term created: {new_term.title} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating academic term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating academic term"
        )
    
    return AcademicTermOut.model_validate(new_term)

@router.get("/years/{year_id}/terms", response_model=List[AcademicTermOut])
async def get_terms_for_year(
    year_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get all terms for a specific academic year"""
    school_id = ctx["school_id"]
    
    try:
        year_uuid = UUID(year_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid academic year ID format"
        )
    
    terms = db.execute(
        select(AcademicTerm)
        .where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == year_uuid  # FIXED
        )
        .order_by(AcademicTerm.term)
    ).scalars().all()
    
    return [AcademicTermOut.model_validate(term) for term in terms]

@router.get("/terms/current", response_model=AcademicTermOut)
async def get_current_term(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get the current/active academic term"""
    school_id = ctx["school_id"]
    
    # Get current academic year first
    current_year = db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
    ).scalar_one_or_none()
    
    if not current_year:
        # Get most recent year if no active one
        current_year = db.execute(
            select(AcademicYear)
            .where(AcademicYear.school_id == UUID(school_id))
            .order_by(AcademicYear.year.desc())
        ).scalar_one_or_none()
    
    if not current_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No academic year found. Please create one first."
        )
    
    # Get active term for current year
    current_term = db.execute(
        select(AcademicTerm)
        .where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == current_year.id,  # FIXED
            AcademicTerm.state == "ACTIVE"
        )
    ).scalar_one_or_none()
    
    # If no active term, get the most recent one
    if not current_term:
        current_term = db.execute(
            select(AcademicTerm)
            .where(
                AcademicTerm.school_id == UUID(school_id),
                AcademicTerm.academic_year_id == current_year.id  # FIXED
            )
            .order_by(AcademicTerm.term.desc())
        ).scalar_one_or_none()
    
    if not current_term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No terms found for academic year {current_year.year}. Please create one first."
        )
    
    return AcademicTermOut.model_validate(current_term)


@router.put("/terms/{term_id}/activate")
async def activate_term(
    term_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Activate an academic term (set as current)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        term_uuid = UUID(term_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid term ID format"
        )
    
    # Find the term
    term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == term_uuid,
            AcademicTerm.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found"
        )
    
    # Deactivate all other terms for this year
    all_terms = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == term.academic_year_id  # FIXED
        )
    ).scalars().all()
    
    for t in all_terms:
        t.state = "PLANNED" if t.id != term_uuid else "ACTIVE"
    
    try:
        db.commit()
        logger.info(f"Term {term.title} activated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error activating term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating term"
        )
    
    return {"message": f"Term {term.title} activated successfully"}

# ==================== ENROLLMENTS ====================

@router.post("/enrollments", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    enrollment_data: EnrollmentCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Enroll a student in a class for a specific term"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Verify student, class, and term exist and belong to the school
    student = db.execute(
        select(Student).where(
            Student.id == enrollment_data.student_id,
            Student.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    class_obj = db.execute(
        select(Class).where(
            Class.id == enrollment_data.class_id,
            Class.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == enrollment_data.term_id,
            AcademicTerm.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found"
        )
    
    # Check if student is already enrolled for this term
    existing_enrollment = db.execute(
        select(Enrollment).where(
            Enrollment.school_id == UUID(school_id),
            Enrollment.student_id == enrollment_data.student_id,
            Enrollment.term_id == enrollment_data.term_id
        )
    ).scalar_one_or_none()
    
    if existing_enrollment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student is already enrolled for {term.title}"
        )
    
    # Create enrollment
    new_enrollment = Enrollment(
        school_id=UUID(school_id),
        student_id=enrollment_data.student_id,
        class_id=enrollment_data.class_id,
        term_id=enrollment_data.term_id,
        joined_on=enrollment_data.joined_on or date.today()
    )
    
    db.add(new_enrollment)
    
    try:
        db.commit()
        db.refresh(new_enrollment)
        logger.info(f"Student {student.admission_no} enrolled in {class_obj.name} for {term.title} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating enrollment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating enrollment"
        )
    
    return EnrollmentOut.model_validate(new_enrollment)

@router.get("/students/{student_id}/enrollments", response_model=List[EnrollmentOut])
async def get_student_enrollments(
    student_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get all enrollments for a specific student"""
    school_id = ctx["school_id"]
    
    try:
        student_uuid = UUID(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid student ID format"
        )
    
    enrollments = db.execute(
        select(Enrollment)
        .where(
            Enrollment.school_id == UUID(school_id),
            Enrollment.student_id == student_uuid
        )
        .order_by(Enrollment.created_at.desc())
    ).scalars().all()
    
    return [EnrollmentOut.model_validate(enrollment) for enrollment in enrollments]

@router.get("/terms/{term_id}/enrollments")
async def get_term_enrollments(
    term_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    class_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    """Get all enrollments for a specific term, optionally filtered by class or status"""
    school_id = ctx["school_id"]
    
    try:
        term_uuid = UUID(term_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid term ID format"
        )
    
    query = (
        select(Enrollment, Student, Class)
        .join(Student, Enrollment.student_id == Student.id)
        .join(Class, Enrollment.class_id == Class.id)
        .where(
            Enrollment.school_id == UUID(school_id),
            Enrollment.term_id == term_uuid
        )
    )
    
    if class_id:
        query = query.where(Enrollment.class_id == UUID(class_id))
    
    if status:
        query = query.where(Enrollment.status == status)
    
    results = db.execute(query.order_by(Class.name, Student.first_name)).all()
    
    enrollments = []
    for enrollment, student, class_obj in results:
        enrollments.append({
            "enrollment": EnrollmentOut.model_validate(enrollment),
            "student": {
                "id": str(student.id),
                "admission_no": student.admission_no,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "full_name": f"{student.first_name} {student.last_name}".strip()
            },
            "class": {
                "id": str(class_obj.id),
                "name": class_obj.name,
                "level": class_obj.level
            }
        })
    
    return {
        "enrollments": enrollments,
        "total": len(enrollments)
    }

# Quick utility endpoint for the current academic setup
@router.get("/current-setup")
async def get_current_academic_setup(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get current academic year and term information"""
    school_id = ctx["school_id"]
    
    # Get current academic year
    current_year = db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
        .order_by(AcademicYear.year.desc())
    ).scalars().first()
    
    if not current_year:
        current_year = db.execute(
            select(AcademicYear)
            .where(AcademicYear.school_id == UUID(school_id))
            .order_by(AcademicYear.year.desc())
        ).scalars().first()
    
    current_term = None
    if current_year:  # Check if current_year exists
        current_term = db.execute(
            select(AcademicTerm)
            .where(
                AcademicTerm.school_id == UUID(school_id),
                AcademicTerm.academic_year_id == current_year.id,  # FIXED: Changed from year_id
                AcademicTerm.state == "ACTIVE"
            )
            .order_by(AcademicTerm.term.desc())
        ).scalars().first()
        
        if not current_term:
            current_term = db.execute(
                select(AcademicTerm)
                .where(
                    AcademicTerm.school_id == UUID(school_id),
                    AcademicTerm.academic_year_id == current_year.id  # FIXED: Changed from year_id
                )
                .order_by(AcademicTerm.term.desc())
            ).scalars().first()
    
    return {
        "current_year": AcademicYearOut.model_validate(current_year) if current_year else None,
        "current_term": AcademicTermOut.model_validate(current_term) if current_term else None,
        "setup_complete": bool(current_year and current_term),
        "needs_year": not current_year,
        "needs_term": current_year and not current_term
    }


@router.put("/years/{year_id}/activate")
async def activate_academic_year(
    year_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Activate an academic year (set as current)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        year_uuid = UUID(year_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid academic year ID format"
        )
    
    # Find the year
    year = db.execute(
        select(AcademicYear).where(
            AcademicYear.id == year_uuid,
            AcademicYear.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found"
        )
    
    # Deactivate ALL other years for this school FIRST
    all_years = db.execute(
        select(AcademicYear).where(AcademicYear.school_id == UUID(school_id))
    ).scalars().all()
    
    for y in all_years:
        if y.id != year_uuid:
            y.state = "INACTIVE" if y.state == "ACTIVE" else "DRAFT"
    
    # Activate the target year
    year.state = "ACTIVE"
    
    try:
        db.commit()
        logger.info(f"Academic year {year.year} activated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error activating academic year: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating academic year"
        )
    
    return {"message": f"Academic year {year.year} activated successfully"}


@router.put("/years/{year_id}/deactivate")
async def deactivate_academic_year(
    year_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Deactivate an academic year (set to DRAFT or INACTIVE)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        year_uuid = UUID(year_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid academic year ID format"
        )
    
    year = db.execute(
        select(AcademicYear).where(
            AcademicYear.id == year_uuid,
            AcademicYear.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found"
        )
    
    # Check if it has been used (has terms/enrollments)
    has_terms = db.execute(
        select(AcademicTerm).where(AcademicTerm.academic_year_id == year_uuid)  # FIXED
    ).first() is not None
    
    # Set appropriate state based on usage
    if has_terms:
        year.state = "INACTIVE"  # Was used, now closed
    else:
        year.state = "DRAFT"     # Never used, back to draft
    
    try:
        db.commit()
        logger.info(f"Academic year {year.year} deactivated to {year.state} by {user.email}")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating academic year"
        )
    
    return {"message": f"Academic year {year.year} deactivated successfully"}

@router.post("/terms/{term_id}/promote-students")
async def promote_students_to_next_term(
    term_id: str,
    promotion_data: dict,  # {target_term_id: str, student_ids?: List[str], class_mappings?: dict}
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Promote students from current term to next term with optional class changes"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        current_term_uuid = UUID(term_id)
        target_term_uuid = UUID(promotion_data["target_term_id"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid term ID format"
        )
    
    # Verify both terms exist
    current_term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == current_term_uuid,
            AcademicTerm.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    target_term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.id == target_term_uuid,
            AcademicTerm.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not current_term or not target_term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source or target term not found"
        )
    
    # Get students to promote (specific list or all enrolled)
    student_ids = promotion_data.get("student_ids")
    if student_ids:
        # Promote specific students
        enrollments_query = select(Enrollment).where(
            Enrollment.term_id == current_term_uuid,
            Enrollment.student_id.in_([UUID(sid) for sid in student_ids]),
            Enrollment.status == "ENROLLED"
        )
    else:
        # Promote all students from current term
        enrollments_query = select(Enrollment).where(
            Enrollment.term_id == current_term_uuid,
            Enrollment.status == "ENROLLED"
        )
    
    current_enrollments = db.execute(enrollments_query).scalars().all()
    
    if not current_enrollments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eligible students found for promotion"
        )
    
    # Class mappings for promotion (e.g., Grade 3 → Grade 4)
    class_mappings = promotion_data.get("class_mappings", {})
    promoted_count = 0
    
    try:
        for enrollment in current_enrollments:
            # Determine target class
            current_class_id = str(enrollment.class_id)
            target_class_id = class_mappings.get(current_class_id, current_class_id)
            
            # Check if student already enrolled in target term
            existing_enrollment = db.execute(
                select(Enrollment).where(
                    Enrollment.student_id == enrollment.student_id,
                    Enrollment.term_id == target_term_uuid
                )
            ).scalar_one_or_none()
            
            if existing_enrollment:
                # Update existing enrollment
                existing_enrollment.class_id = UUID(target_class_id)
                existing_enrollment.status = "ENROLLED"
                existing_enrollment.joined_on = date.today()
            else:
                # Create new enrollment
                new_enrollment = Enrollment(
                    school_id=UUID(school_id),
                    student_id=enrollment.student_id,
                    class_id=UUID(target_class_id),
                    term_id=target_term_uuid,
                    status="ENROLLED",
                    joined_on=date.today()
                )
                db.add(new_enrollment)
            
            promoted_count += 1
        
        db.commit()
        logger.info(f"{promoted_count} students promoted from {current_term.title} to {target_term.title} by {user.email}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error promoting students: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error promoting students"
        )
    
    return {
        "message": f"Successfully promoted {promoted_count} students from {current_term.title} to {target_term.title}",
        "promoted_count": promoted_count
    }


@router.put("/terms/{academic_year}/{term}/complete")
async def complete_term(
    academic_year: int,
    term: int,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Mark a term as completed"""
    school_id = ctx["school_id"]
    
    # First find the academic year
    year_obj = db.execute(
        select(AcademicYear).where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.year == academic_year
        )
    ).scalar_one_or_none()
    
    if not year_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic year {academic_year} not found"
        )
    
    # Now find the term using academic_year_id
    term_obj = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == year_obj.id,  # FIXED
            AcademicTerm.term == term
        )
    ).scalar_one_or_none()
    
    if not term_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Term {term} not found for academic year {academic_year}"
        )
    
    # Update state to CLOSED
    term_obj.state = "CLOSED"
    db.commit()
    db.refresh(term_obj)
    
    return {
        "message": f"Term {term} for {academic_year} has been closed",
        "term_id": str(term_obj.id),
        "state": term_obj.state
    }

@router.post("/terms", response_model=AcademicTermOut, status_code=status.HTTP_201_CREATED)
async def create_term(
    term_data: AcademicTermCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new academic term"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Get the academic year
    year_obj = db.execute(
        select(AcademicYear).where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.year == term_data.academic_year
        )
    ).scalar_one_or_none()
    
    if not year_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic year {term_data.academic_year} not found"
        )
    
    if year_obj.state != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Academic year {term_data.academic_year} is {year_obj.state}. Terms can only be created in ACTIVE years."
        )
    
    # Check if term already exists
    existing_term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == year_obj.id,  # FIXED
            AcademicTerm.term == term_data.term
        )
    ).scalar_one_or_none()
    
    if existing_term:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Term {term_data.term} already exists for {term_data.academic_year}"
        )
    
    # Create term
    new_term = AcademicTerm(
        school_id=UUID(school_id),
        academic_year_id=year_obj.id,  # FIXED
        term=term_data.term,
        title=term_data.title,
        start_date=term_data.start_date,
        end_date=term_data.end_date,
        state="PLANNED"
    )
    
    try:
        db.add(new_term)
        db.commit()
        db.refresh(new_term)
        logger.info(f"Term {new_term.term} created for year {year_obj.year} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating term: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating term"
        )
    
    return new_term


@router.get("/current-term")
async def get_current_term_simple(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get the current active academic term"""
    school_id = ctx["school_id"]
    
    # First get the active academic year
    active_year = db.execute(
        select(AcademicYear).where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
    ).scalar_one_or_none()
    
    if not active_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active academic year found"
        )
    
    # Get the active term for this year
    active_term = db.execute(
        select(AcademicTerm).where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == active_year.id,  # FIXED
            AcademicTerm.state == "ACTIVE"
        )
    ).scalar_one_or_none()
    
    if not active_term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active term found"
        )
    
    return {
        "id": str(active_term.id),
        "term": active_term.term,
        "title": active_term.title,
        "state": active_term.state,
        "academic_year": active_year.year,
        "start_date": active_term.start_date,
        "end_date": active_term.end_date
    }


@router.get("/current-year")
async def get_current_academic_year(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get the current active academic year"""
    school_id = ctx["school_id"]
    
    # Get the active academic year
    active_year = db.execute(
        select(AcademicYear).where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
    ).scalar_one_or_none()
    
    if not active_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active academic year found"
        )
    
    return {
        "id": str(active_year.id),
        "year": active_year.year,
        "title": active_year.title,
        "state": active_year.state,
        "start_date": active_year.start_date,
        "end_date": active_year.end_date
    }


# ==================== ACADEMIC STATUS (for UI status bar) ====================

@router.get("/status")
async def get_academic_status(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get current academic status for the status bar UI"""
    school_id = ctx["school_id"]
    
    current_year = db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
        .order_by(AcademicYear.year.desc())
    ).scalars().first()
    
    if not current_year:
        current_year = db.execute(
            select(AcademicYear)
            .where(AcademicYear.school_id == UUID(school_id))
            .order_by(AcademicYear.year.desc())
        ).scalars().first()
    
    active_term = None
    if current_year:
        active_term = db.execute(
            select(AcademicTerm)
            .where(
                AcademicTerm.school_id == UUID(school_id),
                AcademicTerm.academic_year_id == current_year.id,
                AcademicTerm.state == "ACTIVE"
            )
            .order_by(AcademicTerm.term.desc())
        ).scalars().first()
        
        if not active_term:
            active_term = db.execute(
                select(AcademicTerm)
                .where(
                    AcademicTerm.school_id == UUID(school_id),
                    AcademicTerm.academic_year_id == current_year.id
                )
                .order_by(AcademicTerm.term.desc())
            ).scalars().first()
    
    has_classes = db.execute(
        select(func.count(Class.id))
        .where(Class.school_id == UUID(school_id))
    ).scalar() > 0
    
    warnings = []
    if not current_year:
        warnings.append("No academic year configured. Create one to get started.")
    elif current_year.state != "ACTIVE":
        warnings.append(f"Academic year {current_year.year} is {current_year.state}. Please activate it.")
    
    if current_year and not active_term:
        warnings.append(f"No active term for {current_year.year}. Create and activate a term.")
    elif active_term and active_term.state != "ACTIVE":
        warnings.append(f"Term {active_term.term} is {active_term.state}. Please activate it.")
    
    if not has_classes:
        warnings.append("No classes created. Students need classes for enrollment.")
    
    setup_complete = (
        current_year is not None and 
        current_year.state == "ACTIVE" and
        active_term is not None and 
        active_term.state == "ACTIVE" and
        has_classes
    )
    
    # Build response with proper null checking
    response = {
        "academic_year": None,
        "active_term": None,
        "has_classes": has_classes,
        "setup_complete": setup_complete,
        "warnings": warnings
    }
    
    # Only add academic_year data if it exists
    if current_year:
        response["academic_year"] = {
            "id": str(current_year.id),
            "name": current_year.title or f"Academic Year {current_year.year}",
            "year": current_year.year,
            "start_date": current_year.start_date.isoformat() if current_year.start_date else None,
            "end_date": current_year.end_date.isoformat() if current_year.end_date else None,
            "state": current_year.state
        }
    
    # Only add active_term data if it exists
    if active_term:
        response["active_term"] = {
            "id": str(active_term.id),
            "name": active_term.title,
            "term": active_term.term,
            "start_date": active_term.start_date.isoformat() if active_term.start_date else None,
            "end_date": active_term.end_date.isoformat() if active_term.end_date else None,
            "state": active_term.state
        }
    
    return response