# app/api/routers/rasa_content.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

from app.core.db import get_db
from app.api.deps.tenancy import require_school
from app.models.rasa_content import (
    NLUIntent, NLUEntity, RasaStory, RasaRule,
    RasaResponse, RasaAction, RasaSlot, RasaForm, TrainingJob
)
from app.schemas.rasa import (
    NLUIntentCreate, NLUIntentUpdate, NLUIntentOut,
    NLUEntityCreate, NLUEntityUpdate, NLUEntityOut,
    RasaStoryCreate, RasaStoryUpdate, RasaStoryOut,
    RasaRuleCreate, RasaRuleUpdate, RasaRuleOut,
    RasaResponseCreate, RasaResponseUpdate, RasaResponseOut,
    RasaActionCreate, RasaActionUpdate, RasaActionOut,
    RasaSlotCreate, RasaSlotUpdate, RasaSlotOut,
    RasaFormCreate, RasaFormUpdate, RasaFormOut,
    TrainingJobCreate, TrainingJobOut,
    RasaContentExport
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== NLU INTENTS ====================

@router.post("/intents", response_model=NLUIntentOut, status_code=status.HTTP_201_CREATED)
async def create_intent(
    intent_data: NLUIntentCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False, description="Create as global content (school_id=NULL)")
):
    """Create a new NLU intent"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    # Check if intent already exists (global uniqueness)
    existing_intent = db.execute(
        select(NLUIntent).where(NLUIntent.intent_name == intent_data.intent_name)
    ).scalar_one_or_none()
    
    if existing_intent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intent '{intent_data.intent_name}' already exists"
        )
    
    new_intent = NLUIntent(
        school_id=UUID(school_id) if school_id else None,
        intent_name=intent_data.intent_name,
        examples=intent_data.examples,
        description=intent_data.description,
        created_by=user.id
    )
    
    db.add(new_intent)
    
    try:
        db.commit()
        db.refresh(new_intent)
        scope = "global" if school_id is None else f"school {school_id}"
        logger.info(f"Intent '{intent_data.intent_name}' created as {scope} by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating intent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating intent"
        )
    
    return NLUIntentOut.model_validate(new_intent)


@router.get("/intents", response_model=List[NLUIntentOut])
async def list_intents(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None, description="Filter by school_id (or 'global' for NULL)")
):
    """List all NLU intents"""
    query = select(NLUIntent)
    
    if active_only:
        query = query.where(NLUIntent.is_active == True)
    
    # Apply school filter if requested
    if filter_school == "global":
        query = query.where(NLUIntent.school_id == None)
    elif filter_school:
        query = query.where(NLUIntent.school_id == UUID(filter_school))
    # Otherwise, return all (global + all schools)
    
    query = query.order_by(NLUIntent.intent_name)
    
    intents = db.execute(query).scalars().all()
    return [NLUIntentOut.model_validate(intent) for intent in intents]


@router.get("/intents/{intent_id}", response_model=NLUIntentOut)
async def get_intent(
    intent_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get a specific intent by ID"""
    try:
        intent_uuid = UUID(intent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid intent ID format"
        )
    
    intent = db.execute(
        select(NLUIntent).where(NLUIntent.id == intent_uuid)
    ).scalar_one_or_none()
    
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent not found"
        )
    
    return NLUIntentOut.model_validate(intent)


@router.put("/intents/{intent_id}", response_model=NLUIntentOut)
async def update_intent(
    intent_id: str,
    intent_data: NLUIntentUpdate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update an existing intent"""
    user = ctx["user"]
    
    try:
        intent_uuid = UUID(intent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid intent ID format"
        )
    
    intent = db.execute(
        select(NLUIntent).where(NLUIntent.id == intent_uuid)
    ).scalar_one_or_none()
    
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent not found"
        )
    
    # Update fields
    if intent_data.intent_name is not None:
        # Check for duplicate name
        existing = db.execute(
            select(NLUIntent).where(
                NLUIntent.intent_name == intent_data.intent_name,
                NLUIntent.id != intent_uuid
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Intent name '{intent_data.intent_name}' already exists"
            )
        intent.intent_name = intent_data.intent_name
    
    if intent_data.examples is not None:
        intent.examples = intent_data.examples
    if intent_data.description is not None:
        intent.description = intent_data.description
    if intent_data.is_active is not None:
        intent.is_active = intent_data.is_active
    
    try:
        db.commit()
        db.refresh(intent)
        logger.info(f"Intent '{intent.intent_name}' updated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating intent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating intent"
        )
    
    return NLUIntentOut.model_validate(intent)


@router.delete("/intents/{intent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intent(
    intent_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete an intent (soft delete by setting is_active=False)"""
    user = ctx["user"]
    
    try:
        intent_uuid = UUID(intent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid intent ID format"
        )
    
    intent = db.execute(
        select(NLUIntent).where(NLUIntent.id == intent_uuid)
    ).scalar_one_or_none()
    
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent not found"
        )
    
    intent.is_active = False
    
    try:
        db.commit()
        logger.info(f"Intent '{intent.intent_name}' deactivated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting intent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting intent"
        )


