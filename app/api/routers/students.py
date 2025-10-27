# app/api/routers/students.py - Fixed imports
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, or_, and_
from typing import Dict, Any, List, Optional
from uuid import UUID
import logging
import requests
from datetime import date

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.student import Student
from app.models.class_model import Class
from app.models.academic import AcademicYear, AcademicTerm
# FIXED: Import Enrollment from enrollment.py, not academic.py
from app.models.enrollment import Enrollment
from app.schemas.student import (
    StudentCreate, 
    StudentOut, 
    StudentList, 
    StudentDetail,
    StudentUpdate,
    StudentSearch
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Helper function to get current academic setup
async def get_current_academic_setup(db: Session, school_id: str) -> tuple:
    """Get current academic year and term - handle PLANNED terms gracefully"""
    
    # Get ACTIVE academic year ONLY
    current_year = db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == UUID(school_id),
            AcademicYear.state == "ACTIVE"
        )
        .order_by(AcademicYear.year.desc())
    ).scalars().first()
    
    if not current_year:
        return None, None
    
    # First try to get ACTIVE term
    # FIXED: Changed year_id to academic_year_id
    current_term = db.execute(
        select(AcademicTerm)
        .where(
            AcademicTerm.school_id == UUID(school_id),
            AcademicTerm.academic_year_id == current_year.id,  # FIXED
            AcademicTerm.state == "ACTIVE"
        )
        .order_by(AcademicTerm.term.desc())
    ).scalars().first()
    
    # If no ACTIVE term, use the most recent PLANNED term
    if not current_term:
        current_term = db.execute(
            select(AcademicTerm)
            .where(
                AcademicTerm.school_id == UUID(school_id),
                AcademicTerm.academic_year_id == current_year.id,  # FIXED
                AcademicTerm.state == "PLANNED"
            )
            .order_by(AcademicTerm.term.desc())
        ).scalars().first()
    
    return current_year, current_term

@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """
    Create a new student and automatically enroll them in the specified class
    for the current academic term
    """
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # NORMALIZE: Strip all # prefixes from admission number before storing
    clean_admission_no = str(student_data.admission_no).lstrip("#").strip()
    
    # Check if admission number is unique within the school
    existing_student = db.execute(
        select(Student).where(
            Student.school_id == UUID(school_id),
            Student.admission_no == clean_admission_no
        )
    ).scalar_one_or_none()
    
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with admission number {clean_admission_no} already exists"
        )
    
    # Get current academic setup
    current_year, current_term = await get_current_academic_setup(db, school_id)
    
    if not current_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No academic year found. Please create an academic year first."
        )
    
    if not current_term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No academic term found for {current_year.year}. Please create an academic term first."
        )
    
    # Verify class exists if provided
    class_obj = None
    if student_data.class_id:
        class_obj = db.execute(
            select(Class).where(
                Class.id == student_data.class_id,
                Class.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
        
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified class does not exist"
            )
        
        # Verify class belongs to the current academic year
        if class_obj.academic_year != current_year.year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Class {class_obj.name} is for academic year {class_obj.academic_year}, but current year is {current_year.year}"
            )
    
    # Create student with cleaned admission number
    new_student = Student(
        school_id=UUID(school_id),
        admission_no=clean_admission_no,  # Store without # prefix
        first_name=student_data.first_name,
        last_name=student_data.last_name,
        gender=student_data.gender,
        dob=student_data.dob,
        class_id=student_data.class_id,
        status="ACTIVE"
    )
    
    db.add(new_student)
    
    try:
        db.flush()  # Get the student ID without committing
        
        # If class is provided, create enrollment record
        enrollment = None
        if class_obj:
            enrollment = Enrollment(
                school_id=UUID(school_id),
                student_id=new_student.id,
                class_id=class_obj.id,
                term_id=current_term.id,
                status="ENROLLED",
                enrolled_date=date.today()
            )
            db.add(enrollment)
        
        db.commit()
        db.refresh(new_student)
        
        logger.info(f"Student created: {new_student.admission_no} by {user.email}")
        if enrollment:
            logger.info(f"Student enrolled in {class_obj.name} for {current_term.title}")
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating student"
        )
    
    # Load class information for response
    class_name = class_obj.name if class_obj else None
    
    return StudentOut(
        id=new_student.id,
        admission_no=new_student.admission_no,
        first_name=new_student.first_name,
        last_name=new_student.last_name,
        full_name=f"{new_student.first_name} {new_student.last_name}".strip(),
        gender=new_student.gender,
        dob=new_student.dob,
        class_id=new_student.class_id,
        class_name=class_name,
        status=new_student.status,
        created_at=new_student.created_at
    )

