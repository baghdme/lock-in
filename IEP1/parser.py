import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import logging
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')
logger.debug("OpenAI API key configured")

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        logger.debug(f"Received data: {data}")
        
        if not data or 'prompt' not in data:
            logger.error("Missing prompt parameter in request")
            return jsonify({"error": "Missing prompt parameter"}), 400
            
        # Call OpenAI API
        logger.debug("Calling OpenAI API...")
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": data['prompt']}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            logger.debug(f"OpenAI response: {response}")
            
            if not response.choices or len(response.choices) == 0:
                logger.error("No choices in OpenAI response")
                return jsonify({"error": "No response from OpenAI"}), 500
                
            # Return the raw response from OpenAI
            content = response.choices[0].message.content
            logger.debug(f"Response content: {content}")
            
            # Try to parse the content as JSON to validate it
            try:
                json.loads(content)
            except json.JSONDecodeError:
                logger.warning("OpenAI response is not valid JSON, returning as is")
                
            return jsonify(content)
            
        except openai.error.OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return jsonify({"error": f"OpenAI API error: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in predict route: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

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
    app.run(host='0.0.0.0', port=5001, debug=True)