# ==================== NLU ENTITIES ====================

@router.post("/entities", response_model=NLUEntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity(
    entity_data: NLUEntityCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False)
):
    """Create a new NLU entity"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    new_entity = NLUEntity(
        school_id=UUID(school_id) if school_id else None,
        intent_id=entity_data.intent_id,
        entity_name=entity_data.entity_name,
        entity_type=entity_data.entity_type,
        patterns=entity_data.patterns,
        description=entity_data.description,
        created_by=user.id
    )
    
    db.add(new_entity)
    
    try:
        db.commit()
        db.refresh(new_entity)
        logger.info(f"Entity '{entity_data.entity_name}' created by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating entity"
        )
    
    return NLUEntityOut.model_validate(new_entity)


@router.get("/entities", response_model=List[NLUEntityOut])
async def list_entities(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None)
):
    """List all NLU entities"""
    query = select(NLUEntity)
    
    if active_only:
        query = query.where(NLUEntity.is_active == True)
    
    if filter_school == "global":
        query = query.where(NLUEntity.school_id == None)
    elif filter_school:
        query = query.where(NLUEntity.school_id == UUID(filter_school))
    
    query = query.order_by(NLUEntity.entity_name)
    
    entities = db.execute(query).scalars().all()
    return [NLUEntityOut.model_validate(entity) for entity in entities]


@router.get("/entities/{entity_id}", response_model=NLUEntityOut)
async def get_entity(
    entity_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get a specific entity by ID"""
    try:
        entity_uuid = UUID(entity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entity ID format"
        )
    
    entity = db.execute(
        select(NLUEntity).where(NLUEntity.id == entity_uuid)
    ).scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    return NLUEntityOut.model_validate(entity)


@router.put("/entities/{entity_id}", response_model=NLUEntityOut)
async def update_entity(
    entity_id: str,
    entity_data: NLUEntityUpdate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update an existing entity"""
    user = ctx["user"]
    
    try:
        entity_uuid = UUID(entity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entity ID format"
        )
    
    entity = db.execute(
        select(NLUEntity).where(NLUEntity.id == entity_uuid)
    ).scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    if entity_data.entity_name is not None:
        entity.entity_name = entity_data.entity_name
    if entity_data.entity_type is not None:
        entity.entity_type = entity_data.entity_type
    if entity_data.patterns is not None:
        entity.patterns = entity_data.patterns
    if entity_data.description is not None:
        entity.description = entity_data.description
    if entity_data.is_active is not None:
        entity.is_active = entity_data.is_active
    
    try:
        db.commit()
        db.refresh(entity)
        logger.info(f"Entity '{entity.entity_name}' updated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating entity"
        )
    
    return NLUEntityOut.model_validate(entity)


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete an entity (soft delete)"""
    user = ctx["user"]
    
    try:
        entity_uuid = UUID(entity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entity ID format"
        )
    
    entity = db.execute(
        select(NLUEntity).where(NLUEntity.id == entity_uuid)
    ).scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )
    
    entity.is_active = False
    
    try:
        db.commit()
        logger.info(f"Entity '{entity.entity_name}' deactivated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting entity"
        )


# ==================== RASA STORIES ====================

