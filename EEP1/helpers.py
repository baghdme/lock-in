import os
import json
import uuid
from datetime import datetime
import logging

# ===============================
# Imports and Constants
# ===============================
# (Ensure that all import statements and constant definitions are below this header)

# Define storage paths
STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'latest_schedule.json')
FINAL_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'final_schedule.json')

# ===============================
# File I/O Operations
# ===============================

# Functions for saving and loading schedules

def save_schedule(schedule, path=STORAGE_PATH):
    """Save the schedule to storage."""
    try:
        # Ensure the schedule has all required IDs
        schedule = ensure_ids(schedule)
        # Create storage directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Save to file
        with open(path, 'w') as f:
            json.dump(schedule, f, indent=2)
        return schedule
    except Exception as e:
        raise Exception(f"Error saving schedule: {str(e)}")


def load_schedule(path=STORAGE_PATH):
    """Load the schedule from storage."""
    try:
        with open(path, 'r') as f:
            schedule = json.load(f)
        return schedule
    except FileNotFoundError:
        # Return empty schedule if file doesn't exist
        return {"meetings": [], "tasks": [], "course_codes": []}
    except Exception as e:
        raise Exception(f"Error loading schedule: {str(e)}")

# ===============================
# Time Related Functions
# ===============================

# Functions for time conversions and validations

def convert_to_24h(time_str: str) -> str:
    if not time_str or time_str in ['None', 'null']:
        return None
    time_str = time_str.strip().lower()
    if time_str == "noon":
        return "12:00"
    if time_str == "midnight":
        return "00:00"
    try:
        if "am" in time_str or "pm" in time_str:
            time_parts = time_str.replace("am", "").replace("pm", "").strip().split(":")
            hours = int(time_parts[0])
            minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
            if "pm" in time_str and hours != 12:
                hours += 12
            elif "am" in time_str and hours == 12:
                hours = 0
            return f"{hours:02d}:{minutes:02d}"
        if time_str.isdigit():
            hours = int(time_str)
            return f"{hours:02d}:00"
        if ":" in time_str:
            hours, minutes = map(int, time_str.split(":"))
            return f"{hours:02d}:{minutes:02d}"
        return time_str
    except Exception:
        return time_str


def validate_and_fix_times(data: dict) -> dict:
    for task in data.get("tasks", []):
        if task.get("time"):
            task["time"] = convert_to_24h(task["time"])
    for meeting in data.get("meetings", []):
        if meeting.get("time"):
            meeting["time"] = convert_to_24h(meeting["time"])
    return data

# ===============================
# Missing Information and Cleaning Functions
# ===============================

# Functions to check for missing information and clean schedule data

