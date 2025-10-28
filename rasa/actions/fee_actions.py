# rasa/actions/fee_actions.py
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
import logging
import re
from typing import Dict, Text, Any, List
from decimal import Decimal
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000/api")



def fix_swapped_year_term(academic_year: str, term: str, user_message: str) -> tuple:
    """
    Detect and fix when Rasa swaps year and term entities.
    Returns (corrected_year, corrected_term)
    """
    if not academic_year or not term:
        return academic_year, term
    
    # Convert to strings for comparison
    year_str = str(academic_year).strip()
    term_str = str(term).strip()
    
    # Check if they're swapped (year should be 4 digits, term should be 1 digit)
    year_is_4_digits = len(year_str) == 4 and year_str.isdigit()
    term_is_1_digit = len(term_str) == 1 and term_str.isdigit()
    
    year_is_1_digit = len(year_str) == 1 and year_str.isdigit()
    term_is_4_digits = len(term_str) == 4 and term_str.isdigit()
    
    # If year is 1 digit and term is 4 digits, they're swapped
    if year_is_1_digit and term_is_4_digits:
        logger.warning(
            f"Detected swapped entities in '{user_message}': "
            f"year='{year_str}' (should be term), term='{term_str}' (should be year). "
            f"Correcting..."
        )
        return term_str, year_str  # Swap them back
    
    # If already correct, return as-is
    if year_is_4_digits and term_is_1_digit:
        return year_str, term_str
    
    # Fallback: return as-is with warning
    logger.warning(
        f"Ambiguous year/term values: year='{year_str}', term='{term_str}'. "
        f"Using as-is, but may be incorrect."
    )
    return year_str, term_str


class ActionCreateFeeStructure(Action):
    def name(self) -> Text:
        return "action_create_fee_structure"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required. Please log in first.")
            return []
        
        academic_year = tracker.get_slot("academic_year")
        term = tracker.get_slot("term")
        level = tracker.get_slot("level")
        structure_name = tracker.get_slot("structure_name")
        
        # Enhanced level extraction
        if not level:
            message_text = tracker.latest_message.get("text", "").lower()
            import re
            patterns = [
                r'(grade|form|jss|pp|standard|class)\s*(\d+[a-z]?)',
                r'(nursery|kindergarten|baby\s+class)',
            ]
            for pattern in patterns:
                match = re.search(pattern, message_text, re.IGNORECASE)
                if match:
                    if match.lastindex == 2:
                        level = f"{match.group(1).title()} {match.group(2)}"
                    else:
                        level = match.group(1).title()
                    break
        
        if not level:
            level = "ALL"
        
        # If term is provided but year is not, get current academic year
        if term and not academic_year:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                current_year_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-year",
                    headers=headers
                )
                
                if current_year_response.status_code == 200:
                    year_data = current_year_response.json()
                    academic_year = str(year_data.get("year"))
                    logger.info(f"Using current academic year: {academic_year}")
                else:
                    logger.warning(f"Could not get current year, status: {current_year_response.status_code}")
            except Exception as e:
                logger.error(f"Error getting current year: {e}")
        
        # Check if both year and term are present
        if not academic_year or not term:
            dispatcher.utter_message(
                text="Please specify both year and term. Example:\n"
                     "• 'create fee structure for 2025 term 1'\n"
                     "• 'create fee structure named Standard Package for 2025 term 1'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # CHECK FOR EXISTING STRUCTURES FIRST
            check_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers,
                params={"year": academic_year, "term": term}
            )
            
            if check_response.status_code == 200:
                existing = check_response.json()
                
                # Check for exact level match
                level_match = [s for s in existing if s['level'] == level]
                
                if level_match:
                    existing_struct = level_match[0]
                    msg = f"**A fee structure already exists!**\n\n"
                    msg += f"**Name:** {existing_struct['name']}\n"
                    msg += f"**Level:** {existing_struct['level']}\n"
                    msg += f"**Year:** {existing_struct['year']}, **Term:** {existing_struct['term']}\n"
                    msg += f"**Status:** {'Published' if existing_struct['is_published'] else 'Draft'}\n\n"
                    
                    if not existing_struct['is_published']:
                        msg += "**You can:**\n\n"
                        msg += f"• Add items:\n```\nadd tuition fee of 25,000 to {existing_struct['name']}\n```\n\n"
                        msg += f"• View details:\n```\nshow fee structure {existing_struct['name']}\n```\n\n"
                        msg += f"• Use a different level:\n```\ncreate fee structure for Grade 4 {academic_year} term {term}\n```\n\n"
                        msg += f"• Use a custom name:\n```\ncreate fee structure named Premium for {academic_year} term {term}\n```"
                    else:
                        msg += "This structure is already published.\n\n"
                        msg += "• View it:\n```\nshow fee structures\n```\n\n"
                        msg += f"• Create for different level:\n```\ncreate fee structure for Grade X {academic_year} term {term}\n```"
                    
                    dispatcher.utter_message(text=msg)
                    return []
                
                # Check for name collision if custom name provided
                if structure_name:
                    name_match = [s for s in existing if s['name'].lower() == structure_name.lower()]
                    if name_match:
                        dispatcher.utter_message(
                            text=f"**A fee structure named '{structure_name}' already exists.**\n\n"
                                 f"Try a different name or view existing:\n\n"
                                 f"```\nshow fee structures for {academic_year} term {term}\n```"
                        )
                        return []
            
            # Generate name if not provided
            if not structure_name:
                if level == "ALL":
                    structure_name = f"Term {term} {academic_year}"
                else:
                    structure_name = f"{level} - Term {term} {academic_year}"
            else:
                structure_name = structure_name.strip()
            
            payload = {
                "name": structure_name,
                "level": level,
                "term": int(term),
                "year": int(academic_year),
                "is_default": (level == "ALL")
            }
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                json=payload,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                msg = f"**Fee structure created successfully!**\n\n"
                msg += f"**Name:** {structure_name}\n"
                msg += f"**Level:** {level}\n"
                msg += f"**Academic Year:** {academic_year}\n"
                msg += f"**Term:** {term}\n"
                msg += f"**Status:** Draft\n\n"
                msg += f"---\n\n"
                
                # Dynamic next steps
                if level == "ALL":
                    msg += f"**Next step:** Add fee items (applies to all students)\n\n"
                    msg += f"**Examples:**\n\n"
                    msg += f"```\nadd tuition fee of 25,000 to {structure_name}\n```\n\n"
                    msg += f"```\nadd transport fee of 5,000 to {structure_name}\n```\n\n"
                    msg += f"```\nadd exam fee of 2,500 to {structure_name}\n```"
                else:
                    msg += f"**Next step:** Add {level}-specific fee items\n\n"
                    msg += f"**Examples:**\n\n"
                    msg += f"```\nadd tuition fee of 25,000 to {structure_name}\n```\n\n"
                    msg += f"```\nadd lab fee of 3,000 to {structure_name}\n```"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to create fee structure')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error creating fee structure: {e}")
            dispatcher.utter_message(text="An error occurred while creating the fee structure.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None),
            SlotSet("level", None),
            SlotSet("structure_name", None)
        ]

class ActionListFeeStructures(Action):
    def name(self) -> Text:
        return "action_list_fee_structures"

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
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            params = {}
            if academic_year:
                params["year"] = academic_year
            if term:
                params["term"] = term
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                structures = response.json()
                
                if not structures:
                    if academic_year and term:
                        msg = f"No fee structures found for {academic_year} Term {term}.\n\n"
                        msg += f"Create one: 'create fee structure for {academic_year} term {term}'"
                    elif academic_year:
                        msg = f"No fee structures found for {academic_year}.\n\n"
                        msg += f"Create one: 'create fee structure for {academic_year} term 1'"
                    else:
                        msg = "No fee structures found.\n\n"
                        msg += "Create one: 'create fee structure for 2025 term 1'"
                    
                    dispatcher.utter_message(text=msg)
                    return []
                
                # Filter out empty duplicates - keep only structures with items or the first one
                relevant_structures = []
                seen_keys = set()
                
                for struct in structures:
                    item_count = struct.get('item_count', 0)
                    key = (struct['year'], struct['term'], struct['level'])
                    
                    # Keep if: has items, or is first of its year/term/level
                    if item_count > 0 or key not in seen_keys:
                        relevant_structures.append(struct)
                        seen_keys.add(key)
                
                empty_count = len(structures) - len(relevant_structures)
                
                # Build title
                if academic_year and term:
                    msg = f"Fee Structures for {academic_year} Term {term}:\n\n"
                elif academic_year:
                    msg = f"Fee Structures for {academic_year}:\n\n"
                else:
                    msg = "Fee Structures:\n\n"
                
                for i, struct in enumerate(relevant_structures, 1):
                    if struct['is_published']:
                        status_icon = "✓"
                        status_text = "Published"
                    else:
                        status_icon = "○"
                        status_text = "Draft"
                    
                    default_text = " (Default)" if struct['is_default'] else ""
                    
                    msg += f"{i}. {struct['name']}{default_text}\n"
                    msg += f"   Level: {struct['level']}\n"
                    
                    item_count = struct.get('item_count', 0)
                    msg += f"   Items: {item_count} fee item{'s' if item_count != 1 else ''}\n"
                    
                    try:
                        total_amount = float(struct.get('total_amount', 0))
                        msg += f"   Total: KES {total_amount:,.2f}\n"
                    except (ValueError, TypeError):
                        msg += f"   Total: KES {struct.get('total_amount', '0.00')}\n"
                    
                    msg += f"   Status: {status_text}\n\n"
                
                if empty_count > 0:
                    msg += f"Note: {empty_count} empty structure{'s' if empty_count != 1 else ''} hidden.\n\n"
                
                draft_count = sum(1 for s in relevant_structures if not s['is_published'])
                if draft_count > 0:
                    msg += f"Next steps:\n"
                    msg += "• Add items: 'add [fee type] of [amount] to [structure name]'\n"
                    msg += "• Publish: 'publish [structure name]'"
                else:
                    msg += "All structures are published and ready for invoicing."
                
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
        
        except Exception as e:
            logger.error(f"Error listing fee structures: {e}")
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None)
        ]