@router.get("/", response_model=StudentList)
async def get_students(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name (partial match)"),
    admission_no: Optional[str] = Query(None, description="Search by exact admission number"),
    class_id: Optional[str] = Query(None, description="Filter by class ID"),
    term_id: Optional[str] = Query(None, description="Filter by term (shows enrolled students)"),
    status: Optional[str] = Query(None),
    unassigned: Optional[bool] = Query(False, description="Show students not enrolled in current term")
):
    """Get students with filtering and pagination, including enrollment-aware filtering"""
    school_id = ctx["school_id"]
    
    # Get current term if not specified and unassigned filter is requested
    current_term = None
    if unassigned or not term_id:
        _, current_term = await get_current_academic_setup(db, school_id)
        if not current_term and unassigned:
            pass
    
    # Base query - different approach based on filters
    if unassigned and current_term:
        enrolled_student_ids = db.execute(
            select(Enrollment.student_id).where(
                Enrollment.school_id == UUID(school_id),
                Enrollment.term_id == current_term.id,
                Enrollment.status == "ENROLLED"
            )
        ).scalars().all()
        
        query = (
            select(Student, Class.name.label("class_name"))
            .outerjoin(Class, Student.class_id == Class.id)
            .where(
                Student.school_id == UUID(school_id),
                ~Student.id.in_(enrolled_student_ids) if enrolled_student_ids else True
            )
        )
        
    elif term_id:
        try:
            term_uuid = UUID(term_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid term ID format"
            )
        
        query = (
            select(Student, Class.name.label("class_name"))
            .join(Enrollment, Student.id == Enrollment.student_id)
            .outerjoin(Class, Enrollment.class_id == Class.id)
            .where(
                Student.school_id == UUID(school_id),
                Enrollment.term_id == term_uuid,
                Enrollment.status == "ENROLLED"
            )
        )
        
    else:
        query = (
            select(Student, Class.name.label("class_name"))
            .outerjoin(Class, Student.class_id == Class.id)
            .where(Student.school_id == UUID(school_id))
        )
    
    # Apply additional filters with normalization
    if admission_no:
        # NORMALIZE: Strip # prefix from search term
        clean_admission_no = str(admission_no).lstrip("#").strip()
        query = query.where(Student.admission_no == clean_admission_no)
    elif search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Student.first_name.ilike(search_term),
                Student.last_name.ilike(search_term),
                func.concat(Student.first_name, ' ', Student.last_name).ilike(search_term)
            )
        )
    
    if class_id and not term_id:
        try:
            query = query.where(Student.class_id == UUID(class_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid class ID format"
            )
    
    if status:
        query = query.where(Student.status == status)
    
    # Order results
    if admission_no:
        query = query.order_by(Student.admission_no)
    elif search:
        query = query.order_by(
            func.lower(Student.first_name) != search.lower(),
            func.lower(Student.last_name) != search.lower(),
            Student.first_name, 
            Student.last_name
        )
    else:
        query = query.order_by(Student.first_name, Student.last_name)
    
    # Get total count
    total_query = query.with_only_columns(Student.id)
    total = len(db.execute(total_query).scalars().all())
    
    # Apply pagination
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).all()
    
    # Format results
    students = []
    for student, class_name in results:
        students.append(StudentOut(
            id=student.id,
            admission_no=student.admission_no,
            first_name=student.first_name,
            last_name=student.last_name,
            full_name=f"{student.first_name} {student.last_name}".strip(),
            gender=student.gender,
            dob=student.dob,
            class_id=student.class_id,
            class_name=class_name,
            status=student.status,
            created_at=student.created_at
        ))
    
    has_next = total > page * limit
    
    return StudentList(
        students=students,
        total=total,
        page=page,
        limit=limit,
        has_next=has_next
    )

