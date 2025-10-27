# app/api/routers/enrollments.py - Fixed imports
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Any
from uuid import UUID
from datetime import date
import logging

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.enrollment import Enrollment
from app.models.academic import AcademicTerm, AcademicYear
from app.models.student import Student
from app.models.class_model import Class
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut  # FIXED: Import from correct location

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    enrollment_data: EnrollmentCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new enrollment for a student in a class for a term"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Verify student exists
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
    
    # Verify class exists
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
    
    # Verify term exists
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
    
    # Check if student is already enrolled in this term
    existing = db.execute(
        select(Enrollment).where(
            Enrollment.school_id == UUID(school_id),
            Enrollment.student_id == enrollment_data.student_id,
            Enrollment.term_id == enrollment_data.term_id
        )
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student already enrolled in a class for this term"
        )
    
    # Create enrollment
    new_enrollment = Enrollment(
        school_id=UUID(school_id),
        student_id=enrollment_data.student_id,
        class_id=enrollment_data.class_id,
        term_id=enrollment_data.term_id,
        status="ENROLLED",
        enrolled_date=enrollment_data.enrolled_date or date.today()
    )
    
    try:
        db.add(new_enrollment)
        db.commit()
        db.refresh(new_enrollment)
        logger.info(f"Enrollment created: Student {student.admission_no} in {class_obj.name} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating enrollment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating enrollment"
        )
    
    return EnrollmentOut(
        id=new_enrollment.id,
        student_id=new_enrollment.student_id,
        class_id=new_enrollment.class_id,
        term_id=new_enrollment.term_id,
        status=new_enrollment.status,
        enrolled_date=new_enrollment.enrolled_date,
        withdrawn_date=new_enrollment.withdrawn_date,
        invoice_generated=new_enrollment.invoice_generated
    )