@router.post("/stories", response_model=RasaStoryOut, status_code=status.HTTP_201_CREATED)
async def create_story(
    story_data: RasaStoryCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False)
):
    """Create a new Rasa story"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    # Check if story already exists
    existing_story = db.execute(
        select(RasaStory).where(RasaStory.story_name == story_data.story_name)
    ).scalar_one_or_none()
    
    if existing_story:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Story '{story_data.story_name}' already exists"
        )
    
    new_story = RasaStory(
        school_id=UUID(school_id) if school_id else None,
        story_name=story_data.story_name,
        content=story_data.content,
        yaml_content=story_data.yaml_content,
        description=story_data.description,
        priority=story_data.priority,
        created_by=user.id
    )
    
    db.add(new_story)
    
    try:
        db.commit()
        db.refresh(new_story)
        logger.info(f"Story '{story_data.story_name}' created by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating story"
        )
    
    return RasaStoryOut.model_validate(new_story)


@router.get("/stories", response_model=List[RasaStoryOut])
async def list_stories(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None)
):
    """List all Rasa stories"""
    query = select(RasaStory)
    
    if active_only:
        query = query.where(RasaStory.is_active == True)
    
    if filter_school == "global":
        query = query.where(RasaStory.school_id == None)
    elif filter_school:
        query = query.where(RasaStory.school_id == UUID(filter_school))
    
    query = query.order_by(RasaStory.priority.desc(), RasaStory.story_name)
    
    stories = db.execute(query).scalars().all()
    return [RasaStoryOut.model_validate(story) for story in stories]


@router.get("/stories/{story_id}", response_model=RasaStoryOut)
async def get_story(
    story_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get a specific story by ID"""
    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid story ID format"
        )
    
    story = db.execute(
        select(RasaStory).where(RasaStory.id == story_uuid)
    ).scalar_one_or_none()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    return RasaStoryOut.model_validate(story)


@router.put("/stories/{story_id}", response_model=RasaStoryOut)
async def update_story(
    story_id: str,
    story_data: RasaStoryUpdate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update an existing story"""
    user = ctx["user"]
    
    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid story ID format"
        )
    
    story = db.execute(
        select(RasaStory).where(RasaStory.id == story_uuid)
    ).scalar_one_or_none()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    if story_data.story_name is not None:
        # Check for duplicate
        existing = db.execute(
            select(RasaStory).where(
                RasaStory.story_name == story_data.story_name,
                RasaStory.id != story_uuid
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Story name '{story_data.story_name}' already exists"
            )
        story.story_name = story_data.story_name
    
    if story_data.content is not None:
        story.content = story_data.content
    if story_data.yaml_content is not None:
        story.yaml_content = story_data.yaml_content
    if story_data.description is not None:
        story.description = story_data.description
    if story_data.priority is not None:
        story.priority = story_data.priority
    if story_data.is_active is not None:
        story.is_active = story_data.is_active
    
    try:
        db.commit()
        db.refresh(story)
        logger.info(f"Story '{story.story_name}' updated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating story"
        )
    
    return RasaStoryOut.model_validate(story)


@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    story_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete a story (soft delete)"""
    user = ctx["user"]
    
    try:
        story_uuid = UUID(story_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid story ID format"
        )
    
    story = db.execute(
        select(RasaStory).where(RasaStory.id == story_uuid)
    ).scalar_one_or_none()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    story.is_active = False
    
    try:
        db.commit()
        logger.info(f"Story '{story.story_name}' deactivated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting story: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting story"
        )


# ==================== RASA RULES ====================

@router.post("/rules", response_model=RasaRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RasaRuleCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False)
):
    """Create a new Rasa rule"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    # Check if rule already exists
    existing_rule = db.execute(
        select(RasaRule).where(RasaRule.rule_name == rule_data.rule_name)
    ).scalar_one_or_none()
    
    if existing_rule:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule '{rule_data.rule_name}' already exists"
        )
    
    new_rule = RasaRule(
        school_id=UUID(school_id) if school_id else None,
        rule_name=rule_data.rule_name,
        content=rule_data.content,
        yaml_content=rule_data.yaml_content,
        description=rule_data.description,
        priority=rule_data.priority,
        created_by=user.id
    )
    
    db.add(new_rule)
    
    try:
        db.commit()
        db.refresh(new_rule)
        logger.info(f"Rule '{rule_data.rule_name}' created by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating rule"
        )
    
    return RasaRuleOut.model_validate(new_rule)


@router.get("/rules", response_model=List[RasaRuleOut])
async def list_rules(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None)
):
    """List all Rasa rules"""
    query = select(RasaRule)
    
    if active_only:
        query = query.where(RasaRule.is_active == True)
    
    if filter_school == "global":
        query = query.where(RasaRule.school_id == None)
    elif filter_school:
        query = query.where(RasaRule.school_id == UUID(filter_school))
    
    query = query.order_by(RasaRule.priority.desc(), RasaRule.rule_name)
    
    rules = db.execute(query).scalars().all()
    return [RasaRuleOut.model_validate(rule) for rule in rules]


@router.get("/rules/{rule_id}", response_model=RasaRuleOut)
async def get_rule(
    rule_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get a specific rule by ID"""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid rule ID format"
        )
    
    rule = db.execute(
        select(RasaRule).where(RasaRule.id == rule_uuid)
    ).scalar_one_or_none()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    return RasaRuleOut.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=RasaRuleOut)
