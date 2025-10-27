from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict
import requests
import logging
import re  # CRITICAL: Add this import
from typing import Dict, Text, Any, List

logger = logging.getLogger(__name__)
FASTAPI_BASE_URL = "http://127.0.0.1:8000/api"


class ActionAddGuardian(Action):
    def name(self) -> Text:
        return "action_add_guardian"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        # Get all required slots
        guardian_name = tracker.get_slot("guardian_name")
        student_name = tracker.get_slot("student_name")
        admission_no = tracker.get_slot("admission_no")
        phone = tracker.get_slot("phone")
        email = tracker.get_slot("email")
        relationship = tracker.get_slot("relationship") or "GUARDIAN"
        
        # VALIDATION: Check all required fields
        if not guardian_name:
            dispatcher.utter_message(text="Guardian name is required.")
            return []
        
        if not phone:
            dispatcher.utter_message(text="Phone number is required.")
            return []
        
        if not email:
            dispatcher.utter_message(text="Email is required.")
            return []
        
        logger.info(f"Adding guardian: {guardian_name} for student: {student_name or admission_no}")
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Find student
            search_params = {}
            if admission_no:
                clean_admission = str(admission_no).lstrip("#").strip()
                search_params["admission_no"] = clean_admission
            elif student_name:
                search_params["search"] = student_name
            else:
                dispatcher.utter_message(text="Could not identify student.")
                return []
            
            students_response = requests.get(
                f"{FASTAPI_BASE_URL}/students",
                headers=headers,
                params=search_params
            )
            
            if students_response.status_code != 200:
                dispatcher.utter_message(text="Could not find student.")
                return []
            
            students = students_response.json().get("students", [])
            
            if not students:
                query = admission_no or student_name
                dispatcher.utter_message(text=f"No student found matching '{query}'.")
                return []
            
            if len(students) > 1:
                msg = f"Multiple students found:\n\n"
                for i, s in enumerate(students[:5], 1):
                    msg += f"{i}. {s['first_name']} {s['last_name']} (#{s['admission_no']})\n"
                msg += "\nPlease specify by admission number."
                dispatcher.utter_message(text=msg)
                return []
            
            student = students[0]
            student_id = student["id"]
            full_name = f"{student['first_name']} {student['last_name']}"
            
            # Parse guardian name into first and last
            name_parts = guardian_name.strip().split()
            if len(name_parts) < 2:
                first_name = name_parts[0]
                last_name = name_parts[0]
            else:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
            
            # Create guardian
            guardian_data = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email.lower().strip() if email else None,
                "phone": phone.strip() if phone else None,
                "relationship": relationship.upper() if relationship else "GUARDIAN",
                "student_id": student_id
            }
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/guardians/",
                json=guardian_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                msg = f"✅ **Guardian added successfully!**\n\n"
                msg += f"**Name:** {data['full_name']}\n"
                msg += f"**Relationship:** {data['relationship']}\n"
                msg += f"**Phone:** {data['phone']}\n"
                msg += f"**Email:** {data['email']}\n\n"
                msg += f"**Linked to:** {full_name} (#{student['admission_no']})"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to add guardian')
                dispatcher.utter_message(text=f"❌ Error: {error_msg}")
        
        except AttributeError as e:
            logger.error(f"AttributeError adding guardian: {e}", exc_info=True)
            dispatcher.utter_message(text="Missing required information. Please ensure all fields are provided.")
        except Exception as e:
            logger.error(f"Error adding guardian: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while adding the guardian.")
        
        return [
            SlotSet("guardian_name", None),
            SlotSet("student_name", None),
            SlotSet("admission_no", None),
            SlotSet("phone", None),
            SlotSet("email", None),
            SlotSet("relationship", None)
        ]


