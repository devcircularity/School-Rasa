from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Dict, Text, Any, List
import logging

logger = logging.getLogger(__name__)


class ActionResumeStudentForm(Action):
    """Resume the student creation form after an interruption"""
    def name(self) -> Text:
        return "action_resume_student_form"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Resume the form by re-asking for the currently requested slot.
        This is called after interruptions like 'list classes', 'check academic setup', etc.
        """
        
        # Get which slot was being requested when interrupted
        requested_slot = tracker.get_slot("requested_slot")
        
        logger.info(f"Resuming student form - requested_slot: {requested_slot}")
        
        # Get already collected values to provide context
        student_name = tracker.get_slot("student_name")
        admission_no = tracker.get_slot("admission_no")
        class_name = tracker.get_slot("class_name")
        
        # Resume based on which slot was being requested
        if requested_slot == "class_name":
            if student_name and admission_no:
                dispatcher.utter_message(
                    text=f"Almost done! Let's continue creating {student_name} (#{admission_no}).\n\n"
                         f"Which class should the student be enrolled in?"
                )
            else:
                dispatcher.utter_message(
                    text="Almost done! Which class should the student be enrolled in?"
                )
        
        elif requested_slot == "admission_no":
            if student_name:
                dispatcher.utter_message(
                    text=f"Let's continue creating {student_name}.\n\n"
                         f"What is the admission number? (Or say 'auto generate' to create one automatically)"
                )
            else:
                dispatcher.utter_message(
                    text="What is the admission number? (Or say 'auto generate' to create one automatically)"
                )
        
        elif requested_slot == "student_name":
            dispatcher.utter_message(
                text="Let's continue with the student creation.\n\n"
                     "What is the student's name?"
            )
        
        else:
            # Fallback - shouldn't normally reach here
            logger.warning(f"Resume called with unexpected requested_slot: {requested_slot}")
            dispatcher.utter_message(
                text="Let's continue creating the student. What information were we collecting?"
            )
        
        # Don't modify any slots - just resume form collection
        return []


class ActionHandleFormInterruption(Action):
    """Handle interruptions intelligently based on context"""
    
    def name(self) -> Text:
        return "action_handle_form_interruption"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get what slots have been filled so far
        student_name = tracker.get_slot("student_name")
        admission_no = tracker.get_slot("admission_no")
        class_name = tracker.get_slot("class_name")
        
        # Build a context-aware message
        filled_slots = []
        if student_name:
            filled_slots.append(f"Name: {student_name}")
        if admission_no:
            filled_slots.append(f"Admission: {admission_no}")
        if class_name:
            filled_slots.append(f"Class: {class_name}")
        
        if filled_slots:
            progress = "\n".join([f"✓ {slot}" for slot in filled_slots])
            dispatcher.utter_message(
                text=f"Student creation in progress:\n\n{progress}\n\nWould you like to continue?"
            )
        else:
            dispatcher.utter_message(
                text="We just started creating a student. Continue?"
            )
        
        return []