async def update_rule(
    rule_id: str,
    rule_data: RasaRuleUpdate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update an existing rule"""
    user = ctx["user"]
    
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid rule ID format"
        )
    
    rule = db.execute(
        select(RasaRule).where(RasaRule.id == rule_uuid)
    ).scalar_one_or_none()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    if rule_data.rule_name is not None:
        existing = db.execute(
            select(RasaRule).where(
                RasaRule.rule_name == rule_data.rule_name,
                RasaRule.id != rule_uuid
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Rule name '{rule_data.rule_name}' already exists"
            )
        rule.rule_name = rule_data.rule_name
    
    if rule_data.content is not None:
        rule.content = rule_data.content
    if rule_data.yaml_content is not None:
        rule.yaml_content = rule_data.yaml_content
    if rule_data.description is not None:
        rule.description = rule_data.description
    if rule_data.priority is not None:
        rule.priority = rule_data.priority
    if rule_data.is_active is not None:
        rule.is_active = rule_data.is_active
    
    try:
        db.commit()
        db.refresh(rule)
        logger.info(f"Rule '{rule.rule_name}' updated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating rule"
        )
    
    return RasaRuleOut.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete a rule (soft delete)"""
    user = ctx["user"]
    
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid rule ID format"
        )
    
    rule = db.execute(
        select(RasaRule).where(RasaRule.id == rule_uuid)
    ).scalar_one_or_none()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    rule.is_active = False
    
    try:
        db.commit()
        logger.info(f"Rule '{rule.rule_name}' deactivated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting rule"
        )


# ==================== RASA RESPONSES ====================

@router.post("/responses", response_model=RasaResponseOut, status_code=status.HTTP_201_CREATED)
async def create_response(
    response_data: RasaResponseCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False)
):
    """Create a new Rasa response"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    # Check if response already exists
    existing_response = db.execute(
        select(RasaResponse).where(RasaResponse.utterance_name == response_data.utterance_name)
    ).scalar_one_or_none()
    
    if existing_response:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Response '{response_data.utterance_name}' already exists"
        )
    
    new_response = RasaResponse(
        school_id=UUID(school_id) if school_id else None,
        utterance_name=response_data.utterance_name,
        messages=response_data.messages,
        description=response_data.description,
        created_by=user.id
    )
    
    db.add(new_response)
    
    try:
        db.commit()
        db.refresh(new_response)
        logger.info(f"Response '{response_data.utterance_name}' created by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating response"
        )
    
    return RasaResponseOut.model_validate(new_response)


@router.get("/responses", response_model=List[RasaResponseOut])
async def list_responses(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None)
):
    """List all Rasa responses"""
    query = select(RasaResponse)
    
    if active_only:
        query = query.where(RasaResponse.is_active == True)
    
    if filter_school == "global":
        query = query.where(RasaResponse.school_id == None)
    elif filter_school:
        query = query.where(RasaResponse.school_id == UUID(filter_school))
    
    query = query.order_by(RasaResponse.utterance_name)
    
    responses = db.execute(query).scalars().all()
    return [RasaResponseOut.model_validate(response) for response in responses]


@router.get("/responses/{response_id}", response_model=RasaResponseOut)
async def get_response(
    response_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get a specific response by ID"""
    try:
        response_uuid = UUID(response_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid response ID format"
        )
    
    response = db.execute(
        select(RasaResponse).where(RasaResponse.id == response_uuid)
    ).scalar_one_or_none()
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found"
        )
    
    return RasaResponseOut.model_validate(response)


@router.put("/responses/{response_id}", response_model=RasaResponseOut)
async def update_response(
    response_id: str,
    response_data: RasaResponseUpdate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Update an existing response"""
    user = ctx["user"]
    
    try:
        response_uuid = UUID(response_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid response ID format"
        )
    
    response = db.execute(
        select(RasaResponse).where(RasaResponse.id == response_uuid)
    ).scalar_one_or_none()
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found"
        )
    
    if response_data.utterance_name is not None:
        existing = db.execute(
            select(RasaResponse).where(
                RasaResponse.utterance_name == response_data.utterance_name,
                RasaResponse.id != response_uuid
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Response name '{response_data.utterance_name}' already exists"
            )
        response.utterance_name = response_data.utterance_name
    
    if response_data.messages is not None:
        response.messages = response_data.messages
    if response_data.description is not None:
        response.description = response_data.description
    if response_data.is_active is not None:
        response.is_active = response_data.is_active
    
    try:
        db.commit()
        db.refresh(response)
        logger.info(f"Response '{response.utterance_name}' updated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating response"
        )
    
    return RasaResponseOut.model_validate(response)


@router.delete("/responses/{response_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_response(
    response_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Delete a response (soft delete)"""
    user = ctx["user"]
    
    try:
        response_uuid = UUID(response_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid response ID format"
        )
    
    response = db.execute(
        select(RasaResponse).where(RasaResponse.id == response_uuid)
    ).scalar_one_or_none()
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found"
        )
    
    response.is_active = False
    
    try:
        db.commit()
        logger.info(f"Response '{response.utterance_name}' deactivated by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting response"
        )