def check_missing_info(schedule: dict) -> list:
    logger = logging.getLogger(__name__)
    
    questions = []
    
    logger.info("Starting check_missing_info function")
    
    # Create mappings to track relationships and avoid redundant questions
    meeting_ids_with_missing_course = set()  # Track meeting IDs missing course codes
    meeting_descriptions = {}  # Map meeting IDs to descriptions
    related_tasks = {}  # Map meeting descriptions to their related task IDs
    
    # Dictionary to track meeting counts by description
    meeting_counts = {}
    for meeting in schedule.get("meetings", []):
        desc = meeting.get("description", "")
        meeting_counts[desc] = meeting_counts.get(desc, 0) + 1
    
    # First pass: collect all meetings and their properties
    for meeting in schedule.get("meetings", []):
        meeting_id = meeting.get("id")
        description = meeting.get("description")
        if meeting_id and description:
            meeting_descriptions[meeting_id] = description
        
        # Track meetings missing course codes
        if not meeting.get("course_code") and meeting.get("type") in ["exam", "presentation"]:
            if meeting_id:
                meeting_ids_with_missing_course.add(meeting_id)
                logger.info(f"Meeting {description} (id: {meeting_id}) is missing course_code")
    
    logger.info(f"Meetings missing course codes: {meeting_ids_with_missing_course}")
    
    # Second pass: identify related tasks
    for task in schedule.get("tasks", []):
        related_event = task.get("related_event")
        task_id = task.get("id")
        if related_event and task_id:
            if related_event not in related_tasks:
                related_tasks[related_event] = []
            related_tasks[related_event].append(task_id)
    
    logger.info(f"Related tasks mapping: {related_tasks}")
    
    # Function to generate a more specific description for ambiguous meetings
    def get_specific_description(meeting):
        desc = meeting.get("description", "")
        
        # Check if this description appears more than once
        if meeting_counts.get(desc, 0) > 1:
            # Include time in the description if available
            if meeting.get("time"):
                return f"{desc} at {meeting.get('time')}"
            # Include day if available
            elif meeting.get("day"):
                return f"{desc} on {meeting.get('day')}"
        
        return desc
    
    # Now generate questions for meetings
    for meeting in schedule.get("meetings", []):
        specific_desc = get_specific_description(meeting)
        
        if not meeting.get("time"):
            questions.append({
                "type": "time",
                "question": f"What time is the {specific_desc}?",
                "field": "time",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
        if not meeting.get("duration_minutes"):
            questions.append({
                "type": "duration",
                "question": f"How long is the {specific_desc}?",
                "field": "duration_minutes",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
        if not meeting.get("course_code") and meeting.get("type") in ["exam", "presentation"]:
            questions.append({
                "type": "course_code",
                "question": f"What is the course code for the {specific_desc}?",
                "field": "course_code",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
    
    # Check tasks - only ask for course_code when not related to a meeting we're already asking about
    for task in schedule.get("tasks", []):
        # DEBUG: Log task properties
        logger.info(f"Checking task: {task.get('description')}, course_code: {task.get('course_code')}, category: {task.get('category')}, missing_info: {task.get('missing_info')}")
        
        # Only process tasks that don't have a course code and are preparation tasks
        if not task.get("course_code") and task.get("category") == "preparation":
            logger.info(f"Task {task.get('description')} is a preparation task without course_code")
            related_event = task.get("related_event")
            logger.info(f"Related event: {related_event}")
            
            # Skip if this task is related to a meeting we're already asking about
            should_skip = False
            for meeting in schedule.get("meetings", []):
                # If the meeting description is contained in the related_event or vice versa
                meeting_id = meeting.get("id")
                meeting_desc = meeting.get("description")
                logger.info(f"Checking meeting: {meeting_desc}, id: {meeting_id}, in missing_course: {meeting_id in meeting_ids_with_missing_course}")
                
                # Use partial matching for related events
                if (related_event and meeting_desc and 
                   (meeting_desc in related_event or related_event in meeting_desc) and 
                   meeting_id in meeting_ids_with_missing_course):
                    should_skip = True
                    logger.info(f"Should skip question for task {task.get('description')} - related to meeting being queried")
                    break
            
            # Only add the question if we shouldn't skip it
            if not should_skip:
                logger.info(f"Adding course code question for task: {task.get('description')}")
                questions.append({
                    "type": "course_code",
                    "question": f"What is the course code for the {task.get('description')}?",
                    "field": "course_code",
                    "target": task.get("description"),
                    "target_type": "task",
                    "target_id": task.get("id")
                })
            else:
                logger.info(f"Skipping course code question for task: {task.get('description')}")
    
    logger.info(f"Final questions list: {questions}")
    return questions


def clean_missing_info_from_tasks(schedule: dict) -> dict:
    # Remove duration_minutes from missing_info for tasks
    schedule = json.loads(json.dumps(schedule))  # deep copy
    for task in schedule.get("tasks", []):
        if "missing_info" in task:
            if "duration_minutes" in task.get("missing_info", []):
                task["missing_info"].remove("duration_minutes")
            if not task["missing_info"]:
                del task["missing_info"]
    return schedule


def clean_schedule(schedule: dict) -> dict:
    # Remove missing_info fields from the schedule without changing any field values
    schedule = json.loads(json.dumps(schedule))  # deep copy
    for task in schedule.get("tasks", []):
        if "missing_info" in task:
            del task["missing_info"]
    for meeting in schedule.get("meetings", []):
        if "missing_info" in meeting:
            del meeting["missing_info"]
    return schedule

# ===============================
# Update Functions
# ===============================

# Functions for converting answer values and updating the schedule with new answers

def convert_answer_value(answer_type: str, value: str) -> any:
    if answer_type == "duration":
        return int(value)
    return value


def update_schedule_with_answers(schedule: dict, answers: list) -> dict:
    import copy
    import logging
    logger = logging.getLogger(__name__)
    
    schedule = copy.deepcopy(schedule)
    
    # First pass: update meetings and tasks directly based on their IDs
    for answer in answers:
        field = answer.get("field")
        value = answer.get("value")
        target = answer.get("target")
        target_id = answer.get("target_id")
        if not all([field, value]):
            continue
        
        value = convert_answer_value(answer.get("type", ""), value)
        
        found = False
        # Try to update by ID first (most accurate)
        if target_id:
            # Update meetings
            for meeting in schedule.get("meetings", []):
                if meeting.get("id") == target_id:
                    meeting[field] = value
                    logger.info(f"Updated meeting {meeting.get('description')} {field} to {value} by ID")
                    found = True
                    break
            
            # Update tasks
            if not found:
                for task in schedule.get("tasks", []):
                    if task.get("id") == target_id:
                        task[field] = value
                        logger.info(f"Updated task {task.get('description')} {field} to {value} by ID")
                        found = True
                        break
        
        # Fallback to description match if ID didn't work
        if not found and target:
            # Try exact match first
            for meeting in schedule.get("meetings", []):
                if meeting.get("description") == target:
                    meeting[field] = value
                    logger.info(f"Updated meeting {meeting.get('description')} {field} to {value} by description")
                    found = True
            
            for task in schedule.get("tasks", []):
                if task.get("description") == target:
                    task[field] = value
                    logger.info(f"Updated task {task.get('description')} {field} to {value} by description")
                    found = True
    
    # Second pass: handle propagation of course codes from meetings to related tasks
    # and ensure preparation tasks exist for each exam
    
    # Map meeting descriptions to their course codes
    meeting_course_codes = {}
    meeting_properties = {}  # Store all key properties by meeting description
    
    for meeting in schedule.get("meetings", []):
        desc = meeting.get("description")
        if desc:
            # Store important meeting properties
            meeting_properties[desc] = {
                "type": meeting.get("type"),
                "course_code": meeting.get("course_code"),
                "day": meeting.get("day"),
                "time": meeting.get("time"),
                "id": meeting.get("id")
            }
            
            # Track course codes
            if meeting.get("course_code"):
                meeting_course_codes[desc] = meeting.get("course_code")
    
    # Find all exam events
    exam_meetings = [m for m in schedule.get("meetings", []) 
                    if m.get("type") == "exam" and 
                    m.get("course_code") and 
                    m.get("duration_minutes")]
    
    # Get existing preparation tasks
    existing_prep_tasks = {t.get("related_event"): t for t in schedule.get("tasks", []) 
                          if t.get("category") == "preparation" and t.get("related_event")}
    
    # Ensure every exam has a preparation task
    for exam in exam_meetings:
        exam_desc = exam.get("description")
        
        # Skip if a preparation task already exists for this exam
        if exam_desc in existing_prep_tasks:
            # If it exists, ensure it has the course code
            prep_task = existing_prep_tasks[exam_desc]
            if exam.get("course_code") and not prep_task.get("course_code"):
                prep_task["course_code"] = exam.get("course_code")
                logger.info(f"Updated existing prep task for {exam_desc} with course code {exam.get('course_code')}")
                
            # Remove from missing_info if needed
            if "missing_info" in prep_task and "course_code" in prep_task.get("missing_info", []):
                prep_task["missing_info"].remove("course_code")
                if not prep_task["missing_info"]:
                    del prep_task["missing_info"]
        else:
            # Create a new preparation task for this exam
            prep_desc = f"Prepare for {exam_desc}"
            new_prep_task = {
                "id": str(uuid.uuid4()),
                "description": prep_desc,
                "day": None,
                "priority": "high",
                "time": None,
                "duration_minutes": 120,  # Default 2 hours
                "category": "preparation",
                "is_fixed_time": False,
                "location": None,
                "prerequisites": [],
                "course_code": exam.get("course_code"),
                "related_event": exam_desc
            }
            
            schedule["tasks"].append(new_prep_task)
            logger.info(f"Created new preparation task for {exam_desc}")
            
            # Also add to the exam's preparation_tasks array
            if "preparation_tasks" not in exam:
                exam["preparation_tasks"] = []
            if prep_desc not in exam["preparation_tasks"]:
                exam["preparation_tasks"].append(prep_desc)
    
    # Apply course codes to related tasks
    for task in schedule.get("tasks", []):
        related_event = task.get("related_event")
        if related_event and related_event in meeting_course_codes and not task.get("course_code"):
            task["course_code"] = meeting_course_codes[related_event]
            logger.info(f"Propagated course code {meeting_course_codes[related_event]} to task {task.get('description')}")
            
            # Remove from missing_info if needed
            if "missing_info" in task and "course_code" in task.get("missing_info", []):
                task["missing_info"].remove("course_code")
                if not task["missing_info"]:
                    del task["missing_info"]
    
    return schedule

# ===============================
# Utility Functions
# ===============================

# Miscellaneous helper functions

def ensure_ids(schedule):
    # Added check to handle case where schedule is a JSON string
    if isinstance(schedule, str):
        schedule = json.loads(schedule)

    # Existing logic to ensure every meeting/task has an ID
    for meeting in schedule.get('meetings', []):
        if 'id' not in meeting:
            meeting['id'] = str(uuid.uuid4())
    for task in schedule.get('tasks', []):
        if 'id' not in task:
            task['id'] = str(uuid.uuid4())
    return schedule 