class ActionGenerateInvoices(Action):
    def name(self) -> Text:
        return "action_generate_invoices"

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
        class_name = tracker.get_slot("class_name")
        user_message = tracker.latest_message.get("text", "")
        
        # DEBUG LOGGING
        logger.info("="*80)
        logger.info(f"GENERATE INVOICES DEBUG")
        logger.info(f"User message: '{user_message}'")
        logger.info(f"Extracted slots (BEFORE fix):")
        logger.info(f"   academic_year: '{academic_year}'")
        logger.info(f"   term: '{term}'")
        logger.info(f"   class_name: '{class_name}'")
        
        # FIX SWAPPED ENTITIES
        if academic_year and term:
            academic_year, term = fix_swapped_year_term(academic_year, term, user_message)
            logger.info(f"After swap detection:")
            logger.info(f"   academic_year: '{academic_year}'")
            logger.info(f"   term: '{term}'")
        
        # ADDITIONAL FIX: Parse from user message if one is missing
        if not academic_year or not term:
            logger.info("One or both entities missing, attempting to parse from message...")
            
            import re
            year_match = re.search(r'\b(20\d{2})\b', user_message)
            term_match = re.search(r'(?:term\s+)?(\d)(?!\d)', user_message, re.IGNORECASE)
            
            if year_match:
                extracted_year = year_match.group(1)
                logger.info(f"Found year in message: {extracted_year}")
            else:
                extracted_year = None
            
            if term_match:
                extracted_term = term_match.group(1)
                logger.info(f"Found term in message: {extracted_term}")
            else:
                extracted_term = None
            
            # Smart assignment: if term slot has 4 digits, it's actually the year
            if term and len(str(term)) == 4 and str(term).isdigit():
                academic_year = term
                term = extracted_term
                logger.info(f"Swapped: term slot '{academic_year}' -> academic_year, using extracted term '{term}'")
            else:
                if not academic_year and extracted_year:
                    academic_year = extracted_year
                if not term and extracted_term:
                    term = extracted_term
        
        logger.info(f"Final check - academic_year: '{academic_year}', term: '{term}'")
        logger.info("="*80)
        
        if not academic_year or not term:
            dispatcher.utter_message(
                text="Please specify year and term. Example: 'generate invoices for 2025 term 1'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            payload = {
                "year": int(academic_year),
                "term": int(term)
            }
            
            logger.info(f"Calling generate API with payload: {payload}")
            
            if class_name:
                # Normalize class name
                from actions.actions import normalize_class_name
                class_name = normalize_class_name(class_name)
                
                # Find class ID
                class_response = requests.get(
                    f"{FASTAPI_BASE_URL}/classes",
                    headers=headers,
                    params={"search": class_name}
                )
                
                if class_response.status_code == 200:
                    classes = class_response.json().get("classes", [])
                    if classes:
                        payload["class_id"] = classes[0]["id"]
                        logger.info(f"Added class_id to payload: {payload}")
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/invoices/generate/",
                json=payload,
                headers=headers
            )
            
            logger.info(f"API response status: {response.status_code}")
            
            if response.status_code == 200:
                invoices = response.json()
                count = len(invoices)
                class_text = f" for {class_name}" if class_name else ""
                
                msg = f"Invoices generated successfully!\n\n"
                msg += f"Generated {count} invoice{'s' if count != 1 else ''}{class_text}\n"
                msg += f"Year: {academic_year}, Term: {term}\n"
                msg += f"Status: DRAFT (ready for review)\n\n"
                
                if count > 0:
                    msg += "Next steps:\n"
                    msg += f"1. Review (optional): 'show invoice for [student name]'\n"
                    msg += f"2. Issue all invoices: 'issue invoices for {academic_year} term {term}'\n"
                    msg += f"   Or by class: 'issue invoices for [class] {academic_year} term {term}'"
                else:
                    msg += "Note: All students already have invoices for this term.\n"
                    msg += f"Check existing invoices: 'show invoice for [student name]'"
                
                dispatcher.utter_message(text=msg)
                
            elif response.status_code == 404:
                # No default structure found - provide helpful guidance
                error_data = response.json() if response.content else {}
                error_detail = error_data.get('detail', '')
                
                if 'default fee structure' in error_detail.lower():
                    # Check what published structures exist
                    structures_response = requests.get(
                        f"{FASTAPI_BASE_URL}/fees/structures/",
                        headers=headers,
                        params={"year": academic_year, "term": term}
                    )
                    
                    if structures_response.status_code == 200:
                        structures = structures_response.json()
                        published = [s for s in structures if s.get('is_published')]
                        
                        if published:
                            msg = f"No default fee structure set for Term {term} {academic_year}.\n\n"
                            msg += "Published structures available:\n"
                            for i, struct in enumerate(published, 1):
                                total = struct.get('total_amount', 0)
                                default_mark = " (DEFAULT)" if struct.get('is_default') else ""
                                msg += f"{i}. {struct['name']}{default_mark} - KES {float(total):,.2f}\n"
                            
                            msg += f"\nTo set a default:\n"
                            msg += f"'make {published[0]['name']} the default for term {term}'\n\n"
                            msg += "Then generate invoices again."
                            
                            dispatcher.utter_message(text=msg)
                        else:
                            msg = f"No published fee structures found for Term {term} {academic_year}.\n\n"
                            msg += "You need to:\n"
                            msg += f"1. Create: 'create fee structure for {academic_year} term {term}'\n"
                            msg += "2. Add fee items: 'add tuition fee of 25000 to [structure name]'\n"
                            msg += "3. Publish: 'publish [structure name]'\n"
                            msg += "4. Set as default (when prompted)"
                            dispatcher.utter_message(text=msg)
                    else:
                        dispatcher.utter_message(text=error_detail)
                else:
                    dispatcher.utter_message(text=error_detail)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to generate invoices')
                logger.error(f"API error response: {error_data}")
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error generating invoices: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while generating invoices.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None),
            SlotSet("class_name", None)
        ]

