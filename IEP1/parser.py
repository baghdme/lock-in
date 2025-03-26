import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict
import openai

# Initialize Flask app and enable CORS
app = Flask(__name__)
CORS(app)

# Configure OpenAI API key (ensure this is set in your environment)
openai.api_key = os.getenv('OPENAI_API_KEY')

def convert_to_24h(time_str: str) -> str:
    """Convert 12-hour time format to 24-hour format."""
    if not time_str or time_str == 'None' or time_str == 'null':
        return None
    
    # Remove any whitespace and convert to lowercase
    time_str = time_str.strip().lower()
    
    # Handle special cases
    if time_str == "noon":
        return "12:00"
    if time_str == "midnight":
        return "00:00"
    
    # Try to parse the time
    try:
        # Handle cases like "2pm", "2:30pm"
        if "am" in time_str or "pm" in time_str:
            # Remove am/pm and split into hours and minutes
            time_parts = time_str.replace("am", "").replace("pm", "").strip().split(":")
            
            # Parse hours and minutes
            hours = int(time_parts[0])
            minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            # Convert to 24-hour format
            if "pm" in time_str.lower() and hours != 12:
                hours += 12
            elif "am" in time_str.lower() and hours == 12:
                hours = 0
            
            # Return formatted time
            return f"{hours:02d}:{minutes:02d}"
        
        # Handle cases where time is just a number (assume it's hours)
        if time_str.isdigit():
            hours = int(time_str)
            return f"{hours:02d}:00"
        
        # If already in 24-hour format or no am/pm specified
        if ":" in time_str:
            hours, minutes = map(int, time_str.split(":"))
            return f"{hours:02d}:{minutes:02d}"
        
        return time_str
    except Exception:
        return time_str  # Return original if parsing fails

def validate_and_fix_times(data: Dict) -> Dict:
    """Validate and fix time formats in the parsed data."""
    # Fix task times
    for task in data.get("tasks", []):
        if task.get("time"):
            task["time"] = convert_to_24h(task["time"])
    
    # Fix meeting times
    for meeting in data.get("meetings", []):
        if meeting.get("time"):
            meeting["time"] = convert_to_24h(meeting["time"])
    
    return data

