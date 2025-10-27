# app/schemas/rasa.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from uuid import UUID


# NLU Intent Schemas
class NLUIntentCreate(BaseModel):
    intent_name: str = Field(..., max_length=128)
    examples: List[str] = Field(..., min_items=1)
    description: Optional[str] = None

class NLUIntentUpdate(BaseModel):
    intent_name: Optional[str] = Field(None, max_length=128)
    examples: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class NLUIntentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    intent_name: str
    examples: List[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# NLU Entity Schemas
class NLUEntityCreate(BaseModel):
    intent_id: Optional[UUID] = None
    entity_name: str = Field(..., max_length=128)
    entity_type: str = Field(..., max_length=64)
    patterns: Optional[List[str]] = None
    description: Optional[str] = None

class NLUEntityUpdate(BaseModel):
    entity_name: Optional[str] = Field(None, max_length=128)
    entity_type: Optional[str] = Field(None, max_length=64)
    patterns: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class NLUEntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    intent_id: Optional[UUID]
    entity_name: str
    entity_type: str
    patterns: Optional[List[str]]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Rasa Story Schemas
class RasaStoryCreate(BaseModel):
    story_name: str = Field(..., max_length=256)
    content: Dict[str, Any]
    yaml_content: Optional[str] = None
    description: Optional[str] = None
    priority: int = Field(default=0)

class RasaStoryUpdate(BaseModel):
    story_name: Optional[str] = Field(None, max_length=256)
    content: Optional[Dict[str, Any]] = None
    yaml_content: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class RasaStoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    story_name: str
    content: Dict[str, Any]
    yaml_content: Optional[str]
    description: Optional[str]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Rasa Rule Schemas
class RasaRuleCreate(BaseModel):
    rule_name: str = Field(..., max_length=256)
    content: Dict[str, Any]
    yaml_content: Optional[str] = None
    description: Optional[str] = None
    priority: int = Field(default=0)

class RasaRuleUpdate(BaseModel):
    rule_name: Optional[str] = Field(None, max_length=256)
    content: Optional[Dict[str, Any]] = None
    yaml_content: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class RasaRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    rule_name: str
    content: Dict[str, Any]
    yaml_content: Optional[str]
    description: Optional[str]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Rasa Response Schemas
class RasaResponseCreate(BaseModel):
    utterance_name: str = Field(..., max_length=128)
    messages: List[Dict[str, str]] = Field(..., min_items=1)
    description: Optional[str] = None

class RasaResponseUpdate(BaseModel):
    utterance_name: Optional[str] = Field(None, max_length=128)
    messages: Optional[List[Dict[str, str]]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RasaResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    utterance_name: str
    messages: List[Dict[str, str]]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Rasa Action Schemas
class RasaActionCreate(BaseModel):
    action_name: str = Field(..., max_length=128)
    python_code: str
    description: Optional[str] = None

class RasaActionUpdate(BaseModel):
    action_name: Optional[str] = Field(None, max_length=128)
    python_code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RasaActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    action_name: str
    python_code: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Rasa Slot Schemas
class RasaSlotCreate(BaseModel):
    slot_name: str = Field(..., max_length=128)
    slot_type: str = Field(..., max_length=64)
    influence_conversation: bool = True
    mappings: List[Dict[str, Any]]
    initial_value: Optional[str] = None
    description: Optional[str] = None

class RasaSlotUpdate(BaseModel):
    slot_name: Optional[str] = Field(None, max_length=128)
    slot_type: Optional[str] = Field(None, max_length=64)
    influence_conversation: Optional[bool] = None
    mappings: Optional[List[Dict[str, Any]]] = None
    initial_value: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RasaSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    slot_name: str
    slot_type: str
    influence_conversation: bool
    mappings: List[Dict[str, Any]]
    initial_value: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Rasa Form Schemas
class RasaFormCreate(BaseModel):
    form_name: str = Field(..., max_length=128)
    required_slots: List[str] = Field(..., min_items=1)
    configuration: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class RasaFormUpdate(BaseModel):
    form_name: Optional[str] = Field(None, max_length=128)
    required_slots: Optional[List[str]] = None
    configuration: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RasaFormOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    form_name: str
    required_slots: List[str]
    configuration: Optional[Dict[str, Any]]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Training Job Schemas
class TrainingJobCreate(BaseModel):
    triggered_by: UUID

class TrainingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    school_id: Optional[UUID]
    status: str
    triggered_by: UUID
    model_path: Optional[str]
    logs: Optional[str]
    error_message: Optional[str]
    training_metadata: Optional[Dict[str, Any]] 
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


# Bulk Export/Import Schemas
class RasaContentExport(BaseModel):
    """Complete export of all Rasa content"""
    intents: List[NLUIntentOut]
    entities: List[NLUEntityOut]
    stories: List[RasaStoryOut]
    rules: List[RasaRuleOut]
    responses: List[RasaResponseOut]
    actions: List[RasaActionOut]
    slots: List[RasaSlotOut]
    forms: List[RasaFormOut]

class RasaContentImport(BaseModel):
    """Bulk import of Rasa content"""
    intents: Optional[List[NLUIntentCreate]] = None
    entities: Optional[List[NLUEntityCreate]] = None
    stories: Optional[List[RasaStoryCreate]] = None
    rules: Optional[List[RasaRuleCreate]] = None
    responses: Optional[List[RasaResponseCreate]] = None
    actions: Optional[List[RasaActionCreate]] = None
    slots: Optional[List[RasaSlotCreate]] = None
    forms: Optional[List[RasaFormCreate]] = None