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
from schedule_prompts import get_schedule_prompt, get_response_parsing_prompt

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

        # DEBUG: Log the initial state of tasks
        logger.info("INITIAL TASKS STATE:")
        for task in schedule.get('tasks', []):
            logger.info(f"Task: {task.get('description')}, course_code: {task.get('course_code')}, missing_info: {task.get('missing_info')}, related_event: {task.get('related_event')}")

        item_id = data.get('item_id')
        answer_type = data.get('type')
        answer_value = data.get('answer')

        if not all([item_id, answer_type, answer_value]):
            return jsonify({'error': 'Missing required fields'}), 400

        updated = False
        for item_list in [schedule.get('meetings', []), schedule.get('tasks', [])]:
            for item in item_list:
                if item.get('id') == item_id:
                    logger.info(f"Found item to update: {item.get('description')}, type: {'meeting' if item_list == schedule.get('meetings', []) else 'task'}")
                    
                    if answer_type == 'time':
                        item['time'] = convert_to_24h(answer_value)
                    elif answer_type == 'duration':
                        try:
                            item['duration_minutes'] = int(answer_value)
                        except ValueError:
                            return jsonify({'error': 'Invalid duration value'}), 400
                    elif answer_type == 'course_code':
                        logger.info(f"Updating course_code for {item.get('description')} to {answer_value}")
                        item['course_code'] = answer_value
                        
                        # If this is a meeting with a course code, propagate to related tasks
                        if item_list == schedule.get('meetings', []):
                            meeting_description = item.get('description')
                            logger.info(f"Looking for tasks related to meeting: {meeting_description}")
                            # Find and update any tasks related to this meeting
                            for task in schedule.get('tasks', []):
                                # Use partial matching: if meeting description is contained within related_event
                                # or if related_event is contained within meeting description
                                task_related_event = task.get('related_event', '')
                                if (meeting_description and task_related_event and 
                                   (meeting_description in task_related_event or 
                                    task_related_event in meeting_description)):
                                    logger.info(f"Found related task: {task.get('description')}, missing_info before: {task.get('missing_info')}")
                                    task['course_code'] = answer_value
                                    # Also remove course_code from the task's missing_info array if present
                                    if 'missing_info' in task and 'course_code' in task['missing_info']:
                                        task['missing_info'].remove('course_code')
                                        logger.info(f"Removed course_code from missing_info, now: {task.get('missing_info')}")
                                        # If missing_info is now empty, remove it entirely
                                        if not task['missing_info']:
                                            del task['missing_info']
                                            logger.info("Deleted empty missing_info array")
                                    else:
                                        logger.info(f"No course_code in missing_info or no missing_info field")
                                    logger.info(f"Propagated course code {answer_value} to task {task.get('description')}")

                    field_map = {
                        'time': 'time',
                        'duration': 'duration_minutes',
                        'course_code': 'course_code'
                    }
                    if field_map[answer_type] in item.get('missing_info', []):
                        item['missing_info'].remove(field_map[answer_type])
                        logger.info(f"Removed {field_map[answer_type]} from missing_info of {item.get('description')}")
                    updated = True
                    break
            if updated:
                break
        if not updated:
            return jsonify({'error': 'Item not found'}), 404

        save_schedule(schedule)
        
        # DEBUG: Log the state after updates
        logger.info("TASKS STATE AFTER UPDATES:")
        for task in schedule.get('tasks', []):
            logger.info(f"Task: {task.get('description')}, course_code: {task.get('course_code')}, missing_info: {task.get('missing_info')}, related_event: {task.get('related_event')}")
        
        questions = check_missing_info(schedule)
        
        # DEBUG: Log the questions generated
        logger.info(f"Questions generated by check_missing_info: {questions}")
        
        if not questions:
            schedule = clean_schedule(schedule)
            save_schedule(schedule)
            logger.info("No questions remaining, schedule cleaned")
        
        # DEBUG: Log final state before returning
        logger.info("FINAL TASKS STATE:")
        for task in schedule.get('tasks', []):
            logger.info(f"Task: {task.get('description')}, course_code: {task.get('course_code')}, missing_info: {task.get('missing_info')}")
        
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

