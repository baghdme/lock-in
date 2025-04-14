import json
import logging
import os
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
        os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)
        with open(STORAGE_PATH, 'w', encoding='utf-8') as f:
            json.dump(schedule, f, indent=2, ensure_ascii=False)
        logger.info("Schedule saved to %s", STORAGE_PATH)
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
    Generate a schedule based on the complete schedule data and preferences.
    This endpoint receives a JSON containing 'schedule' (with 'meetings' and 'tasks')
    and 'preferences', calls the scheduling algorithm, saves, and returns the generated schedule.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        if 'schedule' not in data:
            return jsonify({"error": "Missing schedule data"}), 400
        
        schedule_data = data['schedule']
        if 'meetings' not in schedule_data or 'tasks' not in schedule_data:
            return jsonify({
                "error": "Invalid schedule format",
                "message": "Schedule must contain 'meetings' and 'tasks' arrays"
            }), 400

        if 'preferences' not in data:
            logger.warning("No preferences provided, using defaults")
            data['preferences'] = _get_default_preferences()
        
        # Prepare input for the scheduling algorithm.
        input_data = {
            'meetings': schedule_data.get('meetings', []),
            'tasks': schedule_data.get('tasks', []),
            'preferences': data['preferences']
        }
        
        if 'course_codes' in schedule_data:
            input_data['preferences']['course_codes'] = schedule_data['course_codes']
        
        # Normalize field names if needed.
        for meeting in input_data['meetings']:
            if 'duration_minutes' in meeting and 'duration' not in meeting:
                meeting['duration'] = meeting['duration_minutes']
        for task in input_data['tasks']:
            if 'duration_minutes' in task and 'duration' not in task:
                task['duration'] = task['duration_minutes']
        
        logger.info("Input for scheduling algorithm: %s", json.dumps(input_data, indent=2))
        logger.info(f"Generating schedule for {len(input_data['tasks'])} tasks and {len(input_data['meetings'])} meetings")

        print(f"Input data: {input_data}")

        # Call the scheduling algorithm.
        result = advanced_generate_schedule(input_data)

        logger.info(f"Result: {result}")

        logger.info("Scheduling algorithm returned: %s", json.dumps(result, indent=2))
        
        # Use the full result from the scheduling algorithm.
        output = result

        # Save the generated schedule.
        save_generated_schedule(output)
        
        return jsonify(output)
    except Exception as e:
        logger.error(f"Error generating schedule: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-generated-schedule', methods=['GET'])
def get_generated_schedule():
    """Retrieve the most recently generated schedule."""
    try:
        if not os.path.exists(STORAGE_PATH):
            return jsonify({"error": "No generated schedule found"}), 404
        with open(STORAGE_PATH, 'r', encoding='utf-8') as f:
            schedule = json.load(f)
        return jsonify(schedule)
    except Exception as e:
        logger.error(f"Error retrieving generated schedule: {str(e)}")
        return jsonify({"error": str(e)}), 500

def _get_default_preferences():
    """Return default scheduling preferences."""
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
            return int(time_str) * 60
    except (ValueError, TypeError):
        return 0

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    app.run(host='0.0.0.0', port=port, debug=True)
