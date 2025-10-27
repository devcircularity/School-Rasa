# app/api/routers/chat.py - Updated to use Rasa with proper authentication
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import Dict, Any, List, Optional
from uuid import UUID
import logging
import time
import os
import httpx
from datetime import datetime, timezone

from app.core.db import get_db
from app.core.config import settings
from app.api.deps.tenancy import require_school
from app.models.chat import ChatConversation, ChatMessage, MessageType
from app.schemas.chat import (
    ChatMessage as ChatMessageSchema,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationList,
    ConversationDetail,
    MessageResponse,
    UpdateConversation,
    FileAttachment,
    prepare_for_json_storage
)


logger = logging.getLogger(__name__)
router = APIRouter()

# Rasa configuration
RASA_SERVER_URL = os.getenv("RASA_SERVER_URL", "http://localhost:5005")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def extract_auth_token(request: Request) -> Optional[str]:
    """Extract JWT token from Authorization header"""
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]  # Remove "Bearer " prefix
    return None

async def send_message_to_rasa(
    message: str,
    sender_id: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Send a message to Rasa and get the response
    
    Args:
        message: The user's message
        sender_id: Unique identifier for the conversation
        metadata: Additional context data for Rasa (includes JWT token)
    
    Returns:
        Dict containing Rasa's response
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "sender": sender_id,
                "message": message
            }
            
            if metadata:
                payload["metadata"] = metadata
            
            logger.info(f"Sending to Rasa: sender={sender_id}, metadata keys={list(metadata.keys()) if metadata else []}")
            
            response = await client.post(
                f"{RASA_SERVER_URL}/webhooks/rest/webhook",
                json=payload
            )
            
            if response.status_code == 200:
                rasa_responses = response.json()
                logger.info(f"Rasa responded with {len(rasa_responses)} messages")
                return {
                    "success": True,
                    "responses": rasa_responses
                }
            else:
                logger.error(f"Rasa returned status code {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"Rasa server error: {response.status_code}"
                }
                
    except httpx.TimeoutException:
        logger.error("Rasa request timed out")
        return {
            "success": False,
            "error": "Request to Rasa timed out"
        }
    except Exception as e:
        logger.error(f"Error communicating with Rasa: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

async def check_rasa_health() -> Dict[str, Any]:
    """Check if Rasa server is healthy"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{RASA_SERVER_URL}/")
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code
            }
    except Exception as e:
        logger.error(f"Rasa health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e)
        }

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Create a new chat conversation"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Create timestamp for consistent use
    now = datetime.now(timezone.utc)
    
    new_conversation = ChatConversation(
        user_id=user.id,
        school_id=UUID(school_id),
        title=conversation_data.title,
        first_message=conversation_data.first_message,
        message_count=0,
        last_activity=now
    )
    
    db.add(new_conversation)
    
    try:
        db.commit()
        db.refresh(new_conversation)
        logger.info(f"New conversation created: {new_conversation.id} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating conversation"
        )
    
    return ConversationResponse.from_attributes(new_conversation)

@router.get("/conversations", response_model=ConversationList)
async def get_conversations(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    archived: Optional[bool] = Query(None)
):
    """Get user's chat conversations"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    query = (
        select(ChatConversation)
        .where(
            ChatConversation.user_id == user.id,
            ChatConversation.school_id == UUID(school_id)
        )
    )
    
    if archived is not None:
        query = query.where(ChatConversation.is_archived == archived)
    
    query = query.order_by(desc(ChatConversation.last_activity))
    
    # Get total count
    total_query = query.with_only_columns(ChatConversation.id)
    total = len(db.execute(total_query).scalars().all())
    
    # Apply pagination
    offset = (page - 1) * limit
    conversations = db.execute(
        query.offset(offset).limit(limit)
    ).scalars().all()
    
    conversation_list = [
        ConversationResponse.from_attributes(conv) for conv in conversations
    ]
    
    has_next = total > page * limit
    
    return ConversationList(
        conversations=conversation_list,
        total=total,
        page=page,
        limit=limit,
        has_next=has_next
    )

