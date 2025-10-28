# rasa/actions/academic_actions.py
"""
Academic Year, Term, and Class Management Actions for Rasa Chatbot
Handles academic years, terms, classes, and enrollment operations
"""

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
import logging
from datetime import datetime
from typing import Dict, Text, Any, List
from actions.utils import normalize_level_label, extract_level_number, normalize_stream_name
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Configuration - Load from environment
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000/api")

logger.info(f"FastAPI Base URL: {FASTAPI_BASE_URL}")


def normalize_class_name(class_name: str) -> str:
    """Normalize class name for consistency"""
    if not class_name:
        return class_name
    
    class_name = class_name.strip()
    
    # Handle grade/form patterns with letter suffixes
    grade_pattern = r'^(grade|form|jss|pp|class)\s*(\d+)([a-zA-Z])$'
    match = re.match(grade_pattern, class_name, re.IGNORECASE)
    if match:
        prefix, number, letter = match.groups()
        return f"{prefix.title()} {number}{letter.upper()}"
    
    # Handle simple patterns like "8a" -> "8A"
    simple_pattern = r'^(\d+)([a-zA-Z])$'
    match = re.match(simple_pattern, class_name, re.IGNORECASE)
    if match:
        number, letter = match.groups()
        return f"{number}{letter.upper()}"
    
    # Default: title case
    return class_name.title()

class ActionCreateAcademicYear(Action):
    def name(self) -> Text:
        return "action_create_academic_year"

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
            # Check if ANY academic years exist
            years_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/years",
                headers=headers
            )
            
            if years_response.status_code == 200:
                years = years_response.json()
                if years:
                    # Years exist, so problem is with terms/activation
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

def _show_terms_required_message(self, dispatcher: CollectingDispatcher):
    """Show message when academic year exists but terms are missing"""
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
        "```"
    ]
    dispatcher.utter_message(text="\n".join(lines))


class ActionCreateAcademicTerm(Action):
    def name(self) -> Text:
        return "action_create_academic_term"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        if not term:
            dispatcher.utter_message(
                text="Which term would you like to create? (1, 2, or 3)\n"
                     "Example: 'create term 1'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Get current academic year if not specified
            if not academic_year:
                current_year_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-year",
                    headers=headers
                )
                
                if current_year_response.status_code == 200:
                    year_data = current_year_response.json()
                    academic_year = year_data.get("year")
                else:
                    dispatcher.utter_message(
                        text="No active academic year found.\n"
                             "Please create and activate an academic year first:\n"
                             "'create academic year 2025'"
                    )
                    return [SlotSet("term", None)]
            
            # Create the term
            term_data = {
                "term": int(term),
                "academic_year": int(academic_year),
                "title": f"Term {term}"
            }
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/academic/terms",
                json=term_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                msg = f"Term {term} created successfully for Academic Year {academic_year}!\n\n"
                
                # Check if there are any active terms
                terms_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/terms?academic_year={academic_year}",
                    headers=headers
                )
                
                if terms_response.status_code == 200:
                    terms = terms_response.json().get("terms", [])
                    active_terms = [t for t in terms if t.get("state") == "ACTIVE"]
                    
                    if not active_terms:
                        msg += f"Term {term} is PLANNED (not yet started).\n"
                        msg += f"To activate it for enrollment: 'activate term {term}'"
                    else:
                        msg += "Academic setup is ready for class and student creation."
                else:
                    msg += "Academic setup is ready for class and student creation."
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to create term')
                
                # Handle specific error cases
                if "Academic year" in error_msg and "is DRAFT" in error_msg:
                    dispatcher.utter_message(
                        text=f"Academic year {academic_year} is DRAFT.\n\n"
                             f"Terms can only be created in ACTIVE years. To activate:\n"
                             f"'activate academic year {academic_year}'"
                    )
                elif "Academic year" in error_msg and "is CLOSED" in error_msg:
                    dispatcher.utter_message(
                        text=f"Academic year {academic_year} is CLOSED.\n\n"
                             f"Cannot create terms in closed years. Create a new academic year:\n"
                             f"'create academic year {int(academic_year) + 1}'"
                    )
                elif "already exists" in error_msg.lower():
                    dispatcher.utter_message(
                        text=f"Term {term} already exists for Academic Year {academic_year}.\n\n"
                             f"To view all terms: 'list academic terms'"
                    )
                elif "not found" in error_msg.lower():
                    dispatcher.utter_message(
                        text=f"Academic year {academic_year} does not exist.\n\n"
                             f"Create it first: 'create academic year {academic_year}'"
                    )
                else:
                    dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error creating term: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while creating the term.")
        
        return [
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]


class ActionCheckAcademicSetup(Action):
    def name(self) -> Text:
        return "action_check_academic_setup"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if response.status_code == 200:
                setup_data = response.json()
                
                if setup_data.get("setup_complete"):
                    current_year = setup_data["current_year"]
                    current_term = setup_data["current_term"]
                    
                    status_msg = f"Current Academic Setup:\n\n"
                    status_msg += f"Academic Year: {current_year['year']} ({current_year['state']})\n"
                    status_msg += f"Current Term: {current_term['title']} "
                    
                    if current_term['state'] == "ACTIVE":
                        status_msg += "(ACTIVE - enrollment open)\n"
                    elif current_term['state'] == "PLANNED":
                        status_msg += "(PLANNED - not yet started)\n"
                        status_msg += f"\n⚠️ Note: Term is planned but not active.\n"
                        status_msg += f"To activate for student enrollment: 'activate term {current_term['term']}'\n"
                    elif current_term['state'] == "COMPLETED":
                        status_msg += "(COMPLETED - term ended)\n"
                    
                    status_msg += f"\nSystem status: "
                    if current_term['state'] == "ACTIVE":
                        status_msg += "Ready for operations"
                    else:
                        status_msg += "Term activation required for enrollment"
                    
                    dispatcher.utter_message(text=status_msg)
                else:
                    current_year = setup_data.get("current_year")
                    current_term = setup_data.get("current_term")
                    
                    status_msg = "Current Academic Setup:\n\n"
                    
                    if current_year:
                        status_msg += f"Academic Year: {current_year['year']} ({current_year['state']})\n"
                    else:
                        status_msg += "Academic Year: Not set\n"
                    
                    if current_term:
                        status_msg += f"Current Term: {current_term['title']} ({current_term['state']})\n"
                    else:
                        status_msg += "Current Term: Not set\n"
                    
                    status_msg += "\n"
                    if not current_year:
                        status_msg += "To set up academic year: 'create academic year 2025'\n"
                    if current_year and not current_term:
                        status_msg += "To add terms: 'create term 1'"
                    
                    dispatcher.utter_message(text=status_msg)
            else:
                dispatcher.utter_message(
                    text="Unable to check academic setup status. Please try again."
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking academic setup: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again in a moment."
            )
        except Exception as e:
            logger.error(f"Unexpected error in ActionCheckAcademicSetup: {e}")
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
        
        return []


