# app/services/rasa_generator.py
"""
Service to generate Rasa YAML files and action code from database
"""
import yaml
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
import logging

from app.models.rasa_content import (
    NLUIntent, NLUEntity, RasaStory, RasaRule,
    RasaResponse, RasaAction, RasaSlot, RasaForm
)

logger = logging.getLogger(__name__)


class RasaFileGenerator:
    """Generates Rasa training files from database content"""
    
    def __init__(self, db: Session, output_dir: Path):
        self.db = db
        self.output_dir = Path(output_dir)
        self.data_dir = self.output_dir / 'data'
        self.actions_dir = self.output_dir / 'actions'
        
    def generate_all_files(self):
        """Generate all Rasa files from database"""
        logger.info("Generating Rasa files from database...")
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.actions_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate each file
        self.generate_nlu_yml()
        self.generate_stories_yml()
        self.generate_rules_yml()
        self.generate_domain_yml()
        self.generate_action_files()
        
        logger.info("All Rasa files generated successfully")
        
    def generate_nlu_yml(self):
        """Generate nlu.yml from database"""
        logger.info("Generating nlu.yml...")
        
        # Fetch all active intents
        intents = self.db.execute(
            select(NLUIntent)
            .where(NLUIntent.is_active == True)
            .order_by(NLUIntent.intent_name)
        ).scalars().all()
        
        # Fetch all active lookup entities
        entities = self.db.execute(
            select(NLUEntity)
            .where(
                NLUEntity.is_active == True,
                NLUEntity.entity_type == 'lookup'
            )
            .order_by(NLUEntity.entity_name)
        ).scalars().all()
        
        # Build NLU data structure
        nlu_data = {'version': '3.1', 'nlu': []}
        
        # Add intents
        for intent in intents:
            intent_item = {
                'intent': intent.intent_name,
                'examples': '|\n' + '\n'.join(f'    - {ex}' for ex in intent.examples)
            }
            nlu_data['nlu'].append(intent_item)
        
        # Add lookup entities
        for entity in entities:
            if entity.patterns:
                lookup_item = {
                    'lookup': entity.entity_name,
                    'examples': '|\n' + '\n'.join(f'    - {p}' for p in entity.patterns)
                }
                nlu_data['nlu'].append(lookup_item)
        
        # Write to file
        output_file = self.data_dir / 'nlu.yml'
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(nlu_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        logger.info(f"Generated nlu.yml with {len(intents)} intents and {len(entities)} entities")
        
    def generate_stories_yml(self):
        """Generate stories.yml from database"""
        logger.info("Generating stories.yml...")
        
        stories = self.db.execute(
            select(RasaStory)
            .where(RasaStory.is_active == True)
            .order_by(RasaStory.priority.desc(), RasaStory.story_name)
        ).scalars().all()
        
        stories_data = {'version': '3.1', 'stories': []}
        
        for story in stories:
            story_item = {
                'story': story.story_name,
                'steps': story.content.get('steps', [])
            }
            
            if story.content.get('metadata'):
                story_item['metadata'] = story.content['metadata']
            
            stories_data['stories'].append(story_item)
        
        output_file = self.data_dir / 'stories.yml'
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(stories_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        logger.info(f"Generated stories.yml with {len(stories)} stories")
        
    def generate_rules_yml(self):
        """Generate rules.yml from database"""
        logger.info("Generating rules.yml...")
        
        rules = self.db.execute(
            select(RasaRule)
            .where(RasaRule.is_active == True)
            .order_by(RasaRule.priority.desc(), RasaRule.rule_name)
        ).scalars().all()
        
        rules_data = {'version': '3.1', 'rules': []}
        
        for rule in rules:
            rule_item = {
                'rule': rule.rule_name,
                'steps': rule.content.get('steps', [])
            }
            
            if rule.content.get('condition'):
                rule_item['condition'] = rule.content['condition']
            
            if rule.content.get('metadata'):
                rule_item['metadata'] = rule.content['metadata']
            
            rules_data['rules'].append(rule_item)
        
        output_file = self.data_dir / 'rules.yml'
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(rules_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        logger.info(f"Generated rules.yml with {len(rules)} rules")
        
    def generate_domain_yml(self):
        """Generate domain.yml from database"""
        logger.info("Generating domain.yml...")
        
        # Fetch all domain components
        intents = self.db.execute(
            select(NLUIntent.intent_name)
            .where(NLUIntent.is_active == True)
            .order_by(NLUIntent.intent_name)
        ).scalars().all()
        
        entities = self.db.execute(
            select(NLUEntity.entity_name)
            .where(NLUEntity.is_active == True)
            .order_by(NLUEntity.entity_name)
        ).scalars().all()
        
        responses = self.db.execute(
            select(RasaResponse)
            .where(RasaResponse.is_active == True)
            .order_by(RasaResponse.utterance_name)
        ).scalars().all()
        
        slots = self.db.execute(
            select(RasaSlot)
            .where(RasaSlot.is_active == True)
            .order_by(RasaSlot.slot_name)
        ).scalars().all()
        
        forms = self.db.execute(
            select(RasaForm)
            .where(RasaForm.is_active == True)
            .order_by(RasaForm.form_name)
        ).scalars().all()
        
        actions = self.db.execute(
            select(RasaAction)
            .where(RasaAction.is_active == True)
            .order_by(RasaAction.action_name)
        ).scalars().all()
        
        # Build domain structure
        domain_data = {
            'version': '3.1',
            'intents': sorted(list(set(intents))),
            'entities': sorted(list(set(entities))),
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
                # Merge additional configuration
                form_config.update({k: v for k, v in form.configuration.items() 
                                   if k != 'required_slots'})
            
            domain_data['forms'][form.form_name] = form_config
        
        # Add actions (responses + custom actions)
        action_names = [r.utterance_name for r in responses]
        action_names.extend([a.action_name for a in actions])
        domain_data['actions'] = sorted(list(set(action_names)))
        
        # Write to file
        output_file = self.output_dir / 'domain.yml'
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(domain_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        logger.info(f"Generated domain.yml with {len(intents)} intents, "
                   f"{len(responses)} responses, {len(slots)} slots, {len(forms)} forms")
        
    def generate_action_files(self):
        """Generate Python action files from database"""
        logger.info("Generating action files...")
        
        actions = self.db.execute(
            select(RasaAction)
            .where(RasaAction.is_active == True)
            .order_by(RasaAction.action_name)
        ).scalars().all()
        
        if not actions:
            logger.info("No custom actions to generate")
            return
        
        # Create __init__.py
        init_file = self.actions_dir / '__init__.py'
        with open(init_file, 'w') as f:
            f.write('# Auto-generated actions module\n')
        
        # Generate actions.py with all actions
        actions_file = self.actions_dir / 'actions.py'
        
        imports = """# Auto-generated from database
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from typing import Dict, Text, Any, List
import requests
import logging

logger = logging.getLogger(__name__)

# FastAPI configuration
FASTAPI_BASE_URL = "http://127.0.0.1:8000/api"

"""
        
        action_classes = []
        for action in actions:
            # Wrap the stored code in a class if it's not already
            if not action.python_code.strip().startswith('class'):
                class_code = f"""
class {self._to_class_name(action.action_name)}(Action):
    def name(self) -> Text:
        return "{action.action_name}"
    
{self._indent_code(action.python_code, 4)}
"""
            else:
                class_code = action.python_code
            
            action_classes.append(class_code)
        
        with open(actions_file, 'w') as f:
            f.write(imports)
            f.write('\n\n'.join(action_classes))
        
        logger.info(f"Generated {len(actions)} action files")
        
    def _to_class_name(self, action_name: str) -> str:
        """Convert action_name to ClassName"""
        # action_create_student -> ActionCreateStudent
        parts = action_name.split('_')
        return ''.join(word.capitalize() for word in parts)
    
    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code block"""
        indent = ' ' * spaces
        lines = code.split('\n')
        return '\n'.join(indent + line if line.strip() else '' for line in lines)


def generate_rasa_files(db: Session, output_dir: str = './rasa') -> dict:
    """
    Generate all Rasa files from database
    
    Returns:
        dict with file counts
    """
    generator = RasaFileGenerator(db, output_dir)
    generator.generate_all_files()
    
    # Count what was generated
    intents_count = db.execute(
        select(NLUIntent).where(NLUIntent.is_active == True)
    ).scalars().all().__len__()
    
    stories_count = db.execute(
        select(RasaStory).where(RasaStory.is_active == True)
    ).scalars().all().__len__()
    
    rules_count = db.execute(
        select(RasaRule).where(RasaRule.is_active == True)
    ).scalars().all().__len__()
    
    actions_count = db.execute(
        select(RasaAction).where(RasaAction.is_active == True)
    ).scalars().all().__len__()
    
    return {
        'intents': intents_count,
        'stories': stories_count,
        'rules': rules_count,
        'actions': actions_count,
        'output_dir': str(output_dir)
    }