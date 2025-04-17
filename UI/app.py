from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import logging
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5002", "http://127.0.0.1:5002"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Service URLs
EEP1_URL = os.getenv('EEP1_URL', 'http://localhost:5000')
IEP2_URL = os.getenv('IEP2_URL', 'http://localhost:5004')
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:5004')

# Add state management
current_schedule = None

logger.debug(f"Using EEP1_URL: {EEP1_URL}")
logger.debug(f"Using IEP2_URL: {IEP2_URL}")
logger.debug(f"Using AUTH_SERVICE_URL: {AUTH_SERVICE_URL}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule-only')
def schedule_only():
    return render_template('schedule-only.html')

@app.route('/parse-schedule', methods=['POST'])
def parse_schedule():
    global current_schedule
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        logger.info(f"Sending parse request to EEP1 with text: {data['text'][:100]}...")
        
        # Send to EEP1 for parsing
        response = requests.post(f'{EEP1_URL}/parse-schedule', json=data, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        
        logger.info(f"Received response from EEP1: {response_data}")
        
        # Store the schedule
        if 'schedule' in response_data:
            current_schedule = response_data['schedule']
            logger.info(f"Updated current schedule with new data")
            logger.debug(f"Current schedule: {current_schedule}")

            # Store the schedule in EEP1
            store_response = requests.post(f'{EEP1_URL}/store-schedule', json={'schedule': current_schedule}, timeout=30)
            if store_response.ok:
                logger.info("Successfully stored schedule in EEP1")
            else:
                logger.warning(f"Failed to store schedule in EEP1: {store_response.text}")
        else:
            logger.warning("No schedule in response data")
            
        return jsonify(response_data)

    except requests.exceptions.Timeout:
        logger.error("Request to EEP1 timed out")
        return jsonify({'error': 'Request timed out'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to EEP1 failed: {str(e)}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/get-schedule', methods=['GET'])
def get_schedule():
    try:
        if current_schedule:
            return jsonify({'schedule': current_schedule})
            
        response = requests.get(f'{EEP1_URL}/get-schedule', timeout=30)
        response.raise_for_status()
        return jsonify(response.json())

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/answer-question', methods=['POST'])
def answer_question():
    """Answer a question about missing information in the schedule"""
    global current_schedule
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        logger.info(f"Processing answer for {data.get('type', 'unknown')} question")

        # First, try to get the current schedule from EEP1
        try:
            schedule_response = requests.get(f'{EEP1_URL}/get-schedule', timeout=10)
            if schedule_response.ok:
                current_schedule = schedule_response.json().get('schedule')
                logger.info("Retrieved current schedule from EEP1")
            else:
                logger.warning("Could not retrieve schedule from EEP1, using local schedule")
        except Exception as e:
            logger.warning(f"Error getting schedule from EEP1: {str(e)}")

        # Use the schedule from the request if provided, otherwise use current_schedule
        schedule = data.get('schedule', current_schedule)
        if not schedule:
            logger.error("No schedule available")
            return jsonify({"error": "No schedule available"}), 400

        # Construct request data for EEP1
        request_data = {
            'item_id': data['item_id'],
            'type': data['type'],
            'answer': data['answer'],
            'field': data.get('field'),
            'target': data.get('target'),
            'target_type': data.get('target_type'),
            'schedule': schedule
        }

        # Remove None values
        request_data = {k: v for k, v in request_data.items() if v is not None}

        logger.debug(f"Sending request to EEP1: {request_data}")

        # Send request to EEP1
        response = requests.post(
            f'{EEP1_URL}/answer-question',
            json=request_data,
            timeout=10
        )

        # Log response for debugging
        logger.debug(f"EEP1 response status: {response.status_code}")
        logger.debug(f"EEP1 response content: {response.text}")

        if not response.ok:
            error_msg = "Error from EEP1"
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                error_msg = response.text or error_msg
            logger.error(f"EEP1 error: {error_msg}")
            return jsonify({"error": error_msg}), response.status_code

        response_data = response.json()
        
        # Log the full EEP1 response for debugging
        logger.info(f"Received response from EEP1 with keys: {list(response_data.keys())}")
        
        # Update current schedule if provided in response
        if 'schedule' in response_data:
            current_schedule = response_data['schedule']
            logger.debug(f"Updated current_schedule with response data")

            # Store the updated schedule in EEP1
            try:
                store_response = requests.post(f'{EEP1_URL}/store-schedule', json={'schedule': current_schedule}, timeout=10)
                if store_response.ok:
                    logger.info("Successfully stored updated schedule in EEP1")
                else:
                    logger.warning(f"Failed to store updated schedule in EEP1: {store_response.text}")
            except Exception as e:
                logger.warning(f"Error storing schedule in EEP1: {str(e)}")

        # Pass the ready_for_optimization flag from EEP1 to the frontend
        ready_for_optimization = response_data.get('ready_for_optimization', False)
        logger.info(f"IMPORTANT - ready_for_optimization flag from EEP1: {ready_for_optimization}")

        # Check if all questions have been answered
        has_more_questions = response_data.get('has_more_questions', True)
        logger.info(f"IMPORTANT - has_more_questions flag from EEP1: {has_more_questions}")

        # Construct response to frontend
        frontend_response = {
            "success": True,
            "schedule": response_data.get('schedule'),
            "message": "Answer submitted successfully",
            "ready_for_optimization": ready_for_optimization,
            "has_more_questions": has_more_questions,
            "questions": response_data.get('questions')
        }
        
        logger.info(f"Sending response to frontend with ready_for_optimization={ready_for_optimization}")
        return jsonify(frontend_response)

    except requests.Timeout:
        logger.error("Timeout while connecting to EEP1")
        return jsonify({"error": "Timeout while connecting to EEP1"}), 504
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

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

@app.route('/preference-questions', methods=['GET'])
def preference_questions():
    """Get preference questions from EEP1."""
    global current_schedule
    
    try:
        logger.info("Getting preference questions from EEP1")
        
        # Check if we have a schedule
        if not current_schedule:
            try:
                # Try to retrieve from EEP1
                schedule_response = requests.get(f'{EEP1_URL}/get-schedule', timeout=10)
                if schedule_response.ok:
                    current_schedule = schedule_response.json().get('schedule')
                    logger.info("Retrieved current schedule from EEP1")
                else:
                    logger.error("No schedule available and couldn't retrieve from EEP1")
                    return jsonify({"error": "No schedule available"}), 400
            except Exception as e:
                logger.error(f"Error getting schedule from EEP1: {str(e)}")
                return jsonify({"error": f"Failed to get schedule: {str(e)}"}), 500
        
        # Call EEP1 to get preference questions
        try:
            logger.info(f"Making request to {EEP1_URL}/preference-questions")
            response = requests.get(
                f'{EEP1_URL}/preference-questions', 
                timeout=15
            )
            
            if not response.ok:
                error_message = f"EEP1 returned error status: {response.status_code}"
                try:
                    error_data = response.json()
                    error_message = f"{error_message}, message: {error_data.get('error', 'Unknown error')}"
                except:
                    error_message = f"{error_message}, raw response: {response.text[:200]}"
                
                logger.error(error_message)
                return jsonify({"error": error_message}), response.status_code
            
            response_data = response.json()
            logger.info(f"Successfully received preference questions from EEP1")
            
            return jsonify(response_data)
            
        except requests.Timeout:
            logger.error("Timeout while connecting to EEP1 for preference questions")
            return jsonify({"error": "Timeout while connecting to EEP1"}), 504
        except requests.RequestException as e:
            logger.error(f"Request error while getting preference questions: {str(e)}")
            return jsonify({"error": f"Request failed: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Unexpected error in preference_questions: {str(e)}", exc_info=True)
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/generate-optimized-schedule', methods=['POST'])
def generate_optimized_schedule():
    """Generate an optimized schedule using EEP1 service, which will call IEP2."""
    global current_schedule
    try:
        data = request.get_json()
        logger.info("Generating optimized schedule")
        
        # Get the schedule from the request or use current_schedule
        schedule = data.get('schedule', current_schedule)
        if not schedule:
            logger.error("No schedule available for optimization")
            return jsonify({"error": "No schedule available"}), 400
            
        # Get preferences from the request
        preferences = data.get('preferences', {})
        if not preferences:
            logger.warning("No preferences provided, using defaults")
            preferences = {
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
        
        logger.info(f"Using preferences: {preferences}")
        
        # Call EEP1 to generate optimized schedule (it will call IEP2 internally)
        logger.info("Calling EEP1 to generate optimized schedule")
        
        response = requests.post(
            f'{EEP1_URL}/generate-optimized-schedule',
            json={
                'schedule': schedule,
                'preferences': preferences
            },
            timeout=30  # Longer timeout for schedule generation
        )
        
        if not response.ok:
            error_msg = "Error from EEP1"
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                error_msg = response.text or error_msg
            logger.error(f"EEP1 error: {error_msg}")
            return jsonify({"error": error_msg}), response.status_code
            
        response_data = response.json()
        
        # Ensure we got a schedule back
        if 'schedule' not in response_data:
            logger.error("No schedule returned from EEP1")
            return jsonify({"error": "No schedule returned from optimization service"}), 500
        
        # Update current schedule with optimized schedule
        current_schedule = response_data['schedule']
        logger.info("Updated current schedule with optimized schedule")
        
        return jsonify(response_data)
        
    except requests.Timeout:
        logger.error("Timeout while connecting to EEP1")
        return jsonify({"error": "Timeout while connecting to EEP1"}), 504
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True) 