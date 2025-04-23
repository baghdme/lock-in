from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import logging
import requests  # Changed from anthropic to requests
from dotenv import load_dotenv
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Get Anthropic API key
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
if not ANTHROPIC_API_KEY:
    logger.error("ANTHROPIC_API_KEY environment variable is not set!")
else:
    logger.info("ANTHROPIC_API_KEY is configured")

# Set the LLM model to use
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-3-7-sonnet-20250219')
logger.info(f"Using LLM model: {LLM_MODEL}")

# Function to call Anthropic API directly instead of using the client library
def call_anthropic_api(prompt, model=None, temperature=0.7, max_tokens=4000):
    """
    Pure function to call Anthropic API with a prompt.
    Returns the raw API response.
    """
    try:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        # Use provided model or fall back to default
        model_to_use = model or LLM_MODEL
        logger.info(f"Calling Anthropic API with model: {model_to_use}")
        
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Messages API format for Claude models
        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=300  # Increased timeout from 60 to 300 seconds (5 minutes)
        )
        
        if response.status_code != 200:
            logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
            return {"error": f"Anthropic API returned error: {response.status_code} - {response.text}"}, response.status_code
        
        # Return the raw API response
        return response.json(), 200
            
    except Exception as e:
        logger.error(f"Error calling Anthropic API: {str(e)}")
        return {"error": str(e)}, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        if not ANTHROPIC_API_KEY:
            return jsonify({
                "status": "unhealthy", 
                "error": "ANTHROPIC_API_KEY not set"
            }), 500
            
        # Test connection to Anthropic API
        response, status_code = call_anthropic_api(
            prompt="Hello",
            max_tokens=10
        )
        
        if status_code != 200:
            return jsonify({
                "status": "unhealthy", 
                "error": response.get("error", "Unknown error")
            }), 500
            
        return jsonify({
            "status": "healthy", 
            "model": LLM_MODEL
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy", 
            "error": str(e)
        }), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Process user chat message and update schedule."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Required fields
        user_message = data.get('message')
        current_schedule = data.get('schedule')
        chat_history = data.get('chat_history', [])
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        if not current_schedule:
            return jsonify({"error": "No schedule provided"}), 400
            
        # Log the incoming data in detail
        logger.info(f"Processing chat request with message: {user_message}")
        logger.info(f"FULL INCOMING REQUEST BODY: {json.dumps(data)}")
        
        # Focus ONLY on the generated_calendar
        if 'generated_calendar' in current_schedule:
            logger.info("Found generated_calendar in incoming data - this is what we'll use")
            gen_cal = current_schedule['generated_calendar']
            total_events = sum(len(events) for day, events in gen_cal.items())
            logger.info(f"Generated calendar has {total_events} total events across {len(gen_cal)} days")
            
            # Log the events from the calendar for comparison
            for day, events in gen_cal.items():
                if events:
                    logger.info(f"{day} has {len(events)} events:")
                    for event in events:
                        logger.info(f"  - {event.get('description')} ({event.get('type')}) at {event.get('start_time')}")
        else:
            logger.warning("No generated_calendar found in schedule! This is a critical issue.")
                
        # Build the prompt including chat history for context
        system_prompt = """You are an intelligent scheduling assistant integrated with the user's calendar system. Your task is to help users modify their existing schedule based on their natural language requests.
        
CAPABILITIES:
1. Add new events to the calendar
2. Remove or cancel existing events
3. Modify details of existing events (time, duration, priority, etc.)
4. Add free time or personal activities like exercise, meals, study time
5. Identify and resolve scheduling conflicts

IMPORTANT - FOCUS ONLY ON THE GENERATED_CALENDAR:
The only part of the schedule that matters is the "generated_calendar" object. You should base all your modifications solely on the generated_calendar, and all your changes should be made within the generated_calendar. Ignore the "meetings" and "tasks" arrays - they are legacy data structures and not relevant for this task.

DATA FORMAT REQUIREMENTS:
1. All times must be in 24-hour format (e.g., "14:00" not "2:00 PM")
2. Duration should be specified in minutes as integers
3. Day names must be properly capitalized (e.g., "Monday", not "monday")
4. All fields must be valid according to the schema
5. All events need the required fields (id, type, description, start_time, end_time, duration)

# OUTPUT FORMAT
Your response MUST include a "generated_calendar" object that follows this structure exactly:

{
  "Monday": [
    {
      "id": "meeting-id", 
      "type": "meeting",  // or "exam", "task", "meal", "generated", etc.
      "description": "Meeting description",
      "course_code": "COURSE101",  // if applicable
      "duration": 60,  // duration in minutes
      "start_time": "09:00",
      "end_time": "10:00"
    },
    // More events for Monday...
  ],
  "Tuesday": [ ... ],
  // Other days of the week...
}

EVENT TYPE REQUIREMENTS:
1. For existing events: Preserve the original id, type, description, course_code and other fields exactly.
2. For tasks: Use type "task" and include all original task properties.
3. For exams: Use type "exam" and include course_code and appropriate duration.
4. For meals: Use type "meal" and appropriate descriptions (e.g., "Breakfast", "Lunch", "Dinner").
5. For sports/exercise: Use type "personal" with appropriate description.
6. For generated preparation events (e.g., study sessions): Use type "generated" and include a "related_to" field referencing the ID of the event it's preparing for.

RESPONSE REQUIREMENTS:
1. Respond conversationally as a helpful assistant
2. Explain what changes you've made to the schedule
3. If a request is ambiguous, ask for clarification
4. If a request would create a conflict, explain the conflict and suggest alternatives
5. MAKE SURE YOUR RESPONSE INCLUDES ALL ORIGINAL EVENTS THAT WEREN'T SPECIFICALLY REQUESTED TO BE REMOVED

Your response MUST be in valid JSON format with these properties:
- "response": Your conversational message to the user
- "schedule": Must include the original schedule structure with ONLY the generated_calendar modified
- "generated_calendar": The complete calendar organized by days of the week as described above

DO NOT include any markdown formatting or code blocks in your JSON response. The response should be raw, valid JSON without any additional formatting.
"""

        # Format chat history as a string
        chat_history_text = ""
        for entry in chat_history:
            if entry.get('role') and entry.get('content'):
                chat_history_text += f"{entry['role'].upper()}: {entry['content']}\n\n"
                
        # Check for existing generated_calendar in the schedule
        reference_calendar = None
        reference_calendar_text = ""
        
        if 'generated_calendar' in current_schedule:
            reference_calendar = current_schedule['generated_calendar']
            reference_calendar_text = f"""
REFERENCE CALENDAR: 
This is the existing calendar that MUST be preserved and extended with your changes.
DO NOT remove ANY events from this calendar unless specifically asked to:

```json
{json.dumps(reference_calendar, indent=2)}
```
"""
        
        # Format the complete prompt
        prompt = f"""SYSTEM: {system_prompt}

CHAT HISTORY:
{chat_history_text}

CURRENT SCHEDULE:
```json
{json.dumps(current_schedule, indent=2)}
```

{reference_calendar_text}

IMPORTANT INSTRUCTION: 
1. Your response must include ALL existing events in the generated_calendar. Do NOT remove or change ANY events unless specifically requested to.
2. Make sure to organize all events into a "generated_calendar" object with days of the week as keys.
3. When adding a sports activity or exam, make sure to preserve the event type (use "exam" for exams, "personal" for sports).
4. All events in the generated_calendar must have the following fields at minimum: id, type, description, duration, start_time, end_time.
5. For events with a course_code, make sure to include that field.
6. The "generated_calendar" structure MUST follow the format exactly as shown in the instructions.
7. CRITICAL: Your response should be a plain JSON object without any markdown code block formatting.

USER: {user_message}
"""
        
        logger.info("Sending request to Anthropic API")
        
        # Make API call to Claude
        response, status_code = call_anthropic_api(
            prompt=prompt,
            max_tokens=4000
        )
        
        if status_code != 200:
            logger.error(f"API call failed: {response.get('error', 'Unknown error')}")
            return jsonify({
                "error": response.get('error', 'Failed to process request'),
                "schedule": current_schedule
            }), 500
            
        # Extract the model's response
        model_response = response["content"][0]["text"]
        logger.info(f"Received response from Anthropic API (length: {len(model_response)} chars)")
        
        # Try to parse the response as JSON
        try:
            # Clean up the response text to handle markdown formatting if present
            # First, check if the response is wrapped in ```json or ``` blocks
            if "```json" in model_response:
                # Extract the JSON from inside the code block
                json_str = model_response.split("```json", 1)[1].split("```", 1)[0].strip()
                logger.info("Extracted JSON from markdown code block (started with ```json)")
            elif "```" in model_response:
                # It's a regular code block
                json_str = model_response.split("```", 1)[1].split("```", 1)[0].strip()
                logger.info("Extracted JSON from markdown code block")
            else:
                # Just use the raw text, assuming it's already JSON
                json_str = model_response.strip()
                logger.info("Using raw text as JSON")
                
            # Handle potential "Extra data" errors by ensuring we have a balanced JSON object
            # Find the position of the last balanced curly brace
            try:
                json_decoder = json.JSONDecoder()
                json_decoder.decode(json_str)
            except json.JSONDecodeError as e:
                if "Extra data" in str(e):
                    logger.warning(f"Extra data detected in JSON, truncating to position: {e.pos}")
                    json_str = json_str[:e.pos]
                    logger.info(f"Truncated JSON string length: {len(json_str)}")
            
            parsed_response = json.loads(json_str)
            
            # Log the entire parsed response structure
            logger.info(f"Parsed response structure keys: {list(parsed_response.keys())}")
                
            # Validate the response structure
            if "response" not in parsed_response:
                raise ValueError("Response missing required field: 'response'")
                
            if "schedule" not in parsed_response:
                # Create a schedule if missing
                parsed_response["schedule"] = current_schedule
                logger.warning("Response missing 'schedule' field - using current schedule")
                
            if "generated_calendar" not in parsed_response:
                # If generated_calendar is not directly in the response, check if it's in the schedule
                if "generated_calendar" in parsed_response["schedule"]:
                    # Extract it to the top level for consistency
                    parsed_response["generated_calendar"] = parsed_response["schedule"]["generated_calendar"]
                    logger.info("Moved generated_calendar from schedule to top level")
                else:
                    raise ValueError("Response missing required field: 'generated_calendar'")
            
            # Verify that the generated_calendar contains all necessary data
            calendar = parsed_response["generated_calendar"]
            expected_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            # Log the generated calendar structure
            logger.info(f"Generated calendar days: {list(calendar.keys())}")
            day_counts = {day: len(calendar.get(day, [])) for day in calendar}
            logger.info(f"Events per day: {day_counts}")
            
            # Fallback: If we have a reference calendar and the new calendar has fewer events, use the reference
            if reference_calendar:
                reference_event_count = sum(len(events) for day, events in reference_calendar.items())
                new_event_count = sum(len(events) for day, events in calendar.items())
                
                logger.info(f"Reference calendar has {reference_event_count} events, new calendar has {new_event_count} events")
                
                if new_event_count < reference_event_count - 2:  # Allow for removing one or two events if requested
                    logger.warning(f"New calendar has significantly fewer events than reference! Reference: {reference_event_count}, New: {new_event_count}")
                    
                    # Try to merge the calendars, keeping all reference events and adding the new ones
                    merged_calendar = {day: [] for day in expected_days}
                    
                    # First add all reference events
                    for day, events in reference_calendar.items():
                        if day in merged_calendar:
                            merged_calendar[day].extend(events)
                    
                    # Then add new events that don't already exist (by ID)
                    for day, events in calendar.items():
                        reference_ids = [event.get('id') for event in merged_calendar.get(day, [])]
                        for event in events:
                            if event.get('id') not in reference_ids:
                                merged_calendar[day].append(event)
                    
                    logger.info(f"Merged calendar now has {sum(len(events) for day, events in merged_calendar.items())} total events")
                    calendar = merged_calendar
            
            for day in expected_days:
                if day not in calendar:
                    calendar[day] = []
                    logger.info(f"Added missing day: {day}")
            
            # Validate events in generated_calendar
            event_types_count = {}
            for day, events in calendar.items():
                for i, event in enumerate(events):
                    # Count event types
                    event_type = event.get("type", "unknown")
                    if event_type not in event_types_count:
                        event_types_count[event_type] = 0
                    event_types_count[event_type] += 1
                    
                    # Log event details
                    logger.info(f"{day} event {i}: {event.get('description')} ({event_type}) at {event.get('start_time')}-{event.get('end_time')}")
                    
                    # Check for minimum required fields
                    required_fields = ["id", "type", "description", "start_time", "end_time"]
                    for field in required_fields:
                        if field not in event:
                            logger.warning(f"Event missing required field: {field}")
                            # Set default values if missing
                            if field == "id":
                                event["id"] = f"generated-{i}"
                            elif field == "type":
                                event["type"] = "generated"
                            elif field == "description":
                                event["description"] = "Untitled Event"
                    
                    # Ensure duration is included or calculated
                    if "duration" not in event:
                        # Try to calculate from start and end times
                        try:
                            if "start_time" in event and "end_time" in event:
                                start_parts = event["start_time"].split(":")
                                end_parts = event["end_time"].split(":")
                                start_mins = int(start_parts[0]) * 60 + int(start_parts[1])
                                end_mins = int(end_parts[0]) * 60 + int(end_parts[1])
                                duration = end_mins - start_mins
                                event["duration"] = duration
                                logger.info(f"Calculated duration {duration} minutes for event: {event.get('description')}")
                        except:
                            event["duration"] = 60  # Default duration
                            logger.warning(f"Failed to calculate duration, using default 60 min for: {event.get('description')}")
            
            # Log event type summary
            logger.info(f"Event types in calendar: {event_types_count}")
            
            # Update the generated_calendar in the response
            parsed_response["generated_calendar"] = calendar
            
            # Log the final calendar structure that will be returned
            logger.info(f"Final calendar structure: {len(calendar)} days, {sum(len(events) for events in calendar.values())} total events")
            
            # Ensure that generated_calendar is also in the schedule object
            new_schedule = parsed_response["schedule"]
            new_schedule["generated_calendar"] = calendar
            parsed_response["schedule"] = new_schedule
            logger.info("Added generated_calendar to schedule object for completeness")
            
            logger.info("Returning successful response to client")
            return jsonify(parsed_response), 200
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse response as JSON: {str(e)}")
            # Log a portion of the raw response for debugging
            logger.error(f"Raw response excerpt (first 500 chars): {model_response[:500]}")
            
            # Attempt a more aggressive JSON extraction as a fallback
            try:
                # Look for anything that looks like JSON
                import re
                
                # If we have an "Extra data" error, try to extract the valid JSON part
                if "Extra data" in str(e) and isinstance(e, json.JSONDecodeError):
                    pos = e.pos
                    logger.info(f"Attempting to extract valid JSON up to position {pos}")
                    potential_json = model_response[:pos]
                    try:
                        fallback_parsed = json.loads(potential_json)
                        logger.info("Successfully parsed JSON by truncating at error position")
                    except json.JSONDecodeError:
                        # If that fails, try to find the last valid JSON object
                        logger.info("Truncation failed, trying regex pattern matching")
                        json_pattern = r'\{.*\}'
                        match = re.search(json_pattern, model_response, re.DOTALL)
                        if match:
                            potential_json = match.group(0)
                            fallback_parsed = json.loads(potential_json)
                            logger.info("Successfully parsed JSON with regex pattern matching")
                else:
                    # If it's not an "Extra data" error, use regex
                    json_pattern = r'\{.*\}'
                    match = re.search(json_pattern, model_response, re.DOTALL)
                    if match:
                        potential_json = match.group(0)
                        logger.info(f"Attempting to parse extracted JSON-like text: {potential_json[:100]}...")
                        fallback_parsed = json.loads(potential_json)
                        logger.info("Successfully parsed JSON with fallback method")
                
                # Validate and process this JSON similar to above
                if "response" in fallback_parsed and ("generated_calendar" in fallback_parsed or 
                                                     ("schedule" in fallback_parsed and "generated_calendar" in fallback_parsed["schedule"])):
                    logger.info("Fallback JSON has required fields")
                    
                    # Extract or create necessary components
                    if "generated_calendar" not in fallback_parsed and "schedule" in fallback_parsed and "generated_calendar" in fallback_parsed["schedule"]:
                        fallback_parsed["generated_calendar"] = fallback_parsed["schedule"]["generated_calendar"]
                        
                    # Return the successfully parsed fallback
                    return jsonify(fallback_parsed), 200
            except Exception as fallback_error:
                logger.error(f"Fallback JSON parsing also failed: {str(fallback_error)}")
            
            # If all else fails, return the original schedule
            return jsonify({
                "response": f"I processed your request but encountered an issue formatting the response. Here's what I understand: {model_response[:500]}...",
                "schedule": current_schedule,
                "generated_calendar": current_schedule.get("generated_calendar", {}),
                "error": "Failed to parse LLM response"
            }), 200
            
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e),
            "schedule": data.get('schedule', {}) if data else {}
        }), 500

