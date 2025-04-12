"""
IEP2 (Internal End Point 2) API.

This service provides schedule generation functionality based on user preferences.
It serves as a direct interface to the scheduling algorithm, receiving complete schedule data
from EEP1 and returning an optimized schedule with time allocations.
"""

import json
import logging
import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import the advanced scheduling algorithm
from schedule_generator import generate_schedule as advanced_generate_schedule

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Storage path for saving generated schedules
STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'latest_generated_schedule.json')
os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)

def save_generated_schedule(schedule):
    """Save the generated schedule to storage."""
    try:
        # Create storage directory if it doesn't exist
        os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)
        
        # Save to file
        with open(STORAGE_PATH, 'w') as f:
            json.dump(schedule, f, indent=2)
            
        return schedule
    except Exception as e:
        logger.error(f"Error saving generated schedule: {str(e)}")
        raise

@app.route('/')
def index():
    """Health check endpoint."""
    return jsonify({
        "service": "IEP2 - Schedule Generator",
        "status": "active",
        "version": "1.0.0"
    })

@app.route('/api/generate', methods=['POST'])
def create_schedule():
    """
    Generate a schedule based on completed schedule data and preferences.
    This endpoint receives a complete JSON with schedule and preferences, passes it 
    to the advanced scheduling algorithm, and returns the optimized schedule.
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Check for required fields
        if 'schedule' not in data:
            return jsonify({"error": "Missing schedule data"}), 400
        
        # Verify schedule has meetings and tasks
        schedule_data = data['schedule']
        if 'meetings' not in schedule_data or 'tasks' not in schedule_data:
            return jsonify({
                "error": "Invalid schedule format",
                "message": "Schedule must contain 'meetings' and 'tasks' arrays"
            }), 400
            
        # Set default preferences if not provided
        if 'preferences' not in data:
            logger.warning("No preferences provided, using defaults")
            data['preferences'] = _get_default_preferences()
        
        # Prepare input for the advanced scheduling algorithm
        # The algorithm expects meetings and tasks at the top level
        input_data = {
            'meetings': schedule_data.get('meetings', []),
            'tasks': schedule_data.get('tasks', []),
            'preferences': data['preferences']
        }
        
        # Add course_codes to preferences if available
        if 'course_codes' in schedule_data:
            input_data['preferences']['course_codes'] = schedule_data['course_codes']
        
        # Normalize field names for compatibility with the scheduler
        for meeting in input_data['meetings']:
            if 'duration_minutes' in meeting and 'duration' not in meeting:
                meeting['duration'] = meeting['duration_minutes']
                
        for task in input_data['tasks']:
            if 'duration_minutes' in task and 'duration' not in task:
                task['duration'] = task['duration_minutes']
        
        # Generate the schedule
        logger.info(f"Generating schedule for {len(input_data['tasks'])} tasks and {len(input_data['meetings'])} meetings")
        
        # Call the advanced scheduling algorithm
        result = advanced_generate_schedule(input_data)
        
        # Restructure the output to match the expected format
        output = {
            'schedule': {
                'course_codes': schedule_data.get('course_codes', []),
                'meetings': schedule_data.get('meetings', []),
                'tasks': schedule_data.get('tasks', []),
                'generated_calendar': result.get('schedule', {}).get('generated_calendar', {})
            },
            'preferences': data['preferences'],
            'success': True,
            'message': "Schedule successfully generated"
        }
        
        # Save the generated schedule
        save_generated_schedule(output)
        
        return jsonify(output)
    except Exception as e:
        logger.error(f"Error generating schedule: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-generated-schedule', methods=['GET'])
def get_generated_schedule():
    """Retrieve the most recently generated schedule."""
    try:
        # Check if the file exists
        if not os.path.exists(STORAGE_PATH):
            return jsonify({"error": "No generated schedule found"}), 404
            
        # Load the file
        with open(STORAGE_PATH, 'r') as f:
            schedule = json.load(f)
            
        return jsonify(schedule)
    except Exception as e:
        logger.error(f"Error retrieving generated schedule: {str(e)}")
        return jsonify({"error": str(e)}), 500

def _get_default_preferences():
    """Return default preferences for schedule generation."""
    return {
        "work_start": "09:00",
        "work_end": "17:00",
        "productivity_pattern": "morning",
        "break_preference": "regular",
        "include_weekend": False,
        "task_grouping": "mixed",
        "scheduling_strategy": "balanced",
        "break_duration": 15,
        "break_frequency": "medium",
        "preparation_time": "few_days"
    }

def _time_to_minutes(time_str):
    """Convert a time string (HH:MM) to minutes since midnight."""
    try:
        if ":" in time_str:
            hours, minutes = time_str.split(":")
            return int(hours) * 60 + int(minutes)
        else:
            # Try to parse as hours only
            return int(time_str) * 60
    except (ValueError, TypeError):
        return 0

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    app.run(host='0.0.0.0', port=port, debug=True)