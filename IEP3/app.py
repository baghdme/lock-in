from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
import os
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Service URLs
EEP1_URL = os.getenv('EEP1_URL', 'http://localhost:5000')
logger.debug(f"Using EEP1_URL: {EEP1_URL}")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "IEP3 - Calendar Import Handler"
    })

@app.route('/validate-calendar', methods=['POST'])
def validate_calendar():
    """
    Validate the imported calendar JSON format
    
    Expected structure:
    {
      "Monday": [
        {
          "id": "task-id",
          "type": "task",
          "description": "Task description",
          "course_code": "COURSE101",
          "duration": 120,
          "start_time": "09:00",
          "end_time": "11:00"
        },
        ...
      ],
      "Tuesday": [...],
      ...
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Basic validation
        if not isinstance(data, dict):
            return jsonify({"error": "Calendar must be a JSON object"}), 400
            
        # Check if it has at least one day
        days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        valid_days = [day for day in days_of_week if day in data]
        if not valid_days:
            return jsonify({"error": "Calendar must contain at least one valid day (Monday-Sunday)"}), 400
            
        # Check each day's format
        for day in valid_days:
            if not isinstance(data[day], list):
                return jsonify({"error": f"Calendar entries for {day} must be an array"}), 400
                
            # Check each event in the day
            for idx, event in enumerate(data[day]):
                if not isinstance(event, dict):
                    return jsonify({"error": f"Event {idx} on {day} must be an object"}), 400
                    
                # Check required fields
                required_fields = ["id", "type", "description"]
                for field in required_fields:
                    if field not in event:
                        return jsonify({"error": f"Event {idx} on {day} is missing required field: {field}"}), 400
        
        # Calendar is valid
        return jsonify({
            "valid": True,
            "message": "Calendar format is valid",
            "calendar": data
        })
        
    except Exception as e:
        logger.error(f"Error validating calendar: {str(e)}")
        return jsonify({"error": f"Error validating calendar: {str(e)}"}), 500

@app.route('/process-calendar', methods=['POST'])
def process_calendar():
    """
    Process the imported calendar by:
    1. Validating the format
    2. Forwarding it to EEP1 for storage and further processing
    """
    try:
        data = request.get_json()
        if not data or 'calendar' not in data:
            return jsonify({"error": "No calendar data provided"}), 400
            
        # Validate the calendar
        calendar = data['calendar']
        validation_response = requests.post(
            f"{request.host_url.rstrip('/')}/validate-calendar",
            json=calendar,
            headers={'Content-Type': 'application/json'}
        )
        
        if not validation_response.ok:
            return validation_response.json(), validation_response.status_code
            
        # Add metadata for integration 
        calendar_data = {
            'calendar': calendar,
            'source': 'import',  # Indicate this is an imported calendar
            'metadata': data.get('metadata', {})  # Pass any additional metadata
        }
        
        # Try to save the calendar locally as a backup
        try:
            os.makedirs("/app/storage", exist_ok=True)
            with open("/app/storage/local_calendar_backup.json", "w") as f:
                json.dump(calendar, f)
            logger.info("Saved local backup of calendar")
        except Exception as e:
            logger.warning(f"Failed to save local backup: {str(e)}")
        
        # Forward to EEP1 for storage with increased timeout and retry
        success = False
        max_retries = 2
        retry_count = 0
        
        while not success and retry_count < max_retries:
            try:
                logger.info(f"Attempting to send calendar to EEP1 (attempt {retry_count + 1})")
                eep1_response = requests.post(
                    f"{EEP1_URL}/store-imported-calendar",
                    json=calendar_data,
                    timeout=60  # Increased timeout
                )
                
                if eep1_response.ok:
                    success = True
                    logger.info("Successfully sent calendar to EEP1")
                    
                    # Return success response with validation info
                    return jsonify({
                        "status": "success",
                        "message": "Calendar processed successfully",
                        "validation": validation_response.json(),
                        "attempts_required": retry_count + 1
                    })
                else:
                    error_msg = "Error from EEP1"
                    try:
                        error_data = eep1_response.json()
                        error_msg = error_data.get('error', error_msg)
                    except:
                        error_msg = eep1_response.text or error_msg
                    logger.error(f"EEP1 error: {error_msg}")
                    retry_count += 1
                    
            except requests.RequestException as e:
                logger.error(f"Error communicating with EEP1 (attempt {retry_count + 1}): {str(e)}")
                retry_count += 1
        
        # If we've exhausted retries but have a local backup, return a partial success
        if os.path.exists("/app/storage/local_calendar_backup.json"):
            logger.warning("Failed to send calendar to EEP1, but local backup is available")
            return jsonify({
                "status": "partial_success",
                "message": "Calendar validated but EEP1 storage failed. A local backup was created.",
                "validation": validation_response.json()
            }), 207  # Multi-Status code
            
        # Otherwise return an error
        return jsonify({
            "error": "Failed to communicate with EEP1 after multiple attempts",
            "validation_status": "Calendar format is valid"
        }), 500
            
    except Exception as e:
        logger.error(f"Error processing calendar: {str(e)}")
        return jsonify({"error": f"Error processing calendar: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5005))
    app.run(host='0.0.0.0', port=port, debug=True) 