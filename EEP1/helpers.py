import os
import json
import uuid
from datetime import datetime
import logging

# ===============================
# Imports and Constants
# ===============================
# (Ensure that all import statements and constant definitions are below this header)

# In-memory storage for schedules
_CURRENT_SCHEDULE = None
_FINAL_SCHEDULE = None

# ===============================
# Schedule Storage Operations
# ===============================

# Functions for saving and loading schedules

def save_schedule(schedule, is_final=False):
    """Save the schedule to in-memory storage."""
    global _CURRENT_SCHEDULE, _FINAL_SCHEDULE
    
    try:
        # Ensure the schedule has all required IDs
        schedule = ensure_ids(schedule)
        
        # Store in the appropriate in-memory variable
        if is_final:
            _FINAL_SCHEDULE = schedule
        else:
            _CURRENT_SCHEDULE = schedule
            
        return schedule
    except Exception as e:
        raise Exception(f"Error saving schedule: {str(e)}")


def load_schedule(is_final=False):
    """Load the schedule from in-memory storage."""
    global _CURRENT_SCHEDULE, _FINAL_SCHEDULE
    
    try:
        # Return the appropriate in-memory schedule
        if is_final:
            if _FINAL_SCHEDULE is None:
                return {"meetings": [], "tasks": [], "course_codes": []}
            return _FINAL_SCHEDULE
        else:
            if _CURRENT_SCHEDULE is None:
                return {"meetings": [], "tasks": [], "course_codes": []}
            return _CURRENT_SCHEDULE
    except Exception as e:
        # Return empty schedule if any error occurs
        return {"meetings": [], "tasks": [], "course_codes": []}

# Reset the in-memory schedules
def reset_schedules():
    """Reset all in-memory schedules."""
    global _CURRENT_SCHEDULE, _FINAL_SCHEDULE
    _CURRENT_SCHEDULE = None
    _FINAL_SCHEDULE = None
    return True

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
        # Handle explicit AM/PM
        if "am" in time_str or "pm" in time_str:
            time_parts = time_str.replace("am", "").replace("pm", "").strip().split(":")
            hours = int(time_parts[0])
            minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
            if "pm" in time_str and hours != 12:
                hours += 12
            elif "am" in time_str and hours == 12:
                hours = 0
            return f"{hours:02d}:{minutes:02d}"
        # Simple digit-only case
        if time_str.isdigit():
            hours = int(time_str)
            # Flag ambiguous times (1-12) that don't specify AM/PM
            if 1 <= hours <= 12:
                return "AMBIGUOUS:" + time_str
            # Assume 24-hour format for values > 12
            return f"{hours:02d}:00"
        # Handle HH:MM format without AM/PM
        if ":" in time_str:
            hours, minutes = map(int, time_str.split(":"))
            # Flag ambiguous times (1-12) that don't specify AM/PM
            if 1 <= hours <= 12:
                return "AMBIGUOUS:" + time_str
            # Assume 24-hour format for values > 12
            return f"{hours:02d}:{minutes:02d}"
        return time_str
    except Exception:
        return time_str

def is_time_ambiguous(time_str: str) -> bool:
    """Check if a time string is ambiguous (lacks AM/PM specification when needed)"""
    if not time_str:
        return False
    if isinstance(time_str, str) and time_str.startswith("AMBIGUOUS:"):
        return True
    return False

