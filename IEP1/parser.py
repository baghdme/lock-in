import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import logging
import json
import traceback

# ----------------------------------------------
# Initialization and Setup
# ----------------------------------------------

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Check if API key is available
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    logger.error("OPENAI_API_KEY environment variable is not set!")
else:
    logger.info("OPENAI_API_KEY environment variable is set")

# Create OpenAI client
client = OpenAI(api_key=api_key)
logger.debug("OpenAI client configured")

# ----------------------------------------------
# Prediction Endpoint
# ----------------------------------------------

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        logger.debug(f"Received data: {data}")
        
        if not data or 'prompt' not in data:
            logger.error("Missing prompt parameter in request")
            return jsonify({"error": "Missing prompt parameter"}), 400
        
        if not api_key:
            logger.error("Cannot call OpenAI API: OPENAI_API_KEY is not set")
            return jsonify({"error": "OpenAI API key is not configured"}), 500
            
        # Call OpenAI API
        logger.debug("Calling OpenAI API...")
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": data['prompt']}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            logger.debug(f"OpenAI response type: {type(response)}")
            logger.debug(f"OpenAI response: {response}")
            
            if not response.choices or len(response.choices) == 0:
                logger.error("No choices in OpenAI response")
                return jsonify({"error": "No response from OpenAI"}), 500
                
            # Return the raw response from OpenAI
            content = response.choices[0].message.content
            logger.debug(f"Response content: {content}")
            
            # Try to parse the content as JSON to validate it
            try:
                parsed_json = json.loads(content)
                # If it's valid JSON, return it as an object
                return jsonify(parsed_json)
            except json.JSONDecodeError as e:
                logger.warning(f"OpenAI response is not valid JSON: {e}")
                # If it's not valid JSON, wrap it in a response object
                return jsonify({"response": content, "warning": "Response was not valid JSON"})
            
        except Exception as e:
            error_stack = traceback.format_exc()
            logger.error(f"OpenAI API error: {str(e)}")
            logger.error(f"Stack trace: {error_stack}")
            return jsonify({"error": f"OpenAI API error: {str(e)}"}), 500
            
    except Exception as e:
        error_stack = traceback.format_exc()
        logger.error(f"Error in predict route: {str(e)}")
        logger.error(f"Stack trace: {error_stack}")
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------
# Health Check Endpoint
# ----------------------------------------------

@app.route('/health', methods=['GET'])
def health_endpoint():
    if not api_key:
        return jsonify({"status": "unhealthy", "error": "OPENAI_API_KEY environment variable not set"}), 500
    try:
        # Simple test completion to check API connectivity
        client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        return jsonify({"status": "healthy", "model": "gpt-3.5-turbo", "openai_status": "connected"}), 200
    except Exception as e:
        error_stack = traceback.format_exc()
        logger.error(f"OpenAI connection error: {str(e)}")
        logger.error(f"Stack trace: {error_stack}")
        return jsonify({"status": "unhealthy", "error": f"OpenAI connection error: {str(e)}", "openai_status": "disconnected"}), 500

# ----------------------------------------------
# Main Execution
# ----------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
