from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from copy import deepcopy
import logging
from prompts import PARSING_PROMPT, MODIFY_PROMPT
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Service URLs
IEP1_URL = os.getenv('IEP1_URL', 'http://localhost:5001')
logger.debug(f"Using IEP1_URL: {IEP1_URL}")

# Storage configuration
STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'latest_schedule.json')
os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)

def save_schedule(schedule):
    """Save the schedule to storage."""
    try:
        # Ensure the schedule has all required IDs
        schedule = ensure_ids(schedule)
        
        # Create storage directory if it doesn't exist
        os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)
        
        # Save to file
        with open(STORAGE_PATH, 'w') as f:
            json.dump(schedule, f, indent=2)
            
        return schedule
    except Exception as e:
        logger.error(f"Error saving schedule: {str(e)}")
        raise

def load_schedule():
    """Load the schedule from storage."""
    try:
        with open(STORAGE_PATH, 'r') as f:
            schedule = json.load(f)
        return schedule
    except FileNotFoundError:
        # Return empty schedule if file doesn't exist
        return {"meetings": [], "tasks": [], "course_codes": []}
    except Exception as e:
        logger.error(f"Error loading schedule: {str(e)}")
        raise

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
    
    # Check tasks - only ask for course code for preparation tasks
    for task in schedule.get("tasks", []):
        if not task.get("course_code") and task.get("type") in ["exam_preparation", "presentation_preparation"]:
            questions.append({
                "type": "course_code",
                "question": f"What is the course code for the {task.get('description')}?",
                "field": "course_code",
                "target": task.get("description"),
                "target_type": "task",
                "target_id": task.get("id")
            })
    
    return questions

def clean_schedule(schedule: dict) -> dict:
    """Remove missing_info fields from the schedule"""
    schedule = deepcopy(schedule)
    
    for meeting in schedule.get("meetings", []):
        if "missing_info" in meeting:
            del meeting["missing_info"]
    
    for task in schedule.get("tasks", []):
        if "missing_info" in task:
            del task["missing_info"]
    
    return schedule

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

def ensure_ids(schedule):
    """Ensure all items in the schedule have unique IDs."""
    if not schedule:
        return schedule
        
    # Handle meetings
    if 'meetings' in schedule:
        for meeting in schedule['meetings']:
            if 'id' not in meeting or not meeting['id']:
                meeting['id'] = str(uuid.uuid4())
                
    # Handle tasks
    if 'tasks' in schedule:
        for task in schedule['tasks']:
            if 'id' not in task or not task['id']:
                task['id'] = str(uuid.uuid4())
                
    return schedule

