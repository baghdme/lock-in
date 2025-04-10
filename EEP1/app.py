from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from copy import deepcopy

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Service URLs
IEP1_URL = os.getenv('IEP1_URL', 'http://iep1:5001')

# Storage configuration
STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'latest_schedule.json')
os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)

# Prompt templates
PARSING_PROMPT = """You are a task parsing assistant for a weekly scheduling system. Parse the following weekly overview text into structured information following these rules:

1. Input Understanding:
   - The user provides descriptions of events and their related tasks
   - Events can be: exams, meetings, presentations, project deadlines, interviews, etc.
   - For each main event, identify if preparation is needed but DO NOT schedule specific prep times
   - Examples:
       "I have an exam on Thursday at 14:00" -> Just note that exam prep is needed
       "Team presentation next Monday at 10:00 AM" -> Just note that presentation prep is needed

2. Event Classification:
   - Main Events (treated as meetings):
     * Exams: Flag that preparation is needed
     * Presentations: Flag that preparation is needed
     * Project deadlines: Flag that work sessions are needed
     * Team meetings: Flag if preparation is mentioned
   
   - Preparation Needs:
     * Exams: Add a general "prepare for exam" task
     * Presentations: Add a general "prepare presentation" task
     * Projects: Add a general "work on project" task
     * Meetings: Add prep task only if explicitly mentioned

3. Task Creation Rules:
   - For each main event:
     * Create the event in meetings array with exact time
     * Add a general preparation task if needed
     * DO NOT specify study times or session durations
     * Let the schedule generator handle when and how long to study

4. Priority and Linking Rules:
   - ALL exam-related events and tasks are high priority
   - ALL presentation-related events and tasks are high priority
   - Link tasks to their main event using related_event
   - Use consistent descriptions
   - Inherit course codes from main events to tasks

Output a JSON object with this structure:
{
    "tasks": [
        {
            "description": "task description",
            "day": "day of week or date",
            "priority": "high/medium/low",
            "time": null,
            "duration_minutes": null,
            "category": "study/preparation/research/project_work/follow_up",
            "is_fixed_time": false,
            "location": "location if specified or None",
            "prerequisites": ["list of prerequisite task descriptions"],
            "course_code": "associated course code or None",
            "related_event": "description of the main event this task is for"
        }
    ],
    "meetings": [
        {
            "description": "meeting description",
            "day": "day of week or date",
            "priority": "high/medium/low",
            "time": "HH:MM",
            "duration_minutes": null,
            "type": "exam/presentation/interview/project_deadline/regular",
            "location": "meeting location or None",
            "preparation_tasks": ["list of required prep task descriptions"],
            "course_code": "associated course code or None"
        }
    ],
    "course_codes": ["list of course codes"],
    "topics": []
}

IMPORTANT VALIDATION RULES: 
1. For exams:
   - Add ONE general preparation task without specific times
   - Let schedule generator handle study sessions
   - Course code must be consistent across items

2. For presentations:
   - Add ONE general preparation task without specific times
   - Let schedule generator handle prep schedule
   - ALL tasks must be high priority

3. General rules:
   - Every task MUST have a related_event that matches a meeting description
   - Every meeting MUST have corresponding tasks in the tasks array
   - Course codes must be propagated to all related tasks
   - DO NOT specify times for preparation tasks

Parse the input text completely and output only the JSON object.
Text to parse: "{text}"
"""

def save_schedule(schedule):
    """Save the schedule to persistent storage"""
    with open(STORAGE_PATH, 'w') as f:
        json.dump(schedule, f, indent=2)

def load_schedule():
    """Load the latest schedule from storage"""
    if os.path.exists(STORAGE_PATH):
        with open(STORAGE_PATH, 'r') as f:
            return json.load(f)
    return None

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

def check_missing_info(schedule: dict) -> list:
    """Check for missing information in the schedule and return questions if needed"""
    questions = []
    
    # Check meetings
    for meeting in schedule.get("meetings", []):
        if not meeting.get("time"):
            questions.append({
                "type": "time",
                "question": f"What time is the {meeting.get('description')}?",
                "options": ["morning", "afternoon", "evening", "specific_time"],
                "field": "time",
                "target": meeting.get("description")
            })
        if not meeting.get("duration_minutes"):
            questions.append({
                "type": "duration",
                "question": f"How long is the {meeting.get('description')}?",
                "options": ["30", "60", "90", "120"],
                "field": "duration_minutes",
                "target": meeting.get("description")
            })
    
    # Check tasks
    for task in schedule.get("tasks", []):
        if not task.get("day"):
            questions.append({
                "type": "day",
                "question": f"When should the task '{task.get('description')}' be scheduled?",
                "options": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                "field": "day",
                "target": task.get("description")
            })
    
    return questions