@app.route('/update-prompt', methods=['POST'])
def update_prompt():
    """Update user's custom prompt based on chat history."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Required fields
        original_prompt = data.get('original_prompt')
        chat_history = data.get('chat_history', [])
        
        if not original_prompt:
            return jsonify({"error": "No original prompt provided"}), 400
        if not chat_history:
            # If no chat history, just return the original prompt
            return jsonify({"custom_prompt": original_prompt}), 200
            
        # Build the system prompt
        system_prompt = """You are an expert at improving prompt instructions for schedule optimization.
        
Your task is to analyze the chat history between a user and a scheduling assistant, then update the user's custom prompt to better reflect their preferences and needs.

PROMPT STRUCTURE UNDERSTANDING:
The original prompt has two main sections:
1. FIXED COMPONENTS: Technical instructions about formatting, data structures, and constraints that MUST NEVER be modified
2. USER STYLE INSTRUCTIONS: Preferences about how to arrange the schedule, prioritize activities, handle free time, etc.

ANALYSIS REQUIREMENTS:
1. Carefully review the chat history to identify:
   - Repeated requests for certain types of scheduling (e.g., "more study time", "breaks between classes")
   - Complaints about the current schedule ("too packed", "not enough free time")
   - Preferences about time of day for certain activities
   - Preferences about grouping or spacing of similar activities
   - Balance preferences between work and leisure

