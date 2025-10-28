from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Dict, Text, Any, List
import requests
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000/api")


class ActionGetSchoolInfo(Action):
    def name(self) -> Text:
        return "action_get_school_info"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token or not school_id:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Fetch school overview
            response = requests.get(
                f"{FASTAPI_BASE_URL}/schools/{school_id}/overview",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Build comprehensive overview
                msg = f"**📚 School Overview: {data['school_name']}**\n\n"
                
                # Academic context (if available)
                if data.get('academic_year') and data.get('current_term'):
                    msg += f"**Academic Year:** {data['academic_year']}\n"
                    msg += f"**Current Term:** {data['current_term']}\n\n"
                elif data.get('academic_year'):
                    msg += f"**Academic Year:** {data['academic_year']}\n\n"
                
                # Student stats
                msg += f"**Students:**\n"
                msg += f"• Total: {data['students_total']}\n"
                
                if data.get('current_term'):
                    msg += f"• Enrolled: {data['students_enrolled']}\n"
                    if data['students_unassigned'] > 0:
                        msg += f"• Unassigned: {data['students_unassigned']}\n"
                
                msg += f"\n**Classes:** {data['classes']} active\n"
                msg += f"**Guardians:** {data['guardians']} registered\n\n"
                
                # Financial overview (if there are invoices)
                if data['invoices_total'] > 0:
                    msg += f"**Financial Summary:**\n"
                    msg += f"• Total Invoices: {data['invoices_total']}\n"
                    msg += f"• Paid: {data['invoices_paid']}\n"
                    msg += f"• Pending: {data['invoices_pending']}\n"
                    msg += f"• Fees Collected: KES {data['fees_collected']:,.2f}\n"
                
                dispatcher.utter_message(text=msg)
                
            elif response.status_code == 404:
                dispatcher.utter_message(text="School not found.")
            else:
                dispatcher.utter_message(
                    text="Could not retrieve school overview at this time."
                )
        
        except Exception as e:
            logger.error(f"Error getting school overview: {e}", exc_info=True)
            dispatcher.utter_message(
                text="An error occurred while retrieving school information."
            )
        
        return []