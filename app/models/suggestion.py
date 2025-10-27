# app/models/suggestion.py
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from app.models.base import Base


class SuggestionType(str, enum.Enum):
    REGEX_PATTERN = "regex_pattern"
    PROMPT_TEMPLATE = "prompt_template"
    INTENT_MAPPING = "intent_mapping"
    HANDLER_IMPROVEMENT = "handler_improvement"


class SuggestionPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestionStatus(str, enum.Enum):
    PENDING = "pending"  # Changed from "PENDING" to "pending"
    APPROVED = "approved"  # Changed from "APPROVED" to "approved"
    REJECTED = "rejected"  # Changed from "REJECTED" to "rejected"
    IMPLEMENTED = "implemented"  # Changed from "IMPLEMENTED" to "implemented"
    NEEDS_ANALYSIS = "needs_analysis"  # Changed from "NEEDS_ANALYSIS" to "needs_analysis"


class ActionItemStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ImplementationType(str, enum.Enum):
    PATTERN = "pattern"
    TEMPLATE = "template"
    CODE_FIX = "code_fix"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_message_id = Column(UUID(as_uuid=True), nullable=True)
    routing_log_id = Column(String(255), nullable=True)  # Keep as String to match routing_logs
    
    suggestion_type = Column(Enum(SuggestionType), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    handler = Column(String(200), nullable=False)
    intent = Column(String(200), nullable=False)
    pattern = Column(Text, nullable=True)
    template_text = Column(Text, nullable=True)
    
    priority = Column(Enum(SuggestionPriority), nullable=False, default=SuggestionPriority.MEDIUM)
    status = Column(Enum(SuggestionStatus), nullable=False, default=SuggestionStatus.PENDING)
    
    tester_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    admin_analysis = Column(Text, nullable=True)
    implementation_notes = Column(Text, nullable=True)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by_name = Column(String(255), nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_by_name = Column(String(255), nullable=True)
    
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    
    original_message = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)
    
    # Keep existing column names from intent_suggestions table
    implemented_version_id = Column(String(255), nullable=True)
    implemented_pattern_id = Column(String(255), nullable=True)
    implemented_template_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    implemented_at = Column(DateTime, nullable=True)
    
    # Relationships
    action_items = relationship("ActionItem", back_populates="suggestion", cascade="all, delete-orphan")


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id = Column(UUID(as_uuid=True), ForeignKey("suggestions.id"), nullable=False)
    
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Enum(SuggestionPriority), nullable=False, default=SuggestionPriority.MEDIUM)
    status = Column(Enum(ActionItemStatus), nullable=False, default=ActionItemStatus.PENDING)
    implementation_type = Column(Enum(ImplementationType), nullable=False)
    
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to_name = Column(String(255), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by_name = Column(String(255), nullable=False)
    
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completion_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    suggestion = relationship("Suggestion", back_populates="action_items")