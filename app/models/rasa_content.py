from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Text, Boolean, ForeignKey, DateTime, Index, JSON, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class NLUIntent(Base):
    """Stores NLU intents and their training examples"""
    __tablename__ = "nlu_intents"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)  # NULL = global
    intent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    examples: Mapped[list] = mapped_column(JSONB, nullable=False)  # List of training examples
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entities: Mapped[list["NLUEntity"]] = relationship("NLUEntity", back_populates="intent", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("uq_intent_name", "intent_name", unique=True),  # Global uniqueness
        Index("ix_nlu_intents_school_active", "school_id", "is_active"),
    )


class NLUEntity(Base):
    """Stores NLU entities and their patterns"""
    __tablename__ = "nlu_entities"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)  # NULL = global
    intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("nlu_intents.id", ondelete="CASCADE"),
        nullable=True
    )
    entity_name: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)  # from_entity, from_text, etc.
    patterns: Mapped[list] = mapped_column(JSONB, nullable=True)  # Regex patterns or lookup values
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    intent: Mapped["NLUIntent"] = relationship("NLUIntent", back_populates="entities")
    
    __table_args__ = (
        Index("ix_nlu_entities_school_entity", "school_id", "entity_name"),
        Index("ix_nlu_entities_intent", "intent_id"),
    )


class RasaStory(Base):
    """Stores Rasa stories for conversation flow"""
    __tablename__ = "rasa_stories"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    story_name: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Story steps as JSON
    yaml_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Original YAML for reference
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # For ordering
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("uq_story_per_school", "school_id", "story_name", unique=True),
        Index("ix_stories_school_active", "school_id", "is_active"),
        Index("ix_stories_priority", "school_id", "priority"),
    )


class RasaRule(Base):
    """Stores Rasa rules for deterministic behavior"""
    __tablename__ = "rasa_rules"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Rule steps as JSON
    yaml_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Original YAML for reference
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("uq_rule_per_school", "school_id", "rule_name", unique=True),
        Index("ix_rules_school_active", "school_id", "is_active"),
        Index("ix_rules_priority", "school_id", "priority"),
    )


class RasaResponse(Base):
    """Stores bot responses/utterances"""
    __tablename__ = "rasa_responses"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    utterance_name: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g., utter_greet
    messages: Mapped[list] = mapped_column(JSONB, nullable=False)  # List of response variations
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("uq_response_per_school", "school_id", "utterance_name", unique=True),
        Index("ix_responses_school_active", "school_id", "is_active"),
    )


class RasaAction(Base):
    """Stores custom action code"""
    __tablename__ = "rasa_actions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    action_name: Mapped[str] = mapped_column(String(128), nullable=False)
    python_code: Mapped[str] = mapped_column(Text, nullable=False)  # Python code as text
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("uq_action_per_school", "school_id", "action_name", unique=True),
        Index("ix_actions_school_active", "school_id", "is_active"),
    )


class RasaSlot(Base):
    """Stores slot definitions"""
    __tablename__ = "rasa_slots"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    slot_name: Mapped[str] = mapped_column(String(128), nullable=False)
    slot_type: Mapped[str] = mapped_column(String(64), nullable=False)  # text, bool, categorical, etc.
    influence_conversation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mappings: Mapped[list] = mapped_column(JSONB, nullable=False)  # Mapping configuration
    initial_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("uq_slot_per_school", "school_id", "slot_name", unique=True),
        Index("ix_slots_school_active", "school_id", "is_active"),
    )


class RasaForm(Base):
    """Stores form definitions"""
    __tablename__ = "rasa_forms"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    form_name: Mapped[str] = mapped_column(String(128), nullable=False)
    required_slots: Mapped[list] = mapped_column(JSONB, nullable=False)  # List of required slot names
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=True)  # Additional form config
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("uq_form_per_school", "school_id", "form_name", unique=True),
        Index("ix_forms_school_active", "school_id", "is_active"),
    )


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # pending, running, completed, failed
    triggered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ✅ Rename this to avoid conflict
    training_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    yaml_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_counts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)