@app.route('/parse-schedule', methods=['POST'])
def parse_schedule():
    try:
        data = request.get_json()
        logger.debug(f"Received data: {data}")
        
        if not data or 'text' not in data:
            logger.error("Missing text parameter in request")
            return jsonify({'error': 'Missing text parameter'}), 400

        # Prepare prompt for IEP1
        prompt = f"{PARSING_PROMPT}\n\nSchedule text:\n{data['text']}"
        logger.debug(f"Sending request to IEP1 with prompt length: {len(prompt)}")

        # Call IEP1 for parsing
        try:
            logger.debug(f"Making request to IEP1 at {IEP1_URL}/predict")
            response = requests.post(
                f"{IEP1_URL}/predict",
                json={'prompt': prompt},
                timeout=30
            )
            logger.debug(f"IEP1 response status: {response.status_code}")
            logger.debug(f"IEP1 response content: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"IEP1 returned error: {response.text}")
                return jsonify({'error': f'IEP1 error: {response.text}'}), response.status_code
                
            response.raise_for_status()
            
            # Get the response text and clean it
            try:
                response_text = response.json()
                logger.debug(f"Cleaned response text: {response_text}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode IEP1 response as JSON: {e}")
                return jsonify({'error': 'Invalid JSON response from IEP1'}), 500
            
            # If the response is wrapped in markdown code blocks, extract the JSON
            if isinstance(response_text, str):
                if response_text.startswith('```'):
                    # Extract the JSON string between the code blocks
                    json_str = response_text.split('```')[1]
                    if json_str.startswith('json\n'):
                        json_str = json_str[5:]
                    try:
                        parsed_data = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from markdown: {e}")
                        return jsonify({'error': 'Invalid JSON in markdown response'}), 500
                else:
                    # If it's a string but not markdown, try parsing it as JSON
                    try:
                        parsed_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from string: {e}")
                        return jsonify({'error': 'Invalid JSON in response'}), 500
            else:
                # If it's already a dict/object, use it as is
                parsed_data = response_text
            
            # Validate the parsed data
            if not isinstance(parsed_data, dict):
                logger.error(f"Parsed data is not a dictionary: {type(parsed_data)}")
                return jsonify({'error': 'Invalid response format from IEP1'}), 500
            
            # Ensure all items have IDs
            parsed_data = ensure_ids(parsed_data)
            
            # Check for missing information
            questions = check_missing_info(parsed_data)
            
            if questions:
                return jsonify({
                    'status': 'questions_needed',
                    'questions': questions,
                    'schedule': parsed_data
                })
            
            # Save the parsed schedule
            try:
                save_schedule(parsed_data)
            except Exception as e:
                logger.error(f"Failed to save schedule: {e}")
                return jsonify({'error': 'Failed to save schedule'}), 500
            
            return jsonify({
                'status': 'complete',
                'schedule': parsed_data
            })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with IEP1: {str(e)}")
            return jsonify({'error': f'Error communicating with IEP1: {str(e)}'}), 500
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from IEP1: {str(e)}")
            return jsonify({'error': f'Invalid JSON response from IEP1: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/modify-schedule', methods=['POST'])
def modify_schedule():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing text parameter"}), 400
            
        # Load current schedule
        current_schedule = load_schedule()
        if not current_schedule:
            return jsonify({"error": "No schedule found to modify"}), 404
            
        # Create prompt for IEP1
        prompt = f"{PARSING_PROMPT}\n\nSchedule text:\n{data['text']}"
        
        # Call IEP1 for parsing
        response = requests.post(
            f"{IEP1_URL}/predict",
            json={"prompt": prompt},
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"IEP1 error: {response.text}"}), 500
            
        # Parse the response
        try:
            response_text = response.json()
            if isinstance(response_text, str):
                if response_text.startswith('```'):
                    json_str = response_text.split('```')[1]
                    if json_str.startswith('json\n'):
                        json_str = json_str[5:]
                    new_schedule = json.loads(json_str)
                else:
                    new_schedule = json.loads(response_text)
            else:
                new_schedule = response_text
                
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
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return jsonify({"error": "Invalid JSON response from IEP1"}), 500
            
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return jsonify({"error": f"Request error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
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

@app.route('/answer-question', methods=['POST'])
def answer_question():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        logger.info(f"Processing answer for {data.get('type', 'unknown')} question")

        # Load current schedule
        schedule = load_schedule()
        if not schedule:
            return jsonify({'error': 'No schedule found'}), 404

        # Update the schedule with the answer
        item_id = data.get('item_id')
        answer_type = data.get('type')
        answer_value = data.get('answer')

        if not all([item_id, answer_type, answer_value]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Find and update the item
        updated = False
        for item_list in [schedule.get('meetings', []), schedule.get('tasks', [])]:
            for item in item_list:
                if item.get('id') == item_id:
                    if answer_type == 'time':
                        item['time'] = convert_to_24h(answer_value)
                    elif answer_type == 'duration':
                        try:
                            item['duration_minutes'] = int(answer_value)
                        except ValueError:
                            return jsonify({'error': 'Invalid duration value'}), 400
                    elif answer_type == 'course_code':
                        item['course_code'] = answer_value

                    # Remove the field from missing_info
                    field_map = {
                        'time': 'time',
                        'duration': 'duration_minutes',
                        'course_code': 'course_code'
                    }
                    if field_map[answer_type] in item.get('missing_info', []):
                        item['missing_info'].remove(field_map[answer_type])
                    updated = True
                    break
            if updated:
                break

        if not updated:
            return jsonify({'error': 'Item not found'}), 404

        # Save the updated schedule
        save_schedule(schedule)

        # Check if there are more questions
        questions = check_missing_info(schedule)
        
        return jsonify({
            'success': True,
            'has_more_questions': len(questions) > 0,
            'questions': questions if questions else None,
            'schedule': schedule
        })

    except Exception as e:
        logger.error(f"Error processing answer: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/handle-missing-info', methods=['POST'])
def handle_missing_info():
    try:
        data = request.get_json()
        logger.debug(f"Received missing info data: {data}")
        
        if not data or 'schedule' not in data or 'answer' not in data:
            logger.error("Missing required parameters in request")
            return jsonify({'error': 'Missing required parameters'}), 400
            
        schedule = data['schedule']
        answer = data['answer']
        
        # Update the schedule with the answer
        updated_schedule = update_schedule_with_answers(schedule, [answer])
        
        # Check if there are more missing fields
        remaining_questions = check_missing_info(updated_schedule)
        
        # If no more questions, clean the schedule before returning
        if not remaining_questions:
            updated_schedule = clean_schedule(updated_schedule)
            return jsonify({
                'schedule': updated_schedule,
                'complete': True
            })
        
        # Return the next question
        return jsonify({
            'schedule': updated_schedule,
            'next_question': remaining_questions[0],
            'complete': False
        })
        
    except Exception as e:
        logger.error(f"Error handling missing info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/store-schedule', methods=['POST'])
def store_schedule_endpoint():
    try:
        data = request.get_json()
        if not data or 'schedule' not in data:
            return jsonify({'error': 'No schedule provided'}), 400

        schedule = data['schedule']
        
        # Ensure all items have IDs
        schedule = ensure_ids(schedule)
        
        # Save the schedule
        save_schedule(schedule)
        
        return jsonify({
            'status': 'success',
            'schedule': schedule
        })
        
    except Exception as e:
        logger.error(f"Error storing schedule: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 