from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import logging

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
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:5004')

# Add state management
current_schedule = None

logger.debug(f"Using EEP1_URL: {EEP1_URL}")
logger.debug(f"Using AUTH_SERVICE_URL: {AUTH_SERVICE_URL}")

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/modify-schedule', methods=['POST'])
def modify_schedule():
    global current_schedule
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        response = requests.post(f'{EEP1_URL}/modify-schedule', json=data, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        
        # Store the schedule
        if 'schedule' in response_data:
            current_schedule = response_data['schedule']
            logger.info("Updated current schedule from modify-schedule")
            
        return jsonify(response_data)

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
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
    global current_schedule
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No data provided"}), 400

        # Log received data for debugging
        logger.debug(f"Received answer data: {data}")

        # Check required fields
        required_fields = ['item_id', 'type', 'answer']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({"error": f"Missing required fields: {missing_fields}"}), 400

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

        return jsonify({
            "success": True,
            "schedule": response_data.get('schedule'),
            "message": "Answer submitted successfully"
        })

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True) 