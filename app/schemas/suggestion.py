# app/schemas/suggestion.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class SuggestionTypeEnum(str, Enum):
    REGEX_PATTERN = "regex_pattern"
    PROMPT_TEMPLATE = "prompt_template"
    INTENT_MAPPING = "intent_mapping"
    HANDLER_IMPROVEMENT = "handler_improvement"


class PriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestionStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    NEEDS_ANALYSIS = "needs_analysis"


class ActionItemStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ImplementationTypeEnum(str, Enum):
    PATTERN = "pattern"
    TEMPLATE = "template"
    CODE_FIX = "code_fix"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class ActionItemOut(BaseModel):
    id: str
    suggestion_id: str
    title: str
    description: str
    priority: str
    status: str
    implementation_type: str
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    created_by: str
    created_by_name: str
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SuggestionOut(BaseModel):
    id: str
    chat_message_id: Optional[str] = None
    routing_log_id: Optional[str] = None
    suggestion_type: str
    title: str
    description: str
    handler: str
    intent: str
    pattern: Optional[str] = None
    template_text: Optional[str] = None
    priority: str
    tester_note: Optional[str] = None
    admin_note: Optional[str] = None
    status: str
    created_by: str
    created_by_name: str
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    school_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None
    implemented_at: Optional[datetime] = None
    original_message: Optional[str] = None
    assistant_response: Optional[str] = None
    admin_analysis: Optional[str] = None
    implementation_notes: Optional[str] = None
    action_items: List[ActionItemOut] = []
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm(cls, suggestion, action_items=None):
        data = {
            "id": str(suggestion.id),
            "chat_message_id": str(suggestion.chat_message_id) if suggestion.chat_message_id else None,
            "routing_log_id": str(suggestion.routing_log_id) if suggestion.routing_log_id else None,
            "suggestion_type": suggestion.suggestion_type,
            "title": suggestion.title,
            "description": suggestion.description,
            "handler": suggestion.handler,
            "intent": suggestion.intent,
            "pattern": suggestion.pattern,
            "template_text": suggestion.template_text,
            "priority": suggestion.priority,
            "tester_note": suggestion.tester_note,
            "admin_note": suggestion.admin_note,
            "status": suggestion.status,
            "created_by": str(suggestion.created_by),
            "created_by_name": suggestion.created_by_name,
            "reviewed_by": str(suggestion.reviewed_by) if suggestion.reviewed_by else None,
            "reviewed_by_name": suggestion.reviewed_by_name,
            "school_id": str(suggestion.school_id) if suggestion.school_id else None,
            "created_at": suggestion.created_at,
            "updated_at": suggestion.updated_at,
            "reviewed_at": suggestion.reviewed_at,
            "implemented_at": suggestion.implemented_at,
            "original_message": suggestion.original_message,
            "assistant_response": suggestion.assistant_response,
            "admin_analysis": suggestion.admin_analysis,
            "implementation_notes": suggestion.implementation_notes,
            "action_items": [ActionItemOut.from_orm(ai) for ai in (action_items or [])]
        }
        return cls(**data)


class SuggestionCreate(BaseModel):
    """Schema for creating a new suggestion"""
    chat_message_id: Optional[str] = None
    routing_log_id: Optional[str] = None
    suggestion_type: SuggestionTypeEnum
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    handler: str = Field(..., min_length=1, max_length=200)
    intent: str = Field(..., min_length=1, max_length=200)
    pattern: Optional[str] = None
    template_text: Optional[str] = None
    priority: Optional[PriorityEnum] = PriorityEnum.MEDIUM
    tester_note: Optional[str] = None
    school_id: Optional[str] = None
    original_message: Optional[str] = None
    assistant_response: Optional[str] = None


class SuggestionUpdate(BaseModel):
    """Schema for updating a suggestion"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, min_length=1)
    handler: Optional[str] = Field(None, min_length=1, max_length=200)
    intent: Optional[str] = Field(None, min_length=1, max_length=200)
    pattern: Optional[str] = None
    template_text: Optional[str] = None
    priority: Optional[PriorityEnum] = None
    tester_note: Optional[str] = None
    admin_note: Optional[str] = None
    admin_analysis: Optional[str] = None
    implementation_notes: Optional[str] = None


class SuggestionListResponse(BaseModel):
    suggestions: List[dict]
    total: int
    page: int
    limit: int
    has_next: bool


class ReviewSuggestionRequest(BaseModel):
    status: SuggestionStatusEnum
    admin_note: Optional[str] = None
    auto_implement: bool = False


class EnhancedReviewSuggestionRequest(BaseModel):
    status: SuggestionStatusEnum
    admin_note: Optional[str] = None
    admin_analysis: Optional[str] = None
    implementation_notes: Optional[str] = None
    create_action_items: bool = False
    action_items: Optional[List[dict]] = None


class ActionItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    priority: PriorityEnum
    implementation_type: ImplementationTypeEnum
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None


class ActionItemUpdate(BaseModel):
    status: Optional[ActionItemStatusEnum] = None
    completion_notes: Optional[str] = None


class ActionItemListResponse(BaseModel):
    action_items: List[ActionItemOut]
    total: int
    page: int
    limit: int
    has_next: bool


class SuggestionStatsOut(BaseModel):
    total_suggestions: int
    pending: int
    approved: int
    rejected: int
    implemented: int
    needs_analysis: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]


class EnhancedSuggestionStatsOut(SuggestionStatsOut):
    action_items: Dict[str, int]
    suggestions_with_action_items: int
    avg_time_to_resolution: Optional[float] = None


class TesterSuggestionCreate(BaseModel):
    message_id: Optional[str] = None
    routing_log_id: Optional[str] = None
    suggestion_type: SuggestionTypeEnum
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    handler: str = Field(..., min_length=1, max_length=200)
    intent: str = Field(..., min_length=1, max_length=200)
    pattern: Optional[str] = None
    template_text: Optional[str] = None
    priority: Optional[PriorityEnum] = PriorityEnum.MEDIUM
    tester_note: Optional[str] = None


class ProblematicMessageOut(BaseModel):
    message_id: str
    conversation_id: str
    user_message: str
    assistant_response: str
    intent: Optional[str] = None
    rating: Optional[int] = None
    rated_at: Optional[datetime] = None
    created_at: datetime
    processing_time_ms: Optional[int] = None
    routing_log_id: Optional[str] = None
    llm_intent: Optional[str] = None
    llm_confidence: Optional[float] = None
    router_intent: Optional[str] = None
    final_intent: Optional[str] = None
    fallback_used: Optional[bool] = None
    issue_type: str
    priority: int
    school_id: Optional[str] = None
    user_id: str


class TesterStatsOut(BaseModel):
    total_messages: int
    negative_ratings: int
    fallback_used: int
    low_confidence: int
    unhandled: int
    needs_attention: int
    by_priority: Dict[str, int]
    by_issue_type: Dict[str, int]