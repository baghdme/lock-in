import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict
import openai

app = Flask(__name__)
CORS(app)

# Configure OpenAI API key from environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')

# Global variable to simulate storing the latest schedule JSON
LATEST_SCHEDULE = {}

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

def validate_and_fix_times(data: Dict) -> Dict:
    for task in data.get("tasks", []):
        if task.get("time"):
            task["time"] = convert_to_24h(task["time"])
    for meeting in data.get("meetings", []):
        if meeting.get("time"):
            meeting["time"] = convert_to_24h(meeting["time"])
    return data

# Prompt templates for parsing and modification extraction.
PARSING_PROMPT = """You are a task parsing assistant for a weekly scheduling system. Parse the following weekly overview text into structured information following these rules:

1. Input:
   - The user provides a full weekly description with tasks, meetings, exams, and other events.
   - The text may include days (e.g., Monday, Tuesday, etc.) and specific times.
   - Examples:
       "I have an exam on Thursday at 14:00 and I need to study for it on Thursday morning."
       "I have a meeting on Friday at 10:00; please also schedule time to prepare for the meeting."

2. Extraction Requirements:
   - Extract events into two main categories: tasks and meetings.
   - For meetings and exams, extract the event itself (with its scheduled time and day) and also create a separate task for any necessary preparation.
   - Extract the day information (e.g., Monday, Tuesday, etc.) for each event.
   - Convert all times to 24-hour format (HH:MM) and all durations (if mentioned) to integer minutes.
   - Capture additional details: priority cues, location if provided, course codes, and any dependencies or prerequisites.

3. Format Requirements:
   - For tasks, include a new field "day" representing the day of the week or a specific date.
   - For meetings, include the "day" field as well.
   - Follow the JSON structure exactly as specified below.

Output a JSON object with the following exact structure:
{{
    "tasks": [
        {{
            "description": "task description",
            "day": "day of week or date",
            "priority": "high/medium/low",
            "time": "HH:MM or None",
            "duration_minutes": null,
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
            "day": "day of week or date",
            "priority": "high/medium/low",
            "time": "HH:MM",
            "duration_minutes": null,
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

IMPORTANT: All times must be in 24-hour format (HH:MM) and durations in integer minutes.
Parse the input text completely and output only the JSON object.
Text to parse: "{text}"
"""

MODIFICATION_PROMPT = """You are a task modification assistant for a weekly scheduling system. Extract structured modification instructions from the following user prompt.
Text to parse: "{text}"
Output a JSON object with the following structure:
{{
    "action": "e.g., adjust_time, reschedule",
    "target": "identifier for the target event (e.g., 'Friday meeting')",
    "parameter": "parameter to change (e.g., 'prep_time')",
    "adjustment": "modification detail (e.g., '+15')"
}}
IMPORTANT: Output only the JSON object."""

def call_openai(prompt: str) -> Dict:
    """Helper function to call the OpenAI API with a given prompt."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": (
                    "You are a task assistant that outputs only valid JSON. "
                    "For parsing tasks, include a \"day\" field; for modification extraction, output a structured modification action as specified. "
                    "Ensure times are in 24-hour format and durations are integer minutes. "
                    "Never output times in 12-hour format."
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message['content'])
    except Exception as e:
        return {"error": str(e)}

def parse_tasks(text: str) -> Dict:
    """Parse the input text to generate a structured JSON schedule."""
    global LATEST_SCHEDULE
    prompt = PARSING_PROMPT.format(text=text)
    result = call_openai(prompt)
    result = validate_and_fix_times(result)
    # Simulate saving the latest schedule
    LATEST_SCHEDULE = result
    return result

def modify_tasks(text: str) -> Dict:
    """
    Process a modification prompt by:
      1. Extracting structured modification instructions from the free-form text.
      2. Fetching the most recent JSON schedule (simulated via a global variable).
      3. Combining the modification instructions and current schedule into a prompt to update the schedule.
      4. Returning the updated JSON schedule.
    """
    global LATEST_SCHEDULE
    # Step 1: Extract modification instructions.
    mod_prompt = MODIFICATION_PROMPT.format(text=text)
    mod_instructions = call_openai(mod_prompt)
    if "error" in mod_instructions:
        return mod_instructions

    # Step 2: Fetch the most recent schedule (simulate with global variable).
    current_schedule = LATEST_SCHEDULE if LATEST_SCHEDULE else {}

    # Step 3: Prepare a combined prompt to apply modifications.
    combined_prompt = f"""You are a schedule updater. Apply the following modification instructions to the current schedule JSON.
Modification instructions: {json.dumps(mod_instructions)}
Current schedule: {json.dumps(current_schedule)}
Output the updated schedule JSON in the same format as the current schedule.
"""
    updated_schedule = call_openai(combined_prompt)
    if "error" in updated_schedule:
        return updated_schedule
    updated_schedule = validate_and_fix_times(updated_schedule)
    # Update the global schedule.
    LATEST_SCHEDULE = updated_schedule
    return updated_schedule

@app.route('/parse-tasks', methods=['POST'])
def parse_tasks_endpoint():
    if not os.getenv('OPENAI_API_KEY'):
        return jsonify({"error": "OPENAI_API_KEY environment variable not set", "status": "configuration_error"}), 500
    data = request.get_json()
    text = data.get('text', '')
    context = data.get('context', 'parsing')  # Expect "parsing" or "modification"
    if not text:
        return jsonify({"error": "No text provided", "status": "invalid_request"}), 400

    if context == "parsing":
        result = parse_tasks(text)
    elif context == "modification":
        result = modify_tasks(text)
    else:
        result = {"error": "Invalid context. Must be either 'parsing' or 'modification'."}

    if "error" in result:
        return jsonify({**result, "status": "processing_error"}), 500
    return jsonify(result), 200, {'Content-Type': 'application/json; charset=utf-8'}

@app.route('/health', methods=['GET'])
def health_endpoint():
    if not os.getenv('OPENAI_API_KEY'):
        return jsonify({"status": "unhealthy", "error": "OPENAI_API_KEY environment variable not set"}), 500
    try:
        # Simple test completion to check API connectivity
        openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        return jsonify({"status": "healthy", "model": "gpt-3.5-turbo-1106", "openai_status": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": f"OpenAI connection error: {str(e)}", "openai_status": "disconnected"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