# ==================== RASA SLOTS ====================

@router.post("/slots", response_model=RasaSlotOut, status_code=status.HTTP_201_CREATED)
async def create_slot(
    slot_data: RasaSlotCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False)
):
    """Create a new Rasa slot"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    # Check if slot already exists
    existing_slot = db.execute(
        select(RasaSlot).where(RasaSlot.slot_name == slot_data.slot_name)
    ).scalar_one_or_none()
    
    if existing_slot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slot '{slot_data.slot_name}' already exists"
        )
    
    new_slot = RasaSlot(
        school_id=UUID(school_id) if school_id else None,
        slot_name=slot_data.slot_name,
        slot_type=slot_data.slot_type,
        influence_conversation=slot_data.influence_conversation,
        mappings=slot_data.mappings,
        initial_value=slot_data.initial_value,
        description=slot_data.description,
        created_by=user.id
    )
    
    db.add(new_slot)
    
    try:
        db.commit()
        db.refresh(new_slot)
        logger.info(f"Slot '{slot_data.slot_name}' created by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating slot"
        )
    
    return RasaSlotOut.model_validate(new_slot)


@router.get("/slots", response_model=List[RasaSlotOut])
async def list_slots(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None)
):
    """List all Rasa slots"""
    query = select(RasaSlot)
    
    if active_only:
        query = query.where(RasaSlot.is_active == True)
    
    if filter_school == "global":
        query = query.where(RasaSlot.school_id == None)
    elif filter_school:
        query = query.where(RasaSlot.school_id == UUID(filter_school))
    
    query = query.order_by(RasaSlot.slot_name)
    
    slots = db.execute(query).scalars().all()
    return [RasaSlotOut.model_validate(slot) for slot in slots]


# ==================== RASA FORMS ====================

@router.post("/forms", response_model=RasaFormOut, status_code=status.HTTP_201_CREATED)
async def create_form(
    form_data: RasaFormCreate,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    make_global: bool = Query(False)
):
    """Create a new Rasa form"""
    user = ctx["user"]
    school_id = None if make_global else ctx["school_id"]
    
    # Check if form already exists
    existing_form = db.execute(
        select(RasaForm).where(RasaForm.form_name == form_data.form_name)
    ).scalar_one_or_none()
    
    if existing_form:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Form '{form_data.form_name}' already exists"
        )
    
    new_form = RasaForm(
        school_id=UUID(school_id) if school_id else None,
        form_name=form_data.form_name,
        required_slots=form_data.required_slots,
        configuration=form_data.configuration,
        description=form_data.description,
        created_by=user.id
    )
    
    db.add(new_form)
    
    try:
        db.commit()
        db.refresh(new_form)
        logger.info(f"Form '{form_data.form_name}' created by {user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating form: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating form"
        )
    
    return RasaFormOut.model_validate(new_form)


@router.get("/forms", response_model=List[RasaFormOut])
async def list_forms(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
    filter_school: Optional[str] = Query(None)
):
    """List all Rasa forms"""
    query = select(RasaForm)
    
    if active_only:
        query = query.where(RasaForm.is_active == True)
    
    if filter_school == "global":
        query = query.where(RasaForm.school_id == None)
    elif filter_school:
        query = query.where(RasaForm.school_id == UUID(filter_school))
    
    query = query.order_by(RasaForm.form_name)
    
    forms = db.execute(query).scalars().all()
    return [RasaFormOut.model_validate(form) for form in forms]


# ==================== EXPORT/IMPORT ====================

@router.get("/export", response_model=RasaContentExport)
async def export_all_content(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    filter_school: Optional[str] = Query(None, description="Filter by school or 'global'")
):
    """Export all Rasa content"""
    
    # Build filter condition
    def build_filter(model_class):
        query = select(model_class).where(model_class.is_active == True)
        if filter_school == "global":
            query = query.where(model_class.school_id == None)
        elif filter_school:
            query = query.where(model_class.school_id == UUID(filter_school))
        return query
    
    # Fetch all content
    intents = db.execute(build_filter(NLUIntent).order_by(NLUIntent.intent_name)).scalars().all()
    entities = db.execute(build_filter(NLUEntity).order_by(NLUEntity.entity_name)).scalars().all()
    stories = db.execute(build_filter(RasaStory).order_by(RasaStory.priority.desc())).scalars().all()
    rules = db.execute(build_filter(RasaRule).order_by(RasaRule.priority.desc())).scalars().all()
    responses = db.execute(build_filter(RasaResponse).order_by(RasaResponse.utterance_name)).scalars().all()
    actions = db.execute(build_filter(RasaAction).order_by(RasaAction.action_name)).scalars().all()
    slots = db.execute(build_filter(RasaSlot).order_by(RasaSlot.slot_name)).scalars().all()
    forms = db.execute(build_filter(RasaForm).order_by(RasaForm.form_name)).scalars().all()
    
    return RasaContentExport(
        intents=[NLUIntentOut.model_validate(i) for i in intents],
        entities=[NLUEntityOut.model_validate(e) for e in entities],
        stories=[RasaStoryOut.model_validate(s) for s in stories],
        rules=[RasaRuleOut.model_validate(r) for r in rules],
        responses=[RasaResponseOut.model_validate(r) for r in responses],
        actions=[RasaActionOut.model_validate(a) for a in actions],
        slots=[RasaSlotOut.model_validate(s) for s in slots],
        forms=[RasaFormOut.model_validate(f) for f in forms]
    )


# ==================== TRAINING JOBS ====================

@router.post("/train", response_model=TrainingJobOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_training(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Trigger a new Rasa training job"""
    user = ctx["user"]
    
    # Create training job (school_id = NULL for global model)
    training_job = TrainingJob(
        school_id=None,  # Global model
        status="pending",
        triggered_by=user.id
    )
    
    db.add(training_job)
    
    try:
        db.commit()
        db.refresh(training_job)
        logger.info(f"Training job {training_job.id} created by {user.email}")
        
        # Import here to avoid circular imports
        from app.services.rasa_trainer import train_rasa_model_async
        
        # Add training to background tasks if available
        if background_tasks:
            background_tasks.add_task(train_rasa_model_async, db, training_job.id)
            logger.info(f"Training job {training_job.id} added to background tasks")
        else:
            # If no background tasks, run synchronously (not recommended for production)
            logger.warning("No background tasks available, training will run synchronously")
            from app.services.rasa_trainer import RasaTrainer
            trainer = RasaTrainer(db)
            training_job = trainer.train_model(training_job.id)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating training job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating training job"
        )
    
    return TrainingJobOut.model_validate(training_job)


