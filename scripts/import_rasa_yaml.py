#!/usr/bin/env python3
"""
Script to import existing Rasa YAML files into PostgreSQL database
Usage: python scripts/import_rasa_yaml.py --school-id <uuid> --user-id <uuid>
"""
import argparse
import yaml
import sys
import uuid
from pathlib import Path
from sqlalchemy.orm import Session

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.db import get_engine
from app.models.rasa_content import (
    NLUIntent, NLUEntity, RasaStory, RasaRule, 
    RasaResponse, RasaAction, RasaSlot, RasaForm
)


def parse_nlu_yaml(file_path: Path, school_id: uuid.UUID, user_id: uuid.UUID, db: Session):
    """Parse nlu.yml and import intents and entities"""
    print(f"Parsing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data or 'nlu' not in data:
        print("No NLU data found in file")
        return
    
    intents_imported = 0
    entities_imported = 0
    
    for item in data['nlu']:
        if 'intent' in item:
            intent_name = item['intent']
            examples = []
            
            # Parse examples
            if 'examples' in item:
                examples_text = item['examples'].strip()
                for line in examples_text.split('\n'):
                    line = line.strip()
                    if line.startswith('- '):
                        examples.append(line[2:])
            
            # Create intent
            intent = NLUIntent(
                id=uuid.uuid4(),
                school_id=school_id,
                intent_name=intent_name,
                examples=examples,
                created_by=user_id
            )
            db.add(intent)
            intents_imported += 1
            
            print(f"  ✓ Intent: {intent_name} ({len(examples)} examples)")
        
        elif 'lookup' in item:
            # Handle lookup tables as entities
            entity_name = item['lookup']
            patterns = []
            
            if 'examples' in item:
                examples_text = item['examples'].strip()
                for line in examples_text.split('\n'):
                    line = line.strip()
                    if line.startswith('- '):
                        patterns.append(line[2:])
            
            entity = NLUEntity(
                id=uuid.uuid4(),
                school_id=school_id,
                entity_name=entity_name,
                entity_type='lookup',
                patterns=patterns,
                created_by=user_id
            )
            db.add(entity)
            entities_imported += 1
            
            print(f"  ✓ Lookup Entity: {entity_name} ({len(patterns)} patterns)")
    
    print(f"Imported {intents_imported} intents and {entities_imported} entities")


def parse_stories_yaml(file_path: Path, school_id: uuid.UUID, user_id: uuid.UUID, db: Session):
    """Parse stories.yml and import stories"""
    print(f"Parsing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        data = yaml.safe_load(content)
    
    if not data or 'stories' not in data:
        print("No stories data found in file")
        return
    
    stories_imported = 0
    
    for story in data['stories']:
        story_name = story.get('story', 'Unnamed Story')
        steps = story.get('steps', [])
        
        # Convert steps to JSON-serializable format
        content_data = {
            'steps': steps,
            'metadata': story.get('metadata', {})
        }
        
        # Create story
        story_obj = RasaStory(
            id=uuid.uuid4(),
            school_id=school_id,
            story_name=story_name,
            content=content_data,
            yaml_content=yaml.dump(story, default_flow_style=False),
            created_by=user_id
        )
        db.add(story_obj)
        stories_imported += 1
        
        print(f"  ✓ Story: {story_name} ({len(steps)} steps)")
    
    print(f"Imported {stories_imported} stories")


def parse_rules_yaml(file_path: Path, school_id: uuid.UUID, user_id: uuid.UUID, db: Session):
    """Parse rules.yml and import rules"""
    print(f"Parsing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        data = yaml.safe_load(content)
    
    if not data or 'rules' not in data:
        print("No rules data found in file")
        return
    
    rules_imported = 0
    
    for rule in data['rules']:
        rule_name = rule.get('rule', 'Unnamed Rule')
        steps = rule.get('steps', [])
        condition = rule.get('condition')
        
        # Convert to JSON-serializable format
        content_data = {
            'steps': steps,
            'condition': condition,
            'metadata': rule.get('metadata', {})
        }
        
        # Create rule
        rule_obj = RasaRule(
            id=uuid.uuid4(),
            school_id=school_id,
            rule_name=rule_name,
            content=content_data,
            yaml_content=yaml.dump(rule, default_flow_style=False),
            created_by=user_id
        )
        db.add(rule_obj)
        rules_imported += 1
        
        print(f"  ✓ Rule: {rule_name} ({len(steps)} steps)")
    
    print(f"Imported {rules_imported} rules")


def parse_domain_yaml(file_path: Path, school_id: uuid.UUID, user_id: uuid.UUID, db: Session):
    """Parse domain.yml and import responses, actions, slots, and forms"""
    print(f"Parsing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data:
        print("No domain data found in file")
        return
    
    responses_imported = 0
    slots_imported = 0
    forms_imported = 0
    actions_imported = 0
    
    # Import responses
    if 'responses' in data:
        for utterance_name, messages in data['responses'].items():
            # Convert messages to proper format
            message_list = []
            for msg in messages:
                if isinstance(msg, str):
                    message_list.append({'text': msg})
                elif isinstance(msg, dict):
                    message_list.append(msg)
            
            response = RasaResponse(
                id=uuid.uuid4(),
                school_id=school_id,
                utterance_name=utterance_name,
                messages=message_list,
                created_by=user_id
            )
            db.add(response)
            responses_imported += 1
            
            print(f"  ✓ Response: {utterance_name} ({len(message_list)} variations)")
    
    # Import slots
    if 'slots' in data:
        for slot_name, slot_config in data['slots'].items():
            slot_type = slot_config.get('type', 'text')
            influence_conversation = slot_config.get('influence_conversation', True)
            mappings = slot_config.get('mappings', [])
            initial_value = slot_config.get('initial_value')
            
            slot = RasaSlot(
                id=uuid.uuid4(),
                school_id=school_id,
                slot_name=slot_name,
                slot_type=slot_type,
                influence_conversation=influence_conversation,
                mappings=mappings,
                initial_value=str(initial_value) if initial_value else None,
                created_by=user_id
            )
            db.add(slot)
            slots_imported += 1
            
            print(f"  ✓ Slot: {slot_name} (type: {slot_type})")
    
    # Import forms
    if 'forms' in data:
        for form_name, form_config in data['forms'].items():
            required_slots = form_config.get('required_slots', [])
            
            form = RasaForm(
                id=uuid.uuid4(),
                school_id=school_id,
                form_name=form_name,
                required_slots=required_slots,
                configuration=form_config,
                created_by=user_id
            )
            db.add(form)
            forms_imported += 1
            
            print(f"  ✓ Form: {form_name} ({len(required_slots)} required slots)")
    
    # Import action names (just the names, not the code)
    if 'actions' in data:
        for action_name in data['actions']:
            # Skip utter_ actions as they're already in responses
            if action_name.startswith('utter_'):
                continue
            
            action = RasaAction(
                id=uuid.uuid4(),
                school_id=school_id,
                action_name=action_name,
                python_code=f"# Action code for {action_name}\n# TODO: Import from actions.py",
                description=f"Placeholder for custom action {action_name}",
                created_by=user_id
            )
            db.add(action)
            actions_imported += 1
            
            print(f"  ✓ Action: {action_name}")
    
    print(f"Imported {responses_imported} responses, {slots_imported} slots, {forms_imported} forms, {actions_imported} actions")


def main():
    parser = argparse.ArgumentParser(description='Import Rasa YAML files to PostgreSQL')
    parser.add_argument('--school-id', required=True, help='School UUID')
    parser.add_argument('--user-id', required=True, help='User UUID who is importing')
    parser.add_argument('--rasa-dir', default='rasa', help='Path to Rasa project directory')
    
    args = parser.parse_args()
    
    try:
        school_id = uuid.UUID(args.school_id)
        user_id = uuid.UUID(args.user_id)
    except ValueError as e:
        print(f"Error: Invalid UUID format - {e}")
        sys.exit(1)
    
    rasa_path = Path(args.rasa_dir)
    if not rasa_path.exists():
        print(f"Error: Rasa directory not found: {rasa_path}")
        sys.exit(1)
    
    # Setup database connection
    engine = get_engine()
    db = Session(engine)
    
    try:
        print(f"\n🚀 Starting Rasa YAML import for school {school_id}")
        print("=" * 60)
        
        # Parse and import each file
        nlu_file = rasa_path / 'data' / 'nlu.yml'
        if nlu_file.exists():
            parse_nlu_yaml(nlu_file, school_id, user_id, db)
        else:
            print(f"⚠️  NLU file not found: {nlu_file}")
        
        stories_file = rasa_path / 'data' / 'stories.yml'
        if stories_file.exists():
            parse_stories_yaml(stories_file, school_id, user_id, db)
        else:
            print(f"⚠️  Stories file not found: {stories_file}")
        
        rules_file = rasa_path / 'data' / 'rules.yml'
        if rules_file.exists():
            parse_rules_yaml(rules_file, school_id, user_id, db)
        else:
            print(f"⚠️  Rules file not found: {rules_file}")
        
        domain_file = rasa_path / 'domain.yml'
        if domain_file.exists():
            parse_domain_yaml(domain_file, school_id, user_id, db)
        else:
            print(f"⚠️  Domain file not found: {domain_file}")
        
        # Commit all changes
        db.commit()
        
        print("\n" + "=" * 60)
        print("✅ Import completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == '__main__':
    main()