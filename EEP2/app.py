from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
import requests
import os
import json
import mimetypes
from werkzeug.utils import secure_filename
import base64
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx', 'csv', 'json', 'pptx'}
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_development')

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Service URLs
IEP_PARSE_URL = os.environ.get('IEP_PARSE_URL', 'http://localhost:5003') + '/parse'
IEP_EMBED_URL = os.environ.get('IEP_EMBED_URL', 'http://localhost:5004') + '/embed'

logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return render_template('index.html', error='No file part')
    
    file = request.files['file']
    
    if file.filename == '':
        return render_template('index.html', error='No selected file')
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Send the file to IEP-parse for document parsing
            with open(filepath, 'rb') as f:
                file_content = f.read()
                
            # Create a files dictionary with the file content
            files = {
                'file': (filename, file_content, mimetypes.guess_type(filepath)[0])
            }
            
            parse_response = requests.post(IEP_PARSE_URL, files=files)
            
            if parse_response.status_code != 200:
                return render_template('results.html', error=f"Document parsing error: {parse_response.text}")
            
            # Get the response data
            response_data = parse_response.json()
            
            # Get the extracted text from the parser
            parsed_text = response_data.get('text', '')
            # Get any extracted images
            images = response_data.get('images', [])
            
            if not parsed_text and not images:
                return render_template('results.html', error="No content could be extracted from the document")
            
            # Process OCR text from images to make it more accessible in the template
            ocr_texts = []
            for img in images:
                if 'ocr_text' in img and img['ocr_text'].strip():
                    ocr_texts.append({
                        'filename': img['filename'],
                        'text': img['ocr_text'].strip(),
                        'data': img['data']
                    })
            
            # If we have text, send it to the embedding service
            embedding_result = None
            if parsed_text:
                try:
                    # Increase timeout from 30 to 120 seconds
                    logger.info(f"Sending text to embedding service (length: {len(parsed_text)} chars)")
                    embed_response = requests.post(
                        IEP_EMBED_URL,
                        json={'text': parsed_text},
                        timeout=120
                    )
                    
                    if embed_response.status_code == 200:
                        embedding_result = embed_response.json()
                        logger.info(f"Successfully received embedding with {embedding_result.get('dimensions', 'unknown')} dimensions")
                    else:
                        logger.error(f"Embedding service error: {embed_response.text}")
                        return render_template('results.html', 
                                             parsed_text=parsed_text,
                                             images=images,
                                             ocr_texts=ocr_texts,
                                             error_embed=f"Embedding error: {embed_response.text}")
                except requests.Timeout:
                    logger.error("Timeout while connecting to embedding service")
                    return render_template('results.html', 
                                         parsed_text=parsed_text,
                                         images=images,
                                         ocr_texts=ocr_texts,
                                         error_embed=f"Embedding service timeout after 120 seconds. The text might be too large to process.")
                except requests.ConnectionError:
                    logger.error("Connection error to embedding service")
                    return render_template('results.html', 
                                         parsed_text=parsed_text,
                                         images=images,
                                         ocr_texts=ocr_texts,
                                         error_embed=f"Could not connect to embedding service. Make sure it's running at {IEP_EMBED_URL}")
                except requests.RequestException as e:
                    logger.error(f"Request error to embedding service: {str(e)}")
                    return render_template('results.html', 
                                         parsed_text=parsed_text,
                                         images=images,
                                         ocr_texts=ocr_texts,
                                         error_embed=f"Embedding service connection error: {str(e)}")
            
            # Display the parsed content, images, and embedding results
            return render_template('results.html', 
                                 parsed_text=parsed_text, 
                                 images=images,
                                 ocr_texts=ocr_texts,
                                 embedding=embedding_result)
                
        except requests.RequestException as e:
            return render_template('results.html', error=f'Connection error: {str(e)}')
        except Exception as e:
            return render_template('results.html', error=f'Error processing file: {str(e)}')
    
    return render_template('index.html', error='Invalid file type')

@app.route('/health', methods=['GET'])
def health_check():
    health_status = {
        'status': 'healthy',
        'services': {}
    }
    
    # Check if we can connect to the IEP-parse service
    try:
        parse_response = requests.get(os.environ.get('IEP_PARSE_URL', 'http://localhost:5003') + '/health', timeout=5)
        health_status['services']['iep_parse'] = {'status': 'healthy'} if parse_response.status_code == 200 else {'status': 'unhealthy'}
    except requests.RequestException:
        health_status['services']['iep_parse'] = {'status': 'unhealthy', 'error': 'Cannot connect to IEP-parse service'}
    
    # Check if we can connect to the IEP-embed service
    try:
        embed_response = requests.get(os.environ.get('IEP_EMBED_URL', 'http://localhost:5004') + '/health', timeout=5)
        health_status['services']['iep_embed'] = {'status': 'healthy'} if embed_response.status_code == 200 else {'status': 'unhealthy'}
    except requests.RequestException:
        health_status['services']['iep_embed'] = {'status': 'unhealthy', 'error': 'Cannot connect to IEP-embed service'}
    
    # Overall status is healthy only if all services are healthy
    if any(service.get('status') != 'healthy' for service in health_status['services'].values()):
        health_status['status'] = 'unhealthy'
    
    return jsonify(health_status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
