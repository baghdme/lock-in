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

# Google API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True) 