def convert_answer_value(answer_type: str, value: str) -> any:
    """Convert answer values to appropriate types"""
    if answer_type == "duration":
        return int(value)
    return value

def update_schedule_with_answers(schedule: dict, answers: list) -> dict:
    """Update schedule with user-provided answers"""
    schedule = deepcopy(schedule)
    
    for answer in answers:
        field = answer.get("field")
        value = answer.get("value")
        target = answer.get("target")
        
        if not all([field, value, target]):
            continue
            
        # Convert value to appropriate type
        value = convert_answer_value(answer.get("type", ""), value)
        
        # Update meetings
        for meeting in schedule.get("meetings", []):
            if meeting.get("description") == target:
                meeting[field] = value
                
        # Update tasks
        for task in schedule.get("tasks", []):
            if task.get("description") == target:
                task[field] = value
                
    return schedule

@app.route('/parse-schedule', methods=['POST'])
def parse_schedule():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'Missing text parameter'}), 400

        # Prepare prompt for IEP1
        prompt = f"{PARSING_PROMPT}\n\nSchedule text:\n{data['text']}"

        # Call IEP1 for parsing
        try:
            response = requests.post(
                f"{IEP1_URL}/predict",
                json={'prompt': prompt}
            )
            response.raise_for_status()
            
            # Get the response text and clean it
            response_text = response.json()
            
            # If the response is wrapped in markdown code blocks, extract the JSON
            if isinstance(response_text, str):
                if response_text.startswith('```'):
                    # Extract the JSON string between the code blocks
                    json_str = response_text.split('```')[1]
                    if json_str.startswith('json\n'):
                        json_str = json_str[5:]
                    parsed_data = json.loads(json_str)
                else:
                    # If it's a string but not markdown, try parsing it as JSON
                    parsed_data = json.loads(response_text)
            else:
                # If it's already a dict/object, use it as is
                parsed_data = response_text
            
            # Save the parsed schedule
            save_schedule(parsed_data)
            
            return jsonify({
                'status': 'complete',
                'schedule': parsed_data
            })
            
        except requests.exceptions.RequestException as e:
            return jsonify({'error': f'Error communicating with IEP1: {str(e)}'}), 500
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Invalid JSON response from IEP1: {str(e)}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/modify-schedule', methods=['POST'])
def modify_schedule():
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Missing text parameter"}), 400
            
        # Load current schedule
        current_schedule = load_schedule()
        if not current_schedule:
            return jsonify({"error": "No schedule found to modify"}), 404
            
        # Create prompt for IEP1
        prompt = PARSING_PROMPT.format(text=data['text'])
        
        # Call IEP1 for parsing
        response = requests.post(
            f"{IEP1_URL}/predict",
            json={"prompt": prompt}
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"IEP1 error: {response.text}"}), 500
            
        # Parse the response
        try:
            new_schedule = json.loads(response.json())
            new_schedule = validate_and_fix_times(new_schedule)
            
            # Check for missing information
            questions = check_missing_info(new_schedule)
            
            if questions:
                return jsonify({
                    "status": "questions_needed",
                    "questions": questions,
                    "schedule": new_schedule
                })
                
            # Save the modified schedule
            save_schedule(new_schedule)
            
            return jsonify({
                "status": "complete",
                "schedule": new_schedule
            })
            
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON response from IEP1"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    try:
        # Check IEP1 health
        iep1_response = requests.get(f"{IEP1_URL}/health")
        iep1_status = iep1_response.status_code == 200
        
        return jsonify({
            "status": "healthy" if iep1_status else "unhealthy",
            "services": {
                "iep1": "healthy" if iep1_status else "unhealthy"
            }
        }), 200 if iep1_status else 500
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/get-schedule', methods=['GET'])
def get_schedule():
    try:
        schedule = load_schedule()
        if not schedule:
            return jsonify({'error': 'No schedule found'}), 404
            
        return jsonify({
            'status': 'success',
            'schedule': schedule
        })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 