# app/models/intent_config.py - Updated IntentPattern model
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import ENUM as PgEnum, ARRAY
from sqlalchemy.orm import relationship

from app.models.base import Base


class ConfigStatus(str, Enum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    ARCHIVED = "archived"


class PatternKind(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    SYNONYM = "synonym"


class TemplateType(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FALLBACK_CONTEXT = "fallback_context"


# Create the enum types with explicit database values
config_status_enum = PgEnum(
    'active', 'candidate', 'archived',
    name='config_status'
)

pattern_kind_enum = PgEnum(
    'positive', 'negative', 'synonym',
    name='pattern_kind'
)

template_type_enum = PgEnum(
    'system', 'user', 'assistant', 'fallback_context',
    name='template_type'
)


class IntentConfigVersion(Base):
    """Versioned configuration for intent patterns and prompts"""
    __tablename__ = "intent_config_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    status = Column(config_status_enum, nullable=False, default='candidate')
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    activated_at = Column(DateTime)
    created_by = Column(String)

    # Relationships
    patterns = relationship("IntentPattern", back_populates="version", cascade="all, delete-orphan")
    prompt_templates = relationship("PromptTemplate", back_populates="version", cascade="all, delete-orphan")
    routing_logs = relationship("RoutingLog", back_populates="version")

    def __repr__(self):
        return f"<IntentConfigVersion(id={self.id}, name={self.name}, status={self.status})>"


class IntentPattern(Base):
    """Enhanced pattern-based routing rules with phrase support"""
    __tablename__ = "intent_patterns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    version_id = Column(String, ForeignKey("intent_config_versions.id", ondelete="CASCADE"), nullable=False)
    handler = Column(String(100), nullable=False)
    intent = Column(String(100), nullable=False)
    kind = Column(pattern_kind_enum, nullable=False)
    pattern = Column(Text, nullable=False)  # The actual regex pattern
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True)
    scope_school_id = Column(String)  # Optional school-specific override
    
    # NEW: Phrase support columns
    phrases = Column(ARRAY(String), nullable=True)  # Array of friendly phrases
    regex_confidence = Column(Float, nullable=True)  # Confidence in generated regex (0.0-1.0)
    regex_explanation = Column(Text, nullable=True)  # Human-readable explanation of the regex
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String)

    # Relationships
    version = relationship("IntentConfigVersion", back_populates="patterns")

    def __repr__(self):
        return f"<IntentPattern(handler={self.handler}, intent={self.intent}, kind={self.kind})>"
    
    def get_phrases_display(self) -> str:
        """Get a human-readable display of phrases for UI"""
        if self.phrases:
            return ", ".join(self.phrases)
        return "No phrases defined"
    
    def has_phrases(self) -> bool:
        """Check if this pattern has friendly phrases defined"""
        return bool(self.phrases and len(self.phrases) > 0)
    
    def get_confidence_display(self) -> str:
        """Get a human-readable confidence display"""
        if self.regex_confidence is None:
            return "Unknown"
        elif self.regex_confidence >= 0.8:
            return "High"
        elif self.regex_confidence >= 0.6:
            return "Medium"
        else:
            return "Low"


class PromptTemplate(Base):
    """LLM prompt templates for different handlers and intents"""
    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    version_id = Column(String, ForeignKey("intent_config_versions.id", ondelete="CASCADE"), nullable=False)
    handler = Column(String(100), nullable=False)
    intent = Column(String(100))  # Optional - handler-wide templates have null intent
    template_type = Column(template_type_enum, nullable=False)
    template_text = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    scope_school_id = Column(String)  # Optional school-specific override
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String)

    # Relationships
    version = relationship("IntentConfigVersion", back_populates="prompt_templates")

    def __repr__(self):
        return f"<PromptTemplate(handler={self.handler}, intent={self.intent}, type={self.template_type})>"


class RoutingLog(Base):
    """Comprehensive logging of routing decisions for training"""
    __tablename__ = "routing_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String)
    message_id = Column(String)
    message = Column(Text, nullable=False)
    
    # LLM Classifier results
    llm_intent = Column(String(100))
    llm_confidence = Column(Float)
    llm_entities = Column(JSON)
    
    # ConfigRouter results
    router_intent = Column(String(100))
    router_reason = Column(String(255))  # "pattern:xyz" or "synonym:abc"
    
    # Final decision
    final_intent = Column(String(100), nullable=False)
    final_handler = Column(String(100), nullable=False)
    fallback_used = Column(Boolean, nullable=False, default=False)
    
    # Performance
    latency_ms = Column(Integer)
    
    # Metadata
    version_id = Column(String, ForeignKey("intent_config_versions.id"), nullable=False)
    school_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    version = relationship("IntentConfigVersion", back_populates="routing_logs")

    def __repr__(self):
        return f"<RoutingLog(final_handler={self.final_handler}, final_intent={self.final_intent}, fallback={self.fallback_used})>"