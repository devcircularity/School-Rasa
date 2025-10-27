#!/usr/bin/env python3
"""
Train a global Rasa model from database content
This script aggregates ALL active content from all schools into one model
Usage: python scripts/train_global_model.py --output-dir ./models
"""
import argparse
import yaml
import sys
import uuid
import subprocess
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.db import get_engine
from app.models.rasa_content import (
    NLUIntent, NLUEntity, RasaStory, RasaRule,
    RasaResponse, RasaSlot, RasaForm, TrainingJob
)


# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def generate_nlu_yml(output_path: Path, db: Session):
    """Generate global nlu.yml from all active intents"""
    print("Generating nlu.yml...")
    
    # Get ALL active intents (school_id can be NULL or any value)
    intents = db.execute(
        select(NLUIntent).where(NLUIntent.is_active == True)
        .order_by(NLUIntent.intent_name)
    ).scalars().all()
    
    entities = db.execute(
        select(NLUEntity).where(
            NLUEntity.is_active == True,
            NLUEntity.entity_type == 'lookup'
        ).order_by(NLUEntity.entity_name)
    ).scalars().all()
    
    nlu_data = {'version': '3.1', 'nlu': []}
    
    # Add intents
    for intent in intents:
        intent_data = {
            'intent': intent.intent_name,
            'examples': '|\n' + '\n'.join(f'    - {ex}' for ex in intent.examples)
        }
        nlu_data['nlu'].append(intent_data)
    
    # Add lookup entities
    for entity in entities:
        if entity.patterns:
            lookup_data = {
                'lookup': entity.entity_name,
                'examples': '|\n' + '\n'.join(f'    - {pattern}' for pattern in entity.patterns)
            }
            nlu_data['nlu'].append(lookup_data)
    
    with open(output_path / 'nlu.yml', 'w', encoding='utf-8') as f:
        yaml.dump(nlu_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"  ✓ {len(intents)} intents, {len(entities)} entities")


def generate_stories_yml(output_path: Path, db: Session):
    """Generate global stories.yml"""
    print("Generating stories.yml...")
    
    stories = db.execute(
        select(RasaStory).where(RasaStory.is_active == True)
        .order_by(RasaStory.priority.desc(), RasaStory.story_name)
    ).scalars().all()
    
    stories_data = {'version': '3.1', 'stories': []}
    
    for story in stories:
        story_dict = {
            'story': story.story_name,
            'steps': story.content.get('steps', [])
        }
        if story.content.get('metadata'):
            story_dict['metadata'] = story.content['metadata']
        stories_data['stories'].append(story_dict)
    
    with open(output_path / 'stories.yml', 'w', encoding='utf-8') as f:
        yaml.dump(stories_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"  ✓ {len(stories)} stories")


def generate_rules_yml(output_path: Path, db: Session):
    """Generate global rules.yml"""
    print("Generating rules.yml...")
    
    rules = db.execute(
        select(RasaRule).where(RasaRule.is_active == True)
        .order_by(RasaRule.priority.desc(), RasaRule.rule_name)
    ).scalars().all()
    
    rules_data = {'version': '3.1', 'rules': []}
    
    for rule in rules:
        rule_dict = {
            'rule': rule.rule_name,
            'steps': rule.content.get('steps', [])
        }
        if rule.content.get('condition'):
            rule_dict['condition'] = rule.content['condition']
        if rule.content.get('metadata'):
            rule_dict['metadata'] = rule.content['metadata']
        rules_data['rules'].append(rule_dict)
    
    with open(output_path / 'rules.yml', 'w', encoding='utf-8') as f:
        yaml.dump(rules_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"  ✓ {len(rules)} rules")