class ActionGetCurrentAcademicYear(Action):
    def name(self) -> Text:
        return "action_get_current_academic_year"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if response.status_code == 200:
                setup_data = response.json()
                current_year = setup_data.get("current_year")
                
                if current_year and current_year.get("state") == "ACTIVE":
                    dispatcher.utter_message(
                        text=f"Current Academic Year: {current_year['year']} ({current_year['state']})"
                    )
                else:
                    years_response = requests.get(
                        f"{FASTAPI_BASE_URL}/academic/years",
                        headers=headers
                    )
                    
                    if years_response.status_code == 200:
                        years_data = years_response.json()
                        
                        if years_data:
                            draft_years = []
                            inactive_years = []
                            
                            for year in years_data:
                                if year["state"] == "DRAFT":
                                    draft_years.append(str(year["year"]))
                                elif year["state"] == "INACTIVE":
                                    inactive_years.append(str(year["year"]))
                            
                            message = "No ACTIVE academic year found.\n\n"
                            
                            if draft_years:
                                message += f"Draft years available: {', '.join(draft_years)}\n"
                            
                            if inactive_years:
                                message += f"Inactive years: {', '.join(inactive_years)}\n"
                            
                            if draft_years or inactive_years:
                                message += f"\nTo activate a year: 'activate academic year YYYY'"
                            else:
                                message += "No academic years found. Create one with: 'create academic year 2025'"
                            
                            dispatcher.utter_message(text=message)
                        else:
                            dispatcher.utter_message(
                                text="No academic years found in the system.\n\n"
                                     "Create one with: 'create academic year 2025'"
                            )
                    else:
                        dispatcher.utter_message(
                            text="No active academic year found.\n\n"
                                 "Create one with: 'create academic year 2025'"
                        )
            else:
                dispatcher.utter_message(
                    text="Unable to retrieve academic year information. Please try again."
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting current academic year: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again in a moment."
            )
        except Exception as e:
            logger.error(f"Unexpected error in ActionGetCurrentAcademicYear: {e}")
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
        
        return []


class ActionGetCurrentTerm(Action):
    def name(self) -> Text:
        return "action_get_current_term"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if response.status_code == 200:
                setup_data = response.json()
                current_year = setup_data.get("current_year")
                current_term = setup_data.get("current_term")
                
                if current_term:
                    term_state = current_term['state']
                    
                    msg = f"Current Term: {current_term['title']} ({current_year['year']})\n"
                    msg += f"Status: {term_state}\n\n"
                    
                    if term_state == "ACTIVE":
                        msg += "✓ Enrollment is open\n"
                        msg += "✓ Students can be added and enrolled\n"
                        msg += "✓ Classes are running"
                    elif term_state == "PLANNED":
                        msg += "⚠️ Term is scheduled but not yet active\n"
                        msg += "• Students cannot be enrolled yet\n"
                        msg += f"• To activate: 'activate term {current_term['term']}'\n"
                        msg += "• Once activated, enrollment will open"
                    elif term_state == "COMPLETED":
                        msg += "✓ Term has ended\n"
                        msg += "• Enrollment is closed\n"
                        msg += "• Create next term to continue"
                    
                    dispatcher.utter_message(text=msg)
                elif current_year:
                    dispatcher.utter_message(
                        text=f"No term is currently set up for Academic Year {current_year['year']}.\n\n"
                             "To create one: 'create term 1'"
                    )
                else:
                    dispatcher.utter_message(
                        text="No academic year or term is set up.\n\n"
                             "First create an academic year: 'create academic year 2025'"
                    )
            else:
                dispatcher.utter_message(
                    text="Unable to retrieve term information. Please try again."
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting current term: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again in a moment."
            )
        except Exception as e:
            logger.error(f"Unexpected error in ActionGetCurrentTerm: {e}")
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
        
        return []


class ActionActivateAcademicYear(Action):
    def name(self) -> Text:
        return "action_activate_academic_year"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        academic_year = tracker.get_slot("academic_year")
        
        if not academic_year:
            dispatcher.utter_message(text="Please specify which academic year to activate. Example: 'activate academic year 2025'")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            years_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/years",
                headers=headers
            )
            
            if years_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve academic years.")
                return []
            
            years = years_response.json()
            year_id = None
            year_found = None
            
            for year in years:
                if str(year["year"]) == str(academic_year):
                    year_id = year["id"]
                    year_found = year
                    break
            
            if not year_id:
                dispatcher.utter_message(text=f"Academic year {academic_year} not found.")
                return []
            
            if year_found["state"] == "ACTIVE":
                dispatcher.utter_message(text=f"Academic year {academic_year} is already active.")
                return []
            
            activate_response = requests.put(
                f"{FASTAPI_BASE_URL}/academic/years/{year_id}/activate",
                headers=headers
            )
            
            if activate_response.status_code == 200:
                dispatcher.utter_message(
                    text=f"Academic year {academic_year} activated successfully!\n\n"
                         f"This year is now the current active academic year.\n"
                         f"You can now create terms and enroll students."
                )
            else:
                error_data = activate_response.json() if activate_response.content else {}
                error_msg = error_data.get('detail', f'Failed to activate academic year {academic_year}')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error activating academic year: {e}")
            dispatcher.utter_message(text="An error occurred while activating the academic year.")
        
        return [SlotSet("academic_year", None)]


class ActionDeactivateAcademicYear(Action):
    def name(self) -> Text:
        return "action_deactivate_academic_year"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        academic_year = tracker.get_slot("academic_year")
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            if not academic_year:
                setup_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-setup",
                    headers=headers
                )
                
                if setup_response.status_code == 200:
                    setup_data = setup_response.json()
                    current_year = setup_data.get("current_year")
                    if current_year:
                        academic_year = str(current_year["year"])
                        year_id = current_year["id"]
                    else:
                        dispatcher.utter_message(text="No active academic year found to deactivate.")
                        return []
                else:
                    dispatcher.utter_message(text="Could not check current academic setup.")
                    return []
            else:
                years_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/years",
                    headers=headers
                )
                
                if years_response.status_code == 200:
                    years = years_response.json()
                    year_id = None
                    for year in years:
                        if str(year["year"]) == str(academic_year):
                            year_id = year["id"]
                            break
                    
                    if not year_id:
                        dispatcher.utter_message(text=f"Academic year {academic_year} not found.")
                        return []
                else:
                    dispatcher.utter_message(text="Could not retrieve academic years.")
                    return []
            
            deactivate_response = requests.put(
                f"{FASTAPI_BASE_URL}/academic/years/{year_id}/deactivate",
                headers=headers
            )
            
            if deactivate_response.status_code == 200:
                dispatcher.utter_message(
                    text=f"Academic year {academic_year} has been deactivated.\n\n"
                         f"Note: This will affect student enrollment and class operations.\n"
                         f"To reactivate, use: 'activate academic year {academic_year}'"
                )
            else:
                dispatcher.utter_message(text=f"Failed to deactivate academic year {academic_year}.")
        
        except Exception as e:
            logger.error(f"Error deactivating academic year: {e}")
            dispatcher.utter_message(text="An error occurred while deactivating the academic year.")
        
        return [SlotSet("academic_year", None)]