def get_clean_time(time_str: str) -> str:
    """Remove the AMBIGUOUS flag from a time string"""
    if isinstance(time_str, str) and time_str.startswith("AMBIGUOUS:"):
        return time_str[10:]
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
    
    # Create separate lists for different types of questions to allow prioritization
    day_questions = []
    time_questions = []
    ampm_questions = [] # New list for AM/PM clarification questions
    duration_questions = []
    course_code_questions = []
    
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
            if meeting.get("time") and not is_time_ambiguous(meeting.get("time")):
                return f"{desc} at {get_clean_time(meeting.get('time'))}"
            # Include day if available
            elif meeting.get("day"):
                return f"{desc} on {meeting.get('day')}"
        
        return desc
    
    # Now generate questions for meetings
    for meeting in schedule.get("meetings", []):
        specific_desc = get_specific_description(meeting)
        
        # Check for missing day - essential for scheduling
        if not meeting.get("day"):
            day_questions.append({
                "type": "day",
                "question": f"On which day of the week is the {specific_desc}?",
                "field": "day",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id"),
                "input_type": "dropdown",
                "options": [
                    {"value": "Monday", "text": "Monday"},
                    {"value": "Tuesday", "text": "Tuesday"},
                    {"value": "Wednesday", "text": "Wednesday"},
                    {"value": "Thursday", "text": "Thursday"},
                    {"value": "Friday", "text": "Friday"},
                    {"value": "Saturday", "text": "Saturday"},
                    {"value": "Sunday", "text": "Sunday"}
                ]
            })
        
        # Check for ambiguous time (missing AM/PM)
        if meeting.get("time") and is_time_ambiguous(meeting.get("time")):
            clean_time = get_clean_time(meeting.get("time"))
            ampm_questions.append({
                "type": "ampm",
                "question": f"Is {clean_time} for the {specific_desc} AM or PM?",
                "field": "time_ampm",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id"),
                "original_time": clean_time,
                "input_type": "dropdown",
                "options": [
                    {"value": "am", "text": "AM"},
                    {"value": "pm", "text": "PM"}
                ]
            })
        # Check for missing time
        elif not meeting.get("time"):
            time_questions.append({
                "type": "time",
                "question": f"What time is the {specific_desc}?",
                "field": "time",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
        
        if not meeting.get("duration_minutes"):
            duration_questions.append({
                "type": "duration",
                "question": f"How long is the {specific_desc} (in minutes)?",
                "field": "duration_minutes",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
        if not meeting.get("course_code") and meeting.get("type") in ["exam", "presentation"]:
            course_code_questions.append({
                "type": "course_code",
                "question": f"What is the course code for the {specific_desc}?",
                "field": "course_code",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
    
    # Check tasks - ask for day if missing, and course_code when not related to a meeting we're already asking about
    for task in schedule.get("tasks", []):
        # DEBUG: Log task properties
        logger.info(f"Checking task: {task.get('description')}, course_code: {task.get('course_code')}, category: {task.get('category')}, day: {task.get('day')}, missing_info: {task.get('missing_info')}")
        
        # Check for missing day on tasks that need scheduling
        if not task.get("day") and task.get("is_fixed_time", False):
            task_desc = task.get("description", "")
            day_questions.append({
                "type": "day",
                "question": f"On which day of the week is the task '{task_desc}'?",
                "field": "day",
                "target": task_desc,
                "target_type": "task",
                "target_id": task.get("id"),
                "input_type": "dropdown",
                "options": [
                    {"value": "Monday", "text": "Monday"},
                    {"value": "Tuesday", "text": "Tuesday"},
                    {"value": "Wednesday", "text": "Wednesday"},
                    {"value": "Thursday", "text": "Thursday"},
                    {"value": "Friday", "text": "Friday"},
                    {"value": "Saturday", "text": "Saturday"},
                    {"value": "Sunday", "text": "Sunday"}
                ]
            })
        
        # Check for ambiguous time (missing AM/PM)
        if task.get("time") and is_time_ambiguous(task.get("time")) and task.get("is_fixed_time", False):
            clean_time = get_clean_time(task.get("time"))
            task_desc = task.get("description", "")
            ampm_questions.append({
                "type": "ampm",
                "question": f"Is {clean_time} for the task '{task_desc}' AM or PM?",
                "field": "time_ampm",
                "target": task_desc,
                "target_type": "task",
                "target_id": task.get("id"),
                "original_time": clean_time,
                "input_type": "dropdown",
                "options": [
                    {"value": "am", "text": "AM"},
                    {"value": "pm", "text": "PM"}
                ]
            })
        
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
                course_code_questions.append({
                    "type": "course_code",
                    "question": f"What is the course code for the {task.get('description')}?",
                    "field": "course_code",
                    "target": task.get("description"),
                    "target_type": "task",
                    "target_id": task.get("id")
                })
            else:
                logger.info(f"Skipping course code question for task: {task.get('description')}")
    
    # Combine questions in priority order: day, ampm, time, duration, course_code
    questions = day_questions + ampm_questions + time_questions + duration_questions + course_code_questions
    
    logger.info(f"Final questions list (prioritized): {questions}")
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
    elif answer_type == "day":
        # Capitalize the day name for consistency
        day_value = value.strip().capitalize()
        # Ensure it's a valid day of the week
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if day_value in valid_days:
            return day_value
        # If it's a shortened form, expand it
        day_map = {
            'Mon': 'Monday',
            'Tues': 'Tuesday',
            'Tue': 'Tuesday', 
            'Wed': 'Wednesday',
            'Thurs': 'Thursday',
            'Thu': 'Thursday',
            'Th': 'Thursday',
            'Fri': 'Friday',
            'Sat': 'Saturday',
            'Sun': 'Sunday'
        }
        if day_value in day_map:
            return day_map[day_value]
        # Return as is if not recognized
        return day_value
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
    
    # Remove missing_info entries for fields that are now filled
    for collection in ["meetings", "tasks"]:
        for item in schedule.get(collection, []):
            if "missing_info" in item:
                for field in list(item.get("missing_info", [])):
                    if field in item and item[field] is not None:
                        item["missing_info"].remove(field)
                if not item["missing_info"]:
                    del item["missing_info"]
    
    # Update the course_codes array with any new course codes
    course_codes = set(schedule.get("course_codes", []))
    for collection in ["meetings", "tasks"]:
        for item in schedule.get(collection, []):
            if item.get("course_code"):
                course_codes.add(item["course_code"])
    
    schedule["course_codes"] = list(course_codes)
    
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