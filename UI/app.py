from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
from dotenv import load_dotenv
import logging
import uuid
from functools import wraps
import json
from datetime import datetime, timedelta

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
app.secret_key = "supersecretkey"

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    latest_schedule = db.Column(db.Text, nullable=True)  # New column to store latest final_schedule.json
    schedule_timestamp = db.Column(db.DateTime, nullable=True)  # New column to store timestamp when schedule was updated
    
    def __repr__(self):
        return f'<User {self.email}>'

# Create database tables
with app.app_context():
    # Only create tables if they don't exist
    db.create_all()
    logger.info("Database tables have been initialized")

CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5002", "http://127.0.0.1:5002"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Service URLs
EEP1_URL = os.getenv('EEP1_URL', 'http://localhost:5000')

# Add state management
current_schedule = None

logger.debug(f"Using EEP1_URL: {EEP1_URL}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def require_login():
    # List of allowed endpoint prefixes that don't require login
    allowed = ['login', 'register', 'static']
    # If no endpoint is set, return (could be 404)
    if not request.endpoint:
        return

    # If user is not in session and the endpoint does not start with any allowed prefix, redirect to login
    if 'user' not in session and not any(request.endpoint.startswith(ep) for ep in allowed):
        return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    user = User.query.filter_by(email=session['user']).first()
    if user and user.latest_schedule and user.schedule_timestamp and (datetime.utcnow() - user.schedule_timestamp < timedelta(days=7)):
        return render_template('schedule-only.html')
    else:
        return render_template('index.html')

@app.route('/schedule-only')
@login_required
def schedule_only():
    user = User.query.filter_by(email=session['user']).first()
    if not (user and user.latest_schedule and user.schedule_timestamp and (datetime.utcnow() - user.schedule_timestamp < timedelta(days=7))):
        return redirect(url_for('index'))
    return render_template('schedule-only.html')

@app.route('/parse-schedule', methods=['POST'])
@login_required
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
        
        # Debug: Log questions from EEP1
        if 'questions' in response_data:
            logger.info(f"Questions from EEP1: {json.dumps(response_data['questions'])}")
        else:
            logger.info("No questions in EEP1 response")
        
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

            # Update user's latest_schedule in the database
            user = User.query.filter_by(email=session['user']).first()
            if user:
                user.latest_schedule = json.dumps(response_data['schedule'])
                user.schedule_timestamp = datetime.utcnow()
                db.session.commit()
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
@login_required
def get_schedule():
    try:
        if current_schedule:
            return jsonify({'schedule': current_schedule})
        user = User.query.filter_by(email=session['user']).first()
        if user and user.latest_schedule:
            schedule = json.loads(user.latest_schedule)
            return jsonify({'schedule': schedule})
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
@login_required
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

            # If the answer was for a course code for a meeting, propagate it to related tasks
            if data.get('type') == 'course_code' and data.get('target_type') == 'meeting':
                meeting_description = data.get('target')
                course_code = data.get('answer')
                
                # Apply the course code to any preparation task related to this meeting
                if meeting_description and course_code:
                    for task in current_schedule.get('tasks', []):
                        if task.get('related_event') == meeting_description and not task.get('course_code'):
                            task['course_code'] = course_code
                            logger.info(f"Propagated course code {course_code} to task {task.get('description')}")
            
            # Store the updated schedule in EEP1
            try:
                store_response = requests.post(f'{EEP1_URL}/store-schedule', json={'schedule': current_schedule}, timeout=10)
                if store_response.ok:
                    logger.info("Successfully stored updated schedule in EEP1")
                else:
                    logger.warning(f"Failed to store updated schedule in EEP1: {store_response.text}")
            except Exception as e:
                logger.warning(f"Error storing schedule in EEP1: {str(e)}")

            # Update user's latest_schedule in the database
            user = User.query.filter_by(email=session['user']).first()
            if user:
                user.latest_schedule = json.dumps(response_data['schedule'])
                user.schedule_timestamp = datetime.utcnow()
                db.session.commit()

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
    questions = []
    
    # Log the schedule structure for debugging
    logger.info(f"Schedule structure - meetings: {len(schedule.get('meetings', []))}, tasks: {len(schedule.get('tasks', []))}")
    for task in schedule.get('tasks', []):
        logger.info(f"Task structure: {json.dumps(task)}")
    
    # Create mappings to track relationships and avoid redundant questions
    meeting_ids_with_missing_course = set()  # Track meeting IDs missing course codes
    meeting_descriptions = {}  # Map meeting IDs to descriptions
    related_tasks = {}  # Map meeting descriptions to their related task IDs
    
    # First pass: collect all meetings and their properties
    for meeting in schedule.get("meetings", []):
        meeting_id = meeting.get("id")
        description = meeting.get("description")
        if meeting_id and description:
            meeting_descriptions[meeting_id] = description
        
        # Track meetings missing course codes
        if not meeting.get("course_code") and meeting.get("type") in ["exam", "presentation"]:
            if meeting_id:
                meeting_ids_with_missing_course.add(meeting_id)
    
    # Second pass: identify related tasks
    for task in schedule.get("tasks", []):
        related_event = task.get("related_event")
        task_id = task.get("id")
        if related_event and task_id:
            if related_event not in related_tasks:
                related_tasks[related_event] = []
            related_tasks[related_event].append(task_id)
    
    # Now generate questions for meetings
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
    
    # Check tasks - only ask for course_code when not related to a meeting we're already asking about
    for task in schedule.get("tasks", []):
        # Only process tasks that don't have a course code and are preparation tasks
        if not task.get("course_code") and task.get("category") == "preparation":
            related_event = task.get("related_event")
            
            # Skip if this task is related to a meeting we're already asking about
            should_skip = False
            for meeting in schedule.get("meetings", []):
                # If the meeting description matches the related_event and we're already asking about it
                if meeting.get("description") == related_event and meeting.get("id") in meeting_ids_with_missing_course:
                    should_skip = True
                    break
            
            # Only add the question if we shouldn't skip it
            if not should_skip:
                logger.info(f"Adding course code question for task: {task.get('description')}")
            else:
                logger.info(f"Skipping course code question for task: {task.get('description')} - related to meeting being queried")
                
            if not should_skip:
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
@login_required
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
@login_required
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
        
        # Update user's record with the new schedule
        user = User.query.filter_by(email=session['user']).first()
        if user:
            user.latest_schedule = json.dumps(response_data['schedule'])
            user.schedule_timestamp = datetime.utcnow()
            db.session.commit()

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        # If user is already logged in, redirect to index
        if 'user' in session:
            return redirect(url_for('index'))
        return render_template('login.html', error=None, success=None)
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if not user:
                logger.info(f"Login attempt with non-existent email: {email}")
                flash('Email address not found.')
                return render_template('login.html', error='Email address not found.', success=None)
            
            # Check if the password matches
            if not check_password_hash(user.password, password):
                logger.info(f"Failed login attempt for user: {email}")
                flash('Incorrect password.')
                return render_template('login.html', error='Incorrect password.', success=None)
                
            # Success! Set up the session
            session['user'] = email
            session['first_name'] = user.first_name
            logger.info(f"User logged in successfully: {email}")
            if user.latest_schedule and user.schedule_timestamp and (datetime.utcnow() - user.schedule_timestamp < timedelta(days=7)):
                return redirect(url_for('schedule_only'))
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login.')
            return render_template('login.html', error='Login failed. Please try again.', success=None)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        # If user is already logged in, redirect to index
        if 'user' in session:
            return redirect(url_for('index'))
        return render_template('login.html', error=None)
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Validate required fields
        if not all([email, password, confirm_password, first_name, last_name]):
            flash('All fields are required.')
            return render_template('login.html', error='All fields are required.')
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return render_template('login.html', error='Passwords do not match.')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists.')
            return render_template('login.html', error='Email address already exists.')
            
        # Create new user with hashed password
        hashed_password = generate_password_hash(password)
        new_user = User(
            email=email, 
            password=hashed_password,
            first_name=first_name,
            last_name=last_name
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            # Automatically log in the user after registration
            session['user'] = email
            session['first_name'] = first_name
            logger.info(f"User registered and logged in successfully: {email}")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error registering user: {str(e)}")
            flash('An error occurred during registration.')
            return render_template('login.html', error='Registration failed. Please try again.')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/reset-schedule', methods=['POST'])
@login_required
def reset_schedule():
    try:
        user = User.query.filter_by(email=session['user']).first()
        if user:
            user.latest_schedule = None
            db.session.commit()
            logger.info(f"Reset schedule for user: {user.email}")
        global current_schedule
        current_schedule = None

        # Call EEP1 to reset the stored schedule from storage
        response = requests.post(f'{EEP1_URL}/reset-stored-schedule', timeout=10)
        if response.ok:
            logger.info("Successfully reset stored schedule in EEP1.")
        else:
            logger.warning(f"Failed to reset stored schedule in EEP1: {response.text}")

        return jsonify({"status": "reset done"})
    except Exception as e:
        logger.error(f"Error in reset schedule: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True) 