from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from copy import deepcopy
import logging
from prompts import PARSING_PROMPT
from preference_questions import get_preference_questions, get_algorithm_questions, get_default_preferences
from helpers import save_schedule, load_schedule, convert_to_24h, validate_and_fix_times, check_missing_info, clean_missing_info_from_tasks, clean_schedule, convert_answer_value, update_schedule_with_answers, ensure_ids, STORAGE_PATH, FINAL_PATH
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
IEP2_URL = os.getenv('IEP2_URL', 'http://localhost:5004')
logger.debug(f"Using IEP1_URL: {IEP1_URL}")
logger.debug(f"Using IEP2_URL: {IEP2_URL}")

# -------------------------------
# Parsing and Storage Endpoints
# -------------------------------
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
            
            # Ensure all items have IDs
            response_text = ensure_ids(response_text)
            
            # Check for missing information
            questions = check_missing_info(response_text)
            
            if questions:
                return jsonify({
                    'status': 'questions_needed',
                    'questions': questions,
                    'schedule': response_text
                })
            
            # Save the parsed schedule
            try:
                save_schedule(response_text)
            except Exception as e:
                logger.error(f"Failed to save schedule: {e}")
                return jsonify({'error': 'Failed to save schedule'}), 500
            
            return jsonify({
                'status': 'complete',
                'schedule': response_text
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

@app.route('/store-schedule', methods=['POST'])
def store_schedule_endpoint():
    try:
        data = request.get_json()
        if not data or 'schedule' not in data:
            return jsonify({'error': 'No schedule provided'}), 400

        schedule = data['schedule']
        schedule = ensure_ids(schedule)
        save_schedule(schedule)
        return jsonify({
            'status': 'success',
            'schedule': schedule
        })
    except Exception as e:
        logger.error(f"Error storing schedule: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/get-schedule', methods=['GET'])
def get_schedule():
    try:
        schedule = load_schedule(FINAL_PATH)
        if not schedule:
            return jsonify({'error': 'No schedule found'}), 404
            
        return jsonify({
            'status': 'success',
            'schedule': schedule
        })
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------------
# Missing Information and Answer Endpoints
# -------------------------------
@app.route('/answer-question', methods=['POST'])
def answer_question():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        logger.info(f"Processing answer for {data.get('type', 'unknown')} question")

        schedule = load_schedule()
        if not schedule:
            return jsonify({'error': 'No schedule found'}), 404

        item_id = data.get('item_id')
        answer_type = data.get('type')
        answer_value = data.get('answer')

        if not all([item_id, answer_type, answer_value]):
            return jsonify({'error': 'Missing required fields'}), 400

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

        save_schedule(schedule)
        questions = check_missing_info(schedule)
        if not questions:
            schedule = clean_schedule(schedule)
            save_schedule(schedule)
        return jsonify({
            'success': True,
            'has_more_questions': len(questions) > 0,
            'questions': questions if questions else None,
            'schedule': schedule,
            'ready_for_optimization': len(questions) == 0
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
        
        updated_schedule = update_schedule_with_answers(schedule, [answer])
        remaining_questions = check_missing_info(updated_schedule)
        if not remaining_questions:
            updated_schedule = clean_schedule(updated_schedule)
            return jsonify({
                'schedule': updated_schedule,
                'complete': True
            })
        return jsonify({
            'schedule': updated_schedule,
            'next_question': remaining_questions[0],
            'complete': False
        })
            
    except Exception as e:
        logger.error(f"Error handling missing info: {str(e)}")
        return jsonify({'error': str(e)}), 500

# -------------------------------
# Preferences and Optimization Endpoints
# -------------------------------
@app.route('/preference-questions', methods=['GET'])
def get_preference_questions_endpoint():
    try:
        preferences = get_preference_questions()
        algorithm = get_algorithm_questions()
        return jsonify({
            "preference_questions": preferences,
            "algorithm_questions": algorithm
        })
    except Exception as e:
        logger.error(f"Error getting preference questions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate-optimized-schedule', methods=['POST'])
def generate_optimized_schedule():
    try:
        data = request.get_json()
        if not data or 'schedule' not in data:
            schedule = load_schedule()
        else:
            schedule = data['schedule']
            
        if not schedule:
            return jsonify({'error': 'No schedule found'}), 404
            
        questions = check_missing_info(schedule)
        if questions:
            return jsonify({
                'error': 'Schedule is incomplete',
                'questions': questions
            }), 400
            
        preferences = data.get('preferences', {})
        if not preferences:
            preferences = get_default_preferences()
            logger.info("Using default preferences for schedule generation")
        
        cleaned_schedule = clean_schedule(schedule)
        logger.info(f"Cleaned schedule: {json.dumps(cleaned_schedule, indent=2)}")
        
        iep2_data = {
            'schedule': cleaned_schedule,
            'preferences': preferences
        }

        logger.info("Calling IEP2 to generate optimized schedule")
        response = requests.post(
            f"{IEP2_URL}/api/generate",
            json=iep2_data,
            timeout=30
        )
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Error from IEP2: {error_text}")
            try:
                error_json = response.json()
                logger.error(f"Detailed IEP2 error: {json.dumps(error_json, indent=2)}")
            except Exception as e:
                logger.error(f"Could not parse IEP2 error response as JSON: {e}")
            return jsonify({'error': f'IEP2 error: {error_text}'}), response.status_code
            
        optimized_schedule = response.json()
        save_schedule(optimized_schedule, FINAL_PATH)
        return jsonify({
            'status': 'success',
            'schedule': optimized_schedule
        })
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with IEP2: {str(e)}")
        return jsonify({
            'error': f'Error communicating with IEP2: {str(e)}'
        }), 500
    except Exception as e:
        logger.error(f"Error generating optimized schedule: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# -------------------------------
# Health Endpoint
# -------------------------------
@app.route('/health', methods=['GET'])
def health():
    try:
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

# -------------------------------
# Reset Stored Schedule Endpoint
# -------------------------------
@app.route('/reset-stored-schedule', methods=['POST'])
def reset_stored_schedule():
    import os
    try:
        # Delete the final schedule file
        if os.path.exists(FINAL_PATH):
            os.remove(FINAL_PATH)
            logger.info("Deleted final_schedule.json")
        else:
            logger.info("final_schedule.json not found")
        
        # Delete the latest schedule file (assuming it's in the same directory)
        latest_path = os.path.join(os.path.dirname(FINAL_PATH), 'latest_schedule.json')
        if os.path.exists(latest_path):
            os.remove(latest_path)
            logger.info("Deleted latest_schedule.json")
        else:
            logger.info("latest_schedule.json not found")
        
        return jsonify({"status": "stored schedule reset"}), 200
    except Exception as e:
        logger.error("Error resetting stored schedule:", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 