class ActionSetStructureAsDefault(Action):
    def name(self) -> Text:
        return "action_set_structure_as_default"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        structure_name = tracker.get_slot("structure_name")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        if not structure_name:
            dispatcher.utter_message(
                text="Please specify which fee structure to set as default. Example:\n"
                     "'make Term 3 2025 the default'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # Find the structure
            structures_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers
            )
            
            if structures_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
                return []
            
            structures = structures_response.json()
            target_structure = None
            structure_name_lower = structure_name.lower().strip()
            
            for struct in structures:
                if struct['name'].lower().strip() == structure_name_lower:
                    target_structure = struct
                    break
            
            if not target_structure:
                dispatcher.utter_message(text=f"Fee structure '{structure_name}' not found.")
                return []
            
            if not target_structure.get('is_published'):
                dispatcher.utter_message(
                    text=f"{target_structure['name']} must be published before setting as default.\n\n"
                         f"Publish it first: 'publish {target_structure['name']}'"
                )
                return []
            
            # Set as default
            response = requests.put(
                f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}",
                params={"is_default": True},
                headers=headers
            )
            
            if response.status_code == 200:
                msg = f"{target_structure['name']} is now the default structure for Term {target_structure['term']} {target_structure['year']}.\n\n"
                msg += "You can now generate invoices:\n"
                msg += f"• 'generate invoices for {target_structure['year']} term {target_structure['term']}'"
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Failed to set as default.")
        
        except Exception as e:
            logger.error(f"Error setting default: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("structure_name", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]

class ActionGetInvoice(Action):
    def name(self) -> Text:
        return "action_get_invoice"

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
                text="Please specify which student. Example:\n\n"
                     "```\nget invoice for Eric\n```"
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
            full_name = f"{student['first_name']} {student['last_name']}"
            
            # Get current term
            term_response = requests.get(
                f"{FASTAPI_BASE_URL}/academic/current-term",
                headers=headers
            )
            
            if term_response.status_code != 200:
                dispatcher.utter_message(
                    text="No active term found. Please activate a term first:\n\n"
                         "```\nactivate term 3\n```"
                )
                return []
            
            term_data = term_response.json()
            academic_year = term_data.get("academic_year")
            term = term_data.get("term")
            
            # Get student's invoices (returns a LIST)
            invoice_response = requests.get(
                f"{FASTAPI_BASE_URL}/invoices/student/{student['id']}",
                headers=headers,
                params={"year": academic_year, "term": term}
            )
            
            if invoice_response.status_code == 200:
                invoices = invoice_response.json()
                
                # Filter for current term invoices
                current_invoices = [
                    inv for inv in invoices
                    if inv.get('year') == academic_year and inv.get('term') == term
                ]
                
                if current_invoices:
                    # Get the first (most recent) invoice
                    invoice = current_invoices[0]
                    
                    # Display invoice
                    msg = f"**Invoice for {full_name} (#{student['admission_no']})**\n\n"
                    msg += f"**Term:** {term_data['title']}\n"
                    msg += f"**Status:** {invoice.get('status', 'N/A')}\n"
                    msg += f"**Total:** KES {float(invoice.get('total', 0)):,.2f}\n"
                    msg += f"**Paid:** KES {float(invoice.get('amount_paid', 0)):,.2f}\n"
                    msg += f"**Balance:** KES {float(invoice.get('balance', 0)):,.2f}\n"
                    
                    dispatcher.utter_message(text=msg)
                else:
                    # No invoice for current term - guide user
                    self._guide_no_invoice(dispatcher, full_name, academic_year, term, headers)
            else:
                # API error
                self._guide_no_invoice(dispatcher, full_name, academic_year, term, headers)
        
        except Exception as e:
            logger.error(f"Error getting invoice: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while retrieving the invoice.")
        
        return [
            SlotSet("student_name", None),
            SlotSet("admission_no", None)
        ]
    
    def _guide_no_invoice(self, dispatcher, student_name, academic_year, term, headers):
        """Helper method to guide user when no invoice found"""
        # Check if fee structure exists
        fee_structure_response = requests.get(
            f"{FASTAPI_BASE_URL}/fees/structures",
            headers=headers,
            params={"year": academic_year, "term": term}
        )
        
        if fee_structure_response.status_code == 200:
            structures = fee_structure_response.json()
            
            if not structures:
                # No fee structure - guide user
                msg = f"No invoice found for {student_name} because there's no fee structure for Term {term} {academic_year}.\n\n"
                msg += f"**Next steps:**\n\n"
                msg += f"1. Create a fee structure:\n"
                msg += f"```\ncreate fee structure for {academic_year} term {term}\n```\n\n"
                msg += f"2. Add fee items:\n"
                msg += f"```\nadd tuition 25000 to term {term} {academic_year}\n```\n\n"
                msg += f"3. Publish the structure:\n"
                msg += f"```\npublish term {term}\n```\n\n"
                msg += f"4. Generate invoices:\n"
                msg += f"```\ngenerate invoices for {academic_year} term {term}\n```"
                
                dispatcher.utter_message(text=msg)
            else:
                # Fee structure exists but no invoice - offer to generate
                msg = f"No invoice found for {student_name}.\n\n"
                msg += f"A fee structure exists for Term {term} {academic_year}. Generate invoices:\n\n"
                msg += f"```\ngenerate invoices for {academic_year} term {term}\n```"
                
                dispatcher.utter_message(text=msg)
        else:
            dispatcher.utter_message(text=f"Could not check fee structures.")

class ActionAddFeeItem(Action):
    def name(self) -> Text:
        return "action_add_fee_item"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        fee_type = tracker.get_slot("fee_type")
        amount = tracker.get_slot("amount")
        structure_name = tracker.get_slot("structure_name")
        level = tracker.get_slot("level")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        # Extract fee type from message if not in slot
        if not fee_type:
            message_text = tracker.latest_message.get("text", "").lower()
            fee_types = ["tuition", "transport", "exam", "boarding", "lunch", "lab", 
                        "materials", "activity", "library", "sports", "uniform"]
            
            for ft in fee_types:
                if ft in message_text:
                    fee_type = ft
                    break
        
        if not fee_type:
            dispatcher.utter_message(
                text="Please specify the fee type. Examples:\n\n"
                     "```\nadd tuition fee of 25,000 to Term 3 2025\n```\n\n"
                     "```\nadd transport fee of 5,000 to Standard Package\n```"
            )
            return []
        
        if not amount:
            dispatcher.utter_message(
                text=f"Please specify the amount for {fee_type} fee. Example:\n\n"
                     f"```\nadd {fee_type} fee of 25,000 to [structure name]\n```"
            )
            return []
        
        # If no structure_name but we have term/year, construct it
        if not structure_name and term and academic_year:
            structure_name = f"Term {term} {academic_year}"
        
        # NEW: Check conversation context for recently used structure
        if not structure_name:
            events = tracker.events
            for event in reversed(events[-15:]):  # Check last 15 events
                if event.get("event") == "bot":
                    text = event.get("text", "")
                    # Look for patterns like "Structure: Term 3 2025" or "to Term 3 2025"
                    import re
                    patterns = [
                        r'Structure:\s*([^\\n]+)',
                        r'to\s+(Term\s+\d+\s+\d{4})',
                        r'for\s+(Term\s+\d+\s+\d{4})',
                        r'show fee structure\s+([^\\n\']+)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            structure_name = match.group(1).strip()
                            logger.info(f"Inferred structure from context: {structure_name}")
                            break
                if structure_name:
                    break
        
        if not structure_name:
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
                    current_term_data = current_response.json()
                    structures_response = requests.get(
                        f"{FASTAPI_BASE_URL}/fees/structures/",
                        headers=headers,
                        params={
                            "year": current_term_data['academic_year'],
                            "term": current_term_data['term']
                        }
                    )
                    
                    if structures_response.status_code == 200:
                        structures = structures_response.json()
                        if structures:
                            structure_names = [s['name'] for s in structures[:3]]
                            msg = f"Please specify which fee structure to add this to.\n\n"
                            msg += f"**Available structures for current term:**\n\n"
                            for name in structure_names:
                                msg += f"• {name}\n"
                            msg += f"\n**Example:**\n\n"
                            msg += f"```\nadd {fee_type} fee of {amount} to {structure_names[0]}\n```"
                            dispatcher.utter_message(text=msg)
                            return []
                    
                    suggested_name = f"Term {current_term_data['term']} {current_term_data['academic_year']}"
                    dispatcher.utter_message(
                        text=f"No fee structures found for current term ({suggested_name}).\n\n"
                             f"Create one first:\n\n"
                             f"```\ncreate fee structure for {current_term_data['academic_year']} term {current_term_data['term']}\n```"
                    )
                    return []
                    
            except Exception as e:
                logger.error(f"Error fetching current term: {e}", exc_info=True)
            
            dispatcher.utter_message(
                text=f"Please specify which fee structure to add this to. Example:\n\n"
                     f"```\nadd {fee_type} fee of {amount} to Term 3 2025\n```\n\n"
                     f"Or view available structures:\n\n"
                     f"```\nshow fee structures\n```"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # Clean and convert amount - handle "bob" slang
            amount_clean = amount.replace(",", "").replace("bob", "").replace("kes", "").strip()
            try:
                amount_value = float(amount_clean)
            except ValueError:
                dispatcher.utter_message(
                    text=f"Invalid amount: '{amount}'. Use numbers only (e.g., 25000 or 25,000)."
                )
                return []
            
            # Get all fee structures
            structures_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers
            )
            
            if structures_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
                return []
            
            structures = structures_response.json()
            
            if not structures:
                dispatcher.utter_message(
                    text="No fee structures found. Create one first:\n\n"
                         "```\ncreate fee structure for 2025 term 1\n```"
                )
                return []
            
            # SMART MATCHING
            target_structure = None
            structure_name_lower = structure_name.lower().strip()
            
            for struct in structures:
                if struct['name'].lower().strip() == structure_name_lower:
                    target_structure = struct
                    break
            
            if not target_structure:
                year_match = re.search(r'\b(20\d{2})\b', structure_name)
                term_match = re.search(r'\bterm\s*(\d)\b', structure_name_lower)
                
                if year_match and term_match:
                    year = year_match.group(1)
                    term_value = term_match.group(1)
                    
                    for struct in structures:
                        if str(struct['year']) == year and str(struct['term']) == term_value:
                            if struct['level'] == 'ALL':
                                target_structure = struct
                                break
            
            if not target_structure:
                for struct in structures:
                    struct_name_lower = struct['name'].lower().strip()
                    if (structure_name_lower in struct_name_lower or 
                        struct_name_lower in structure_name_lower):
                        target_structure = struct
                        break
            
            if not target_structure:
                msg = f"Fee structure '{structure_name}' not found.\n\n"
                msg += "**Available structures:**\n\n"
                
                for i, struct in enumerate(structures[:5], 1):
                    draft_indicator = "○" if not struct['is_published'] else "✓"
                    msg += f"{draft_indicator} {struct['name']} (Year: {struct['year']}, Term: {struct['term']})\n"
                
                if len(structures) > 5:
                    msg += f"\n... and {len(structures) - 5} more\n"
                
                msg += f"\nTry using the exact name from above, or:\n\n"
                msg += f"```\nshow fee structures\n```\n\n"
                msg += f"```\nadd {fee_type} fee of {amount} to [exact structure name]\n```"
                
                dispatcher.utter_message(text=msg)
                return []
            
            if target_structure['is_published']:
                dispatcher.utter_message(
                    text=f"Cannot modify '{target_structure['name']}' - it's already published.\n\n"
                         f"Published structures are locked to prevent changes after invoicing."
                )
                return []
            
            # Get structure details with items to check for existing fee
            structure_detail_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}",
                headers=headers
            )
            
            is_update = False
            existing_item_id = None
            
            if structure_detail_response.status_code == 200:
                structure_detail = structure_detail_response.json()
                existing_items = structure_detail.get('items', [])
                
                for item in existing_items:
                    if item['item_name'].lower() == fee_type.title().lower():
                        is_update = True
                        existing_item_id = item['id']
                        break
            
            # Prepare fee item payload
            fee_item_payload = {
                "item_name": fee_type.title(),
                "amount": amount_value,
                "description": f"{fee_type.title()} fee"
            }

            if level:
                fee_item_payload["level"] = level
                fee_item_payload["description"] = f"{fee_type.title()} fee for {level}"
            
            # UPDATE or CREATE
            if is_update and existing_item_id:
                response = requests.put(
                    f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}/items/{existing_item_id}",
                    json=fee_item_payload,
                    headers=headers
                )
            else:
                response = requests.post(
                    f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}/items/",
                    json=fee_item_payload,
                    headers=headers
                )
            
            if response.status_code in [200, 201]:
                item_data = response.json()
                
                action_word = "updated" if is_update else "added"
                msg = f"**{fee_type.title()} fee {action_word} successfully!**\n\n"
                msg += f"**Structure:** {target_structure['name']}\n"
                msg += f"**Amount:** KES {amount_value:,.2f}\n"
                
                if level:
                    msg += f"**Applies to:** {level} only\n\n"
                else:
                    msg += f"**Applies to:** ALL students\n\n"
                
                msg += f"---\n\n"
                msg += f"**Next steps:**\n\n"
                msg += f"• Add more items:\n```\nadd [fee type] of [amount] to {target_structure['name']}\n```\n\n"
                msg += f"• View structure:\n```\nshow fee structure {target_structure['name']}\n```\n\n"
                msg += f"• Publish when ready:\n```\npublish {target_structure['name']}\n```"
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', f'Failed to add fee item')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error adding/updating fee item: {str(e)}", exc_info=True)
            dispatcher.utter_message(text=f"An error occurred: {str(e)}")
        
        return [
            SlotSet("fee_type", None),
            SlotSet("amount", None),
            SlotSet("structure_name", None),
            SlotSet("level", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]
    
class ActionViewFeeStructureDetails(Action):
    def name(self) -> Text:
        return "action_view_fee_structure_details"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        structure_name = tracker.get_slot("structure_name")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        # Construct structure name from term/year if not provided
        if not structure_name and term and academic_year:
            structure_name = f"Term {term} {academic_year}"
        
        # If still no structure name, try to infer from context
        if not structure_name:
            events = tracker.events
            for event in reversed(events[-10:]):
                if event.get("event") == "user":
                    text = event.get("text", "").lower()
                    if "term 3 2025" in text:
                        structure_name = "Term 3 2025"
                        break
                    elif "term 1 2025" in text:
                        structure_name = "Term 1 2025"
                        break
                    elif "term 2 2024" in text:
                        structure_name = "Term 2 2024"
                        break
        
        if not structure_name:
            dispatcher.utter_message(
                text="Please specify which fee structure to view. Example:\n"
                     "'show fee items for Term 3 2025'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Get all structures to find the right one
            structures_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers
            )
            
            if structures_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
                return []
            
            structures = structures_response.json()
            
            # IMPROVED MATCHING LOGIC
            target_structure = None
            structure_name_lower = structure_name.lower().strip()
            
            # Strategy 1: Exact match
            for struct in structures:
                if struct['name'].lower().strip() == structure_name_lower:
                    target_structure = struct
                    break
            
            # Strategy 2: Fuzzy match with year/term
            if not target_structure:
                year_match = re.search(r'\b(20\d{2})\b', structure_name)
                term_match = re.search(r'\bterm\s*(\d)\b', structure_name_lower) or re.search(r'\b(\d)\b', structure_name_lower)
                
                if year_match and term_match:
                    year = year_match.group(1)
                    term_value = term_match.group(1)
                    
                    # Find ALL matching structures by year/term
                    matching_structures = [
                        s for s in structures 
                        if str(s['year']) == year and str(s['term']) == term_value
                    ]
                    
                    if matching_structures:
                        # Prefer: 1) structures with items, 2) level='ALL', 3) first one
                        structures_with_items = [s for s in matching_structures if s.get('item_count', 0) > 0]
                        
                        if structures_with_items:
                            target_structure = structures_with_items[0]
                        else:
                            all_level = [s for s in matching_structures if s['level'] == 'ALL']
                            target_structure = all_level[0] if all_level else matching_structures[0]
            
            # Strategy 3: Partial match fallback
            if not target_structure:
                for struct in structures:
                    struct_name_lower = struct['name'].lower().strip()
                    if structure_name_lower in struct_name_lower or struct_name_lower in structure_name_lower:
                        target_structure = struct
                        break
            
            if not target_structure:
                msg = f"Fee structure '{structure_name}' not found.\n\n"
                msg += "Available structures:\n"
                for struct in structures[:5]:
                    item_count = struct.get('item_count', 0)
                    msg += f"• {struct['name']} ({item_count} items)\n"
                msg += "\nTry: 'show fee items for [exact structure name]'"
                dispatcher.utter_message(text=msg)
                return []
            
            # Get detailed structure with items
            detail_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}",
                headers=headers
            )
            
            if detail_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve structure details.")
                return []
            
            structure_detail = detail_response.json()
            items = structure_detail.get('items', [])
            
            if not items:
                msg = f"{structure_detail['name']}\n"
                msg += f"Level: {structure_detail['level']}\n"
                msg += f"Year: {structure_detail['year']}, Term: {structure_detail['term']}\n\n"
                msg += "No fee items yet.\n\n"
                msg += f"Add items: 'add tuition fee of 25,000 to {structure_detail['name']}'"
                dispatcher.utter_message(text=msg)
                return []
            
            # Build detailed breakdown
            msg = f"Fee Breakdown - {structure_detail['name']}\n"
            msg += f"Level: {structure_detail['level']}\n"
            msg += f"Year: {structure_detail['year']}, Term: {structure_detail['term']}\n\n"
            
            total = 0.0
            for i, item in enumerate(items, 1):
                try:
                    amount = float(item['amount'])
                    total += amount
                    msg += f"{i}. {item['item_name']}\n"
                    msg += f"   Amount: KES {amount:,.2f}\n"
                    if item.get('description'):
                        msg += f"   {item['description']}\n"
                    msg += "\n"
                except (ValueError, TypeError):
                    msg += f"{i}. {item['item_name']}\n"
                    msg += f"   Amount: {item['amount']}\n\n"
            
            msg += f"Total: KES {total:,.2f}\n"
            msg += f"Status: {'Published' if structure_detail['is_published'] else 'Draft'}\n\n"
            
            if not structure_detail['is_published']:
                msg += "Next steps:\n"
                msg += f"• Update item: 'update tuition to 30,000 for {structure_detail['name']}'\n"
                msg += f"• Add more: 'add transport fee of 5,000 to {structure_detail['name']}'\n"
                msg += f"• Publish: 'publish {structure_detail['name']}'"
            
            dispatcher.utter_message(text=msg)
        
        except Exception as e:
            logger.error(f"Error viewing structure details: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while fetching details.")
        
        return [
            SlotSet("structure_name", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]
    
class ActionDeleteFeeItems(Action):
    def name(self) -> Text:
        return "action_delete_fee_items"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        structure_name = tracker.get_slot("structure_name")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        if not structure_name and term and academic_year:
            structure_name = f"Term {term} {academic_year}"
        
        if not structure_name:
            dispatcher.utter_message(
                text="Please specify which fee structure to clear. Example:\n"
                     "'clear fee items for Term 3 2025'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Find structure
            structures_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers
            )
            
            if structures_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
                return []
            
            structures = structures_response.json()
            target_structure = None
            structure_name_lower = structure_name.lower().strip()
            
            for struct in structures:
                if struct['name'].lower().strip() == structure_name_lower:
                    target_structure = struct
                    break
            
            if not target_structure:
                year_match = re.search(r'\b(20\d{2})\b', structure_name)
                term_match = re.search(r'\bterm\s*(\d)\b', structure_name_lower)
                
                if year_match and term_match:
                    year = year_match.group(1)
                    term_value = term_match.group(1)
                    
                    for struct in structures:
                        if str(struct['year']) == year and str(struct['term']) == term_value:
                            if struct['level'] == 'ALL':
                                target_structure = struct
                                break
            
            if not target_structure:
                dispatcher.utter_message(
                    text=f"Fee structure '{structure_name}' not found."
                )
                return []
            
            if target_structure['is_published']:
                dispatcher.utter_message(
                    text=f"Cannot delete items from '{target_structure['name']}' - it's already published."
                )
                return []
            
            # Delete all items
            response = requests.delete(
                f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}/items",
                headers=headers
            )
            
            if response.status_code == 204:
                msg = f"All fee items cleared from {target_structure['name']}.\n\n"
                msg += "You can now add fresh items:\n"
                msg += f"'add tuition fee of 50,000 to {target_structure['name']}'"
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Failed to delete fee items.")
        
        except Exception as e:
            logger.error(f"Error deleting fee items: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("structure_name", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]


class ActionDeleteSpecificFeeItem(Action):
    def name(self) -> Text:
        return "action_delete_specific_fee_item"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        fee_type = tracker.get_slot("fee_type")
        structure_name = tracker.get_slot("structure_name")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        if not fee_type:
            dispatcher.utter_message(
                text="Please specify which fee type to delete. Example:\n"
                     "'delete tuition fee from Term 3 2025'"
            )
            return []
        
        if not structure_name and term and academic_year:
            structure_name = f"Term {term} {academic_year}"
        
        if not structure_name:
            dispatcher.utter_message(
                text="Please specify the fee structure. Example:\n"
                     "'delete tuition fee from Term 3 2025'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Find structure
            structures_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers
            )
            
            if structures_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
                return []
            
            structures = structures_response.json()
            target_structure = None
            structure_name_lower = structure_name.lower().strip()
            
            for struct in structures:
                if struct['name'].lower().strip() == structure_name_lower:
                    target_structure = struct
                    break
            
            if not target_structure:
                dispatcher.utter_message(text=f"Fee structure '{structure_name}' not found.")
                return []
            
            if target_structure['is_published']:
                dispatcher.utter_message(
                    text=f"Cannot delete items from '{target_structure['name']}' - it's already published."
                )
                return []
            
            # Get structure details
            detail_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}",
                headers=headers
            )
            
            if detail_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve structure details.")
                return []
            
            structure_detail = detail_response.json()
            items = structure_detail.get('items', [])
            
            # Find matching fee items (there might be duplicates)
            matching_items = [item for item in items if item['item_name'].lower() == fee_type.title().lower()]
            
            if not matching_items:
                dispatcher.utter_message(
                    text=f"No {fee_type} fee found in {target_structure['name']}."
                )
                return []
            
            # Delete all matching items
            deleted_count = 0
            for item in matching_items:
                response = requests.delete(
                    f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}/items/{item['id']}",
                    headers=headers
                )
                if response.status_code == 204:
                    deleted_count += 1
            
            if deleted_count > 0:
                plural = "s" if deleted_count > 1 else ""
                msg = f"Deleted {deleted_count} {fee_type} fee item{plural} from {target_structure['name']}.\n\n"
                if deleted_count > 1:
                    msg += f"Note: Found and removed {deleted_count} duplicate entries.\n\n"
                msg += f"Add a fresh one: 'add {fee_type} fee of [amount] to {target_structure['name']}'"
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Failed to delete fee item.")
        
        except Exception as e:
            logger.error(f"Error deleting fee item: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("fee_type", None),
            SlotSet("structure_name", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]
    

class ActionPublishFeeStructure(Action):
    def name(self) -> Text:
        return "action_publish_fee_structure"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        structure_name = tracker.get_slot("structure_name")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        # Normalization
        if term:
            term = str(term).strip()
        
        if term and not academic_year:
            academic_year = "2025"
        
        if not structure_name and not (term and academic_year):
            dispatcher.utter_message(
                text="Please specify which fee structure to publish. Example:\n"
                     "'publish fee structure for Term 1 2025'\n"
                     "Or use the exact name: 'publish Standard Package'"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # Get all structures
            params = {}
            if academic_year:
                params["year"] = academic_year
            if term:
                params["term"] = term
            
            structures_response = requests.get(
                f"{FASTAPI_BASE_URL}/fees/structures/",
                headers=headers,
                params=params
            )
            
            if structures_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve fee structures.")
                return []
            
            structures = structures_response.json()
            
            if not structures:
                if term and academic_year:
                    dispatcher.utter_message(
                        text=f"No fee structures found for Term {term} {academic_year}.\n\n"
                             f"Create one first: 'create fee structure for {academic_year} term {term}'"
                    )
                else:
                    dispatcher.utter_message(text="No fee structures found.")
                return []
            
            # Find target structure using improved matching
            target_structure = None
            matching_structures = []
            
            # Strategy 1: Exact name match
            if structure_name:
                structure_name_lower = structure_name.lower().strip()
                for struct in structures:
                    if struct['name'].lower().strip() == structure_name_lower:
                        target_structure = struct
                        break
            
            # Strategy 2: If no exact match but we have term/year, find ALL matching structures
            if not target_structure and term and academic_year:
                matching_structures = [
                    s for s in structures 
                    if str(s['year']) == str(academic_year) and str(s['term']) == str(term)
                ]
                
                if len(matching_structures) > 1:
                    msg = f"Multiple fee structures found for Term {term} {academic_year}:\n\n"
                    for i, struct in enumerate(matching_structures, 1):
                        item_count = struct.get('item_count', 0)
                        total = struct.get('total_amount', 0)
                        status = "Published" if struct['is_published'] else "Draft"
                        
                        msg += f"{i}. {struct['name']}\n"
                        msg += f"   Level: {struct['level']}\n"
                        msg += f"   Items: {item_count} fee item{'s' if item_count != 1 else ''}\n"
                        msg += f"   Total: KES {float(total):,.2f}\n"
                        msg += f"   Status: {status}\n\n"
                    
                    msg += "Please specify exactly which one to publish:\n"
                    for struct in matching_structures:
                        msg += f"• 'publish {struct['name']}'\n"
                    
                    dispatcher.utter_message(text=msg)
                    return []
                
                elif len(matching_structures) == 1:
                    target_structure = matching_structures[0]
            
            if not target_structure:
                msg = "Fee structure not found.\n\n"
                msg += "Available structures:\n"
                for i, struct in enumerate(structures[:5], 1):
                    draft_indicator = "Draft" if not struct['is_published'] else "Published"
                    msg += f"{i}. {struct['name']} (Year: {struct['year']}, Term: {struct['term']}) - {draft_indicator}\n"
                
                if len(structures) > 5:
                    msg += f"... and {len(structures) - 5} more\n"
                
                msg += f"\nTry using the exact name, or: 'show fee structures'"
                
                dispatcher.utter_message(text=msg)
                return []
            
            # Check if already published
            if target_structure['is_published']:
                # IMPROVEMENT: Check if it's the default
                if target_structure.get('is_default'):
                    dispatcher.utter_message(
                        text=f"{target_structure['name']} is already published and set as the default structure.\n\n"
                             f"You can generate invoices:\n"
                             f"• 'generate invoices for {target_structure['year']} term {target_structure['term']}'"
                    )
                else:
                    # Published but NOT default - offer to make it default
                    msg = f"{target_structure['name']} is already published.\n\n"
                    msg += "Would you like to make it the default structure for invoice generation?\n\n"
                    msg += "Reply:\n"
                    msg += "• 'yes, make it default'\n"
                    msg += "• 'no'"
                    
                    dispatcher.utter_message(text=msg)
                    
                    # Store for follow-up
                    return [
                        SlotSet("pending_default_structure_id", target_structure['id']),
                        SlotSet("structure_name", target_structure['name']),
                        SlotSet("term", str(target_structure['term'])),
                        SlotSet("academic_year", str(target_structure['year']))
                    ]
                
                return []
            
            # Check if structure has items
            if target_structure.get('item_count', 0) == 0:
                dispatcher.utter_message(
                    text=f"Cannot publish {target_structure['name']} - it has no fee items.\n\n"
                         f"Add items first: 'add tuition fee of 50,000 to {target_structure['name']}'"
                )
                return []
            
            # Publish the structure
            response = requests.put(
                f"{FASTAPI_BASE_URL}/fees/structures/{target_structure['id']}",
                params={"is_published": True},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                try:
                    total = float(data.get('total_amount', 0))
                    msg = f"{target_structure['name']} published successfully!\n\n"
                    msg += f"Total Amount: KES {total:,.2f}\n"
                    msg += f"Level: {target_structure['level']}\n"
                    msg += f"Year: {target_structure['year']}, Term: {target_structure['term']}\n\n"
                    msg += "This structure is now locked and ready for invoicing.\n\n"
                    
                    # Check if there's already a default for this term/year
                    check_default_response = requests.get(
                        f"{FASTAPI_BASE_URL}/fees/structures/",
                        headers=headers,
                        params={"year": target_structure['year'], "term": target_structure['term']}
                    )
                    
                    has_default = False
                    current_default_name = None
                    if check_default_response.status_code == 200:
                        term_structures = check_default_response.json()
                        for s in term_structures:
                            if s.get('is_default') and s['id'] != target_structure['id']:
                                has_default = True
                                current_default_name = s['name']
                                break
                    
                    # Ask about default if level is ALL
                    if target_structure['level'] == 'ALL':
                        if has_default:
                            msg += f"Current default for this term: {current_default_name}\n\n"
                            msg += f"Would you like to make '{target_structure['name']}' the new default?\n"
                            msg += "(This will replace the current default for bulk invoice generation)\n\n"
                        else:
                            msg += "Would you like to make this the default structure for invoice generation?\n"
                            msg += "(No default is currently set for this term)\n\n"
                        
                        msg += "Reply:\n"
                        msg += "• 'yes, make it default'\n"
                        msg += "• 'no, I'll set it later'\n"
                        
                        dispatcher.utter_message(text=msg)
                        
                        # Store structure_id for follow-up
                        return [
                            SlotSet("pending_default_structure_id", target_structure['id']),
                            SlotSet("structure_name", target_structure['name']),
                            SlotSet("term", str(target_structure['term'])),
                            SlotSet("academic_year", str(target_structure['year']))
                        ]
                    else:
                        # Level-specific structure - don't offer default
                        msg += "Note: This is a level-specific structure and cannot be set as default.\n\n"
                        msg += "Next steps:\n"
                        msg += f"• View all structures: 'show fee structures'\n"
                        msg += f"• Generate invoices: 'generate invoices for {target_structure['level']} {target_structure['year']} term {target_structure['term']}'"
                        dispatcher.utter_message(text=msg)
                
                except (ValueError, TypeError):
                    msg = f"{target_structure['name']} published successfully!"
                    dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to publish fee structure')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error publishing fee structure: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("structure_name", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]
    

class ActionSetDefaultFeeStructure(Action):
    """Handles the follow-up after user affirms to set structure as default"""
    def name(self) -> Text:
        return "action_set_default_fee_structure"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        # Get the pending structure ID from slot
        structure_id = tracker.get_slot("pending_default_structure_id")
        structure_name = tracker.get_slot("structure_name")
        term = tracker.get_slot("term")
        academic_year = tracker.get_slot("academic_year")
        
        if not structure_id:
            dispatcher.utter_message(
                text="No pending structure to set as default. Please publish a structure first."
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-School-ID": school_id
            }
            
            # Set as default
            response = requests.put(
                f"{FASTAPI_BASE_URL}/fees/structures/{structure_id}",
                params={"is_default": True},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                msg = f"✓ {structure_name or 'Fee structure'} is now the default for Term {term} {academic_year}!\n\n"
                msg += "You can now generate invoices:\n"
                msg += f"• 'generate invoices for {academic_year} term {term}'"
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to set as default')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error setting default: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while setting the default structure.")
        
        # Clear all slots
        return [
            SlotSet("pending_default_structure_id", None),
            SlotSet("structure_name", None),
            SlotSet("term", None),
            SlotSet("academic_year", None)
        ]
    
class ActionIssueInvoices(Action):
    def name(self) -> Text:
        return "action_issue_invoices"

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
        class_name = tracker.get_slot("class_name")
        user_message = tracker.latest_message.get("text", "")
        
        # DEBUG LOGGING
        logger.info("="*80)
        logger.info(f"ISSUE INVOICES DEBUG")
        logger.info(f"User message: '{user_message}'")
        logger.info(f"Extracted slots (BEFORE fix):")
        logger.info(f"   academic_year: '{academic_year}'")
        logger.info(f"   term: '{term}'")
        logger.info(f"   class_name: '{class_name}'")
        
        # FIX SWAPPED ENTITIES
        if academic_year and term:
            academic_year, term = fix_swapped_year_term(academic_year, term, user_message)
            logger.info(f"After swap detection:")
            logger.info(f"   academic_year: '{academic_year}'")
            logger.info(f"   term: '{term}'")
        
        # ADDITIONAL FIX: Parse from user message if one is missing
        if not academic_year or not term:
            logger.info("One or both entities missing, attempting to parse from message...")
            
            import re
            year_match = re.search(r'\b(20\d{2})\b', user_message)
            term_match = re.search(r'(?:term\s+)?(\d)(?!\d)', user_message, re.IGNORECASE)
            
            if year_match:
                extracted_year = year_match.group(1)
                logger.info(f"Found year in message: {extracted_year}")
            else:
                extracted_year = None
            
            if term_match:
                extracted_term = term_match.group(1)
                logger.info(f"Found term in message: {extracted_term}")
            else:
                extracted_term = None
            
            # Smart assignment: if term slot has 4 digits, it's actually the year
            if term and len(str(term)) == 4 and str(term).isdigit():
                academic_year = term
                term = extracted_term
                logger.info(f"Swapped: term slot '{academic_year}' -> academic_year, using extracted term '{term}'")
            else:
                if not academic_year and extracted_year:
                    academic_year = extracted_year
                if not term and extracted_term:
                    term = extracted_term
        
        # NEW: If still missing, try to get current term
        if not academic_year or not term:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                current_term_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-term",
                    headers=headers
                )
                
                if current_term_response.status_code == 200:
                    current_term_data = current_term_response.json()
                    if not academic_year:
                        academic_year = str(current_term_data['academic_year'])
                    if not term:
                        term = str(current_term_data['term'])
                    logger.info(f"Using current term: year={academic_year}, term={term}")
            except Exception as e:
                logger.error(f"Error getting current term: {e}")
        
        logger.info(f"Final check - academic_year: '{academic_year}', term: '{term}'")
        logger.info("="*80)
        
        if not academic_year or not term:
            dispatcher.utter_message(
                text="**Please specify year and term.**\n\n**Example:**\n\n```\nissue invoices for 2025 term 3\n```"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            params = {
                "year": int(academic_year),
                "term": int(term)
            }
            
            logger.info(f"Calling bulk-issue API with params: {params}")
            
            if class_name:
                from actions.actions import normalize_class_name
                class_name = normalize_class_name(class_name)
                
                class_response = requests.get(
                    f"{FASTAPI_BASE_URL}/classes",
                    headers=headers,
                    params={"search": class_name}
                )
                
                if class_response.status_code == 200:
                    classes = class_response.json().get("classes", [])
                    if classes:
                        params["class_id"] = classes[0]["id"]
                        logger.info(f"Added class_id to params: {params}")
            
            response = requests.put(
                f"{FASTAPI_BASE_URL}/invoices/bulk-issue/",
                headers=headers,
                params=params
            )
            
            logger.info(f"API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                count = data.get("issued_count", 0)
                class_text = f" for {class_name}" if class_name else ""
                
                msg = f"**Issued {count} invoice{'s' if count != 1 else ''}{class_text}!**\n\n"
                msg += f"**Year:** {academic_year}, **Term:** {term}\n"
                msg += f"**Status:** ISSUED\n\n"
                msg += "Parents will receive notifications about the invoices."
                
                dispatcher.utter_message(text=msg)
            elif response.status_code == 404:
                dispatcher.utter_message(
                    text=f"No DRAFT invoices found for Term {term} {academic_year}.\n\n"
                         f"Generate them first:\n\n```\ngenerate invoices for {academic_year} term {term}\n```"
                )
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to issue invoices')
                logger.error(f"API error response: {error_data}")
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error issuing invoices: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None),
            SlotSet("class_name", None)
        ]
    
class ActionListInvoices(Action):
    def name(self) -> Text:
        return "action_list_invoices"

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
        
        # Get current term if not specified
        if not academic_year or not term:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                current_response = requests.get(
                    f"{FASTAPI_BASE_URL}/terms/current",
                    headers=headers
                )
                
                if current_response.status_code == 200:
                    current_term = current_response.json()
                    if not academic_year:
                        academic_year = str(current_term['year'])
                    if not term:
                        term = str(current_term['term'])
            except Exception as e:
                logger.error(f"Error getting current term: {e}")
                dispatcher.utter_message(
                    text="Please specify year and term. Example: 'show invoices for 2025 term 3'"
                )
                return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            params = {
                "year": int(academic_year),
                "term": int(term)
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/invoices/",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                invoices = response.json()
                
                if not invoices:
                    dispatcher.utter_message(
                        text=f"No invoices found for Term {term} {academic_year}."
                    )
                    return []
                
                # Group by status
                draft_count = sum(1 for inv in invoices if inv['status'] == 'DRAFT')
                issued_count = sum(1 for inv in invoices if inv['status'] == 'ISSUED')
                partial_count = sum(1 for inv in invoices if inv['status'] == 'PARTIAL')
                paid_count = sum(1 for inv in invoices if inv['status'] == 'PAID')
                cancelled_count = sum(1 for inv in invoices if inv['status'] == 'CANCELLED')
                
                total_billed = sum(float(inv['total']) for inv in invoices)
                total_paid = sum(float(inv['amount_paid']) for inv in invoices)
                total_outstanding = sum(float(inv['balance']) for inv in invoices)
                
                msg = f"Invoices for Term {term} {academic_year}:\n\n"
                msg += f"Total Invoices: {len(invoices)}\n"
                msg += f"Status Breakdown:\n"
                if draft_count > 0:
                    msg += f"  ○ Draft: {draft_count}\n"
                if issued_count > 0:
                    msg += f"  ● Issued: {issued_count}\n"
                if partial_count > 0:
                    msg += f"  ◐ Partially Paid: {partial_count}\n"
                if paid_count > 0:
                    msg += f"  ✓ Fully Paid: {paid_count}\n"
                if cancelled_count > 0:
                    msg += f"  ✗ Cancelled: {cancelled_count}\n"
                
                msg += f"\nFinancial Summary:\n"
                msg += f"Total Billed: KES {total_billed:,.2f}\n"
                msg += f"Total Paid: KES {total_paid:,.2f}\n"
                msg += f"Outstanding: KES {total_outstanding:,.2f}\n\n"
                
                if draft_count > 0:
                    msg += f"Next: Issue {draft_count} draft invoice{'s' if draft_count != 1 else ''}\n"
                    msg += f"• 'issue invoices for {academic_year} term {term}'"
                
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Could not retrieve invoices.")
        
        except Exception as e:
            logger.error(f"Error listing invoices: {e}")
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None)
        ]


class ActionListInvoicesByClass(Action):
    def name(self) -> Text:
        return "action_list_invoices_by_class"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        class_name = tracker.get_slot("class_name")
        academic_year = tracker.get_slot("academic_year")
        term = tracker.get_slot("term")
        
        if not class_name:
            dispatcher.utter_message(
                text="Please specify a class. Example: 'show invoices for Grade 4 2025 term 3'"
            )
            return []
        
        # Get current term if not specified
        if not academic_year or not term:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                current_response = requests.get(
                    f"{FASTAPI_BASE_URL}/terms/current",
                    headers=headers
                )
                
                if current_response.status_code == 200:
                    current_term = current_response.json()
                    if not academic_year:
                        academic_year = str(current_term['year'])
                    if not term:
                        term = str(current_term['term'])
            except Exception as e:
                logger.error(f"Error getting current term: {e}")
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Normalize and find class
            from actions.actions import normalize_class_name
            class_name = normalize_class_name(class_name)
            
            class_response = requests.get(
                f"{FASTAPI_BASE_URL}/classes",
                headers=headers,
                params={"search": class_name}
            )
            
            if class_response.status_code != 200:
                dispatcher.utter_message(text=f"Class '{class_name}' not found.")
                return []
            
            classes = class_response.json().get("classes", [])
            if not classes:
                dispatcher.utter_message(text=f"Class '{class_name}' not found.")
                return []
            
            class_id = classes[0]["id"]
            
            params = {
                "year": int(academic_year),
                "term": int(term),
                "class_id": class_id
            }
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/invoices/",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                invoices = response.json()
                
                if not invoices:
                    dispatcher.utter_message(
                        text=f"No invoices found for {class_name} Term {term} {academic_year}."
                    )
                    return []
                
                paid_count = sum(1 for inv in invoices if inv['status'] == 'PAID')
                unpaid_count = len(invoices) - paid_count
                total_outstanding = sum(float(inv['balance']) for inv in invoices)
                
                msg = f"Invoices for {class_name} - Term {term} {academic_year}:\n\n"
                msg += f"Total Students: {len(invoices)}\n"
                msg += f"Paid: {paid_count}\n"
                msg += f"Unpaid/Partial: {unpaid_count}\n"
                msg += f"Outstanding Balance: KES {total_outstanding:,.2f}\n\n"
                
                msg += "View individual: 'show invoice for [student name]'"
                
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Could not retrieve invoices.")
        
        except Exception as e:
            logger.error(f"Error listing class invoices: {e}")
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("class_name", None),
            SlotSet("academic_year", None),
            SlotSet("term", None)
        ]


class ActionListUnpaidInvoices(Action):
    def name(self) -> Text:
        return "action_list_unpaid_invoices"

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
        class_name = tracker.get_slot("class_name")
        user_message = tracker.latest_message.get("text", "")
        
        # DEBUG LOGGING
        logger.info("="*80)
        logger.info(f"UNPAID INVOICES DEBUG")
        logger.info(f"User message: '{user_message}'")
        logger.info(f"Extracted slots (BEFORE fix):")
        logger.info(f"   academic_year: '{academic_year}'")
        logger.info(f"   term: '{term}'")
        logger.info(f"   class_name: '{class_name}'")
        
        # FIX SWAPPED ENTITIES
        if academic_year and term:
            academic_year, term = fix_swapped_year_term(academic_year, term, user_message)
            logger.info(f"After swap detection:")
            logger.info(f"   academic_year: '{academic_year}'")
            logger.info(f"   term: '{term}'")
        
        # ADDITIONAL FIX: Parse from user message if one is missing
        if not academic_year or not term:
            logger.info("One or both entities missing, attempting to parse from message...")
            
            import re
            year_match = re.search(r'\b(20\d{2})\b', user_message)
            term_match = re.search(r'(?:term\s+)?(\d)(?!\d)', user_message, re.IGNORECASE)
            
            if year_match:
                extracted_year = year_match.group(1)
                logger.info(f"Found year in message: {extracted_year}")
            else:
                extracted_year = None
            
            if term_match:
                extracted_term = term_match.group(1)
                logger.info(f"Found term in message: {extracted_term}")
            else:
                extracted_term = None
            
            # Smart assignment: if term slot has 4 digits, it's actually the year
            if term and len(str(term)) == 4 and str(term).isdigit():
                academic_year = term
                term = extracted_term
                logger.info(f"Swapped: term slot '{academic_year}' -> academic_year, using extracted term '{term}'")
            else:
                if not academic_year and extracted_year:
                    academic_year = extracted_year
                if not term and extracted_term:
                    term = extracted_term
        
        # Default to current term if not specified
        if not academic_year or not term:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                current_response = requests.get(
                    f"{FASTAPI_BASE_URL}/terms/current",
                    headers=headers
                )
                
                if current_response.status_code == 200:
                    current_term = current_response.json()
                    academic_year = str(current_term['year'])
                    term = str(current_term['term'])
                    logger.info(f"Using current term: year={academic_year}, term={term}")
            except Exception as e:
                logger.error(f"Error getting current term: {e}")
                dispatcher.utter_message(text="Could not determine current term.")
                return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            params = {
                "year": int(academic_year),
                "term": int(term)
            }
            
            logger.info(f"Calling API with params: {params}")
            
            if class_name:
                from actions.actions import normalize_class_name
                class_name = normalize_class_name(class_name)
                
                class_response = requests.get(
                    f"{FASTAPI_BASE_URL}/classes",
                    headers=headers,
                    params={"search": class_name}
                )
                
                if class_response.status_code == 200:
                    classes = class_response.json().get("classes", [])
                    if classes:
                        params["class_id"] = classes[0]["id"]
                        logger.info(f"Added class_id to params: {params}")
            
            response = requests.get(
                f"{FASTAPI_BASE_URL}/invoices/",
                headers=headers,
                params=params
            )
            
            logger.info(f"API response status: {response.status_code}")
            
            if response.status_code == 200:
                all_invoices = response.json()
                logger.info(f"Total invoices returned: {len(all_invoices)}")
                
                # LOG EACH INVOICE (first 3 for debugging)
                for i, inv in enumerate(all_invoices[:3], 1):
                    logger.info(f"Invoice {i}: status={inv['status']}, balance={inv['balance']}, total={inv['total']}")
                
                # Filter for unpaid: balance > 0, status in ISSUED/PARTIAL only (exclude DRAFT and CANCELLED)
                unpaid = [
                    inv for inv in all_invoices 
                    if float(inv['balance']) > 0 and inv['status'] in ['ISSUED', 'PARTIAL']
                ]
                
                logger.info(f"Unpaid invoices after filtering (ISSUED/PARTIAL only): {len(unpaid)}")
                logger.info("="*80)
                
                if not unpaid:
                    # Check if there are draft invoices that need to be issued
                    draft_with_balance = [
                        inv for inv in all_invoices
                        if float(inv['balance']) > 0 and inv['status'] == 'DRAFT'
                    ]
                    
                    if draft_with_balance:
                        msg = f"All issued invoices for Term {term} {academic_year} are paid!\n\n"
                        msg += f"However, there are {len(draft_with_balance)} draft invoices that haven't been issued yet.\n\n"
                        msg += f"To issue them: 'issue invoices for {academic_year} term {term}'"
                    else:
                        msg = f"All invoices for Term {term} {academic_year} are fully paid!"
                    
                    dispatcher.utter_message(text=msg)
                    return []
                
                # Group by status for better reporting (ISSUED and PARTIAL only)
                issued_unpaid = [inv for inv in unpaid if inv['status'] == 'ISSUED']
                partial_unpaid = [inv for inv in unpaid if inv['status'] == 'PARTIAL']
                
                total_outstanding = sum(float(inv['balance']) for inv in unpaid)
                
                class_text = f" for {class_name}" if class_name else ""
                msg = f"Unpaid Invoices{class_text} - Term {term} {academic_year}:\n\n"
                msg += f"Students with Balance: {len(unpaid)}\n"
                msg += f"Total Outstanding: KES {total_outstanding:,.2f}\n\n"
                
                # Show status breakdown (no draft in this list)
                msg += "Status Breakdown:\n"
                if issued_unpaid:
                    msg += f"  Issued (unpaid): {len(issued_unpaid)}\n"
                if partial_unpaid:
                    msg += f"  Partially Paid: {len(partial_unpaid)}\n"
                msg += "\n"
                
                # Show top 5 highest balances
                unpaid_sorted = sorted(unpaid, key=lambda x: float(x['balance']), reverse=True)
                msg += "Top Outstanding Balances:\n"
                
                for i, inv in enumerate(unpaid_sorted[:5], 1):
                    balance = float(inv['balance'])
                    status_icon = {
                        "ISSUED": "●",
                        "PARTIAL": "◐"
                    }.get(inv['status'], "•")
                    
                    # Try to get student name
                    student_id = inv['student_id']
                    student_display = f"#{student_id[:8]}..."
                    
                    try:
                        student_response = requests.get(
                            f"{FASTAPI_BASE_URL}/students/{student_id}",
                            headers=headers
                        )
                        if student_response.status_code == 200:
                            student = student_response.json()
                            student_display = f"{student['first_name']} {student['last_name']} (#{student['admission_no']})"
                    except:
                        pass
                    
                    msg += f"{i}. {status_icon} {student_display} - KES {balance:,.2f}\n"
                
                if len(unpaid) > 5:
                    msg += f"... and {len(unpaid) - 5} more\n"
                
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text="Could not retrieve invoices.")
        
        except Exception as e:
            logger.error(f"Error listing unpaid invoices: {e}")
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("academic_year", None),
            SlotSet("term", None),
            SlotSet("class_name", None)
        ]