def parse_with_llm(text: str) -> Dict:
    """
    Parse text using OpenAI's GPT-3.5-turbo model.
    This function sends a prompt instructing GPT-3.5 to extract structured task/meeting data.
    The expected JSON output has this structure:
    {
        "tasks": [
            {
                "description": "task description",
                "priority": "high/medium/low",
                "time": "HH:MM or None",  # 24-hour format with leading zeros
                "duration_minutes": None,  # Integer minutes, None if not specified
                "category": "meaningful category",
                "is_fixed_time": false,
                "location": "location if specified or None",
                "prerequisites": ["list of prerequisite task descriptions"],
                "course_code": "associated course code or None"
            }
        ],
        "meetings": [
            {
                "description": "meeting description",
                "priority": "high/medium/low",
                "time": "HH:MM",  # 24-hour format with leading zeros
                "duration_minutes": None,  # Integer minutes, None if not specified
                "location": "meeting location or None",
                "preparation_tasks": ["list of prep task descriptions"],
                "course_code": "associated course code or None"
            }
        ],
        "course_codes": ["list of course codes"],
        "topics": [
            {
                "id": 0,
                "terms": {"term1": 0.8, "term2": 0.6},
                "label": "Topic label"
            }
        ]
    }
    Output only the JSON object, nothing else.
    """
    prompt = f"""You are a task parsing assistant for a daily scheduling system. Parse the following text into structured information following these rules:

1. Task and Meeting Structure:
   - Extract tasks that need to be done today
   - Identify meetings with specific times
   - Extract duration information ONLY when explicitly mentioned
   - Convert ALL durations to integer minutes (e.g., "1 hour" → 60, "2.5 hours" → 150)
   - Note location information, especially for meetings
   - Identify dependencies between tasks when mentioned

2. Time Format Requirements (STRICT):
   - ALL times MUST be in 24-hour format with leading zeros
   - Format: "HH:MM" (e.g., "09:00", "14:30", "16:45")
   - Examples of conversion:
     * "9am" → "09:00"
     * "2:30pm" → "14:30"
     * "3:45pm" → "15:45"
     * "11:30am" → "11:30"
     * "12pm" → "12:00"
     * "12am" → "00:00"

3. Duration Requirements (STRICT):
   - ALL durations MUST be in integer minutes
   - Examples of conversion:
     * "1 hour" → 60
     * "2.5 hours" → 150
     * "45 mins" → 45
     * "1h" → 60
     * "1 hour 30 mins" → 90
     * "2 hours" → 120

4. Course Code Handling:
   - Extract full codes (e.g., EECE503) and shortened versions (503)
   - Handle variations (EECE503N, 503n)
   - Associate tasks and meetings with relevant courses

5. Priority and Categories:
   - High: Urgent/critical tasks, must be done today
   - Medium: Important but some flexibility
   - Low: Can be postponed if needed
   - Use categories: Lab Work, Assignment, Tutorial, Admin, Grading, Preparation

6. Additional Context:
   - Note any prerequisites or dependencies
   - Capture location details for travel planning
   - Note preparation requirements for meetings
   - Group related tasks together

Text to parse: "{text}"

Output a JSON object with this exact structure:
{{
    "tasks": [
        {{
            "description": "task description",
            "priority": "high/medium/low",
            "time": "HH:MM or None",  # 24-hour format with leading zeros
            "duration_minutes": 60,  # Integer minutes, None if not specified
            "category": "meaningful category",
            "is_fixed_time": false,
            "location": "location if specified or None",
            "prerequisites": ["list of prerequisite task descriptions"],
            "course_code": "associated course code or None"
        }}
    ],
    "meetings": [
        {{
            "description": "meeting description",
            "priority": "high/medium/low",
            "time": "HH:MM",  # 24-hour format with leading zeros
            "duration_minutes": 60,  # Integer minutes, None if not specified
            "location": "meeting location or None",
            "preparation_tasks": ["list of prep task descriptions"],
            "course_code": "associated course code or None"
        }}
    ],
    "course_codes": ["list of course codes"],
    "topics": [
        {{
            "id": 0,
            "terms": {{"term1": 0.8, "term2": 0.6}},
            "label": "Topic label"
        }}
    ]
}}

IMPORTANT: ALL times MUST be in 24-hour format (HH:MM) and ALL durations MUST be in integer minutes.
Output only the JSON object, nothing else."""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": """You are a task parsing assistant that outputs only valid JSON.
STRICT FORMAT REQUIREMENTS:
1. Times must be in 24-hour format with leading zeros (HH:MM)
   - "9am" → "09:00"
   - "2:30pm" → "14:30"
   - "4pm" → "16:00"
   - "12pm" → "12:00"
   - "12am" → "00:00"
2. Durations must be integer minutes
   - "1 hour" → 60
   - "2.5 hours" → 150
   - "45 mins" → 45
   - "1h" → 60
Never output times in 12-hour format (no am/pm). Always use 24-hour format with leading zeros."""},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        # Parse and validate the JSON content from the response
        result = json.loads(response.choices[0].message['content'])
        result = validate_and_fix_times(result)  # Convert times to 24-hour format
        return result
    except openai.error.OpenAIError as e:
        return {
            "error": f"OpenAI API Error: {str(e)}",
            "tasks": [],
            "meetings": [],
            "course_codes": [],
            "topics": []
        }
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON Decode Error: {str(e)}",
            "tasks": [],
            "meetings": [],
            "course_codes": [],
            "topics": []
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "tasks": [],
            "meetings": [],
            "course_codes": [],
            "topics": []
        }

@app.route('/parse-tasks', methods=['POST'])
def parse_tasks_endpoint():
    if not os.getenv('OPENAI_API_KEY'):
        return jsonify({
            "error": "OPENAI_API_KEY environment variable not set",
            "status": "configuration_error"
        }), 500
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({
            "error": "No text provided",
            "status": "invalid_request"
        }), 400
    result = parse_with_llm(text)
    if "error" in result:
        return jsonify({
            **result,
            "status": "processing_error"
        }), 500
    return jsonify(result), 200, {'Content-Type': 'application/json; charset=utf-8'}

@app.route('/health', methods=['GET'])
def health_endpoint():
    if not os.getenv('OPENAI_API_KEY'):
        return jsonify({
            "status": "unhealthy",
            "error": "OPENAI_API_KEY environment variable not set"
        }), 500
    try:
        # Test OpenAI connection by listing available models
        openai.Model.list()
        return jsonify({
            "status": "healthy",
            "model": "gpt-3.5-turbo-1106",
            "openai_status": "connected"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": f"OpenAI connection error: {str(e)}",
            "openai_status": "disconnected"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