class ActionGetGuardians(Action):
    def name(self) -> Text:
        return "action_get_guardians"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        student_name = tracker.get_slot("student_name")
        admission_no = tracker.get_slot("admission_no")
        
        if not student_name and not admission_no:
            dispatcher.utter_message(
                text="Please specify a student. Example: 'show guardians for Eric'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Find student
            search_params = {}
            if admission_no:
                search_params["admission_no"] = admission_no
            elif student_name:
                search_params["search"] = student_name
            
            students_response = requests.get(
                f"{FASTAPI_BASE_URL}/students",
                headers=headers,
                params=search_params
            )
            
            if students_response.status_code != 200:
                dispatcher.utter_message(text="Could not find student.")
                return []
            
            students = students_response.json().get("students", [])
            
            if not students:
                query = admission_no or student_name
                dispatcher.utter_message(text=f"No student found matching '{query}'.")
                return []
            
            if len(students) > 1:
                dispatcher.utter_message(text="Multiple students found. Please specify by admission number.")
                return []
            
            student = students[0]
            student_id = student["id"]
            full_name = f"{student['first_name']} {student['last_name']}"
            
            # Get guardians
            guardians_response = requests.get(
                f"{FASTAPI_BASE_URL}/guardians/student/{student_id}",
                headers=headers
            )
            
            if guardians_response.status_code == 200:
                guardians = guardians_response.json()
                
                if not guardians:
                    dispatcher.utter_message(
                        text=f"No guardians found for {full_name} (#{student['admission_no']}).\n\n"
                             f"To add a guardian:\n"
                             f"'Add guardian [name] ([relationship]) with phone [number] for student {student['admission_no']}'"
                    )
                    return []
                
                # Sort guardians - primary first, then alphabetically
                guardians_sorted = sorted(
                    guardians, 
                    key=lambda g: (
                        not g.get('is_primary', False),
                        g.get('full_name', '')
                    )
                )
                
                msg = f"Guardians for {full_name} (#{student['admission_no']}):\n\n"
                
                for i, guardian in enumerate(guardians_sorted, 1):
                    primary_marker = " (Primary)" if guardian.get('is_primary', False) else ""
                    msg += f"{i}. {guardian['full_name']}{primary_marker}\n"
                    
                    if guardian.get('relationship'):
                        msg += f"   Relationship: {guardian['relationship']}\n"
                    if guardian.get('phone'):
                        msg += f"   Phone: {guardian['phone']}\n"
                    if guardian.get('email'):
                        msg += f"   Email: {guardian['email']}\n"
                    msg += "\n"
                
                msg = msg.rstrip()
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Could not retrieve guardians.")
        
        except Exception as e:
            logger.error(f"Error getting guardians: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("student_name", None),
            SlotSet("admission_no", None)
        ]


class ActionListStudentsWithoutGuardians(Action):
    def name(self) -> Text:
        return "action_list_students_without_guardians"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/guardians/unlinked-students",
                headers=headers
            )
            
            if response.status_code == 200:
                students = response.json()
                
                if not students:
                    dispatcher.utter_message(
                        text="All students have guardians linked!"
                    )
                    return []
                
                msg = f"Students without guardians ({len(students)}):\n\n"
                
                for i, student in enumerate(students[:20], 1):
                    msg += f"{i}. {student['full_name']} (#{student['admission_no']})\n"
                
                if len(students) > 20:
                    msg += f"\n... and {len(students) - 20} more\n"
                
                msg += f"\nTo add a guardian:\n'Add guardian [name] ([relationship]) for student [admission_no]'"
                
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Could not retrieve students.")
        
        except Exception as e:
            logger.error(f"Error listing students: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return []


class ActionSetPrimaryGuardian(Action):
    def name(self) -> Text:
        return "action_set_primary_guardian"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        guardian_name = tracker.get_slot("guardian_name")
        student_name = tracker.get_slot("student_name")
        admission_no = tracker.get_slot("admission_no")
        
        if not guardian_name:
            dispatcher.utter_message(
                text="Please specify which guardian. Example:\n"
                     "'Make Mary Wanjiku the primary guardian for student 2345'"
            )
            return []
        
        if not student_name and not admission_no:
            dispatcher.utter_message(
                text="Please specify which student. Example:\n"
                     "'Make Mary Wanjiku the primary guardian for student 2345'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Find student
            search_params = {}
            if admission_no:
                search_params["admission_no"] = admission_no
            elif student_name:
                search_params["search"] = student_name
            
            students_response = requests.get(
                f"{FASTAPI_BASE_URL}/students",
                headers=headers,
                params=search_params
            )
            
            if students_response.status_code != 200:
                dispatcher.utter_message(text="Could not find student.")
                return []
            
            students = students_response.json().get("students", [])
            
            if not students:
                query = admission_no or student_name
                dispatcher.utter_message(text=f"No student found matching '{query}'.")
                return []
            
            if len(students) > 1:
                dispatcher.utter_message(
                    text="Multiple students found. Please specify by admission number."
                )
                return []
            
            student = students[0]
            student_id = student["id"]
            full_name = f"{student['first_name']} {student['last_name']}"
            
            # Find guardian linked to this student
            guardians_response = requests.get(
                f"{FASTAPI_BASE_URL}/guardians/student/{student_id}",
                headers=headers
            )
            
            if guardians_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve guardians.")
                return []
            
            guardians = guardians_response.json()
            
            if not guardians:
                dispatcher.utter_message(
                    text=f"No guardians found for {full_name}.\n\n"
                         f"Add a guardian first: 'Add guardian {guardian_name} for student {student['admission_no']}'"
                )
                return []
            
            # Find matching guardian
            guardian_name_lower = guardian_name.lower().strip()
            target_guardian = None
            
            for guardian in guardians:
                if guardian_name_lower in guardian['full_name'].lower():
                    target_guardian = guardian
                    break
            
            if not target_guardian:
                available_names = [g['full_name'] for g in guardians]
                dispatcher.utter_message(
                    text=f"Guardian '{guardian_name}' not found for {full_name}.\n\n"
                         f"Available guardians:\n" + "\n".join(f"• {name}" for name in available_names)
                )
                return []
            
            # Update student to set primary guardian
            update_data = {
                "primary_guardian_id": target_guardian['id']
            }
            
            update_response = requests.put(
                f"{FASTAPI_BASE_URL}/students/{student_id}",
                json=update_data,
                headers=headers
            )
            
            if update_response.status_code == 200:
                msg = f"✅ Primary guardian updated successfully!\n\n"
                msg += f"**Student:** {full_name} (#{student['admission_no']})\n"
                msg += f"**Primary Guardian:** {target_guardian['full_name']}\n"
                if target_guardian.get('relationship'):
                    msg += f"**Relationship:** {target_guardian['relationship']}\n"
                if target_guardian.get('phone'):
                    msg += f"**Phone:** {target_guardian['phone']}\n"
                if target_guardian.get('email'):
                    msg += f"**Email:** {target_guardian['email']}"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = update_response.json() if update_response.content else {}
                error_msg = error_data.get('detail', 'Failed to update primary guardian')
                dispatcher.utter_message(text=f"❌ Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error setting primary guardian: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while updating primary guardian.")
        
        return [
            SlotSet("guardian_name", None),
            SlotSet("student_name", None),
            SlotSet("admission_no", None)
        ]


class ActionUpdateGuardian(Action):
    def name(self) -> Text:
        return "action_update_guardian"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        guardian_name = tracker.get_slot("guardian_name")
        email = tracker.get_slot("email")
        phone = tracker.get_slot("phone")
        relationship = tracker.get_slot("relationship")
        
        if not guardian_name:
            dispatcher.utter_message(
                text="Please specify which guardian to update. Example:\n"
                     "'Update Eric Mwirichia email to eric@gmail.com'"
            )
            return []
        
        if not email and not phone and not relationship:
            dispatcher.utter_message(
                text="Please provide what to update (email, phone, or relationship). Example:\n"
                     "'Update Eric Mwirichia email to eric@gmail.com'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Search for guardian across all students
            students_response = requests.get(
                f"{FASTAPI_BASE_URL}/students",
                headers=headers,
                params={"limit": 100}
            )
            
            if students_response.status_code != 200:
                dispatcher.utter_message(text="Could not search for guardian.")
                return []
            
            students = students_response.json().get("students", [])
            
            target_guardian = None
            guardian_name_lower = guardian_name.lower().strip()
            
            for student in students:
                guardians_response = requests.get(
                    f"{FASTAPI_BASE_URL}/guardians/student/{student['id']}",
                    headers=headers
                )
                
                if guardians_response.status_code == 200:
                    guardians = guardians_response.json()
                    for guardian in guardians:
                        if guardian_name_lower in guardian['full_name'].lower():
                            target_guardian = guardian
                            break
                
                if target_guardian:
                    break
            
            if not target_guardian:
                dispatcher.utter_message(
                    text=f"Guardian '{guardian_name}' not found.\n\n"
                         f"Make sure the guardian is already added to a student."
                )
                return []
            
            # Build update payload
            update_data = {}
            if email:
                update_data["email"] = email
            if phone:
                update_data["phone"] = phone
            if relationship:
                clean_rel = relationship.strip().replace("(", "").replace(")", "").upper()
                update_data["relationship"] = clean_rel
            
            # Call update endpoint
            response = requests.put(
                f"{FASTAPI_BASE_URL}/guardians/{target_guardian['id']}",
                json=update_data,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                msg = f"✅ Guardian updated successfully!\n\n"
                msg += f"**Name:** {data['full_name']}\n"
                if data.get('relationship'):
                    msg += f"**Relationship:** {data['relationship']}\n"
                if data.get('phone'):
                    msg += f"**Phone:** {data['phone']}\n"
                if data.get('email'):
                    msg += f"**Email:** {data['email']}"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to update guardian')
                dispatcher.utter_message(text=f"❌ Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error updating guardian: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while updating guardian.")
        
        return [
            SlotSet("guardian_name", None),
            SlotSet("email", None),
            SlotSet("phone", None),
            SlotSet("relationship", None)
        ]


class ActionListAllGuardians(Action):
    def name(self) -> Text:
        return "action_list_all_guardians"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Get all guardians
            response = requests.get(
                f"{FASTAPI_BASE_URL}/guardians/",
                headers=headers
            )
            
            if response.status_code == 200:
                guardians = response.json()
                
                if not guardians:
                    dispatcher.utter_message(
                        text="No guardians found in the system.\n\n"
                             "To add a guardian:\n"
                             "'Add guardian [name] ([relationship]) with phone [number] and email [email] for student [admission_no]'"
                    )
                    return []
                
                # Sort guardians alphabetically
                guardians_sorted = sorted(guardians, key=lambda g: g.get('full_name', ''))
                
                msg = f"**All Guardians ({len(guardians)}):**\n\n"
                
                for i, guardian in enumerate(guardians_sorted[:50], 1):
                    msg += f"**{i}. {guardian['full_name']}**\n"
                    
                    if guardian.get('relationship'):
                        msg += f"   • Relationship: {guardian['relationship']}\n"
                    if guardian.get('phone'):
                        msg += f"   • Phone: {guardian['phone']}\n"
                    if guardian.get('email'):
                        msg += f"   • Email: {guardian['email']}\n"
                    
                    if guardian.get('students'):
                        student_names = [s.get('full_name', 'Unknown') for s in guardian['students']]
                        msg += f"   • Students: {', '.join(student_names)}\n"
                    
                    msg += "\n"
                
                if len(guardians) > 50:
                    msg += f"... and {len(guardians) - 50} more guardians\n"
                
                dispatcher.utter_message(text=msg.rstrip())
            else:
                dispatcher.utter_message(text="Could not retrieve guardians.")
        
        except Exception as e:
            logger.error(f"Error listing all guardians: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while retrieving guardians.")
        
        return []


class ValidateGuardianCreationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_guardian_creation_form"
    
    def validate_student_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate student name - ONLY capture when explicitly asking for student"""
        
        # CRITICAL: Check if student_name was already set in the initial intent
        initial_student = None
        for event in reversed(list(tracker.events)):
            if event.get("event") == "user":
                entities = event.get("parse_data", {}).get("entities", [])
                for entity in entities:
                    if entity.get("entity") == "student_name":
                        initial_student = entity.get("value")
                        break
                if initial_student:
                    break
        
        # If student was captured in initial intent, use that
        if initial_student and not slot_value:
            logger.info(f"✅ Using student_name from initial intent: {initial_student}")
            return {"student_name": initial_student}
        
        # Otherwise, validate normally
        user_text = tracker.latest_message.get('text', '')
        
        if slot_value and len(str(slot_value).strip()) > 0:
            return {"student_name": str(slot_value).strip()}
        
        if user_text and len(user_text.strip()) > 0:
            # Don't accept phone numbers or emails as student names
            if re.match(r'^[\d\s\-\+\(\)]+$', user_text):
                dispatcher.utter_message(text="That looks like a phone number. Please provide the student's name or admission number.")
                return {"student_name": None}
            
            if '@' in user_text:
                dispatcher.utter_message(text="That looks like an email. Please provide the student's name or admission number.")
                return {"student_name": None}
            
            return {"student_name": user_text.strip()}
        
        dispatcher.utter_message(text="Please provide the student's name or admission number.")
        return {"student_name": None}