@app.route('/construct-schedule-prompt', methods=['POST'])
def construct_schedule_prompt():
    """
    Construct a prompt for the LLM based on schedule data and preferences.
    This is called by IEP2 before it makes the LLM API call.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Extract schedule data
        if 'schedule' in data:
            schedule_data = data['schedule']
        else:
            # If not wrapped in 'schedule', create a structure
            schedule_data = {
                'meetings': data.get('meetings', []),
                'tasks': data.get('tasks', []),
                'course_codes': data.get('course_codes', [])
            }
            
        # Check if we have both meetings and tasks
        if 'meetings' not in schedule_data or 'tasks' not in schedule_data:
            return jsonify({
                'error': 'Invalid schedule format',
                'message': 'Schedule must contain "meetings" and "tasks" arrays'
            }), 400
            
        # Get preferences
        preferences = data.get('preferences', get_default_preferences())
        
        # Apply any business logic needed before creating the prompt
        # For example, ensure all tasks and meetings have IDs
        for collection in ['meetings', 'tasks']:
            for item in schedule_data.get(collection, []):
                if 'id' not in item or not item['id']:
                    item['id'] = str(uuid.uuid4())
                    
        # Pre-process task durations
        for task in schedule_data.get('tasks', []):
            if task.get('duration_minutes') in [None, '', 'null']:
                priority = task.get('priority', 'medium').lower()
                task['duration_minutes'] = 240 if priority in ['high', '1', 'urgent'] else 180
                
        # Ensure all meetings have required fields
        for meeting in schedule_data.get('meetings', []):
            if not meeting.get('duration') and meeting.get('duration_minutes'):
                meeting['duration'] = meeting['duration_minutes']
                
        # Build the prompt using the helper function
        prompt = get_schedule_prompt(schedule_data, preferences)
        
        logger.info(f"Generated prompt with length: {len(prompt)}")
        
        return jsonify({
            'prompt': prompt,
            'schedule_data': schedule_data,
            'preferences': preferences
        })
        
    except Exception as e:
        logger.error(f"Error constructing prompt: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
        
@app.route('/parse-schedule-llm-response', methods=['POST'])
def parse_schedule_llm_response():
    """
    Parse and validate the LLM's response, ensuring it follows the correct format.
    This is called by IEP2 after it receives the LLM response.
    """
    try:
        data = request.get_json()
        if not data or 'original_data' not in data:
            return jsonify({'error': 'Missing required data'}), 400
            
        original_data = data['original_data']
        
        # Handle different response formats based on what's provided
        if 'llm_response' in data:
            # Direct text response (old format)
            llm_response = data['llm_response']
        else:
            # Raw Anthropic API response (new format)
            anthropic_response = data.get('response', {})
            # Extract text from content array in Anthropic response
            content_list = anthropic_response.get('content', [])
            if content_list and isinstance(content_list, list) and len(content_list) > 0:
                llm_response = content_list[0].get('text', '')
            else:
                return jsonify({'error': 'Could not extract text from Anthropic response'}), 400
        
        # Extract generated calendar from LLM response
        generated_calendar = None
        
        # First attempt: try to parse the response directly as JSON
        try:
            # Try to find a JSON object in the response
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                parsed_response = json.loads(json_str)
                
                # Check if it's a complete calendar object or just the generated_calendar
                if "generated_calendar" in parsed_response:
                    generated_calendar = parsed_response["generated_calendar"]
                else:
                    # Assume the entire object is the calendar
                    generated_calendar = parsed_response
            else:
                logger.warning("Could not find JSON in LLM response")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            
        # If we couldn't parse it, we need further processing
        if not generated_calendar:
            # Call IEP1 to help parse the response
            try:
                parsing_prompt = get_response_parsing_prompt(llm_response, original_data)
                
                parsing_response = requests.post(
                    f"{IEP1_URL}/predict",
                    json={'prompt': parsing_prompt},
                    timeout=30
                )
                
                if parsing_response.status_code != 200:
                    return jsonify({'error': f'Failed to parse LLM response: {parsing_response.text}'}), 500
                    
                parsed_result = parsing_response.json()
                
                # Try to extract the JSON part from the parsing result
                if isinstance(parsed_result, str):
                    json_start = parsed_result.find('{')
                    json_end = parsed_result.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = parsed_result[json_start:json_end]
                        parsed_json = json.loads(json_str)
                        
                        if "schedule" in parsed_json and "generated_calendar" in parsed_json["schedule"]:
                            generated_calendar = parsed_json["schedule"]["generated_calendar"]
                else:
                    # If it's already a dict
                    if "schedule" in parsed_result and "generated_calendar" in parsed_result["schedule"]:
                        generated_calendar = parsed_result["schedule"]["generated_calendar"]
                
            except Exception as e:
                logger.error(f"Error parsing LLM response with IEP1: {str(e)}", exc_info=True)
                
        # If we still don't have a calendar, return an error
        if not generated_calendar:
            return jsonify({'error': 'Could not extract valid schedule from LLM response'}), 500
            
        # Now construct the final response
        if 'schedule' in original_data:
            schedule_out = original_data['schedule']
        else:
            schedule_out = {
                'meetings': original_data.get('meetings', []),
                'tasks': original_data.get('tasks', []),
                'course_codes': original_data.get('course_codes', [])
            }
            
        # Add the generated calendar
        schedule_out['generated_calendar'] = generated_calendar
        
        # Construct the complete response
        result = {
            'success': True,
            'schedule': schedule_out,
            'message': 'Schedule successfully generated using LLM'
        }
        
        # Save the final schedule
        save_schedule(schedule_out, FINAL_PATH)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error parsing LLM response: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/generate-optimized-schedule', methods=['POST'])
def generate_optimized_schedule():
    """Generate an optimized schedule using EEP1 service, which will call IEP2."""
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
        logger.info("Preparing to generate schedule...")
        
        # Step 1: Generate the prompt directly (don't call our own API)
        try:
            # Prepare schedule data and ensure IDs
            for collection in ['meetings', 'tasks']:
                for item in cleaned_schedule.get(collection, []):
                    if 'id' not in item or not item['id']:
                        item['id'] = str(uuid.uuid4())
                        
            # Pre-process task durations
            for task in cleaned_schedule.get('tasks', []):
                if task.get('duration_minutes') in [None, '', 'null']:
                    priority = task.get('priority', 'medium').lower()
                    task['duration_minutes'] = 240 if priority in ['high', '1', 'urgent'] else 180
                    
            # Ensure all meetings have required fields
            for meeting in cleaned_schedule.get('meetings', []):
                if not meeting.get('duration') and meeting.get('duration_minutes'):
                    meeting['duration'] = meeting['duration_minutes']
                    
            # Generate the prompt directly
            prompt = get_schedule_prompt(cleaned_schedule, preferences)
            logger.info(f"Generated prompt with length: {len(prompt)}")
            
        except Exception as e:
            logger.error(f"Error generating prompt: {str(e)}")
            return jsonify({'error': f'Failed to generate prompt: {str(e)}'}), 500
        
        if not prompt:
            return jsonify({'error': 'Failed to generate prompt - empty result'}), 500
        
        # Step 2: Call IEP2 with the prompt
        logger.info(f"Calling IEP2 with prompt length: {len(prompt)}")
        try:
            iep2_response = requests.post(
                f"{IEP2_URL}/api/generate",
                json={
                    'prompt': prompt,
                    'max_tokens': 4000,
                    'temperature': 0.2
                },
                timeout=60  # Longer timeout for Anthropic API
            )
            
            if iep2_response.status_code != 200:
                logger.error(f"IEP2 error: {iep2_response.text}")
                return jsonify({'error': f'IEP2 error: {iep2_response.text}'}), iep2_response.status_code
                
            # Get the raw Anthropic API response
            anthropic_response = iep2_response.json()
            logger.info("Received response from IEP2, extracting text from response")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling IEP2: {str(e)}")
            return jsonify({'error': f'Error calling IEP2: {str(e)}'}), 500
        
        # Step 3: Extract the text from the Anthropic response
        content_list = anthropic_response.get('content', [])
        if not content_list or not isinstance(content_list, list) or len(content_list) == 0:
            logger.error(f"Invalid response format from IEP2: {anthropic_response}")
            return jsonify({'error': 'Invalid response format from IEP2'}), 500
            
        llm_response = content_list[0].get('text', '')
        if not llm_response:
            logger.error("Empty text content in Anthropic response")
            return jsonify({'error': 'Empty response from Anthropic API'}), 500
            
        logger.info(f"Extracted text from Anthropic response (length: {len(llm_response)})")
        
        # Step 4: Parse the LLM response text
        try:
            # Extract generated calendar from LLM response
            generated_calendar = None
            
            # First attempt: try to parse the response directly as JSON
            try:
                # Try to find a JSON object in the response
                json_start = llm_response.find('{')
                json_end = llm_response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = llm_response[json_start:json_end]
                    parsed_response = json.loads(json_str)
                    
                    # Check if it's a complete calendar object or just the generated_calendar
                    if "generated_calendar" in parsed_response:
                        generated_calendar = parsed_response["generated_calendar"]
                    else:
                        # Assume the entire object is the calendar
                        generated_calendar = parsed_response
                else:
                    logger.warning("Could not find JSON in LLM response")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                
            # If we couldn't parse it, we need further processing
            if not generated_calendar:
                # Call IEP1 to help parse the response
                parsing_prompt = get_response_parsing_prompt(llm_response, {'schedule': cleaned_schedule, 'preferences': preferences})
                
                parsing_response = requests.post(
                    f"{IEP1_URL}/predict",
                    json={'prompt': parsing_prompt},
                    timeout=30
                )
                
                if parsing_response.status_code != 200:
                    return jsonify({'error': f'Failed to parse LLM response: {parsing_response.text}'}), 500
                    
                parsed_result = parsing_response.json()
                
                # Try to extract the JSON part from the parsing result
                if isinstance(parsed_result, str):
                    json_start = parsed_result.find('{')
                    json_end = parsed_result.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = parsed_result[json_start:json_end]
                        parsed_json = json.loads(json_str)
                        
                        if "schedule" in parsed_json and "generated_calendar" in parsed_json["schedule"]:
                            generated_calendar = parsed_json["schedule"]["generated_calendar"]
                else:
                    # If it's already a dict
                    if "schedule" in parsed_result and "generated_calendar" in parsed_result["schedule"]:
                        generated_calendar = parsed_result["schedule"]["generated_calendar"]
            
            # If we still don't have a calendar, return an error
            if not generated_calendar:
                return jsonify({'error': 'Could not extract valid schedule from LLM response'}), 500
                
            # Now construct the final schedule
            schedule_out = {
                'meetings': cleaned_schedule.get('meetings', []),
                'tasks': cleaned_schedule.get('tasks', []),
                'course_codes': cleaned_schedule.get('course_codes', []),
                'generated_calendar': generated_calendar
            }
            
            # Construct the complete response
            result = {
                'success': True,
                'schedule': schedule_out,
                'message': 'Schedule successfully generated using LLM'
            }
            
            # Save the final schedule
            save_schedule(schedule_out, FINAL_PATH)
            logger.info("Successfully generated and saved schedule")
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}", exc_info=True)
            return jsonify({'error': f'Error parsing LLM response: {str(e)}'}), 500
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with services: {str(e)}")
        return jsonify({
            'error': f'Error communicating with services: {str(e)}'
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