@router.get("/train/jobs", response_model=List[TrainingJobOut])
async def list_training_jobs(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    limit: int = Query(10, le=50)
):
    """List recent training jobs"""
    
    jobs = db.execute(
        select(TrainingJob)
        .where(TrainingJob.school_id == None)  # Global model jobs
        .order_by(TrainingJob.created_at.desc())
        .limit(limit)
    ).scalars().all()
    
    return [TrainingJobOut.model_validate(job) for job in jobs]


@router.post("/train/jobs/{job_id}", response_model=TrainingJobOut)
async def get_training_job(
    job_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get training job details"""
    
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job ID format"
        )
    
    job = db.execute(
        select(TrainingJob).where(TrainingJob.id == job_uuid)
    ).scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training job not found"
        )
    
    return TrainingJobOut.model_validate(job)


@router.post("/restart-bot", status_code=status.HTTP_200_OK)
async def restart_rasa_bot(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Restart the Rasa bot using PM2"""
    import subprocess
    
    user = ctx["user"]
    
    try:
        logger.info(f"Restarting Rasa bot requested by {user.email}")
        
        # Execute PM2 restart command
        result = subprocess.run(
            ['pm2', 'restart', 'rasa-server'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"Rasa bot restarted successfully by {user.email}")
            return {
                "status": "success",
                "message": "Rasa bot restarted successfully",
                "output": result.stdout
            }
        else:
            logger.error(f"PM2 restart failed: {result.stderr}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart bot: {result.stderr}"
            )
    
    except subprocess.TimeoutExpired:
        logger.error("PM2 restart command timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Restart command timed out after 30 seconds"
        )
    
    except FileNotFoundError:
        logger.error("PM2 not found - is it installed?")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PM2 not found. Please ensure PM2 is installed: npm install -g pm2"
        )
    
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error restarting bot: {str(e)}"
        )