MODIFICATION RULES:
1. DO NOT MODIFY any technical instructions, formatting guidance, or data structure specifications
2. ONLY update the user preference/style section of the prompt
3. Be specific and clear in your prompt modifications
4. Build upon existing preferences rather than completely replacing them
5. If the user expressed contradictory preferences, go with the most recent one
6. Maintain the same overall structure and format as the original prompt

OUTPUT REQUIREMENTS:
1. Return the COMPLETE prompt with your updates to the user preference section
2. Do not add comments, explanations, or notes - just the prompt itself
3. Format the prompt exactly like the original, preserving all sections
4. Ensure the updated prompt flows naturally and reads coherently
"""

        # Format the chat history as a string
        chat_history_text = json.dumps(chat_history, indent=2)
        
        # Create the complete prompt
        prompt = f"""SYSTEM: {system_prompt}

ORIGINAL PROMPT:
```
{original_prompt}
```

CHAT HISTORY:
```
{chat_history_text}
```

Based on this chat history, please update ONLY the user-specific style instructions in the prompt. Keep all technical instructions, data structures, and fixed sections completely intact.

Look for patterns in how the user wants their schedule arranged based on their chat interactions with the scheduling assistant. Incorporate these preferences into the style section of the prompt.
"""
        
        # Make API call to Claude
        response, status_code = call_anthropic_api(
            prompt=prompt,
            max_tokens=4000
        )
        
        if status_code != 200:
            logger.error(f"API call failed: {response.get('error', 'Unknown error')}")
            return jsonify({
                "error": response.get('error', 'Failed to process request'),
                "custom_prompt": original_prompt
            }), 500
        
        # Extract the updated prompt
        updated_prompt = response["content"][0]["text"]
        
        # Clean up the response to extract just the prompt if it's in a code block
        if "```" in updated_prompt:
            # Try to extract content between first ``` and last ```
            try:
                prompt_parts = updated_prompt.split("```")
                if len(prompt_parts) >= 3:  # At least one pair of ```
                    # Get the first block of code
                    updated_prompt = prompt_parts[1].strip()
                    logger.info("Successfully extracted prompt from code block")
                else:
                    logger.warning("Could not properly extract code block - using whole response")
            except Exception as e:
                logger.error(f"Error extracting from code block: {str(e)}")
                # Just use the original string method as fallback
                updated_prompt = updated_prompt.split("```", 1)[1].split("```", 1)[0].strip()
        
        return jsonify({"custom_prompt": updated_prompt}), 200
        
    except Exception as e:
        logger.error(f"Error updating prompt: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e),
            "custom_prompt": data.get('original_prompt', '') if data else ''
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True) 