class ActionListStudentsWithBalances(Action):
    """Alias for listing students with outstanding balances"""
    def name(self) -> Text:
        return "action_list_students_with_balances"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Delegate to the unpaid invoices action
        action = ActionListUnpaidInvoices()
        return action.run(dispatcher, tracker, domain)

class ActionCancelInvoice(Action):
    def name(self) -> Text:
        return "action_cancel_invoice"

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
                text="Please specify a student. Example: 'cancel invoice for Eric'"
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
            
            # Get student's current invoices
            invoices_response = requests.get(
                f"{FASTAPI_BASE_URL}/invoices/student/{student_id}",
                headers=headers
            )
            
            if invoices_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve invoices.")
                return []
            
            invoices = invoices_response.json()
            
            # Find latest DRAFT or ISSUED invoice
            cancellable = [
                inv for inv in invoices 
                if inv['status'] in ['DRAFT', 'ISSUED']
            ]
            
            if not cancellable:
                dispatcher.utter_message(
                    text=f"No cancellable invoices found for {full_name}.\n"
                         f"Only DRAFT or ISSUED invoices can be cancelled."
                )
                return []
            
            # Cancel the most recent one
            latest = cancellable[0]
            
            cancel_response = requests.put(
                f"{FASTAPI_BASE_URL}/invoices/{latest['id']}/cancel",
                headers=headers
            )
            
            if cancel_response.status_code == 200:
                data = cancel_response.json()
                msg = f"Invoice cancelled for {full_name} (#{student['admission_no']})\n\n"
                msg += f"Term {data['term']} {data['year']}\n"
                msg += f"Amount: KES {float(data['total']):,.2f}\n"
                msg += f"Status: CANCELLED"
                dispatcher.utter_message(text=msg)
            else:
                error_data = cancel_response.json() if cancel_response.content else {}
                error_msg = error_data.get('detail', 'Failed to cancel invoice')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error cancelling invoice: {e}")
            dispatcher.utter_message(text="An error occurred.")
        
        return [
            SlotSet("student_name", None),
            SlotSet("admission_no", None)
        ]
    
