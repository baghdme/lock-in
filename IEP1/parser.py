import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        if not data or 'prompt' not in data:
            return jsonify({"error": "Missing prompt parameter"}), 400
            
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                {"role": "user", "content": data['prompt']}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Return the raw response from OpenAI
        return jsonify(response.choices[0].message.content)
            
    except Exception as e:
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
