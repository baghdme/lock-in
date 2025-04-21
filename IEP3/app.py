import os
import json
import logging
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
from dotenv import load_dotenv
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": "553083759506-725o9f6fu9i3c5bked6b0vh31ve07660.apps.googleusercontent.com",
        "project_id": "lofty-digit-457314-h0",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": [
            "http://localhost:5002/google-calendar/callback",
            "http://localhost:5000/google-calendar/callback"
        ]
    }
}

# Google API scopes - updated to include write permissions
SCOPES = ['https://www.googleapis.com/auth/calendar']  # Full access instead of just .readonly

app = Flask(__name__)
CORS(app)

# --- Google Calendar API Endpoints ---

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

@app.route('/authorize', methods=['GET'])
def authorize():
    """Generate an authorization URL for Google OAuth."""
    try:
        # Get redirect URI from request 
        redirect_uri = request.args.get('redirect_uri')
        if not redirect_uri:
            return jsonify({"error": "Missing redirect_uri parameter"}), 400
        
        # Create a flow instance with client config
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            CLIENT_CONFIG, 
            scopes=SCOPES
        )
        
        # Set the redirect URI
        flow.redirect_uri = redirect_uri
        
        # Generate the authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        logger.info(f"Generated authorization URL: {authorization_url}")
        
        return jsonify({
            "url": authorization_url,
            "state": state
        })
    except Exception as e:
        logger.error(f"Error generating authorization URL: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/callback', methods=['POST'])
def callback():
    """Handle the OAuth callback and exchange the code for tokens."""
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return jsonify({"error": "Code is required"}), 400
            
        redirect_uri = data.get('redirect_uri')
        if not redirect_uri:
            return jsonify({"error": "Missing redirect_uri parameter"}), 400
        
        # Import os to set environment variable
        import os
        # Set environment variable to disable scope validation
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        
        # Create a flow instance
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES
        )
        flow.redirect_uri = redirect_uri
        
        # Exchange the code for tokens
        flow.fetch_token(code=data['code'])
        
        # Get credentials
        credentials = flow.credentials
        
        # Convert to dict for storage
        credentials_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        return jsonify({
            "success": True,
            "credentials": credentials_dict
        })
    except Exception as e:
        logger.error(f"Error in callback: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/fetch-calendar', methods=['POST'])
def fetch_calendar():
    """Fetch the user's calendar data from Google Calendar."""
    try:
        data = request.get_json()
        if not data or 'credentials' not in data:
            return jsonify({"error": "Credentials are required"}), 400
        
        # Recreate the credentials object
        credentials = google.oauth2.credentials.Credentials(
            **data['credentials']
        )
        
        # Build the Calendar API service
        calendar_service = googleapiclient.discovery.build(
            'calendar', 'v3', credentials=credentials
        )
        
        # Get time boundaries (two weeks by default)
        days_to_fetch = data.get('days', 14)
        time_min = datetime.utcnow()
        time_max = time_min + timedelta(days=days_to_fetch)
        
        # Format times for Google API
        time_min_str = time_min.isoformat() + 'Z'
        time_max_str = time_max.isoformat() + 'Z'
        
        # Fetch events from primary calendar
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=time_min_str,
            timeMax=time_max_str,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Process events into our format
        processed_events = process_google_events(events)
        
        return jsonify({
            "success": True,
            "google_calendar": processed_events
        })
    except Exception as e:
        logger.error(f"Error fetching calendar: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/create-events', methods=['POST'])
def create_events():
    """Create events in Google Calendar from the optimized schedule."""
    try:
        data = request.get_json()
        if not data or 'credentials' not in data or 'events' not in data:
            return jsonify({"error": "Both credentials and events are required"}), 400
        
        # Recreate the credentials object
        credentials = google.oauth2.credentials.Credentials(
            **data['credentials']
        )
        
        # Build the Calendar API service
        calendar_service = googleapiclient.discovery.build(
            'calendar', 'v3', credentials=credentials
        )
        
        # Get user's calendar timezone
        calendar_metadata = calendar_service.calendars().get(calendarId='primary').execute()
        user_timezone = calendar_metadata.get('timeZone', 'America/New_York')
        logger.info(f"User's Google Calendar timezone detected: {user_timezone}")
        
        events_to_create = data['events']
        created_events = []
        failed_events = []
        formatted_events_log = []  # Temporary storage for debugging
        
        # Create each event individually
        for event in events_to_create:
            try:
                # Format the event according to Google Calendar API requirements
                google_event = format_event_for_google(event, user_timezone)
                
                # Save formatted event for debugging
                formatted_events_log.append({
                    'original': event,
                    'formatted': google_event,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Insert the event
                created_event = calendar_service.events().insert(
                    calendarId='primary',
                    body=google_event
                ).execute()
                
                # Add to created events list
                created_events.append({
                    'id': created_event.get('id'),
                    'original_id': event.get('id'),
                    'description': event.get('description'),
                    'status': 'created'
                })
                
            except Exception as e:
                # Log the error and continue with next event
                logger.error(f"Error creating event '{event.get('description', 'Unknown')}': {str(e)}")
                failed_events.append({
                    'original_id': event.get('id'),
                    'description': event.get('description'),
                    'error': str(e)
                })
        
        # Write formatted events to a log file for debugging
        try:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f'calendar_events_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(log_path, 'w') as f:
                json.dump(formatted_events_log, f, indent=2)
            logger.info(f"Calendar events log saved to {log_path}")
        except Exception as e:
            logger.error(f"Error saving calendar events log: {str(e)}")
        
        return jsonify({
            "success": True,
            "created": len(created_events),
            "failed": len(failed_events),
            "created_events": created_events,
            "failed_events": failed_events,
            "user_timezone": user_timezone,
            "events_log_path": log_path if 'log_path' in locals() else None
        })
    except Exception as e:
        logger.error(f"Error creating events in Google Calendar: {str(e)}")
        return jsonify({"error": str(e)}), 500

def process_google_events(events):
    """Process Google Calendar events into our application format."""
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    processed_calendar = {day: [] for day in days_of_week}
    
    for event in events:
        # Skip events without start/end times
        if 'dateTime' not in event.get('start', {}) or 'dateTime' not in event.get('end', {}):
            continue
            
        # Parse event times
        start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
        
        # Get the day of the week
        day_of_week = days_of_week[start_time.weekday()]
        
        # Format times as HH:MM
        start_time_str = start_time.strftime('%H:%M')
        end_time_str = end_time.strftime('%H:%M')
        
        # Calculate duration in minutes
        duration = int((end_time - start_time).total_seconds() / 60)
        
        # Create the event entry
        processed_event = {
            "id": event.get('id', ''),
            "type": "google_event",
            "description": event.get('summary', 'Untitled Event'),
            "start_time": start_time_str,
            "end_time": end_time_str,
            "duration": duration,
            "location": event.get('location', ''),
        }
        
        # Add to the appropriate day
        processed_calendar[day_of_week].append(processed_event)
    
    return processed_calendar

def format_event_for_google(event, user_timezone='America/New_York'):
    """Format an event from our application format to Google Calendar API format."""
    # Get the date for the day of the week
    day_name = event.get('day', 'Monday')
    today = datetime.now()
    days_ahead = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 
                 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
    
    # Calculate the next occurrence of this day
    days_until_next = (days_ahead[day_name] - today.weekday()) % 7
    if days_until_next == 0:  # If today is the day, use next week
        days_until_next = 7
    
    event_date = (today + timedelta(days=days_until_next)).strftime('%Y-%m-%d')
    
    # Extract event details
    event_type = event.get('type', 'task')
    description = event.get('description', '').lower()
    
    # Parse and normalize start and end times to 24-hour format
    start_time = normalize_time(event.get('start_time', '09:00'), event_type, description)
    end_time = normalize_time(event.get('end_time', '10:00'), event_type, description)
    
    # Format the event for Google Calendar
    google_event = {
        'summary': event.get('description', 'Scheduled Event'),
        'location': event.get('location', ''),
        'description': f"Event Type: {event_type}\n" +
                      (f"Course: {event.get('course_code')}\n" if event.get('course_code') else "") +
                      f"Created by Lock-In Scheduler",
        'start': {
            'dateTime': f'{event_date}T{start_time}',
            'timeZone': user_timezone,
        },
        'end': {
            'dateTime': f'{event_date}T{end_time}',
            'timeZone': user_timezone,
        },
        'reminders': {
            'useDefault': True
        }
    }
    
    # Add original event data for debugging
    google_event['extendedProperties'] = {
        'private': {
            'originalEvent': json.dumps({k: v for k, v in event.items() if isinstance(v, (str, int, float, bool, list, dict))})
        }
    }
    
    return google_event

def normalize_time(time_str, event_type, description):
    """
    Convert time strings to properly formatted 24-hour format for Google Calendar.
    Returns time string in format 'HH:MM:00'
    """
    # Default times based on event types and descriptions
    default_ranges = {
        'breakfast': (7, 10),   # 7 AM - 10 AM
        'lunch': (11, 14),      # 11 AM - 2 PM
        'dinner': (17, 21),     # 5 PM - 9 PM
        'exam': (9, 17),        # 9 AM - 5 PM (daytime)
        'class': (8, 18),       # 8 AM - 6 PM (daytime)
        'task': (9, 17)         # 9 AM - 5 PM (daytime)
    }
    
    # Determine default time range based on event
    time_range = default_ranges['task']  # Default fallback
    
    if event_type == 'meal':
        if any(meal in description for meal in ['breakfast', 'morning meal']):
            time_range = default_ranges['breakfast']
        elif any(meal in description for meal in ['lunch', 'midday meal']):
            time_range = default_ranges['lunch']
        elif any(meal in description for meal in ['dinner', 'supper', 'evening meal']):
            time_range = default_ranges['dinner']
    elif event_type == 'class' or 'class' in description:
        time_range = default_ranges['class']
    elif event_type == 'exam' or any(term in description for term in ['exam', 'test', 'quiz']):
        time_range = default_ranges['exam']
    
    try:
        # Handle different time formats

        # Format 1: Just a number (e.g., "7" or "19")
        if time_str.isdigit():
            hour = int(time_str)
            # If hour is 1-12 and doesn't make sense for event type, convert to PM
            if 1 <= hour <= 12:
                min_hour, max_hour = time_range
                # If hour falls outside expected range for event type, adjust it
                if hour < min_hour or hour > max_hour:
                    # If we have an early hour for an evening event, make it PM
                    if min_hour > 12 and hour < 12:
                        hour += 12
                    # If we have a late hour for a morning event, make it AM
                    elif max_hour < 12 and hour > max_hour:
                        hour = hour % 12
            return f"{hour:02d}:00:00"
        
        # Format 2: HH:MM or H:MM 
        elif ':' in time_str:
            parts = time_str.split(':')
            if len(parts) >= 2:
                hour = int(parts[0])
                minute = int(parts[1])
                
                # If hour is 1-12, check if it makes sense for the event type
                if 1 <= hour <= 12:
                    min_hour, max_hour = time_range
                    # If hour falls outside expected range, adjust it
                    if hour < min_hour or hour > max_hour:
                        # For evening events with morning hours
                        if min_hour > 12 and hour < 12:
                            hour += 12
                        # For morning events with evening hours
                        elif max_hour < 12 and hour > max_hour:
                            hour = hour % 12
                
                return f"{hour:02d}:{minute:02d}:00"
        
    except (ValueError, TypeError) as e:
        logger.warning(f"Time conversion error: {str(e)} for {time_str}")
    
    # Fallback to default time if parsing fails
    default_hour, _ = time_range
    return f"{default_hour:02d}:00:00"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True) 