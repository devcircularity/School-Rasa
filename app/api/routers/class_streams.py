# app/api/routers/class_streams.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Dict, Any
from uuid import UUID
import logging

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.class_model import Class
from app.models.class_stream import ClassStream
from app.schemas.class_stream import ClassStreamCreate, ClassStreamOut, ClassStreamList

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/classes/{class_id}/streams", response_model=ClassStreamOut, status_code=status.HTTP_201_CREATED)
async def create_stream(
    class_id: str,
    stream_data: ClassStreamCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Add a stream to a class"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        class_uuid = UUID(class_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid class ID format"
        )
    
    # Verify class exists
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
    
    # Check if stream already exists (case-insensitive)
    existing_stream = db.execute(
        select(ClassStream).where(
            ClassStream.class_id == class_uuid,
            func.lower(ClassStream.name) == func.lower(stream_data.name)
        )
    ).scalar_one_or_none()
    
    if existing_stream:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stream '{stream_data.name}' already exists for {class_obj.name}"
        )
    
    # Create stream
    new_stream = ClassStream(
        school_id=UUID(school_id),
        class_id=class_uuid,
        name=stream_data.name.strip().title()  # Normalize: "red" -> "Red"
    )
    
    try:
        db.add(new_stream)
        db.commit()
        db.refresh(new_stream)
        logger.info(f"Stream '{new_stream.name}' added to class '{class_obj.name}' by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating stream"
        )
    
    return ClassStreamOut.model_validate(new_stream)

@router.get("/classes/{class_id}/streams", response_model=ClassStreamList)
async def get_streams(
    class_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get all streams for a class"""
    school_id = ctx["school_id"]
    
    try:
        class_uuid = UUID(class_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid class ID format"
        )
    
    # Verify class exists
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
    
    # Get streams
    streams = db.execute(
        select(ClassStream)
        .where(ClassStream.class_id == class_uuid)
        .order_by(ClassStream.name)
    ).scalars().all()
    
    return ClassStreamList(
        streams=[ClassStreamOut.model_validate(s) for s in streams],
        total=len(streams)
    )

@router.delete("/classes/{class_id}/streams/{stream_id}")
async def delete_stream(
    class_id: str,
    stream_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete a stream from a class"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        class_uuid = UUID(class_id)
        stream_uuid = UUID(stream_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )
    
    # Get stream
    stream = db.execute(
        select(ClassStream).where(
            ClassStream.id == stream_uuid,
            ClassStream.class_id == class_uuid,
            ClassStream.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stream not found"
        )
    
    try:
        db.delete(stream)
        db.commit()
        logger.info(f"Stream '{stream.name}' deleted by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting stream"
        )
    
    return {"message": f"Stream '{stream.name}' deleted successfully"}