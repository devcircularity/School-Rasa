#app/api/routers/guardians.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from typing import List, Optional
from uuid import UUID
import logging

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.guardian import Guardian, StudentGuardian
from app.models.student import Student
from app.schemas.guardian import GuardianCreate, GuardianOut, GuardianDetail, StudentGuardianLink
from app.schemas.guardian import GuardianUpdate 

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=GuardianOut, status_code=status.HTTP_201_CREATED)
async def create_guardian(
    data: GuardianCreate,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a guardian and optionally link to a student"""
    school_id = UUID(ctx["school_id"])
    user = ctx["user"]
    
    # Create guardian
    guardian = Guardian(
        school_id=school_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        relationship=data.relationship
    )
    
    db.add(guardian)
    db.flush()
    
    # If student_id provided, link guardian to student
    if data.student_id:
        student = db.execute(
            select(Student).where(
                Student.id == data.student_id,
                Student.school_id == school_id
            )
        ).scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        # Create link
        link = StudentGuardian(
            school_id=school_id,
            student_id=data.student_id,
            guardian_id=guardian.id
        )
        db.add(link)
        
        # If this is the first guardian, set as primary
        if not student.primary_guardian_id:
            student.primary_guardian_id = guardian.id
    
    db.commit()
    db.refresh(guardian)
    
    logger.info(f"Guardian created: {guardian.first_name} {guardian.last_name} by {user.email}")
    
    return GuardianOut(
        id=guardian.id,
        first_name=guardian.first_name,
        last_name=guardian.last_name,
        full_name=f"{guardian.first_name} {guardian.last_name}",
        email=guardian.email,
        phone=guardian.phone,
        relationship=guardian.relationship,
        created_at=guardian.created_at
    )

@router.get("/", response_model=List[GuardianDetail])
async def list_all_guardians(
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get all guardians in the school with their linked students"""
    school_id = UUID(ctx["school_id"])
    
    # Get all guardians for this school
    guardians = db.execute(
        select(Guardian).where(
            Guardian.school_id == school_id
        ).order_by(Guardian.last_name, Guardian.first_name)
    ).scalars().all()
    
    result = []
    for guardian in guardians:
        # Get all students linked to this guardian
        student_links = db.execute(
            select(Student, StudentGuardian)
            .join(StudentGuardian, Student.id == StudentGuardian.student_id)
            .where(
                StudentGuardian.guardian_id == guardian.id,
                Student.school_id == school_id
            )
        ).all()
        
        # Build list of students with primary status
        students_info = []
        for student, link in student_links:
            students_info.append({
                "id": str(student.id),
                "full_name": f"{student.first_name} {student.last_name}",
                "admission_no": student.admission_no,
                "is_primary": (student.primary_guardian_id == guardian.id)
            })
        
        # Check if this guardian is primary for any student
        is_primary = any(s["is_primary"] for s in students_info)
        
        result.append(GuardianDetail(
            id=guardian.id,
            first_name=guardian.first_name,
            last_name=guardian.last_name,
            full_name=f"{guardian.first_name} {guardian.last_name}",
            email=guardian.email,
            phone=guardian.phone,
            relationship=guardian.relationship,
            is_primary=is_primary,
            created_at=guardian.created_at,
            students=students_info  # Add this field
        ))
    
    return result

@router.get("/student/{student_id}", response_model=List[GuardianDetail])
async def get_student_guardians(
    student_id: UUID,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get all guardians for a specific student"""
    school_id = UUID(ctx["school_id"])
    
    # Verify student exists
    student = db.execute(
        select(Student).where(
            Student.id == student_id,
            Student.school_id == school_id
        )
    ).scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get ALL guardians linked to this student
    results = db.execute(
        select(Guardian, StudentGuardian)
        .join(StudentGuardian, Guardian.id == StudentGuardian.guardian_id)
        .where(
            StudentGuardian.student_id == student_id,
            Guardian.school_id == school_id  # IMPORTANT: Use Guardian.school_id
        )
    ).all()
    
    guardians = []
    for guardian, link in results:
        is_primary = (student.primary_guardian_id == guardian.id)
        guardians.append(GuardianDetail(
            id=guardian.id,
            first_name=guardian.first_name,
            last_name=guardian.last_name,
            full_name=f"{guardian.first_name} {guardian.last_name}",
            email=guardian.email,
            phone=guardian.phone,
            relationship=guardian.relationship,
            is_primary=is_primary,
            created_at=guardian.created_at
        ))
    
    return guardians

@router.get("/unlinked-students", response_model=List[dict])
async def get_students_without_guardians(
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get students who have no guardians linked"""
    school_id = UUID(ctx["school_id"])
    
    # Get all student IDs with guardians
    students_with_guardians = db.execute(
        select(StudentGuardian.student_id).where(
            StudentGuardian.school_id == school_id
        )
    ).scalars().all()
    
    # Get students NOT in that list
    query = select(Student).where(
        Student.school_id == school_id,
        Student.status == "ACTIVE"
    )
    
    if students_with_guardians:
        query = query.where(~Student.id.in_(students_with_guardians))
    
    students = db.execute(query).scalars().all()
    
    return [
        {
            "id": str(student.id),
            "admission_no": student.admission_no,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "full_name": f"{student.first_name} {student.last_name}"
        }
        for student in students
    ]

@router.post("/link", status_code=status.HTTP_201_CREATED)
async def link_guardian_to_student(
    data: StudentGuardianLink,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Link an existing guardian to a student"""
    school_id = UUID(ctx["school_id"])
    
    # Verify both exist
    student = db.get(Student, data.student_id)
    guardian = db.get(Guardian, data.guardian_id)
    
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if not guardian or guardian.school_id != school_id:
        raise HTTPException(status_code=404, detail="Guardian not found")
    
    # Check if link already exists
    existing = db.execute(
        select(StudentGuardian).where(
            StudentGuardian.student_id == data.student_id,
            StudentGuardian.guardian_id == data.guardian_id
        )
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=409, detail="Guardian already linked to this student")
    
    # Create link
    link = StudentGuardian(
        school_id=school_id,
        student_id=data.student_id,
        guardian_id=data.guardian_id
    )
    db.add(link)
    
    # Set as primary if first guardian
    if not student.primary_guardian_id and data.set_as_primary:
        student.primary_guardian_id = data.guardian_id
    
    db.commit()
    
    return {"message": "Guardian linked successfully"}

@router.put("/{guardian_id}", response_model=GuardianOut)
async def update_guardian(
    guardian_id: UUID,
    data: GuardianUpdate,
    ctx: dict = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update guardian contact information"""
    school_id = UUID(ctx["school_id"])
    user = ctx["user"]
    
    guardian = db.execute(
        select(Guardian).where(
            Guardian.id == guardian_id,
            Guardian.school_id == school_id
        )
    ).scalar_one_or_none()
    
    if not guardian:
        raise HTTPException(status_code=404, detail="Guardian not found")
    
    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(guardian, field, value)
    
    db.commit()
    db.refresh(guardian)
    
    logger.info(f"Guardian updated: {guardian.first_name} {guardian.last_name} by {user.email}")
    
    return GuardianOut(
        id=guardian.id,
        first_name=guardian.first_name,
        last_name=guardian.last_name,
        full_name=f"{guardian.first_name} {guardian.last_name}",
        email=guardian.email,
        phone=guardian.phone,
        relationship=guardian.relationship,
        created_at=guardian.created_at
    )