class ActionActivateTerm(Action):
    def name(self) -> Text:
        return "action_activate_term"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        term_number = tracker.get_slot("term")
        
        if not term_number:
            dispatcher.utter_message(text="Please specify which term to activate. Example: 'activate term 1'")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # FIXED: Get current setup to get year ID
            setup_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if setup_response.status_code != 200:
                dispatcher.utter_message(text="Cannot check academic setup.")
                return []
            
            setup_data = setup_response.json()
            current_year = setup_data.get("current_year")
            
            if not current_year:
                dispatcher.utter_message(text="No active academic year found.")
                return []
            
            # Get year ID
            year_id = current_year['id']
            
            # FIXED: Get terms using year ID
            terms_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/years/{year_id}/terms",
                headers=headers
            )
            
            if terms_response.status_code != 200:
                dispatcher.utter_message(text="Cannot retrieve terms.")
                return []
            
            terms = terms_response.json()
            target_term = None
            
            for term in terms:
                if str(term["term"]) == str(term_number):
                    target_term = term
                    break
            
            if not target_term:
                dispatcher.utter_message(
                    text=f"Term {term_number} not found for {current_year['year']}."
                )
                return []
            
            # Activate the term
            activate_response = requests.put(
                f"{FASTAPI_BASE_URL}/academic/terms/{target_term['id']}/activate",
                headers=headers
            )
            
            if activate_response.status_code == 200:
                dispatcher.utter_message(
                    text=f"Term {term_number} activated successfully for {current_year['year']}!\n\n"
                         f"Students can now be enrolled and classes can begin."
                )
            else:
                dispatcher.utter_message(text=f"Failed to activate term {term_number}.")
        
        except Exception as e:
            logger.error(f"Error activating term: {e}")
            dispatcher.utter_message(text="An error occurred while activating the term.")
        
        return [SlotSet("term", None)]


class ActionListAcademicTerms(Action):
    def name(self) -> Text:
        return "action_list_academic_terms"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        academic_year = tracker.get_slot("academic_year")
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # FIXED: First get the current academic year to get its ID
            setup_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if setup_response.status_code != 200:
                dispatcher.utter_message(text="Cannot retrieve academic setup.")
                return []
            
            setup_data = setup_response.json()
            current_year = setup_data.get("current_year")
            
            if not current_year:
                dispatcher.utter_message(text="No academic year found. Please create one first.")
                return []
            
            # Use the year ID, not the year number
            year_id = current_year["id"]
            year_to_check = academic_year or str(current_year["year"])
            
            # FIXED: Use the correct endpoint with year_id
            terms_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/years/{year_id}/terms",
                headers=headers
            )
            
            if terms_response.status_code == 200:
                terms = terms_response.json()
                
                if not terms:
                    dispatcher.utter_message(
                        text=f"No terms found for Academic Year {year_to_check}.\n\n"
                             f"To create terms: 'create term 1', 'create term 2', etc."
                    )
                    return []
                
                terms_list = f"Academic Terms for {year_to_check}:\n\n"
                
                active_count = 0
                planned_count = 0
                completed_count = 0
                
                for term in terms:
                    state = term["state"].upper()
                    
                    if state == "ACTIVE":
                        indicator = "✓"
                        state_desc = "ACTIVE - enrollment open"
                        active_count += 1
                    elif state == "PLANNED":
                        indicator = "○"
                        state_desc = "PLANNED - not started"
                        planned_count += 1
                    elif state == "COMPLETED" or state == "CLOSED":
                        indicator = "✓"
                        state_desc = "COMPLETED - ended"
                        completed_count += 1
                    else:
                        indicator = "•"
                        state_desc = state
                    
                    terms_list += f"{indicator} Term {term['term']}: {term['title']} ({state_desc})\n"
                
                terms_list += f"\nTotal: {len(terms)} term{'s' if len(terms) != 1 else ''}"
                terms_list += f" ({active_count} active, {planned_count} planned, {completed_count} completed)"
                
                if planned_count > 0 and active_count == 0:
                    terms_list += f"\n\n⚠️ All terms are PLANNED (not yet started)\n"
                    terms_list += f"To activate a term for student enrollment:\n"
                    for term in terms:
                        if term["state"].upper() == "PLANNED":
                            terms_list += f"• 'activate term {term['term']}'\n"
                
                dispatcher.utter_message(text=terms_list)
            else:
                dispatcher.utter_message(text="Cannot retrieve terms information.")
        
        except Exception as e:
            logger.error(f"Error listing academic terms: {e}")
            dispatcher.utter_message(text="An error occurred while retrieving terms.")
        
        return [SlotSet("academic_year", None)]


class ActionPromoteStudents(Action):
    def name(self) -> Text:
        return "action_promote_students"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        target_term = tracker.get_slot("target_term")
        source_term = tracker.get_slot("source_term")
        
        # If no target term specified, ask for it
        if not target_term:
            dispatcher.utter_message(
                text="Which term should students be promoted to?\n"
                     "Example: 'promote students to term 3'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # If source term not specified, use current active term
            if not source_term:
                current_term_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-term",
                    headers=headers
                )
                
                if current_term_response.status_code == 200:
                    current_term_data = current_term_response.json()
                    source_term = str(current_term_data.get("term"))
                else:
                    # No current term, so just proceed with promotion to target
                    source_term = None
            
            # Call promotion endpoint
            promotion_data = {
                "target_term": int(target_term)
            }
            
            if source_term:
                promotion_data["source_term"] = int(source_term)
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/academic/promote-students",
                json=promotion_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                students_promoted = data.get("students_promoted", 0)
                
                msg = f"✅ Student promotion completed!\n\n"
                msg += f"Students promoted: {students_promoted}\n"
                msg += f"Target term: Term {target_term}\n\n"
                
                if students_promoted > 0:
                    msg += f"All eligible students have been enrolled in Term {target_term}."
                else:
                    msg += "No students were eligible for promotion."
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to promote students')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error promoting students: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while promoting students.")
        
        return [
            SlotSet("target_term", None),
            SlotSet("source_term", None)
        ]


# ============================================================================
# CLASS MANAGEMENT ACTIONS
# ============================================================================

