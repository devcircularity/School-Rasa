from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
import logging
from typing import Dict, Text, Any, List
import os
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000/api")


class ActionNotifyPendingInvoices(Action):
    def name(self) -> Text:
        return "action_notify_pending_invoices"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        academic_year = tracker.get_slot("academic_year")
        term = tracker.get_slot("term")
        due_date = tracker.get_slot("due_date")
        user_message = tracker.latest_message.get("text", "")
        
        # Parse from message if not in slots
        if not academic_year or not term:
            import re
            year_match = re.search(r'\b(20\d{2})\b', user_message)
            term_match = re.search(r'(?:term\s+)?(\d)(?!\d)', user_message, re.IGNORECASE)
            
            if year_match:
                academic_year = year_match.group(1)
            if term_match:
                term = term_match.group(1)
        
        # Default to current term if not specified
        if not academic_year or not term:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                current_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-term",
                    headers=headers
                )
                
                if current_response.status_code == 200:
                    current_term = current_response.json()
                    academic_year = str(current_term['academic_year'])
                    term = str(current_term['term'])
            except Exception as e:
                logger.error(f"Error getting current term: {e}")
                dispatcher.utter_message(
                    text="Please specify year and term. Example:\n\n"
                         "```\nnotify parents about pending invoices for 2025 term 3\n```"
                )
                return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Prepare params
            params = {
                "year": int(academic_year),
                "term": int(term)
            }
            
            # Add due_date if provided (backend may or may not support this)
            if due_date:
                params["due_date_override"] = due_date
            
            # Call notification endpoint
            response = requests.post(
                f"{FASTAPI_BASE_URL}/notifications/notify-pending-invoices",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                
                sent = data.get("sent", 0)
                failed = data.get("failed", 0)
                errors = data.get("errors", [])
                
                if sent == 0 and failed == 0:
                    msg = f"No pending invoices found for Term {term} {academic_year}."
                    dispatcher.utter_message(text=msg)
                    return []
                
                # Build success message with email preview
                msg = f"**Fee reminder notifications sent successfully!**\n\n"
                msg += f"**Notifications sent:** {sent}\n"
                
                if failed > 0:
                    msg += f"**Failed:** {failed}\n"
                
                msg += f"**Term:** {term} {academic_year}\n"
                
                # Show due date if specified
                if due_date:
                    msg += f"**Due Date:** {due_date}\n"
                
                msg += f"\n---\n\n"
                msg += f"**Email Preview:**\n\n"
                msg += f"```\n"
                msg += f"To: Guardians with Pending Invoices ({sent} recipient{'s' if sent != 1 else ''})\n"
                msg += f"Subject: School Fees Payment Reminder - [Student Name] (Term {term} {academic_year})\n\n"
                msg += f"Dear [Guardian Name],\n\n"
                
                # Custom due date message
                if due_date:
                    msg += f"This is a reminder to pay your child's school fees by {due_date}.\n\n"
                else:
                    msg += f"This is a reminder that there is a pending invoice for your child [Student Name].\n\n"
                
                msg += f"Invoice Details:\n"
                msg += f"• Total Amount: KES [Invoice Total]\n"
                msg += f"• Amount Paid: KES [Amount Paid]\n"
                msg += f"• Balance Due: KES [Balance]\n"
                
                if due_date:
                    msg += f"• Payment Due: {due_date}\n"
                else:
                    msg += f"• Due Date: [Due Date]\n"
                
                msg += f"\nPlease make payment at your earliest convenience.\n\n"
                msg += f"Best regards,\n"
                msg += f"School Administration\n"
                msg += f"```\n\n"
                
                # Show errors if any
                if failed > 0 and errors:
                    msg += f"---\n\n"
                    msg += f"**⚠️ Delivery Issues ({failed}):**\n\n"
                    for error in errors[:10]:
                        msg += f"• {error}\n"
                    
                    if len(errors) > 10:
                        msg += f"\n*...and {len(errors) - 10} more issues*\n"
                    
                    msg += f"\n**Action needed:** Add email addresses for affected guardians to ensure they receive notifications."
                else:
                    msg += f"All guardians have been notified."
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to send notifications')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error sending notifications: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while sending notifications.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None),
            SlotSet("due_date", None)
        ]
    

class ActionSendGuardianMessage(Action):
    def name(self) -> Text:
        return "action_send_guardian_message"

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
        message = tracker.get_slot("message")
        
        if not (student_name or admission_no):
            dispatcher.utter_message(
                text="Please specify which student. Example:\n\n"
                     "```\nsend notification to student #123 guardians to come to school tomorrow\n```"
            )
            return []
        
        if not message:
            dispatcher.utter_message(
                text="Please specify the message. Example:\n\n"
                     "```\nnotify Eric's parent about parent teacher meeting\n```"
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
                clean_admission = str(admission_no).lstrip("#").strip()
                search_params["admission_no"] = clean_admission
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
            
            # Check if student has guardians
            guardians_response = requests.get(
                f"{FASTAPI_BASE_URL}/guardians/student/{student_id}",
                headers=headers
            )
            
            if guardians_response.status_code != 200:
                dispatcher.utter_message(text="Could not check guardian information.")
                return []
            
            guardians = guardians_response.json()
            
            if not guardians:
                msg = f"No guardians found for **{full_name} (#{student['admission_no']})**.\n\n"
                msg += f"Please add a guardian first:\n\n"
                msg += f"```\nAdd [name], [relationship] to [student] with phone [number] and email [email]\n```\n\n"
                msg += f"**Example:**\n\n"
                msg += f"```\nAdd Mary Wanjiku, mother to {student['first_name']} with phone 0712345678 and email mary@gmail.com\n```"
                
                dispatcher.utter_message(text=msg)
                return [
                    SlotSet("student_name", None),
                    SlotSet("admission_no", None),
                    SlotSet("message", None)
                ]
            
            # Send notification to all guardians
            notification_data = {
                "student_id": student_id,
                "message": message
            }
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/notifications/guardian-message",
                json=notification_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                sent_count = data.get("sent_count", len(guardians))
                
                # Build preview message
                msg = f"**Message sent successfully!**\n\n"
                msg += f"**Student:** {full_name} (#{student['admission_no']})\n"
                msg += f"**Recipients:** {sent_count} guardian(s)\n\n"
                msg += f"---\n\n"
                msg += f"**Email Preview:**\n\n"
                
                # Get first guardian for preview
                guardian_name = f"{guardians[0]['first_name']} {guardians[0]['last_name']}"
                
                msg += f"```\n"
                msg += f"To: {guardians[0]['email']}\n"
                msg += f"Subject: Message regarding {full_name}\n\n"
                msg += f"Dear {guardian_name},\n\n"
                msg += f"This is a message regarding your child {full_name}:\n\n"
                msg += f"{message}\n\n"
                msg += f"Best regards,\n"
                msg += f"School Administration\n"
                msg += f"```"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to send message')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error sending guardian message: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while sending the message.")
        
        return [
            SlotSet("student_name", None),
            SlotSet("admission_no", None),
            SlotSet("message", None)
        ]