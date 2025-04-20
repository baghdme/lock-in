import json
import logging
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load environment variables for Anthropic API
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
DEFAULT_MODEL = os.getenv('LLM_MODEL', 'claude-3-7-sonnet-20250219')  # Default to Claude 3.7 Sonnet

# Log the configuration
logger.info(f"Using default model: {DEFAULT_MODEL}")

def call_anthropic_api(prompt, model=None, temperature=0.2, max_tokens=4000):
    """
    Pure function to call Anthropic API with a prompt.
    Returns the raw API response.
    """
    try:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        # Use provided model or fall back to default
        model_to_use = model or DEFAULT_MODEL
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
            timeout=60  # Longer timeout for complex requests
        )
        
        if response.status_code != 200:
            logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
            return {"error": f"Anthropic API returned error: {response.status_code} - {response.text}"}, response.status_code
        
        # Return the raw API response
        return response.json(), 200
            
    except Exception as e:
        logger.error(f"Error calling Anthropic API: {str(e)}")
        return {"error": str(e)}, 500

@app.route('/')
def index():
    """Health check endpoint."""
    return jsonify({
        "service": "IEP2 - Anthropic API Bridge",
        "status": "active",
        "version": "1.0.0",
        "default_model": DEFAULT_MODEL
    })

@app.route('/api/generate', methods=['POST'])
def create_schedule():
    """
    Simple API bridge to Anthropic.
    Takes a prompt and returns the raw API response.
    All business logic is handled by EEP1.
    """
    try:
        data = request.json
        if not data or 'prompt' not in data:
            return jsonify({"error": "No prompt provided"}), 400
        
        # Extract parameters
        prompt = data['prompt']
        model = data.get('model', DEFAULT_MODEL)
        temperature = data.get('temperature', 0.2)
        max_tokens = data.get('max_tokens', 4000)
        
        logger.info(f"Received prompt for Anthropic API (length: {len(prompt)} chars)")
        
        # Make the API call and return the raw response
        response, status_code = call_anthropic_api(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # If there was an error, return it directly
        if status_code != 200:
            return jsonify(response), status_code
            
        logger.info(f"Successfully called Anthropic API, returning raw response")
        
        # Return the raw API response - let EEP1 handle the parsing
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in API bridge: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    app.run(host='0.0.0.0', port=port, debug=True)