@router.post("/deploy-automated", status_code=status.HTTP_202_ACCEPTED)
async def deploy_model_automated(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    auto_restart: bool = Query(True, description="Automatically restart bot after training")
):
    """
    Fully automated deployment workflow with status tracking
    Creates a training job, trains the model, and optionally restarts the bot
    """
    user = ctx["user"]
    
    # Create training job
    training_job = TrainingJob(
        school_id=None,
        status="pending",
        triggered_by=user.id
    )
    
    db.add(training_job)
    db.commit()
    db.refresh(training_job)
    
    logger.info(f"Automated deployment started by {user.email}, job: {training_job.id}")
    
    # Import automation service
    from app.services.training_automation import TrainingAutomation
    automation = TrainingAutomation(db)
    
    # Define notification callback (could be extended to send emails/webhooks)
    async def notify(event_data: dict):
        logger.info(f"Training event: {event_data['event']} for job {event_data.get('job_id')}")
        # TODO: Send actual notifications (email, webhook, etc.)
    
    try:
        # Run automated workflow
        result = await automation.train_and_deploy(
            training_job.id,
            auto_restart=auto_restart,
            notification_callback=notify
        )
        
        return {
            "status": "initiated",
            "job_id": str(training_job.id),
            "message": "Automated deployment started",
            "auto_restart": auto_restart,
            "workflow_result": result
        }
        
    except Exception as e:
        logger.error(f"Automated deployment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment automation failed: {str(e)}"
        )


@router.get("/train/jobs/{job_id}/summary")
async def get_training_summary(
    job_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get detailed training job summary with formatted information"""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job ID format"
        )
    
    from app.services.training_automation import TrainingAutomation
    automation = TrainingAutomation(db)
    
    summary = automation.get_training_summary(job_uuid)
    
    if 'error' in summary and summary['error'] == 'Job not found':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training job not found"
        )
    
    return summary


@router.get("/train/history")
async def get_training_history(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status: completed, failed, running")
):
    """Get training history with statistics"""
    query = select(TrainingJob).where(TrainingJob.school_id == None)
    
    if status_filter:
        query = query.where(TrainingJob.status == status_filter)
    
    jobs = db.execute(
        query.order_by(TrainingJob.created_at.desc()).limit(limit)
    ).scalars().all()
    
    # Calculate statistics
    total_jobs = db.execute(
        select(TrainingJob).where(TrainingJob.school_id == None)
    ).scalars().all().__len__()
    
    completed_jobs = db.execute(
        select(TrainingJob).where(
            TrainingJob.school_id == None,
            TrainingJob.status == "completed"
        )
    ).scalars().all()
    
    failed_jobs = db.execute(
        select(TrainingJob).where(
            TrainingJob.school_id == None,
            TrainingJob.status == "failed"
        )
    ).scalars().all()
    
    # Calculate average duration for completed jobs
    avg_duration = None
    if completed_jobs:
        durations = [j.duration_seconds for j in completed_jobs if j.duration_seconds]
        if durations:
            avg_duration = sum(durations) / len(durations)
    
    return {
        "jobs": [TrainingJobOut.model_validate(job) for job in jobs],
        "statistics": {
            "total_jobs": total_jobs,
            "completed": len(completed_jobs),
            "failed": len(failed_jobs),
            "success_rate": (len(completed_jobs) / total_jobs * 100) if total_jobs > 0 else 0,
            "average_duration_seconds": avg_duration,
            "average_duration_formatted": automation._format_duration(avg_duration) if avg_duration else None
        }
    }
async def deploy_model(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
    model_path: Optional[str] = Query(None, description="Specific model to deploy, or latest if not specified")
):
    """
    Complete deployment workflow: Train -> Deploy -> Restart
    This endpoint trains a new model, then automatically restarts the bot
    """
    import subprocess
    from pathlib import Path
    
    user = ctx["user"]
    
    # Step 1: Create and start training job
    training_job = TrainingJob(
        school_id=None,
        status="pending",
        triggered_by=user.id
    )
    
    db.add(training_job)
    db.commit()
    db.refresh(training_job)
    
    logger.info(f"Deployment initiated by {user.email}, training job: {training_job.id}")
    
    try:
        # Step 2: Train the model (synchronously for deployment)
        from app.services.rasa_trainer import RasaTrainer
        trainer = RasaTrainer(db)
        training_job = trainer.train_model(training_job.id)
        
        if training_job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Training failed: {training_job.error_message}"
            )
        
        # Step 3: Restart the bot with new model
        logger.info(f"Training completed, restarting bot with model: {training_job.model_path}")
        
        result = subprocess.run(
            ['pm2', 'restart', 'rasa-server'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"Bot restarted successfully with new model")
            return {
                "status": "success",
                "message": "Model trained and bot restarted successfully",
                "training_job_id": str(training_job.id),
                "model_path": training_job.model_path,
                "training_stats": training_job.training_metadata
            }
        else:
            logger.warning(f"Training succeeded but restart failed: {result.stderr}")
            return {
                "status": "partial_success",
                "message": "Model trained but bot restart failed",
                "training_job_id": str(training_job.id),
                "model_path": training_job.model_path,
                "restart_error": result.stderr
            }
    
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment failed: {str(e)}"
        )


# ==================== STATISTICS ====================

@router.get("/stats")
async def get_content_statistics(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get statistics about Rasa content"""
    
    stats = {
        "intents": {
            "total": db.execute(select(NLUIntent).where(NLUIntent.is_active == True)).scalars().all().__len__(),
            "global": db.execute(select(NLUIntent).where(NLUIntent.is_active == True, NLUIntent.school_id == None)).scalars().all().__len__(),
        },
        "entities": {
            "total": db.execute(select(NLUEntity).where(NLUEntity.is_active == True)).scalars().all().__len__(),
            "global": db.execute(select(NLUEntity).where(NLUEntity.is_active == True, NLUEntity.school_id == None)).scalars().all().__len__(),
        },
        "stories": {
            "total": db.execute(select(RasaStory).where(RasaStory.is_active == True)).scalars().all().__len__(),
            "global": db.execute(select(RasaStory).where(RasaStory.is_active == True, RasaStory.school_id == None)).scalars().all().__len__(),
        },
        "rules": {
            "total": db.execute(select(RasaRule).where(RasaRule.is_active == True)).scalars().all().__len__(),
            "global": db.execute(select(RasaRule).where(RasaRule.is_active == True, RasaRule.school_id == None)).scalars().all().__len__(),
        },
        "responses": {
            "total": db.execute(select(RasaResponse).where(RasaResponse.is_active == True)).scalars().all().__len__(),
            "global": db.execute(select(RasaResponse).where(RasaResponse.is_active == True, RasaResponse.school_id == None)).scalars().all().__len__(),
        },
        "training_jobs": {
            "total": db.execute(select(TrainingJob)).scalars().all().__len__(),
            "completed": db.execute(select(TrainingJob).where(TrainingJob.status == "completed")).scalars().all().__len__(),
            "failed": db.execute(select(TrainingJob).where(TrainingJob.status == "failed")).scalars().all().__len__(),
        }
    }
    
    return stats


@router.post("/rollback/{job_id}", status_code=status.HTTP_200_OK)
async def rollback_model(
    job_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    auto_restart: bool = Query(True, description="Automatically restart bot after rollback")
):
    """
    Rollback to a previous model version
    
    This will:
    1. Set the target model as active
    2. Restore YAML files from snapshot
    3. Optionally restart the bot
    """
    user = ctx["user"]
    
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job ID format"
        )
    
    try:
        rollback_service = RasaRollback(db)
        result = rollback_service.rollback_to_version(job_uuid, auto_restart)
        
        logger.info(f"Rollback to {result['model_version']} completed by {user.email}")
        
        return {
            "status": "success",
            "message": f"Successfully rolled back to version {result['model_version']}",
            **result
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}"
        )