class ActionCreateClass(Action):
    def name(self) -> Text:
        return "action_create_class"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        class_name = tracker.get_slot("name")
        level = tracker.get_slot("level")
        stream = tracker.get_slot("stream")
        academic_year = tracker.get_slot("academic_year")
        
        # CRITICAL FIX: If academic_year is a single/double digit, it's the class level
        if academic_year:
            try:
                year_val = int(str(academic_year))
                if year_val < 100:
                    logger.warning(f"Detected {year_val} as academic_year, treating as level instead")
                    if not level:
                        level = str(year_val)
                    if not class_name:
                        class_name = str(year_val)
                    academic_year = None
            except (ValueError, TypeError):
                pass
        
        message_text = tracker.latest_message.get("text", "").lower()
        
        # ==========================================
        # HELPER: Normalize level label (Grade/Form → Class)
        # ==========================================
        def normalize_level_label(text: str) -> str:
            """
            Normalize class level labels to consistent format.
            Maps: grade/standard → Class
            Preserves: Form, JSS, PP (specific Kenyan labels)
            
            Examples:
                "Grade 8" → "Class 8"
                "grade 6" → "Class 6"
                "Form 2" → "Form 2" (preserved)
                "JSS 1" → "JSS 1" (preserved)
                "PP1" → "PP1" (preserved)
                "8" → "8"
            """
            if not text:
                return text
            
            text = str(text).strip()
            
            # Keep Form, JSS, PP as-is (they're distinct level types in Kenyan system)
            if re.match(r'^(form|jss|pp|standard)\s+\d+', text, re.IGNORECASE):
                return text.title()
            
            # Check if it's JUST a number
            if text.isdigit():
                return text
            
            # Replace "grade" with "Class"
            text = re.sub(r'\bgrade\s+', 'Class ', text, flags=re.IGNORECASE)
            
            # If it starts with "class" already, just title case it
            if text.lower().startswith('class'):
                return text.title()
            
            return text.title()
        
        # ==========================================
        # HELPER: Parse level and stream from text
        # ==========================================
        def parse_level_and_stream(text: str):
            """
            Parse input like '8 blue', 'grade 5 red', 'form 2 alpha' into level and stream
            Returns: (level, stream) tuple
            """
            import re
            
            # Pattern 1: "grade 8 blue", "form 2 alpha", "class 5 red"
            pattern1 = r'(?:class|grade|form|jss|standard|pp)?\s*(\d+)\s+([a-zA-Z]+)'
            match = re.search(pattern1, text, re.IGNORECASE)
            
            if match:
                level_num = match.group(1)
                stream_name = match.group(2)
                
                # Check if it's a level keyword (grade/form/jss)
                level_prefix_match = re.search(
                    r'(grade|form|jss|standard|pp)\s+\d+',
                    text,
                    re.IGNORECASE
                )
                
                if level_prefix_match:
                    level = f"{level_prefix_match.group(1).title()} {level_num}"
                else:
                    level = level_num
                
                return level, stream_name.title()
            
            # Pattern 2: just "grade 8", "form 2", "class 5" (no stream)
            pattern2 = r'(grade|form|jss|standard|pp|class)?\s*(\d+)(?:\s|$)'
            match = re.search(pattern2, text, re.IGNORECASE)
            
            if match:
                prefix = match.group(1)
                level_num = match.group(2)
                
                if prefix:
                    level = f"{prefix.title()} {level_num}"
                else:
                    level = level_num
                
                return level, None
            
            return None, None
        
        # ==========================================
        # HELPER: Extract all stream names from text
        # ==========================================
        def extract_all_streams(text: str, level_str: str) -> List[str]:
            """
            Extract multiple stream names from text.
            Supports: colors, directions, greek letters, single letters (A-Z), names
            """
            import re
            
            # Comprehensive stream keywords
            stream_keywords = [
                # Colors
                'red', 'blue', 'green', 'yellow', 'purple', 'orange', 'pink', 
                'white', 'black', 'brown', 'gray', 'grey', 'violet', 'indigo',
                'maroon', 'turquoise', 'crimson', 'scarlet', 'amber', 'cyan',
                'magenta', 'gold', 'silver', 'bronze',
                # Directions
                'north', 'south', 'east', 'west',
                # Greek letters
                'alpha', 'beta', 'gamma', 'delta', 'omega', 'sigma', 'theta',
                # Single letters A-Z
                'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
                'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                # Animal/name streams
                'eagle', 'lion', 'tiger', 'falcon', 'hawk', 'phoenix', 'leopard',
                'cheetah', 'panther', 'marvel', 'excellence', 'victory', 'mama', 
                'baba', 'silk'
            ]
            
            # Remove "with streams" to isolate stream names
            clean_text = re.sub(r'\bwith\s+streams?\b', '', text, flags=re.IGNORECASE)
            
            # Remove level references
            if level_str:
                # Extract just the number from level
                level_num = re.search(r'\d+', str(level_str))
                if level_num:
                    num = level_num.group()
                    clean_text = re.sub(
                        rf'\b(class|grade|form|jss|pp|create|new|make|add)\s*{num}\b',
                        '',
                        clean_text,
                        flags=re.IGNORECASE
                    )
            
            # Remove action keywords
            clean_text = re.sub(
                r'\b(class|grade|form|jss|pp|create|new|make|add|streams?)\b',
                '',
                clean_text,
                flags=re.IGNORECASE
            )
            
            # Split by commas and "and"
            parts = re.split(r',|\s+and\s+', clean_text)
            
            found_streams = []
            for part in parts:
                part_clean = part.strip().lower()
                if not part_clean:
                    continue
                
                # Check each word in the part
                words = part_clean.split()
                for word in words:
                    if word in stream_keywords:
                        # Single letters: uppercase (A, B, X)
                        # Everything else: title case (Red, Blue, Alpha)
                        if len(word) == 1:
                            found_streams.append(word.upper())
                        else:
                            found_streams.append(word.title())
                        break
            
            # Remove duplicates while preserving order
            seen = set()
            unique_streams = []
            for stream_name in found_streams:
                if stream_name.lower() not in seen:
                    seen.add(stream_name.lower())
                    unique_streams.append(stream_name)
            
            return unique_streams
        
        # ==========================================
        # PARSE: Extract level and streams
        # ==========================================
        
        # Try to extract level and stream from message
        parsed_level, parsed_stream = parse_level_and_stream(message_text)
        
        if parsed_level:
            level = parsed_level
        if parsed_stream and not stream:
            stream = parsed_stream
        
        # If still no level, try from class_name slot
        if not level and class_name:
            parsed_level, parsed_stream = parse_level_and_stream(class_name)
            if parsed_level:
                level = parsed_level
            if parsed_stream and not stream:
                stream = parsed_stream
        
        # Validation: Must have level
        if not level:
            dispatcher.utter_message(
                text="I need the class level.\n\n"
                     "**Examples:**\n"
                     "- 'create class 8'\n"
                     "- 'create grade 6 Blue'\n"
                     "- 'create form 2 Alpha'\n"
                     "- 'add grade 7 with streams blue and red'"
            )
            return []
        
        # Normalize the level label
        level = normalize_level_label(level)
        
        # Extract all streams from message text
        streams_to_add = extract_all_streams(message_text, level)
        
        # If no streams found via parsing but stream slot has value, use it
        if not streams_to_add and stream:
            # Normalize single stream
            if len(stream) == 1:
                streams_to_add = [stream.upper()]
            else:
                streams_to_add = [stream.title()]
        
        logger.info(f"Creating class '{level}' with streams: {streams_to_add}")
        
        # ==========================================
        # API CALL: Create class with streams
        # ==========================================
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # Get current academic year if not specified
            if not academic_year:
                academic_setup_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-setup",
                    headers=headers
                )
                
                if academic_setup_response.status_code != 200:
                    dispatcher.utter_message(
                        text="⚠️ **Academic Setup Required**\n\n"
                             "Cannot create classes without proper academic setup.\n\n"
                             "Please complete academic setup first."
                    )
                    return []
                
                setup_data = academic_setup_response.json()
                
                if not setup_data.get("setup_complete"):
                    dispatcher.utter_message(
                        text="⚠️ **Academic Setup Incomplete**\n\n"
                             "Please complete academic setup first."
                    )
                    return []
                
                current_year = setup_data.get("current_year")
                if current_year:
                    academic_year = current_year.get("year")
                    
                if not academic_year:
                    dispatcher.utter_message(
                        text="Could not determine current academic year."
                    )
                    return []
            
            academic_year = int(academic_year)
            
            # ==========================================
            # SCENARIO 1: No streams - create base class only
            # ==========================================
            if not streams_to_add:
                class_payload = {
                    "name": level,
                    "level": level,
                    "stream": None,
                    "academic_year": academic_year
                }
                
                logger.info(f"Creating base class with payload: {class_payload}")
                
                response = requests.post(
                    f"{FASTAPI_BASE_URL}/classes/level-stream",
                    json=class_payload,
                    headers=headers
                )
                
                if response.status_code == 201:
                    dispatcher.utter_message(
                        text=f"✅ **{level} created successfully ({academic_year})!**\n\n"
                             f"The class is ready for student enrollment.\n\n"
                             f"To add streams: 'add stream Blue to {level}'"
                    )
                    
                    return [
                        SlotSet("name", None),
                        SlotSet("level", None),
                        SlotSet("stream", None),
                        SlotSet("academic_year", None)
                    ]
                
                elif response.status_code == 409:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('detail', f'{level} already exists')
                    dispatcher.utter_message(text=f"⚠️ {error_msg}")
                
                else:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('detail', f'Failed to create {level}')
                    logger.error(f"Class creation failed: {error_msg}")
                    dispatcher.utter_message(text=f"❌ Error: {error_msg}")
                
                return [
                    SlotSet("name", None),
                    SlotSet("level", None),
                    SlotSet("stream", None),
                    SlotSet("academic_year", None)
                ]
            
            # ==========================================
            # SCENARIO 2: Create class with streams
            # ==========================================
            
            # Step 1: Ensure base class exists
            base_class_payload = {
                "name": level,
                "level": level,
                "stream": None,
                "academic_year": academic_year
            }
            
            logger.info(f"Step 1: Creating/checking base class {level}")
            
            base_response = requests.post(
                f"{FASTAPI_BASE_URL}/classes/level-stream",
                json=base_class_payload,
                headers=headers
            )
            
            # Get the class ID (either from creation or by fetching)
            class_id = None
            
            if base_response.status_code == 201:
                class_data = base_response.json()
                class_id = class_data.get("id")
                logger.info(f"Base class created with ID: {class_id}")
                
            elif base_response.status_code == 409:
                # Class already exists, fetch it
                logger.info(f"Base class {level} already exists, fetching ID")
                fetch_response = requests.get(
                    f"{FASTAPI_BASE_URL}/classes?search={level}&academic_year={academic_year}",
                    headers=headers
                )
                
                if fetch_response.status_code == 200:
                    classes_data = fetch_response.json()
                    classes = classes_data.get("classes", [])
                    
                    for cls in classes:
                        # Match by level AND academic year
                        if cls["level"] == level and cls["academic_year"] == academic_year:
                            class_id = cls["id"]
                            logger.info(f"Found existing class with ID: {class_id}")
                            break
            
            if not class_id:
                dispatcher.utter_message(
                    text=f"❌ Could not create or find {level}. Please try again."
                )
                return [
                    SlotSet("name", None),
                    SlotSet("level", None),
                    SlotSet("stream", None),
                    SlotSet("academic_year", None)
                ]
            
            # Step 2: Add all streams
            added_streams = []
            failed_streams = []
            skipped_streams = []
            
            logger.info(f"Step 2: Adding {len(streams_to_add)} streams to class {class_id}")
            
            for stream_name in streams_to_add:
                stream_payload = {"name": stream_name}
                
                logger.info(f"Adding stream '{stream_name}' to class {class_id}")
                
                stream_response = requests.post(
                    f"{FASTAPI_BASE_URL}/classes/{class_id}/streams",
                    json=stream_payload,
                    headers=headers
                )
                
                logger.info(f"Stream '{stream_name}' response: {stream_response.status_code}")
                
                if stream_response.status_code == 201:
                    added_streams.append(stream_name)
                elif stream_response.status_code == 409:
                    skipped_streams.append(stream_name)
                else:
                    failed_streams.append(stream_name)
            
            # Build response message
            messages = []
            
            if added_streams:
                if len(added_streams) == 1:
                    messages.append(
                        f"✅ **{level} created with stream '{added_streams[0]}' ({academic_year})!**"
                    )
                    messages.append(
                        f"Students can now be enrolled in **{level} {added_streams[0]}**."
                    )
                else:
                    streams_list = "', '".join(added_streams)
                    all_streams = ", ".join(added_streams)
                    messages.append(
                        f"✅ **{level} created with streams: {all_streams} ({academic_year})!**"
                    )
                    messages.append(
                        f"Students can be enrolled in any of these streams."
                    )
            
            if skipped_streams:
                skipped_list = "', '".join(skipped_streams)
                messages.append(
                    f"⚠️ Stream(s) '{skipped_list}' already exist for {level}."
                )
            
            if failed_streams:
                failed_list = "', '".join(failed_streams)
                messages.append(
                    f"❌ Failed to add stream(s): '{failed_list}'. Please try manually."
                )
            
            if not added_streams and not skipped_streams:
                messages.append(
                    f"❌ Failed to create {level} with the specified streams."
                )
            
            dispatcher.utter_message(text="\n\n".join(messages))
            
            return [
                SlotSet("name", None),
                SlotSet("level", None),
                SlotSet("stream", None),
                SlotSet("academic_year", None)
            ]
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating class: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again."
            )
        except Exception as e:
            logger.error(f"Error in ActionCreateClass: {e}", exc_info=True)
            dispatcher.utter_message(
                text="An error occurred. Please try again."
            )
        
        return [
            SlotSet("name", None),
            SlotSet("level", None),
            SlotSet("stream", None),
            SlotSet("academic_year", None)
        ]