@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(
    student_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get student details including current enrollment - accepts UUID or admission number"""
    school_id = ctx["school_id"]
    
    # Try to parse as UUID first
    try:
        student_uuid = UUID(student_id)
        # Search by UUID
        result = db.execute(
            select(Student, Class.name.label("class_name"))
            .outerjoin(Class, Student.class_id == Class.id)
            .where(
                Student.id == student_uuid,
                Student.school_id == UUID(school_id)
            )
        ).first()
    except ValueError:
        # Not a UUID, treat as admission number
        # NORMALIZE: Strip # prefix from admission number
        clean_admission_no = str(student_id).lstrip("#").strip()
        
        logger.info(f"Looking up student by admission number: {clean_admission_no}")
        
        result = db.execute(
            select(Student, Class.name.label("class_name"))
            .outerjoin(Class, Student.class_id == Class.id)
            .where(
                Student.admission_no == clean_admission_no,
                Student.school_id == UUID(school_id)
            )
        ).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found"
        )
    
    student, class_name = result
    
    # Get current enrollment info
    _, current_term = await get_current_academic_setup(db, school_id)
    current_enrollment = None
    
    if current_term:
        current_enrollment = db.execute(
            select(Enrollment, Class.name.label("enrolled_class_name"))
            .join(Class, Enrollment.class_id == Class.id)
            .where(
                Enrollment.student_id == student.id,  # Use student.id (UUID)
                Enrollment.term_id == current_term.id,
                Enrollment.status == "ENROLLED"
            )
        ).first()
    
    return StudentDetail(
        id=student.id,
        admission_no=student.admission_no,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=f"{student.first_name} {student.last_name}".strip(),
        gender=student.gender,
        dob=student.dob,
        class_id=student.class_id,
        class_name=class_name,
        status=student.status,
        created_at=student.created_at,
        updated_at=student.updated_at,
        # Additional enrollment info
        current_enrollment={
            "class_name": current_enrollment[1] if current_enrollment else None,
            "term_id": str(current_term.id) if current_term else None,
            "term_title": current_term.title if current_term else None,
            "enrolled": bool(current_enrollment)
        } if current_term else None
    )

@router.post("/{student_id}/enroll")
async def enroll_student(
    student_id: str,
    enrollment_data: dict,  # {class_id: str, term_id?: str}
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Enroll an existing student in a class for a specific term"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        student_uuid = UUID(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid student ID format"
        )
    
    # Get student
    student = db.execute(
        select(Student).where(
            Student.id == student_uuid,
            Student.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get class
    try:
        class_uuid = UUID(enrollment_data["class_id"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing class_id"
        )
    
    class_obj = db.execute(
        select(Class).where(
            Class.id == class_uuid,
            Class.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Get term (use current if not specified)
    term_id = enrollment_data.get("term_id")
    if term_id:
        try:
            term_uuid = UUID(term_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid term ID format"
            )
        
        term = db.execute(
            select(AcademicTerm).where(
                AcademicTerm.id == term_uuid,
                AcademicTerm.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
    else:
        _, term = await get_current_academic_setup(db, school_id)
        term_uuid = term.id if term else None
    
    if not term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No term specified and no current term found"
        )
    
    # Check if already enrolled for this term
    existing_enrollment = db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_uuid,
            Enrollment.term_id == term_uuid,
            Enrollment.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if existing_enrollment:
        if existing_enrollment.status == "ENROLLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student is already enrolled for {term.title}"
            )
        else:
            # Reactivate existing enrollment
            existing_enrollment.status = "ENROLLED"
            existing_enrollment.class_id = class_uuid
            existing_enrollment.enrolled_date = date.today()
    else:
        # Create new enrollment
        new_enrollment = Enrollment(
            school_id=UUID(school_id),
            student_id=student_uuid,
            class_id=class_uuid,
            term_id=term_uuid,
            status="ENROLLED",
            enrolled_date=date.today()
        )
        db.add(new_enrollment)
    
    # Update student's class_id for backward compatibility
    student.class_id = class_uuid
    
    try:
        db.commit()
        logger.info(f"Student {student.admission_no} enrolled in {class_obj.name} for {term.title} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error enrolling student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error enrolling student"
        )
    
    return {
        "message": f"Student {student.first_name} {student.last_name} successfully enrolled in {class_obj.name} for {term.title}"
    }

# Add unassigned students endpoint
@router.get("/unassigned/current-term", response_model=StudentList)
async def get_unassigned_students(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """Get students not enrolled in the current academic term"""
    school_id = ctx["school_id"]
    
    # Get current term
    _, current_term = await get_current_academic_setup(db, school_id)
    
    if not current_term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current academic term found. Please set up academic year and terms first."
        )
    
    # Get enrolled student IDs for current term
    enrolled_student_ids = db.execute(
        select(Enrollment.student_id).where(
            Enrollment.school_id == UUID(school_id),
            Enrollment.term_id == current_term.id,
            Enrollment.status == "ENROLLED"
        )
    ).scalars().all()
    
    # Query for students NOT in the enrolled list
    query = (
        select(Student, Class.name.label("class_name"))
        .outerjoin(Class, Student.class_id == Class.id)
        .where(
            Student.school_id == UUID(school_id),
            Student.status == "ACTIVE"
        )
    )
    
    if enrolled_student_ids:
        query = query.where(~Student.id.in_(enrolled_student_ids))
    
    query = query.order_by(Student.first_name, Student.last_name)
    
    # Get total count
    total_query = query.with_only_columns(Student.id)
    total = len(db.execute(total_query).scalars().all())
    
    # Apply pagination
    offset = (page - 1) * limit
    results = db.execute(query.offset(offset).limit(limit)).all()
    
    # Format results
    students = []
    for student, class_name in results:
        students.append(StudentOut(
            id=student.id,
            admission_no=student.admission_no,
            first_name=student.first_name,
            last_name=student.last_name,
            full_name=f"{student.first_name} {student.last_name}".strip(),
            gender=student.gender,
            dob=student.dob,
            class_id=student.class_id,
            class_name=class_name,
            status=student.status,
            created_at=student.created_at
        ))
    
    has_next = total > page * limit
    
    return StudentList(
        students=students,
        total=total,
        page=page,
        limit=limit,
        has_next=has_next
    )

# Keep the existing update and delete methods with minor modifications
@router.put("/{student_id}", response_model=StudentOut)
async def update_student(
    student_id: str,
    student_data: StudentUpdate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update student information - accepts UUID or admission number"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Try to parse as UUID first
    try:
        student_uuid = UUID(student_id)
        student = db.execute(
            select(Student).where(
                Student.id == student_uuid,
                Student.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
    except ValueError:
        # Not a UUID, treat as admission number
        clean_admission_no = str(student_id).lstrip("#").strip()
        student = db.execute(
            select(Student).where(
                Student.admission_no == clean_admission_no,
                Student.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found"
        )
    
    student_uuid = student.id
    
    # Check admission number uniqueness if being changed
    if (student_data.admission_no and 
        student_data.admission_no != student.admission_no):
        
        existing_student = db.execute(
            select(Student).where(
                Student.school_id == UUID(school_id),
                Student.admission_no == student_data.admission_no,
                Student.id != student_uuid
            )
        ).scalar_one_or_none()
        
        if existing_student:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student with admission number {student_data.admission_no} already exists"
            )
    
    # If class is being changed, update current enrollment
    if student_data.class_id and student_data.class_id != student.class_id:
        # Verify new class exists
        new_class = db.execute(
            select(Class).where(
                Class.id == student_data.class_id,
                Class.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
        
        if not new_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified class does not exist"
            )
        
        # Update current enrollment if exists
        _, current_term = await get_current_academic_setup(db, school_id)
        if current_term:
            current_enrollment = db.execute(
                select(Enrollment).where(
                    Enrollment.student_id == student_uuid,
                    Enrollment.term_id == current_term.id,
                    Enrollment.status == "ENROLLED"
                )
            ).scalar_one_or_none()
            
            if current_enrollment:
                current_enrollment.class_id = student_data.class_id
    
    # Update student fields
    update_data = student_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(student, field, value)
    
    try:
        db.commit()
        db.refresh(student)
        logger.info(f"Student updated: {student.admission_no} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating student"
        )
    
    # Load class information for response
    if student.class_id:
        class_info = db.get(Class, student.class_id)
        class_name = class_info.name if class_info else None
    else:
        class_name = None
    
    return StudentOut(
        id=student.id,
        admission_no=student.admission_no,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=f"{student.first_name} {student.last_name}".strip(),
        gender=student.gender,
        dob=student.dob,
        class_id=student.class_id,
        class_name=class_name,
        status=student.status,
        created_at=student.created_at
    )

@router.delete("/{student_id}")
async def delete_student(
    student_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete a student - accepts UUID or admission number"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Try to parse as UUID first
    try:
        student_uuid = UUID(student_id)
        student = db.execute(
            select(Student).where(
                Student.id == student_uuid,
                Student.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
    except ValueError:
        # Not a UUID, treat as admission number
        clean_admission_no = str(student_id).lstrip("#").strip()
        student = db.execute(
            select(Student).where(
                Student.admission_no == clean_admission_no,
                Student.school_id == UUID(school_id)
            )
        ).scalar_one_or_none()
        student_uuid = student.id if student else None
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found"
        )
    
    # Soft delete by changing status
    student.status = "DELETED"
    
    # Also update any current enrollments
    current_enrollments = db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_uuid,
            Enrollment.status == "ENROLLED"
        )
    ).scalars().all()
    
    for enrollment in current_enrollments:
        enrollment.status = "DROPPED"
        enrollment.left_on = date.today()
    
    try:
        db.commit()
        logger.info(f"Student deleted: {student.admission_no} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting student"
        )
    
    return {"message": "Student deleted successfully"}

@router.post("/search", response_model=List[StudentOut])
async def search_students(
    search_data: StudentSearch,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Advanced student search"""
    school_id = ctx["school_id"]
    
    query = (
        select(Student, Class.name.label("class_name"))
        .outerjoin(Class, Student.class_id == Class.id)
        .where(Student.school_id == UUID(school_id))
    )
    
    # Apply search filters
    if search_data.admission_no:
        query = query.where(Student.admission_no.ilike(f"%{search_data.admission_no}%"))
    
    if search_data.first_name:
        query = query.where(Student.first_name.ilike(f"%{search_data.first_name}%"))
    
    if search_data.last_name:
        query = query.where(Student.last_name.ilike(f"%{search_data.last_name}%"))
    
    if search_data.class_id:
        query = query.where(Student.class_id == search_data.class_id)
    
    if search_data.status:
        query = query.where(Student.status == search_data.status)
    
    # Limit results to prevent overload
    results = db.execute(query.limit(50)).all()
    
    students = []
    for student, class_name in results:
        students.append(StudentOut(
            id=student.id,
            admission_no=student.admission_no,
            first_name=student.first_name,
            last_name=student.last_name,
            full_name=f"{student.first_name} {student.last_name}".strip(),
            gender=student.gender,
            dob=student.dob,
            class_id=student.class_id,
            class_name=class_name,
            status=student.status,
            created_at=student.created_at
        ))
    
    return students