@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    include_messages: bool = Query(True)
):
    """Get conversation details with messages"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    conversation = db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_uuid,
            ChatConversation.user_id == user.id,
            ChatConversation.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    result = ConversationDetail.from_attributes(conversation)
    
    if include_messages:
        messages = db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv_uuid)
            .order_by(ChatMessage.created_at)
        ).scalars().all()
        
        result.messages = [MessageResponse.from_attributes(msg) for msg in messages]
    
    return result

@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: str,
    message_data: ChatMessageSchema,
    request: Request,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """
    Send a message and get response via Rasa
    
    IMPORTANT: This endpoint passes the JWT token to Rasa so that Rasa's custom actions
    can make authenticated API calls back to FastAPI endpoints.
    """
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # Extract JWT token from request - THIS IS CRITICAL
    auth_token = extract_auth_token(request)
    if not auth_token:
        logger.error("No JWT token found in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )
    
    logger.info(f"Processing message from user {user.email} (school: {school_id})")
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    # Verify conversation exists and belongs to user
    conversation = db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_uuid,
            ChatConversation.user_id == user.id,
            ChatConversation.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    start_time = time.time()
    
    # Create timestamp for consistent use across all operations
    message_timestamp = datetime.now(timezone.utc)
    
    # Store user message
    user_message = ChatMessage(
        conversation_id=conv_uuid,
        user_id=user.id,
        school_id=UUID(school_id),
        message_type=MessageType.USER,
        content=message_data.message,
        context_data=prepare_for_json_storage(message_data.context or {}),
        created_at=message_timestamp
    )
    
    # Handle attachments if present
    if message_data.attachments:
        user_message.response_data = prepare_for_json_storage({
            "attachments": [attachment.dict() for attachment in message_data.attachments]
        })
    
    db.add(user_message)
    
    try:
        # Fetch user's schools from database
        from app.models.school import SchoolMember, School
        
        schools_query = (
            select(School, SchoolMember.role)
            .join(SchoolMember, School.id == SchoolMember.school_id)
            .where(SchoolMember.user_id == user.id)
            .order_by(School.name)
        )
        user_schools = db.execute(schools_query).all()
        
        schools_list = [
            {"id": str(school.id), "name": school.name, "role": role}
            for school, role in user_schools
        ]
        
        # Get current school name
        current_school = db.get(School, UUID(school_id))
        school_name = current_school.name if current_school else None
        
        # Build context metadata for Rasa
        # CRITICAL: Include JWT token and API URL so Rasa can make authenticated calls
        rasa_metadata = {
            # Authentication - use consistent key names
            "auth_token": auth_token,  # Changed from jwt_token
            "authorization": f"Bearer {auth_token}",
            "api_base_url": API_BASE_URL,
            
            # User context
            "user_id": str(user.id),
            "user_email": user.email,
            "user_full_name": user.full_name,
            "user_roles": getattr(user, 'roles', []),
            
            # School context
            "school_id": school_id,
            "school_name": school_name,
            "schools": schools_list,
            
            # Conversation context
            "conversation_id": conversation_id,
            "context": message_data.context or {}
        }
        
        logger.info(f"Metadata prepared for Rasa: user={user.email}, school={school_name}")
        
        # Send message to Rasa
        sender_id = f"{user.id}_{conversation_id}"
        rasa_result = await send_message_to_rasa(
            message=message_data.message,
            sender_id=sender_id,
            metadata=rasa_metadata
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Process Rasa response
        if rasa_result.get("success"):
            rasa_responses = rasa_result.get("responses", [])
            
            # Combine all text responses from Rasa
            response_texts = []
            buttons = []
            custom_data = {}
            
            for rasa_response in rasa_responses:
                if "text" in rasa_response:
                    response_texts.append(rasa_response["text"])
                if "buttons" in rasa_response:
                    buttons.extend(rasa_response["buttons"])
                if "custom" in rasa_response:
                    custom_data.update(rasa_response["custom"])
            
            formatted_response = "\n\n".join(response_texts) if response_texts else "I received your message."
            
            # Extract intent if available in custom data
            intent = custom_data.get("intent", "unknown")
            
            logger.info(f"Rasa response: {len(response_texts)} texts, {len(buttons)} buttons, intent={intent}")
            
            # Store assistant response
            assistant_message = ChatMessage(
                conversation_id=conv_uuid,
                user_id=user.id,
                school_id=UUID(school_id),
                message_type=MessageType.ASSISTANT,
                content=formatted_response,
                intent=intent,
                context_data=prepare_for_json_storage(rasa_metadata),
                response_data=prepare_for_json_storage({
                    "rasa_responses": rasa_responses,
                    "buttons": buttons,
                    "custom_data": custom_data
                }),
                processing_time_ms=processing_time,
                created_at=message_timestamp
            )
            
            db.add(assistant_message)
            
            # Update conversation metadata
            conversation.last_activity = message_timestamp
            conversation.message_count += 2  # User + Assistant messages
            
            db.commit()
            
            logger.info(f"Message processed successfully: conversation={conversation_id}, processing_time={processing_time}ms")
            
            # Return formatted response
            return ChatResponse(
                response=assistant_message.content,
                intent=intent,
                data=custom_data.get("data"),
                action_taken=custom_data.get("action_taken"),
                suggestions=buttons if buttons else custom_data.get("suggestions", []),
                conversation_id=conversation_id,
                blocks=None,
                attachment_processed=bool(message_data.attachments),
                message_id=str(assistant_message.id)
            )
        else:
            # Rasa communication failed
            error_msg = rasa_result.get("error", "Failed to communicate with Rasa")
            logger.error(f"Rasa error: {error_msg}")
            
            # Store error response
            assistant_message = ChatMessage(
                conversation_id=conv_uuid,
                user_id=user.id,
                school_id=UUID(school_id),
                message_type=MessageType.ASSISTANT,
                content="I'm sorry, I'm having trouble processing your message right now. Please try again.",
                context_data=prepare_for_json_storage(rasa_metadata),
                response_data=prepare_for_json_storage({
                    "error": error_msg,
                    "rasa_result": rasa_result
                }),
                processing_time_ms=processing_time,
                created_at=message_timestamp
            )
            
            db.add(assistant_message)
            conversation.last_activity = message_timestamp
            conversation.message_count += 2
            db.commit()
            
            return ChatResponse(
                response="I'm sorry, I'm having trouble processing your message right now. Please try again.",
                conversation_id=conversation_id,
                message_id=str(assistant_message.id)
            )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing message: {e}", exc_info=True)
        
        # Store error message for debugging
        error_message = ChatMessage(
            conversation_id=conv_uuid,
            user_id=user.id,
            school_id=UUID(school_id),
            message_type=MessageType.ASSISTANT,
            content="I'm sorry, I'm having trouble processing your message right now. Please try again.",
            context_data=prepare_for_json_storage(rasa_metadata if 'rasa_metadata' in locals() else {}),
            response_data=prepare_for_json_storage({
                "error": str(e),
                "error_type": type(e).__name__
            }),
            processing_time_ms=int((time.time() - start_time) * 1000),
            created_at=message_timestamp
        )
        
        db.add(error_message)
        conversation.last_activity = message_timestamp
        conversation.message_count += 2
        
        try:
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to save error message: {commit_error}")
            db.rollback()
        
        return ChatResponse(
            response="I'm sorry, I'm having trouble processing your message right now. Please try again.",
            conversation_id=conversation_id,
            message_id=str(error_message.id) if 'error_message' in locals() else None
        )

@router.post("/conversations/{conversation_id}/messages/{message_id}/rate")
async def rate_message(
    conversation_id: str,
    message_id: str,
    rating: dict,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Rate an assistant message (thumbs up/down feedback)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        conv_uuid = UUID(conversation_id)
        msg_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )
    
    # Verify conversation belongs to user
    conversation = db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_uuid,
            ChatConversation.user_id == user.id,
            ChatConversation.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Get the message
    message = db.execute(
        select(ChatMessage).where(
            ChatMessage.id == msg_uuid,
            ChatMessage.conversation_id == conv_uuid,
            ChatMessage.message_type == MessageType.ASSISTANT
        )
    ).scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Validate rating value
    rating_value = rating.get("rating")
    if rating_value not in [1, -1, None]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be 1 (thumbs up), -1 (thumbs down), or null to remove rating"
        )
    
    # Update message rating
    message.rating = rating_value
    message.rated_at = datetime.now(timezone.utc) if rating_value is not None else None
    
    try:
        db.commit()
        logger.info(f"Message rated: {message_id} with {rating_value} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error rating message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving rating"
        )
    
    return {"message": "Rating saved successfully"}

@router.put("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    update_data: UpdateConversation,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update conversation (title, archive status)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    conversation = db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_uuid,
            ChatConversation.user_id == user.id,
            ChatConversation.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Update fields if provided
    if update_data.title is not None:
        conversation.title = update_data.title
    
    if update_data.is_archived is not None:
        conversation.is_archived = update_data.is_archived
    
    try:
        db.commit()
        logger.info(f"Conversation updated: {conversation_id} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating conversation"
        )
    
    return {"message": "Conversation updated successfully"}

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete a conversation and all its messages"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    conversation = db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_uuid,
            ChatConversation.user_id == user.id,
            ChatConversation.school_id == UUID(school_id)
        )
    ).scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    try:
        db.delete(conversation)
        db.commit()
        logger.info(f"Conversation deleted: {conversation_id} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting conversation"
        )
    
    return {"message": "Conversation deleted successfully"}

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    ctx: Dict[str, Any] = Depends(require_school)
):
    """Upload a file for chat (placeholder for file upload service)"""
    user = ctx["user"]
    school_id = ctx["school_id"]
    
    # TODO: Implement file upload to Cloudinary
    
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB."
        )
    
    return {
        "attachment_id": "mock_attachment_id",
        "original_filename": file.filename,
        "content_type": file.content_type,
        "file_size": file.size,
        "cloudinary_url": "https://example.com/mock_url",
        "upload_timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/health")
async def chat_health():
    """Health check for chat service - checks Rasa connectivity"""
    rasa_status = await check_rasa_health()
    
    return {
        "status": "healthy" if rasa_status.get("healthy") else "degraded",
        "chat_backend": "rasa",
        "rasa_url": RASA_SERVER_URL,
        "api_base_url": API_BASE_URL,
        "rasa_status": rasa_status,
        "timestamp": time.time()
    }