class ActionListClasses(Action):
    def name(self) -> Text:
        return "action_list_classes"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/classes",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                classes = data.get("classes", [])
                
                if not classes:
                    dispatcher.utter_message(text="No classes found in the system.")
                    return []
                
                class_list = "Class List:\n\n"
                for i, cls in enumerate(classes, 1):
                    level = cls['level']
                    student_count = cls.get('student_count', 0)
                    year = cls['academic_year']
                    
                    # Get streams
                    streams = cls.get('streams', [])
                    
                    # Build the display string
                    if streams:
                        streams_text = f" [Streams: {', '.join(streams)}]"
                    else:
                        streams_text = ""
                    
                    # Format: "1. Class 8 - 0 students - 2025 [Streams: Red, White]"
                    class_list += f"{i}. Class {level} - {student_count} student{'s' if student_count != 1 else ''} - {year}{streams_text}\n"
                
                dispatcher.utter_message(text=class_list)
                
            elif response.status_code == 403:
                dispatcher.utter_message(
                    text="You don't have permission to view classes. Please contact an administrator."
                )
            else:
                dispatcher.utter_message(
                    text="Sorry, I couldn't retrieve the class list. Please try again."
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing classes: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again in a moment."
            )
        except Exception as e:
            logger.error(f"Unexpected error in ActionListClasses: {e}")
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
        
        return []


