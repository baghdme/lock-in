from flask import Flask, request, jsonify
import logging
import uuid
import json
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory storage for schedules
current_schedule = None

# Make sure we have a data directory for persistence
os.makedirs("mock_data", exist_ok=True)
SCHEDULE_FILE = "mock_data/schedule.json"

# Try to load any existing schedule from file
try:
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            current_schedule = json.load(f)
            logger.info("Loaded existing schedule from file")
except Exception as e:
    logger.error(f"Error loading schedule from file: {str(e)}")
    current_schedule = None

@app.route('/parse-schedule', methods=['POST'])
def parse_schedule():
    """Mock endpoint for parsing schedule text"""
    global current_schedule
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        logger.info(f"Received parse request with text: {text[:100]}...")
        
        # Create a mock schedule based on the input text
        # This is a very simple implementation - in a real scenario, you'd have NLP to extract events
        mock_schedule = {
            "meetings": [],
            "tasks": [],
            "generated_calendar": {}
        }
        
        # Extract some basic information from the text
        if "exam" in text.lower():
            mock_schedule["meetings"].append({
                "id": str(uuid.uuid4()),
                "type": "exam",
                "description": "Exam",
                "day": "Thursday" if "thursday" in text.lower() else "Monday",
                "time": "17:00" if "5pm" in text.lower() else "10:00",
                "duration_minutes": 120,
                "course_code": "EECE442" if "eece442" in text.lower() else "UNKNOWN"
            })
            
            # Add a preparation task
            mock_schedule["tasks"].append({
                "id": str(uuid.uuid4()),
                "type": "exam_preparation",
                "description": "Prepare for Exam",
                "duration_minutes": 180,
                "priority": "high",
                "course_code": "EECE442" if "eece442" in text.lower() else "UNKNOWN"
            })
        
        if "meeting" in text.lower():
            mock_schedule["meetings"].append({
                "id": str(uuid.uuid4()),
                "type": "meeting",
                "description": "Meeting",
                "day": "Wednesday" if "wednesday" in text.lower() else "Friday",
                "time": "14:00",
                "duration_minutes": 60
            })
        
        if "project" in text.lower() or "assignment" in text.lower():
            mock_schedule["tasks"].append({
                "id": str(uuid.uuid4()),
                "type": "assignment",
                "description": "Complete Assignment",
                "duration_minutes": 120,
                "priority": "medium",
                "course_code": "EECE442" if "eece442" in text.lower() else "UNKNOWN"
            })
        
        # Save the schedule
        current_schedule = mock_schedule
        
        # Save to file for persistence
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(current_schedule, f)
            
        logger.info("Created and saved mock schedule")
        
        return jsonify({
            "success": True,
            "schedule": mock_schedule,
            "message": "Schedule parsed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error in parse-schedule: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/get-schedule', methods=['GET'])
def get_schedule():
    """Get the current schedule"""
    global current_schedule
    
    if not current_schedule:
        return jsonify({
            "success": False,
            "error": "No schedule available"
        }), 404
    
    return jsonify({
        "success": True,
        "schedule": current_schedule
    })

@app.route('/store-schedule', methods=['POST'])
def store_schedule():
    """Store a schedule"""
    global current_schedule
    
    try:
        data = request.get_json()
        if not data or 'schedule' not in data:
            return jsonify({
                "success": False,
                "error": "No schedule provided"
            }), 400
        
        current_schedule = data['schedule']
        
        # Save to file for persistence
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(current_schedule, f)
        
        return jsonify({
            "success": True,
            "message": "Schedule stored successfully"
        })
        
    except Exception as e:
        logger.error(f"Error in store-schedule: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/answer-question', methods=['POST'])
def answer_question():
    """Mock endpoint for answering questions about the schedule"""
    global current_schedule
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        # Update schedule with the answer if provided
        if 'schedule' in data:
            current_schedule = data['schedule']
            
            # Save to file for persistence
            with open(SCHEDULE_FILE, 'w') as f:
                json.dump(current_schedule, f)
        
        return jsonify({
            "success": True,
            "schedule": current_schedule,
            "message": "Answer processed successfully",
            "ready_for_optimization": True,
            "has_more_questions": False
        })
        
    except Exception as e:
        logger.error(f"Error in answer-question: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/preference-questions', methods=['GET'])
def preference_questions():
    """Mock endpoint for getting preference questions"""
    
    # Return some mock preference questions
    mock_questions = [
        {
            "id": "work_hours",
            "question": "What are your preferred working hours?",
            "type": "time_range",
            "options": [
                {"value": "9-5", "label": "9 AM - 5 PM"},
                {"value": "10-6", "label": "10 AM - 6 PM"},
                {"value": "8-4", "label": "8 AM - 4 PM"}
            ]
        },
        {
            "id": "productivity",
            "question": "When are you most productive?",
            "type": "single_choice",
            "options": [
                {"value": "morning", "label": "Morning"},
                {"value": "afternoon", "label": "Afternoon"},
                {"value": "evening", "label": "Evening"}
            ]
        }
    ]
    
    return jsonify({
        "success": True,
        "questions": mock_questions
    })

@app.route('/generate-optimized-schedule', methods=['POST'])
def generate_optimized_schedule():
    """Mock endpoint for generating an optimized schedule"""
    global current_schedule
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        schedule = data.get('schedule', current_schedule)
        if not schedule:
            return jsonify({
                "success": False,
                "error": "No schedule available"
            }), 400
        
        # Add a "generated_calendar" field with mock data
        if "meetings" in schedule:
            calendar = {}
            
            # Generate a simple calendar for each day
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            for day in days:
                day_events = []
                
                # Add meetings for this day
                for meeting in schedule["meetings"]:
                    if meeting.get("day") == day:
                        day_events.append({
                            "id": meeting["id"],
                            "type": meeting["type"],
                            "title": meeting["description"],
                            "start_time": meeting.get("time", "09:00"),
                            "duration_minutes": meeting.get("duration_minutes", 60),
                            "course_code": meeting.get("course_code")
                        })
                
                # Add some tasks
                task_start_time = "13:00"  # Start tasks at 1 PM
                for task in schedule.get("tasks", []):
                    day_events.append({
                        "id": task["id"],
                        "type": task["type"],
                        "title": task["description"],
                        "start_time": task_start_time,
                        "duration_minutes": task.get("duration_minutes", 60),
                        "course_code": task.get("course_code")
                    })
                    # Move the next task start time
                    hour, minute = map(int, task_start_time.split(":"))
                    hour = (hour + 2) % 24  # 2 hours later
                    task_start_time = f"{hour:02d}:{minute:02d}"
                    
                    # Only add one task per day
                    break
                
                calendar[day] = day_events
            
            schedule["generated_calendar"] = calendar
        
        current_schedule = schedule
        
        # Save to file for persistence
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(current_schedule, f)
        
        return jsonify({
            "success": True,
            "schedule": current_schedule,
            "message": "Schedule optimized successfully"
        })
        
    except Exception as e:
        logger.error(f"Error in generate-optimized-schedule: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 