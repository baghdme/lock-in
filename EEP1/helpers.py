import os
import json
import uuid
from datetime import datetime

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
    questions = []
    # Check meetings
    for meeting in schedule.get("meetings", []):
        if not meeting.get("time"):
            questions.append({
                "type": "time",
                "question": f"What time is the {meeting.get('description')}?",
                "field": "time",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
        if not meeting.get("duration_minutes"):
            questions.append({
                "type": "duration",
                "question": f"How long is the {meeting.get('description')}?",
                "field": "duration_minutes",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
        if not meeting.get("course_code") and meeting.get("type") in ["exam", "presentation"]:
            questions.append({
                "type": "course_code",
                "question": f"What is the course code for the {meeting.get('description')}?",
                "field": "course_code",
                "target": meeting.get("description"),
                "target_type": "meeting",
                "target_id": meeting.get("id")
            })
    # Check tasks - only ask for course_code for preparation tasks
    for task in schedule.get("tasks", []):
        if not task.get("course_code") and task.get("category") == "preparation":
            questions.append({
                "type": "course_code",
                "question": f"What is the course code for the {task.get('description')}?",
                "field": "course_code",
                "target": task.get("description"),
                "target_type": "task",
                "target_id": task.get("id")
            })
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
    schedule = copy.deepcopy(schedule)
    for answer in answers:
        field = answer.get("field")
        value = answer.get("value")
        target = answer.get("target")
        if not all([field, value, target]):
            continue
        value = convert_answer_value(answer.get("type", ""), value)
        for meeting in schedule.get("meetings", []):
            if meeting.get("description") == target:
                meeting[field] = value
        for task in schedule.get("tasks", []):
            if task.get("description") == target:
                task[field] = value
    return schedule

# ===============================
# Utility Functions
# ===============================

# Miscellaneous helper functions

def ensure_ids(schedule):
    if not schedule:
        return schedule
    if 'meetings' in schedule:
        for meeting in schedule['meetings']:
            if 'id' not in meeting or not meeting['id']:
                meeting['id'] = str(uuid.uuid4())
    if 'tasks' in schedule:
        for task in schedule['tasks']:
            if 'id' not in task or not task['id']:
                task['id'] = str(uuid.uuid4())
    return schedule 