class ActionListEmptyClasses(Action):
    def name(self) -> Text:
        return "action_list_empty_classes"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/classes",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                classes = data.get("classes", [])
                
                if not classes:
                    dispatcher.utter_message(text="No classes found in the system.")
                    return []
                
                empty_classes = [cls for cls in classes if cls.get('student_count', 0) == 0]
                
                if not empty_classes:
                    dispatcher.utter_message(
                        text="All classes have students enrolled. No empty classes found."
                    )
                    return []
                
                class_list = f"**Empty Classes ({len(empty_classes)} found):**\n\n"
                
                for i, cls in enumerate(empty_classes, 1):
                    stream_text = f" - {cls['stream']}" if cls.get('stream') else ""
                    class_list += f"{i}. **{cls['name']}** ({cls['level']}{stream_text}) - {cls['academic_year']}\n"
                
                class_list += f"\n**Total: {len(empty_classes)} class{'es' if len(empty_classes) != 1 else ''} with no students**"
                class_list += f"\n\nThese classes are ready for student enrollment"
                
                dispatcher.utter_message(text=class_list)
                
            elif response.status_code == 403:
                dispatcher.utter_message(
                    text="You don't have permission to view classes. Please contact an administrator."
                )
            else:
                dispatcher.utter_message(
                    text="Sorry, I couldn't retrieve the class list. Please try again."
                )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing empty classes: {e}")
            dispatcher.utter_message(
                text="Sorry, I'm having trouble connecting to the system. Please try again in a moment."
            )
        except Exception as e:
            logger.error(f"Unexpected error in ActionListEmptyClasses: {e}")
            dispatcher.utter_message(
                text="An unexpected error occurred. Please try again."
            )
        
        return []


class ActionDeleteClass(Action):
    def name(self) -> Text:
        return "action_delete_class"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        class_name = tracker.get_slot("class_name")
        
        if not class_name:
            dispatcher.utter_message(
                text="Please specify which class to delete. Example: 'delete class 8A'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            class_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes",
                headers=headers,
                params={"search": class_name}
            )
            
            if class_response.status_code != 200:
                dispatcher.utter_message(text="Error finding class.")
                return []
            
            classes_data = class_response.json()
            matching_classes = []
            
            for cls in classes_data.get("classes", []):
                if cls["name"].lower() == class_name.lower():
                    matching_classes.append(cls)
            
            if not matching_classes:
                dispatcher.utter_message(text=f"Class '{class_name}' not found.")
                return []
            
            if len(matching_classes) > 1:
                msg = f"Multiple classes found matching '{class_name}':\n\n"
                for i, cls in enumerate(matching_classes, 1):
                    msg += f"{i}. {cls['name']} ({cls['academic_year']}) - {cls.get('student_count', 0)} students\n"
                msg += f"\nPlease be more specific or delete from the web interface."
                dispatcher.utter_message(text=msg)
                return []
            
            target_class = matching_classes[0]
            
            if target_class.get('student_count', 0) > 0:
                dispatcher.utter_message(
                    text=f"Cannot delete '{target_class['name']}' - it has {target_class['student_count']} enrolled students.\n\n"
                         f"Please transfer students to another class first."
                )
                return []
            
            delete_response = requests.delete(
                f"{FASTAPI_BASE_URL}/classes/{target_class['id']}",
                headers=headers
            )
            
            if delete_response.status_code == 200:
                dispatcher.utter_message(
                    text=f"Class '{target_class['name']}' deleted successfully!"
                )
            else:
                error_data = delete_response.json() if delete_response.content else {}
                error_msg = error_data.get('detail', 'Failed to delete class')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error deleting class: {e}")
            dispatcher.utter_message(text="An error occurred while deleting the class.")
        
        return [SlotSet("class_name", None)]


class ActionHelp(Action):
    def name(self) -> Text:
        return "action_help"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        help_text = """
**School Assistant Help**

Here's what I can help you with:

**Students:**
• Search for a student: "student eric" or "student 5555"
• Create a student: "Add student [admission_no] named [full name] to class [class name]"
• List all students: "Show me all students" or "List students"
• List students by class: "List students in Grade 4"
• Show unassigned students: "Show unassigned students"

**Classes:**
• Create a class: "Create class [name]" or "New class [level]"
• List all classes: "Show me all classes" or "List classes"
• Show class details: "Show Grade 4 details"
• Find empty classes: "Show empty classes"

**Academic Management:**
The system now uses academic years and terms for proper enrollment tracking.
Students are automatically enrolled in the current term when created.

**Search Examples:**
• "student eric" - Search by first name
• "student 5555" - Search by admission number  
• "student #5555" - Search by admission number with hashtag
• "find john doe" - Search by full name

**Class Examples:**
• "list students in Grade 4" - Students in specific class
• "show students in 8A" - Students in specific class
• "show Grade 4 details" - Class overview
• "empty classes" - Classes with no students
• "unassigned students" - Students not enrolled in current term

**Quick Tips:**
• Use admission numbers for exact student matches
• Use names for broader student searches
• Be specific with class names for best results
• Academic setup (year/term) is required for student creation

Need more specific help? Just ask!
        """
        
        dispatcher.utter_message(text=help_text)
        return []
    

class ActionCompleteTerm(Action):
    def name(self) -> Text:
        return "action_complete_term"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        if not term:
            dispatcher.utter_message(
                text="Which term would you like to close?\n"
                     "Example: 'close term 3'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Get current year if not specified
            if not academic_year:
                year_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-year",
                    headers=headers
                )
                if year_response.status_code == 200:
                    year_data = year_response.json()
                    academic_year = str(year_data.get("year"))
                
                if not academic_year:
                    dispatcher.utter_message(
                        text="No active academic year found. Please specify the year:\n"
                             "Example: 'close term 3 for 2025'"
                    )
                    return [SlotSet("term", None)]
            
            academic_year = str(academic_year)
            
            # Complete the term
            response = requests.put(
                f"{FASTAPI_BASE_URL}/academic/terms/{academic_year}/{term}/complete",
                headers=headers
            )
            
            if response.status_code == 200:
                msg = f"Term {term} for Academic Year {academic_year} has been closed.\n\n"
                
                # Check if this was the last term
                if term == "3":
                    msg += "This was the final term of the academic year.\n\n"
                    msg += "Next steps:\n"
                    msg += f"• Close academic year {academic_year}: 'close academic year {academic_year}'\n"
                    msg += f"• Or create next academic year: 'create academic year {int(academic_year) + 1}'"
                else:
                    next_term = int(term) + 1
                    msg += f"To continue operations:\n"
                    msg += f"• Create term {next_term}: 'add term {next_term} to {academic_year}'\n"
                    msg += f"• Then activate it: 'activate term {next_term}'\n"
                    msg += f"• Promote students: 'promote students to term {next_term}'"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to close term')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error completing term: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while closing the term.")
        
        return [
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]
    