class ActionRecordPayment(Action):
    def name(self) -> Text:
        return "action_record_payment"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        amount = tracker.get_slot("amount")
        student_name = tracker.get_slot("student_name")
        admission_no = tracker.get_slot("admission_no")
        payment_method = tracker.get_slot("payment_method")
        txn_ref = tracker.get_slot("txn_ref")
        
        if not amount:
            dispatcher.utter_message(
                text="Please specify the payment amount. Example:\n\n"
                     "```\nrecord payment of 25,000 for Brian 7777 via MPESA ref TX123\n```"
            )
            return []
        
        if not student_name and not admission_no:
            dispatcher.utter_message(
                text="Please specify the student. Example:\n\n"
                     "```\nrecord payment of 25,000 for Brian 7777\n```"
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
            
            # Get student's current invoices
            invoices_response = requests.get(
                f"{FASTAPI_BASE_URL}/invoices/student/{student_id}",
                headers=headers
            )
            
            if invoices_response.status_code != 200:
                dispatcher.utter_message(text="Could not retrieve invoices.")
                return []
            
            invoices = invoices_response.json()
            
            # Find latest invoice that can receive payments
            payable = [
                inv for inv in invoices 
                if inv['status'] in ['ISSUED', 'PARTIAL', 'PAID']
            ]
            
            if not payable:
                dispatcher.utter_message(
                    text=f"No invoices found for {full_name} that can receive payments.\n"
                         f"Invoices must be ISSUED, PARTIAL, or PAID status."
                )
                return []
            
            # Use the most recent invoice
            latest = payable[0]
            
            # Clean and convert amount
            amount_clean = amount.replace(",", "").replace("bob", "").replace("kes", "").strip()
            try:
                amount_value = float(amount_clean)
            except ValueError:
                dispatcher.utter_message(
                    text=f"Invalid amount: '{amount}'. Use numbers only (e.g., 25000 or 25,000)."
                )
                return []
            
            # Calculate what will happen
            balance = float(latest.get('balance', 0))
            new_balance = max(0, balance - amount_value)
            overpayment = max(0, amount_value - balance)
            
            # Record payment
            payment_data = {
                "invoice_id": latest['id'],
                "amount": amount_value,
                "method": payment_method.upper() if payment_method else "CASH",
                "txn_ref": txn_ref
            }
            
            payment_response = requests.post(
                f"{FASTAPI_BASE_URL}/payments/",
                json=payment_data,
                headers=headers
            )
            
            if payment_response.status_code in [200, 201]:
                data = payment_response.json()
                
                msg = f"**Payment recorded successfully!**\n\n"
                msg += f"**Student:** {full_name} (#{student['admission_no']})\n"
                msg += f"**Amount Paid:** KES {amount_value:,.2f}\n"
                msg += f"**Method:** {payment_data['method']}\n"
                if txn_ref:
                    msg += f"**Reference:** {txn_ref}\n"
                msg += f"**Invoice:** Term {latest['term']} {latest['year']}\n"
                msg += f"**New Balance:** KES {new_balance:,.2f}\n"
                
                if overpayment > 0:
                    msg += f"**Overpayment:** +KES {overpayment:,.2f}\n"
                    msg += f"\n**Status:** FULLY PAID (Overpaid by KES {overpayment:,.2f})"
                elif new_balance == 0:
                    msg += f"\n**Status:** FULLY PAID"
                else:
                    msg += f"\n**Status:** Partially Paid"
                
                msg += f"\n\n---\n\n"
                msg += f"**Would you like to send a payment notification to the guardian?**\n\n"
                msg += f"Reply:\n"
                msg += f"• 'yes' - Send notification\n"
                msg += f"• 'no' - Skip notification"
                
                dispatcher.utter_message(text=msg)
                
                # Store payment details for follow-up
                return [
                    SlotSet("pending_payment_notification", "yes"),
                    SlotSet("payment_student_id", student_id),
                    SlotSet("payment_amount", str(amount_value)),
                    SlotSet("payment_invoice_id", latest['id']),
                    SlotSet("amount", None),
                    SlotSet("student_name", None),
                    SlotSet("admission_no", None),
                    SlotSet("payment_method", None),
                    SlotSet("txn_ref", None)
                ]
            else:
                error_data = payment_response.json() if payment_response.content else {}
                error_msg = error_data.get('detail', 'Failed to record payment')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error recording payment: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while recording the payment.")
        
        return [
            SlotSet("amount", None),
            SlotSet("student_name", None),
            SlotSet("admission_no", None),
            SlotSet("payment_method", None),
            SlotSet("txn_ref", None)
        ]
    
class ActionSendPaymentNotification(Action):
    def name(self) -> Text:
        return "action_send_payment_notification"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        student_id = tracker.get_slot("payment_student_id")
        amount = tracker.get_slot("payment_amount")
        invoice_id = tracker.get_slot("payment_invoice_id")
        
        if not student_id or not amount:
            dispatcher.utter_message(text="Payment details not found.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Send notification
            notification_data = {
                "student_id": student_id,
                "invoice_id": invoice_id,
                "amount": float(amount),
                "notification_type": "PAYMENT_RECEIVED"
            }
            
            response = requests.post(
                f"{FASTAPI_BASE_URL}/notifications/payment",
                json=notification_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                msg = f"**Payment notification sent successfully!**\n\n"
                msg += f"Guardian has been notified about the payment of KES {float(amount):,.2f}."
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to send notification')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while sending the notification.")
        
        return [
            SlotSet("pending_payment_notification", None),
            SlotSet("payment_student_id", None),
            SlotSet("payment_amount", None),
            SlotSet("payment_invoice_id", None)
        ]
    
class ActionResetSlots(Action):
    def name(self) -> Text:
        return "action_reset_slots"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        return [
            SlotSet("pending_payment_notification", None),
            SlotSet("payment_student_id", None),
            SlotSet("payment_amount", None),
            SlotSet("payment_invoice_id", None)
        ]
    

class ActionNotifyParentsWithBalances(Action):
    def name(self) -> Text:
        return "action_notify_parents_with_balances"

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
        
        # Get current term if not specified
        if not academic_year or not term:
            try:
                headers = {
                    "Authorization": f"Bearer {auth_token}",
                    "X-School-ID": school_id
                }
                
                # FIXED: Use correct endpoint
                current_response = requests.get(
                    f"{FASTAPI_BASE_URL}/academic/current-term",
                    headers=headers
                )
                
                if current_response.status_code == 200:
                    current_term = current_response.json()
                    academic_year = str(current_term['academic_year'])
                    term = str(current_term['term'])
                    logger.info(f"Using current term: year={academic_year}, term={term}")
                else:
                    logger.error(f"Failed to get current term: {current_response.status_code}")
                    dispatcher.utter_message(
                        text="Could not determine current term.\n\n"
                             "Please specify year and term:\n\n"
                             "```\nremind parents about fee balances for 2025 term 3\n```"
                    )
                    return []
                    
            except Exception as e:
                logger.error(f"Error getting current term: {e}", exc_info=True)
                dispatcher.utter_message(
                    text="Could not determine current term.\n\n"
                         "Please specify year and term:\n\n"
                         "```\nremind parents about fee balances for 2025 term 3\n```"
                )
                return []
        
        # Additional validation
        if not academic_year or not term:
            dispatcher.utter_message(
                text="Please specify year and term. Example:\n\n"
                     "```\nremind parents about fee balances for 2025 term 3\n```"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Call bulk notification endpoint
            response = requests.post(
                f"{FASTAPI_BASE_URL}/notifications/unpaid-balances",
                headers=headers,
                json={
                    "year": int(academic_year),
                    "term": int(term)
                }
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                count = data.get("notifications_sent", 0)
                failed = data.get("failed", 0)
                
                if count == 0:
                    msg = f"No guardians notified.\n\n"
                    msg += f"Either all invoices for Term {term} {academic_year} are paid,\n"
                    msg += f"or students with balances don't have guardians with email addresses."
                    dispatcher.utter_message(text=msg)
                    return []
                
                msg = f"**Fee reminder notifications sent successfully!**\n\n"
                msg += f"**Notifications sent:** {count}\n"
                
                if failed > 0:
                    msg += f"**Failed:** {failed}\n"
                
                msg += f"**Term:** {term} {academic_year}\n\n"
                msg += f"---\n\n"
                msg += f"**Email Preview:**\n\n"
                msg += f"```\n"
                msg += f"To: Guardians with Outstanding Balances ({count} recipient{'s' if count != 1 else ''})\n"
                msg += f"Subject: Fee Balance Reminder - [Student Name] (Term {term} {academic_year})\n\n"
                msg += f"Dear [Guardian Name],\n\n"
                msg += f"This is a reminder that there is an outstanding balance for your child [Student Name].\n\n"
                msg += f"Invoice Details:\n"
                msg += f"• Total Amount: KES [Invoice Total]\n"
                msg += f"• Amount Paid: KES [Amount Paid]\n"
                msg += f"• Balance Due: KES [Balance]\n"
                msg += f"• Due Date: [Due Date]\n\n"
                msg += f"Please make payment at your earliest convenience.\n\n"
                msg += f"Best regards,\n"
                msg += f"School Administration\n"
                msg += f"```\n\n"
                msg += f"Guardians have been notified about outstanding balances."
                
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
            SlotSet("term", None)
        ]


class ActionBroadcastMessageToAllParents(Action):
    def name(self) -> Text:
        return "action_broadcast_message_to_all_parents"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        metadata = tracker.latest_message.get("metadata", {})
        auth_token = metadata.get("auth_token")
        school_id = metadata.get("school_id")
        
        if not auth_token:
            dispatcher.utter_message(text="Authentication required.")
            return []
        
        message = tracker.get_slot("message")
        
        if not message:
            dispatcher.utter_message(
                text="Please specify the message. Example:\n\n"
                     "```\nsend a message to all parents to come for a meeting tomorrow\n```"
            )
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "X-School-ID": school_id
            }
            
            # Prepare notification data
            notification_data = {
                "message": message,
                "subject": "Important School Announcement"
            }
            
            # Send broadcast
            response = requests.post(
                f"{FASTAPI_BASE_URL}/notifications/broadcast",
                json=notification_data,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                sent_count = data.get("sent_count", 0)
                failed_count = data.get("failed_count", 0)
                total_guardians = data.get("total_guardians", 0)
                
                if sent_count == 0 and total_guardians == 0:
                    msg = "No guardians found in the system.\n\n"
                    msg += "Please ensure students have guardians added before broadcasting messages."
                    dispatcher.utter_message(text=msg)
                    return [SlotSet("message", None)]
                
                # Build success message with email preview
                msg = f"**Broadcast message sent successfully!**\n\n"
                msg += f"**Recipients:** {sent_count} guardian(s)\n"
                
                if failed_count > 0:
                    msg += f"**Failed:** {failed_count}\n"
                
                msg += f"\n---\n\n"
                msg += f"**Email Preview:**\n\n"
                msg += f"```\n"
                msg += f"To: All Guardians ({sent_count} recipients)\n"
                msg += f"Subject: Important School Announcement\n\n"
                msg += f"Dear Parent/Guardian,\n\n"
                msg += f"{message}\n\n"
                msg += f"Best regards,\n"
                msg += f"School Administration\n"
                msg += f"```\n\n"
                msg += f"All guardians have been notified."
                
                dispatcher.utter_message(text=msg)
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('detail', 'Failed to send broadcast message')
                dispatcher.utter_message(text=f"Error: {error_msg}")
        
        except Exception as e:
            logger.error(f"Error broadcasting message: {e}", exc_info=True)
            dispatcher.utter_message(text="An error occurred while broadcasting the message.")
        
        return [SlotSet("message", None)]