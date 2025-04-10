import os
import json
import logging
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import heapq

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants for scheduling
DEFAULT_DURATION = 60  # minutes
BUFFER_TIME = 15  # minutes
WORK_HOURS = {
    'start': datetime.strptime('08:00', '%H:%M').time(),
    'end': datetime.strptime('22:00', '%H:%M').time()
}

# Path to IEP1's storage
IEP1_STORAGE_PATH = '/app/storage/latest_schedule.json'
# Path to IEP2's preferences storage
STORAGE_DIR = "storage"
PREFERENCES_PATH = os.path.join(STORAGE_DIR, "preferences.json")

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

def ensure_storage_exists():
    """Ensure the storage directory exists"""
    storage_dir = os.path.dirname(PREFERENCES_PATH)
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
        logger.info(f"Created storage directory at {storage_dir}")

class Event:
    def __init__(self, data: Dict):
        # Validate required fields
        required_fields = ['description', 'day', 'time', 'duration_minutes']
        if any(data.get(field) is None for field in required_fields):
            raise ValueError(f"Missing required fields for event: {data.get('description', 'Unknown')}")
            
        self.id = data.get('id', '')
        self.type = data.get('type', '')
        self.description = data.get('description')
        self.day = data.get('day')
        self.time = data.get('time')
        self.duration = data.get('duration_minutes')
        self.priority = data.get('priority', 'medium')
        self.course_code = data.get('course_code', '')
        self.location = data.get('location', 'None')
        self.preparation_tasks = data.get('preparation_tasks', [])

    def __lt__(self, other):
        # Higher priority events come first
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        return priority_order[self.priority] < priority_order[other.priority]

class Task:
    def __init__(self, data: Dict):
        # Validate required fields
        required_fields = ['description', 'day', 'duration_minutes']
        if any(data.get(field) is None for field in required_fields):
            raise ValueError(f"Missing required fields for task: {data.get('description', 'Unknown')}")
            
        self.id = data.get('id', '')
        self.description = data.get('description')
        self.category = data.get('category', '')
        self.duration = data.get('duration_minutes')
        self.priority = data.get('priority', 'medium')
        self.related_event = data.get('related_event', '')
        self.course_code = data.get('course_code', '')
        self.is_fixed_time = data.get('is_fixed_time', False)
        self.prerequisites = data.get('prerequisites', [])
        self.day = data.get('day')
        self.time = data.get('time')  # Can be None for flexible scheduling

def load_schedule_from_iep1() -> Dict:
    """Load the latest schedule from IEP1's storage"""
    try:
        if os.path.exists(IEP1_STORAGE_PATH):
            with open(IEP1_STORAGE_PATH, 'r') as f:
                schedule = json.load(f)
                
            # Validate that all required fields are present and not null
            if not schedule:
                logger.error("Empty schedule received")
                return None
                
            # Validate meetings
            meetings = schedule.get('meetings', [])
            for meeting in meetings:
                if any(meeting.get(field) is None for field in ['time', 'duration_minutes', 'day']):
                    logger.error("Incomplete meeting data received: missing required fields")
                    return None
                    
            # Validate tasks
            tasks = schedule.get('tasks', [])
            for task in tasks:
                if any(task.get(field) is None for field in ['duration_minutes', 'day']):
                    logger.error("Incomplete task data received: missing required fields")
                    return None
            
            return schedule
            
        logger.error("No schedule found in IEP1's storage")
        return None
    except Exception as e:
        logger.error(f"Error loading schedule from IEP1: {str(e)}")
        return None

def create_time_slots(day: str) -> List[Dict]:
    """Create time slots for a given day"""
    slots = []
    current_time = datetime.strptime(WORK_HOURS['start'].strftime('%H:%M'), '%H:%M')
    end_time = datetime.strptime(WORK_HOURS['end'].strftime('%H:%M'), '%H:%M')
    
    while current_time < end_time:
        slots.append({
            'start': current_time.strftime('%H:%M'),
            'end': (current_time + timedelta(minutes=DEFAULT_DURATION)).strftime('%H:%M'),
            'available': True,
            'day': day
        })
        current_time += timedelta(minutes=DEFAULT_DURATION + BUFFER_TIME)
    
    return slots