class ActionListAcademicYears(Action):
    def name(self) -> Text:
        return "action_list_academic_years"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/years",
                headers=headers
            )
            
            if response.status_code == 200:
                years = response.json()
                
                if not years:
                    dispatcher.utter_message(
                        text="No academic years found in the system.\n\n"
                             "To create one: 'create academic year 2025'"
                    )
                    return []
                
                years_list = "Academic Years:\n\n"
                
                active_count = 0
                inactive_count = 0
                draft_count = 0
                
                for year in years:
                    state = year["state"].upper()
                    
                    if state == "ACTIVE":
                        indicator = "✓"
                        state_desc = "ACTIVE - current year"
                        active_count += 1
                    elif state == "INACTIVE":
                        indicator = "○"
                        state_desc = "INACTIVE - past year"
                        inactive_count += 1
                    elif state == "DRAFT":
                        indicator = "◐"
                        state_desc = "DRAFT - not activated"
                        draft_count += 1
                    else:
                        indicator = "•"
                        state_desc = state
                    
                    # CORRECT - extract the nested f-string
                year_number = year['year']
                default_title = f'Academic Year {year_number}'
                years_list += f"{indicator} {year_number}: {year.get('title', default_title)} ({state_desc})\n"
                
                years_list += f"\nTotal: {len(years)} year{'s' if len(years) != 1 else ''}"
                years_list += f" ({active_count} active, {inactive_count} inactive, {draft_count} draft)"
                
                if active_count == 0 and draft_count > 0:
                    years_list += f"\n\n⚠️ No active academic year\n"
                    years_list += f"To activate a year:\n"
                    for year in years:
                        if year["state"].upper() == "DRAFT":
                            years_list += f"• 'activate academic year {year['year']}'\n"
                
                dispatcher.utter_message(text=years_list)
            else:
                dispatcher.utter_message(text="Cannot retrieve academic years information.")
        
        except Exception as e:
            logger.error(f"Error listing academic years: {e}")
            dispatcher.utter_message(text="An error occurred while retrieving academic years.")
        
        return []
    

class ActionAddStreamToClass(Action):
    def name(self) -> Text:
        return "action_add_stream_to_class"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        # Get slots
        class_name = tracker.get_slot("class_name")
        stream_slot = tracker.get_slot("stream")
        
        # Parse from message text to get ALL streams
        message_text = tracker.latest_message.get("text", "").lower()
        
        # Extract class name from patterns if not in slot
        if not class_name:
            import re
            # Patterns: "class X", "grade X", "create class X", "add to X"
            class_pattern = r'(?:class|grade|form)\s+(\d+)'
            class_match = re.search(class_pattern, message_text)
            if class_match:
                class_name = class_match.group(1)
        
        if not class_name:
            dispatcher.utter_message(text="Please specify which class to add the stream to.\nExample: 'add stream Red to class 8'")
            return []
        
        # CRITICAL: Extract ALL stream names from the text
        def extract_all_streams(text: str, class_num: str) -> List[str]:
            """
            Extract multiple stream names from text like:
            - "create grade 2 yellow and red"
            - "add blue, green and purple to class 8"
            - "create class 5 with streams red, blue, green"
            """
            import re
            
            # Common color/stream names (expand as needed)
            stream_keywords = [
                'red', 'blue', 'green', 'yellow', 'purple', 'orange', 'pink', 
                'white', 'black', 'brown', 'gray', 'grey', 'violet', 'indigo',
                'maroon', 'turquoise', 'crimson', 'scarlet', 'amber', 'cyan',
                'magenta', 'gold', 'silver', 'bronze',
                'north', 'south', 'east', 'west',
                'alpha', 'beta', 'gamma', 'delta', 'omega',
                'a', 'b', 'c', 'd', 'e',
                'eagle', 'lion', 'tiger', 'falcon', 'hawk', 'phoenix', 'leopard',
                'marvel', 'excellence', 'victory', 'mama', 'baba', 'silk'
            ]
            
            # Remove class number from text to avoid confusion
            text = re.sub(rf'\b(class|grade|form)\s*{class_num}\b', '', text, flags=re.IGNORECASE)
            
            # Split by commas and "and"
            parts = re.split(r',|\s+and\s+', text)
            
            found_streams = []
            for part in parts:
                part = part.strip().lower()
                # Check if this part contains a known stream keyword
                for keyword in stream_keywords:
                    if keyword in part.split():
                        # Capitalize properly
                        found_streams.append(keyword.title())
                        break
            
            # Remove duplicates while preserving order
            seen = set()
            unique_streams = []
            for stream in found_streams:
                if stream.lower() not in seen:
                    seen.add(stream.lower())
                    unique_streams.append(stream)
            
            return unique_streams
        
        # Extract all streams from text
        streams_to_add = extract_all_streams(message_text, str(class_name))
        
        # If no streams found via parsing, fall back to slot value
        if not streams_to_add and stream_slot:
            streams_to_add = [stream_slot]
        
        if not streams_to_add:
            dispatcher.utter_message(text="Please specify the stream name(s).\nExample: 'add stream Red to class 8' or 'create class 8 yellow and red'")
            return []
        
        logger.info(f"Adding streams {streams_to_add} to class {class_name}")
        
        # Normalize stream names
        def normalize_stream_name(stream_name: str, class_name: str) -> str:
            """Remove class number prefix if present and title case"""
            stream_name = stream_name.strip()
            parts = stream_name.split()
            
            if parts and parts[0].isdigit() and parts[0] == str(class_name):
                stream_name = ' '.join(parts[1:]) if len(parts) > 1 else parts[0]
            
            if stream_name.strip().isdigit():
                return None
            
            return stream_name.strip().title()
        
        # Normalize all stream names
        normalized_streams = []
        for stream in streams_to_add:
            normalized = normalize_stream_name(stream, class_name)
            if normalized:
                normalized_streams.append(normalized)
        
        if not normalized_streams:
            dispatcher.utter_message(
                text=f"Invalid stream names. Please specify colors or names, not just numbers.\n"
                     f"Example: 'add stream Red to class {class_name}'"
            )
            return [SlotSet("class_name", None), SlotSet("stream", None)]
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Get current academic year
            setup_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if setup_response.status_code != 200:
                dispatcher.utter_message(text="Cannot retrieve academic setup.")
                return []
            
            setup_data = setup_response.json()
            current_year = setup_data.get("current_year")
            
            if not current_year:
                dispatcher.utter_message(text="No academic year found. Please create one first.")
                return []
            
            academic_year = current_year.get("year")
            
            # Find the class
            classes_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes?search={class_name}&academic_year={academic_year}",
                headers=headers
            )
            
            if classes_response.status_code != 200:
                dispatcher.utter_message(text=f"Could not find class '{class_name}'.")
                return []
            
            classes_data = classes_response.json()
            classes = classes_data.get("classes", [])
            
            if not classes:
                dispatcher.utter_message(
                    text=f"Class '{class_name}' not found for academic year {academic_year}.\n\n"
                         f"Available classes: use 'list classes' to see all classes."
                )
                return []
            
            target_class = classes[0]
            class_id = target_class["id"]
            class_display_name = target_class["name"]
            
            # Track results
            added_streams = []
            failed_streams = []
            skipped_streams = []
            
            # Try to add each stream
            for stream_name in normalized_streams:
                stream_response = requests.post(
                    f"{FASTAPI_BASE_URL}/classes/{class_id}/streams",
                    json={"name": stream_name},
                    headers=headers
                )
                
                if stream_response.status_code == 201:
                    added_streams.append(stream_name)
                elif stream_response.status_code == 409:
                    skipped_streams.append(stream_name)
                else:
                    failed_streams.append(stream_name)
            
            # Build response message
            messages = []
            
            if added_streams:
                if len(added_streams) == 1:
                    messages.append(
                        f"✅ Stream '{added_streams[0]}' has been added to {class_display_name} ({academic_year})!"
                    )
                else:
                    streams_list = "', '".join(added_streams)
                    messages.append(
                        f"✅ Streams '{streams_list}' have been added to {class_display_name} ({academic_year})!"
                    )
            
            if skipped_streams:
                if len(skipped_streams) == 1:
                    messages.append(
                        f"⚠️ Stream '{skipped_streams[0]}' already exists for {class_display_name}."
                    )
                else:
                    streams_list = "', '".join(skipped_streams)
                    messages.append(
                        f"⚠️ Streams '{streams_list}' already exist for {class_display_name}."
                    )
            
            if failed_streams:
                streams_list = "', '".join(failed_streams)
                messages.append(
                    f"❌ Failed to add: '{streams_list}'. Please try again."
                )
            
            if not messages:
                messages.append("No streams were processed.")
            
            # Get updated streams list
            streams_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes/{class_id}/streams",
                headers=headers
            )
            
            if streams_response.status_code == 200:
                data = streams_response.json()
                all_streams = [s['name'] for s in data.get("streams", [])]
                if all_streams:
                    messages.append(
                        f"\nClass {class_display_name} now has streams: {', '.join(all_streams)}"
                    )
            
            dispatcher.utter_message(text="\n".join(messages))
        
        except Exception as e:
            logger.error(f"Error adding streams: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while adding the streams.")
        
        return [
            SlotSet("class_name", None),
            SlotSet("stream", None)
        ]
    
