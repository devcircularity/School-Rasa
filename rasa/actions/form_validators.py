from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet  # Remove FollowupAction import
from typing import Dict, Text, Any, List
import requests
import logging

logger = logging.getLogger(__name__)
FASTAPI_BASE_URL = "http://127.0.0.1:8000/api"


class ActionValidateStudentCreationPrerequisites(Action):
    """Validate that academic setup is complete before starting student creation"""
    
    def name(self) -> Text:
        return "action_validate_student_creation_prerequisites"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return [SlotSet("prerequisites_met", False)]
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # Check academic setup
            setup_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if setup_response.status_code != 200:
                # Check if ANY academic years exist first
                years_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/years",
                    headers=headers
                )
                
                if years_response.status_code == 200:
                    years = years_response.json()
                    if years and len(years) > 0:
                        # Academic year exists, problem is with terms
                        self._show_terms_required_message(dispatcher)
                    else:
                        # No years at all
                        self._show_setup_required_message(dispatcher)
                else:
                    self._show_setup_required_message(dispatcher)
                
                return [SlotSet("prerequisites_met", False)]
            
            setup_data = setup_response.json()
            
            # Check if setup is complete
            if not setup_data.get("setup_complete"):
                self._show_incomplete_setup_message(dispatcher, setup_data)
                return [SlotSet("prerequisites_met", False)]
            
            # Check if there are any classes
            classes_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes",
                headers=headers
            )
            
            if classes_response.status_code == 200:
                classes_data = classes_response.json()
                classes = classes_data.get("classes", [])
                
                if not classes:
                    self._show_no_classes_message(dispatcher, setup_data)
                    return [SlotSet("prerequisites_met", False)]
            
            # All checks passed
            return [SlotSet("prerequisites_met", True)]
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error validating prerequisites: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again in a moment."
            )
            return [SlotSet("prerequisites_met", False)]
        except Exception as e:
            logger.error(f"Unexpected error in prerequisite validation: {e}")
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
            return [SlotSet("prerequisites_met", False)]
    
    def _show_setup_required_message(self, dispatcher: CollectingDispatcher):
        """Show message when academic setup doesn't exist at all"""
        lines = [
            "```",
            "⚠️  ACADEMIC SETUP REQUIRED",
            "══════════════════════════════",
            "",
            "Cannot create students without proper academic setup.",
            "",
            "Required Steps:",
            "1. 'create academic year 2025'",
            "2. 'create term 1'",
            "3. 'create class Grade 4' (or any class)",
            "",
            "Then try creating the student again.",
            "```"
        ]
        dispatcher.utter_message(text="\n".join(lines))
    
    def _show_terms_required_message(self, dispatcher: CollectingDispatcher):
        """Show message when academic year exists but no terms/activation"""
        lines = [
            "```",
            "⚠️  TERMS REQUIRED",
            "══════════════════════════════",
            "",
            "Academic year exists but no active term found.",
            "",
            "Required Steps:",
            "1. 'create term 1'",
            "2. 'activate term 1'",
            "3. 'create class Grade 4' (or any class)",
            "",
            "Then try creating the student again.",
            "",
            "Check current status: 'check academic setup'",
            "```"
        ]
        dispatcher.utter_message(text="\n".join(lines))
    
    def _show_incomplete_setup_message(self, dispatcher: CollectingDispatcher, setup_data: dict):
        """Show message when academic setup is incomplete"""
        missing_items = []
        next_steps = []
        
        if not setup_data.get("current_year"):
            missing_items.append("Academic Year")
            next_steps.append("'create academic year 2025'")
        
        if not setup_data.get("current_term"):
            missing_items.append("Academic Term")
            next_steps.append("'create term 1'")
        
        lines = [
            "```",
            "⚠️  ACADEMIC SETUP INCOMPLETE",
            "═════════════════════════════",
            "",
            f"Missing: {' and '.join(missing_items)}",
            "",
            "Required Steps:"
        ]
        
        for i, step in enumerate(next_steps, 1):
            lines.append(f"{i}. {step}")
        
        lines.extend([
            "",
            "After completing the setup, create at least one class:",
            "• 'create class Grade 4'",
            "",
            "Check status: 'check academic setup'",
            "```"
        ])
        
        dispatcher.utter_message(text="\n".join(lines))
    
    def _show_no_classes_message(self, dispatcher: CollectingDispatcher, setup_data: dict):
        """Show message when no classes exist"""
        current_year = setup_data.get("current_year", {}).get("year", "2025")
        current_term = setup_data.get("current_term", {}).get("title", "Term 1")
        
        lines = [
            "```",
            "⚠️  NO CLASSES AVAILABLE",
            "═══════════════════════════",
            "",
            f"Academic Setup: ✓ {current_year} - {current_term}",
            "",
            "However, you need to create at least one class before adding students.",
            "",
            "Create classes:",
            "• 'create class Grade 4'",
            "• 'create class 8A'",
            "• 'create class Form 1'",
            "",
            "Then try creating students again.",
            "```"
        ]
        
        dispatcher.utter_message(text="\n".join(lines))