def generate_domain_yml(output_path: Path, db: Session):
    """Generate global domain.yml"""
    print("Generating domain.yml...")
    
    intents = db.execute(
        select(NLUIntent.intent_name).where(NLUIntent.is_active == True)
        .order_by(NLUIntent.intent_name)
    ).scalars().all()
    
    entities = db.execute(
        select(NLUEntity.entity_name).where(NLUEntity.is_active == True)
        .order_by(NLUEntity.entity_name)
    ).scalars().all()
    
    responses = db.execute(
        select(RasaResponse).where(RasaResponse.is_active == True)
        .order_by(RasaResponse.utterance_name)
    ).scalars().all()
    
    slots = db.execute(
        select(RasaSlot).where(RasaSlot.is_active == True)
        .order_by(RasaSlot.slot_name)
    ).scalars().all()
    
    forms = db.execute(
        select(RasaForm).where(RasaForm.is_active == True)
        .order_by(RasaForm.form_name)
    ).scalars().all()
    
    domain_data = {
        'version': '3.1',
        'intents': list(set(intents)),
        'entities': list(set(entities)),
        'slots': {},
        'responses': {},
        'actions': [],
        'forms': {},
        'session_config': {
            'session_expiration_time': 60,
            'carry_over_slots_to_new_session': False
        }
    }
    
    # Add responses
    for response in responses:
        domain_data['responses'][response.utterance_name] = response.messages
    
    # Add slots
    for slot in slots:
        slot_config = {
            'type': slot.slot_type,
            'influence_conversation': slot.influence_conversation,
            'mappings': slot.mappings
        }
        if slot.initial_value:
            slot_config['initial_value'] = slot.initial_value
        domain_data['slots'][slot.slot_name] = slot_config
    
    # Add forms
    for form in forms:
        form_config = {'required_slots': form.required_slots}
        if form.configuration:
            form_config.update(form.configuration)
        domain_data['forms'][form.form_name] = form_config
    
    # Add actions
    domain_data['actions'] = [r.utterance_name for r in responses]
    
    with open(output_path / 'domain.yml', 'w', encoding='utf-8') as f:
        yaml.dump(domain_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"  ✓ {len(intents)} intents, {len(responses)} responses, {len(slots)} slots, {len(forms)} forms")


def train_model(rasa_dir: Path, output_dir: Path, db: Session, user_id: uuid.UUID = None):
    """Run Rasa training"""
    print("\nStarting Rasa training...")
    
    # Create training job record
    training_job = TrainingJob(
        school_id=None,  # NULL = global model
        status="running",
        triggered_by=user_id or uuid.uuid4(),
        started_at=datetime.utcnow()
    )
    db.add(training_job)
    db.commit()
    db.refresh(training_job)
    
    try:
        # Run rasa train
        cmd = [
            'rasa', 'train',
            '--domain', str(rasa_dir / 'domain.yml'),
            '--data', str(rasa_dir / 'data'),
            '--out', str(output_dir),
            '--fixed-model-name', 'global_model'
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=rasa_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            model_path = output_dir / 'global_model.tar.gz'
            training_job.status = "completed"
            training_job.model_path = str(model_path)
            training_job.logs = result.stdout
            training_job.completed_at = datetime.utcnow()
            training_job.metadata = {
                'intents_count': len(list((rasa_dir / 'data').glob('*.yml'))),
                'trained_at': datetime.utcnow().isoformat()
            }
            print(f"\n✅ Training completed! Model saved to: {model_path}")
        else:
            training_job.status = "failed"
            training_job.error_message = result.stderr
            training_job.logs = result.stdout
            training_job.completed_at = datetime.utcnow()
            print(f"\n❌ Training failed!")
            print(result.stderr)
            sys.exit(1)
        
        db.commit()
        return training_job
        
    except Exception as e:
        training_job.status = "failed"
        training_job.error_message = str(e)
        training_job.completed_at = datetime.utcnow()
        db.commit()
        raise


def main():
    parser = argparse.ArgumentParser(description='Train global Rasa model from database')
    parser.add_argument('--output-dir', default='./models', help='Output directory for trained model')
    parser.add_argument('--rasa-dir', default='./rasa_training', help='Temporary directory for training files')
    parser.add_argument('--user-id', help='User UUID triggering training (optional)')
    parser.add_argument('--skip-train', action='store_true', help='Only generate files, skip training')
    
    args = parser.parse_args()
    
    rasa_path = Path(args.rasa_dir)
    output_path = Path(args.output_dir)
    data_path = rasa_path / 'data'
    
    # Create directories
    rasa_path.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Parse user_id if provided
    user_id = None
    if args.user_id:
        try:
            user_id = uuid.UUID(args.user_id)
        except ValueError:
            print(f"Warning: Invalid user_id format, ignoring")
    
    # Connect to database
    engine = get_engine()
    db = Session(engine)
    
    try:
        print("🚀 Training Global Rasa Model")
        print("=" * 60)
        
        # Generate all YAML files
        generate_nlu_yml(data_path, db)
        generate_stories_yml(data_path, db)
        generate_rules_yml(data_path, db)
        generate_domain_yml(rasa_path, db)
        
        if args.skip_train:
            print("\n✓ Files generated. Skipping training (--skip-train)")
            print(f"Files available at: {rasa_path.absolute()}")
        else:
            # Train model
            job = train_model(rasa_path, output_path, db, user_id)
            print(f"\nTraining job ID: {job.id}")
            print(f"Status: {job.status}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == '__main__':
    main()