class ActionListStreams(Action):
    def name(self) -> Text:
        return "action_list_streams"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        class_name = tracker.get_slot("class_name")
        
        if not class_name:
            dispatcher.utter_message(text="Please specify which class.\nExample: 'show streams for class 8'")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Get current academic year
            setup_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-setup",
                headers=headers
            )
            
            if setup_response.status_code != 200:
                dispatcher.utter_message(text="Cannot retrieve academic setup.")
                return []
            
            setup_data = setup_response.json()
            current_year = setup_data.get("current_year")
            
            if not current_year:
                dispatcher.utter_message(text="No academic year found.")
                return []
            
            academic_year = current_year.get("year")
            
            # Find the class
            classes_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes?search={class_name}&academic_year={academic_year}",
                headers=headers
            )
            
            if classes_response.status_code != 200:
                dispatcher.utter_message(text=f"Could not find class '{class_name}'.")
                return []
            
            classes_data = classes_response.json()
            classes = classes_data.get("classes", [])
            
            if not classes:
                dispatcher.utter_message(text=f"Class '{class_name}' not found.")
                return []
            
            target_class = classes[0]
            class_id = target_class["id"]
            class_display_name = target_class["name"]
            
            # Get streams
            streams_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes/{class_id}/streams",
                headers=headers
            )
            
            if streams_response.status_code == 200:
                data = streams_response.json()
                streams = data.get("streams", [])
                
                if not streams:
                    dispatcher.utter_message(
                        text=f"No streams found for {class_display_name}.\n\n"
                             f"To add a stream: 'add stream Red to class {class_name}'"
                    )
                else:
                    stream_list = f"Streams for {class_display_name} ({academic_year}):\n\n"
                    for i, stream in enumerate(streams, 1):
                        stream_list += f"{i}. {stream['name']}\n"
                    
                    stream_list += f"\nTotal: {len(streams)} stream{'s' if len(streams) != 1 else ''}"
                    dispatcher.utter_message(text=stream_list)
            else:
                dispatcher.utter_message(text="Could not retrieve streams.")
        
        except Exception as e:
            logger.error(f"Error listing streams: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while listing streams.")
        
        return [SlotSet("class_name", None)]
    

class ActionRenameClass(Action):
    def name(self) -> Text:
        return "action_rename_class"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        old_class_name = tracker.get_slot("class_name")
        new_name = tracker.get_slot("name")
        
        if not old_class_name or not new_name:
            dispatcher.utter_message(
                text="Please specify both the current class name and the new name.\n"
                     "Example: 'rename class 5 to class 55'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Find the class
            response = requests.get(
                f"{FASTAPI_BASE_URL}/classes",
                headers=headers,
                params={"search": old_class_name}
            )
            
            if response.status_code != 200:
                dispatcher.utter_message(text=f"Could not find class '{old_class_name}'.")
                return []
            
            classes = response.json().get("classes", [])
            
            if not classes:
                dispatcher.utter_message(text=f"Class '{old_class_name}' not found.")
                return []
            
            if len(classes) > 1:
                dispatcher.utter_message(
                    text=f"Multiple classes found matching '{old_class_name}'. Please be more specific."
                )
                return []
            
            target_class = classes[0]
            class_id = target_class["id"]
            
            # Update the class name
            update_data = {"name": new_name}
            
            update_response = requests.put(
                f"{FASTAPI_BASE_URL}/classes/{class_id}",
                json=update_data,
                headers=headers
            )
            
            if update_response.status_code == 200:
                dispatcher.utter_message(
                    text=f"✅ Class renamed successfully!\n\n"
                         f"Old name: {old_class_name}\n"
                         f"New name: {new_name}"
                )
            else:
                error_data = update_response.json() if update_response.content else {}
                error_msg = error_data.get('detail', 'Failed to rename class')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error renaming class: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while renaming the class.")
        
        return [
            SlotSet("class_name", None),
            SlotSet("name", None)
        ]