def load_preferences() -> Dict:
    """Load user preferences from storage"""
    ensure_storage_exists()
    try:
        if os.path.exists(PREFERENCES_PATH):
            with open(PREFERENCES_PATH, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading preferences: {str(e)}")
    
    # Return default preferences if file doesn't exist or error occurs
    return {
        "productivity_time": {"morning": 0.8, "afternoon": 0.6, "evening": 0.4},
        "break_preferences": {"frequency": "medium", "duration": 15},
        "task_grouping": {"similar_tasks": True, "max_consecutive": 3},
        "work_hours": {"start": "09:00", "end": "17:00"}
    }

def save_preferences(preferences: Dict) -> bool:
    """Save user preferences to storage"""
    ensure_storage_exists()
    try:
        with open(PREFERENCES_PATH, 'w') as f:
            json.dump(preferences, f, indent=2)
        logger.info("Preferences saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving preferences: {str(e)}")
        return False

def schedule_events(events: List[Event], tasks: List[Task]) -> Dict:
    """Schedule events and tasks using a rule-based algorithm with preferences"""
    logger.info("Starting scheduling algorithm")
    
    # Load preferences
    preferences = load_preferences()
    
    # Get initial schedule
    schedule = schedule_events_base(events, tasks)
    
    # Apply preferences to modify the schedule
    schedule = apply_preferences_to_schedule(schedule, preferences)
    
    logger.info("Scheduling completed successfully with preferences applied")
    return schedule

def schedule_events_base(events: List[Event], tasks: List[Task]) -> Dict:
    """Base scheduling logic without preferences"""
    try:
        logger.info("Starting base scheduling algorithm")
        
        # Initialize schedule structure
        schedule = {
            'scheduled_events': [],
            'scheduled_tasks': [],
            'time_slots': {}
        }
        
        # Create time slots for each day
        days = set(event.day for event in events)
        days.update(task.day for task in tasks)  # Add days from tasks too
        for day in days:
            schedule['time_slots'][day] = create_time_slots(day)
        
        # First, schedule fixed events
        for event in sorted(events):
            event_dict = {
                'id': event.id,
                'type': event.type,
                'description': event.description,
                'day': event.day,
                'start_time': event.time,
                'duration': event.duration,
                'priority': event.priority,
                'course_code': event.course_code,
                'location': event.location
            }
            schedule['scheduled_events'].append(event_dict)
            
            # Mark time slots as unavailable
            if event.time:  # Only block slots if time is specified
                event_start = datetime.strptime(event.time, '%H:%M')
                event_end = event_start + timedelta(minutes=event.duration)
                
                for slot in schedule['time_slots'][event.day]:
                    slot_start = datetime.strptime(slot['start'], '%H:%M')
                    slot_end = datetime.strptime(slot['end'], '%H:%M')
                    
                    if (slot_start <= event_start < slot_end or 
                        slot_start < event_end <= slot_end):
                        slot['available'] = False
        
        # Then, schedule tasks
        for task in sorted(tasks, key=lambda x: (x.priority == 'high', x.is_fixed_time)):
            task_dict = {
                'id': task.id,
                'description': task.description,
                'category': task.category,
                'duration': task.duration,
                'priority': task.priority,
                'course_code': task.course_code,
                'related_event': task.related_event
            }
            
            # If task has a fixed time, use it
            if task.time:
                task_dict['day'] = task.day
                task_dict['start_time'] = task.time
            # If task is related to an event, try to schedule it before the event
            elif task.related_event:
                related_event = next((e for e in events if e.description == task.related_event), None)
                if related_event and related_event.time:
                    event_start = datetime.strptime(related_event.time, '%H:%M')
                    task_dict['day'] = related_event.day
                    task_dict['start_time'] = (event_start - timedelta(minutes=task.duration + BUFFER_TIME)).strftime('%H:%M')
            else:
                # Try to schedule in preferred day first
                preferred_day = task.day
                slot_found = False
                
                if preferred_day in schedule['time_slots']:
                    for slot in schedule['time_slots'][preferred_day]:
                        if slot['available']:
                            task_dict['day'] = preferred_day
                            task_dict['start_time'] = slot['start']
                            slot['available'] = False
                            slot_found = True
                            break
                
                # If no slot found in preferred day, try other days
                if not slot_found:
                    for day in days:
                        if day == preferred_day:
                            continue
                        for slot in schedule['time_slots'][day]:
                            if slot['available']:
                                task_dict['day'] = day
                                task_dict['start_time'] = slot['start']
                                slot['available'] = False
                                slot_found = True
                                break
                        if slot_found:
                            break
            
            schedule['scheduled_tasks'].append(task_dict)
        
        logger.info("Base scheduling completed successfully")
        return schedule
        
    except Exception as e:
        logger.error(f"Error in base scheduling: {str(e)}")
        raise

@app.route('/optimize-schedule', methods=['GET', 'POST'])
def optimize_schedule():
    """Optimize the current schedule"""
    try:
        # Load schedule from IEP1's storage
        schedule = load_schedule_from_iep1()
        if not schedule:
            logger.error("No valid schedule found to optimize")
            return jsonify({"error": "No valid schedule found. Ensure all required information is provided in IEP1."}), 404
        
        try:
            # Convert to Event and Task objects - this will validate all required fields
            events = [Event(event) for event in schedule.get('meetings', [])]
            tasks = [Task(task) for task in schedule.get('tasks', [])]
        except ValueError as e:
            logger.error(f"Invalid schedule data: {str(e)}")
            return jsonify({"error": f"Invalid schedule data: {str(e)}"}), 400
            
        logger.info(f"Loaded {len(events)} events and {len(tasks)} tasks for optimization")
        
        # Apply scheduling algorithm
        optimized_schedule = schedule_events(events, tasks)
        if not optimized_schedule:
            return jsonify({"error": "Failed to optimize schedule"}), 500
            
        # Ensure the response is JSON serializable
        response = {
            'scheduled_events': optimized_schedule['scheduled_events'],
            'scheduled_tasks': optimized_schedule['scheduled_tasks'],
            'time_slots': optimized_schedule['time_slots']
        }
        
        logger.info("Schedule optimization completed")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error during schedule optimization: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/algorithm-questions', methods=['GET'])
def get_algorithm_questions():
    """Return the questions needed for algorithm preferences."""
    questions = [
        {
            "id": "productivity_time",
            "question": "Rate your productivity during different times of day (0.0 to 1.0)",
            "type": "productivity_rating",
            "options": ["morning", "afternoon", "evening"]
        },
        {
            "id": "break_preferences",
            "question": "What are your break preferences?",
            "type": "break_settings",
            "options": {
                "frequency": ["short", "medium", "long"],
                "duration": "number_minutes"
            }
        },
        {
            "id": "task_grouping",
            "question": "How would you like similar tasks to be grouped?",
            "type": "grouping_settings",
            "options": {
                "similar_tasks": "boolean",
                "max_consecutive": "number"
            }
        },
        {
            "id": "work_hours",
            "question": "What are your preferred working hours?",
            "type": "time_range",
            "options": {
                "start": "HH:MM",
                "end": "HH:MM"
            }
        }
    ]
    return jsonify({"questions": questions})

@app.route('/save-preferences', methods=['POST'])
def save_preferences_endpoint():
    """Endpoint to save user preferences"""
    try:
        preferences = request.get_json()
        if not preferences:
            return jsonify({"error": "No preferences provided"}), 400
        
        # Validate preferences
        required_fields = ["productivity_time", "break_preferences", "task_grouping", "work_hours"]
        missing_fields = [field for field in required_fields if field not in preferences]
        if missing_fields:
            return jsonify({"error": f"Missing required preferences: {', '.join(missing_fields)}"}), 400
        
        # Try to save preferences
        if save_preferences(preferences):
            return jsonify({"message": "Preferences saved successfully"})
        else:
            return jsonify({"error": "Failed to save preferences"}), 500
            
    except Exception as e:
        logging.error(f"Error in save_preferences endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

def apply_preferences_to_schedule(schedule: Dict, preferences: Dict) -> Dict:
    """Apply user preferences to the schedule"""
    if not preferences:
        return schedule
    
    scheduled_events = schedule['scheduled_events']
    scheduled_tasks = schedule['scheduled_tasks']
    
    # Apply productivity time preference
    prod_times = preferences.get('productivity_time', {})
    if prod_times:
        # Sort tasks by productivity score for their time slot
        def get_productivity_score(task):
            task_time = task.get('start_time', '00:00')
            if '08:00' <= task_time < '12:00':
                return prod_times.get('morning', 0.5)
            elif '12:00' <= task_time < '17:00':
                return prod_times.get('afternoon', 0.5)
            else:
                return prod_times.get('evening', 0.5)
        
        scheduled_tasks.sort(key=lambda x: (-get_productivity_score(x), -int(x.get('priority', 'low') == 'high')))
    
    # Apply break preferences
    break_prefs = preferences.get('break_preferences', {})
    if break_prefs:
        global BUFFER_TIME
        frequency = break_prefs.get('frequency', 'medium')
        BUFFER_TIME = {
            'short': 10,
            'medium': 15,
            'long': 30
        }.get(frequency, 15)
    
    # Apply task grouping preference
    task_group = preferences.get('task_grouping', {})
    if task_group.get('similar_tasks', False):
        # Group similar tasks but respect max_consecutive
        max_consecutive = task_group.get('max_consecutive', 3)
        grouped_tasks = []
        current_category = None
        category_count = 0
        
        for task in sorted(scheduled_tasks, key=lambda x: x.get('category', '')):
            if task.get('category') != current_category:
                current_category = task.get('category')
                category_count = 1
            elif category_count >= max_consecutive:
                # Find next task from different category
                for next_task in scheduled_tasks:
                    if next_task.get('category') != current_category:
                        grouped_tasks.append(next_task)
                        current_category = next_task.get('category')
                        category_count = 1
                        break
            else:
                category_count += 1
            grouped_tasks.append(task)
        
        scheduled_tasks = grouped_tasks
    
    # Apply work hours
    work_hrs = preferences.get('work_hours', {})
    if work_hrs:
        global WORK_HOURS
        WORK_HOURS['start'] = datetime.strptime(work_hrs.get('start', '09:00'), '%H:%M').time()
        WORK_HOURS['end'] = datetime.strptime(work_hrs.get('end', '17:00'), '%H:%M').time()
    
    return {
        'scheduled_events': scheduled_events,
        'scheduled_tasks': scheduled_tasks,
        'time_slots': schedule['time_slots']
    }

def validate_preferences(preferences: Dict) -> Optional[str]:
    """Validate preferences structure and return error message if invalid"""
    try:
        # Check required sections
        required_sections = ["productivity_time", "break_preferences", "task_grouping", "work_hours"]
        for section in required_sections:
            if section not in preferences:
                return f"Missing required section: {section}"
        
        # Validate productivity_time
        prod_times = preferences.get("productivity_time", {})
        if not all(time in prod_times for time in ["morning", "afternoon", "evening"]):
            return "productivity_time must contain morning, afternoon, and evening values"
        
        # Validate break_preferences
        break_prefs = preferences.get("break_preferences", {})
        if "frequency" not in break_prefs or "duration" not in break_prefs:
            return "break_preferences must contain frequency and duration"
        if break_prefs["frequency"] not in ["short", "medium", "long"]:
            return "break frequency must be short, medium, or long"
        
        # Validate task_grouping
        task_group = preferences.get("task_grouping", {})
        if "similar_tasks" not in task_group or "max_consecutive" not in task_group:
            return "task_grouping must contain similar_tasks and max_consecutive"
        
        # Validate work_hours
        work_hrs = preferences.get("work_hours", {})
        if "start" not in work_hrs or "end" not in work_hrs:
            return "work_hours must contain start and end times"
        
        return None
    except Exception as e:
        return f"Error validating preferences: {str(e)}"

@app.route('/update-preferences', methods=['POST'])
def update_preferences():
    """Update user preferences"""
    try:
        preferences = request.json
        if not preferences:
            return jsonify({"error": "No preferences provided"}), 400
        
        # Validate preferences
        error = validate_preferences(preferences)
        if error:
            return jsonify({"error": error}), 400
        
        # Save preferences
        if save_preferences(preferences):
            return jsonify({"message": "Preferences updated successfully"}), 200
        else:
            return jsonify({"error": "Failed to save preferences"}), 500
            
    except Exception as e:
        logger.error(f"Error updating preferences: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002) 