@router.get("/versions", response_model=List[dict])
async def list_model_versions(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100)
):
    """Get list of all model versions with details"""
    rollback_service = RasaRollback(db)
    versions = rollback_service.get_version_history(limit)
    return versions


@router.get("/versions/{job_id}/snapshot")
async def get_version_snapshot(
    job_id: str,
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get the YAML snapshot for a specific version"""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job ID format"
        )
    
    job = db.execute(
        select(TrainingJob).where(TrainingJob.id == job_uuid)
    ).scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training job not found"
        )
    
    return {
        'version': job.model_version,
        'yaml_snapshot': job.yaml_snapshot,
        'content_counts': job.content_counts,
        'created_at': job.created_at.isoformat(),
        'is_active': job.is_active
    }


@router.get("/active-version")
async def get_active_version(
    ctx: Dict[str, Any] = Depends(require_school),
    db: Session = Depends(get_db)
):
    """Get currently active model version"""
    active_job = db.execute(
        select(TrainingJob).where(
            TrainingJob.school_id == None,
            TrainingJob.is_active == True
        )
    ).scalar_one_or_none()
    
    if not active_job:
        return {
            'has_active_version': False,
            'message': 'No active model version found'
        }
    
    return {
        'has_active_version': True,
        'version': active_job.model_version,
        'model_path': active_job.model_path,
        'deployed_at': active_job.created_at.isoformat(),
        'content_counts': active_job.content_counts
    }