from flask import Flask, request, jsonify
from pdfminer.high_level import extract_text as pdf_extract_text
import docx
from pptx import Presentation
from io import BytesIO
import logging
import traceback

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_pptx(file_stream):
    try:
        logger.debug("Inside parse_pptx function")
        presentation = Presentation(file_stream)
        text = ""
        for slide in presentation.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
        return text
    except Exception as e:
        logger.error(f"Error parsing PPTX file: {str(e)}")
        logger.error(traceback.format_exc())
        raise e

@app.route("/parse", methods=["POST"])
def parse_document():
    # Check if a file is provided in the request
    if "file" not in request.files:
        logger.error("No file provided in request")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename.lower() if file.filename else "unknown"
    logger.debug(f"Received file: {filename}")
    
    # Debug information about the received file
    logger.debug(f"File type: {type(file)}")
    logger.debug(f"File content type: {file.content_type}")
    
    try:
        # If the file is a PDF, extract text using pdfminer
        if filename.endswith(".pdf"):
            logger.debug("Parsing PDF file")
            try:
                # Save the file content to a BytesIO object
                file_content = BytesIO(file.read())
                text = pdf_extract_text(file_content)
                logger.debug(f"PDF extraction successful. Text length: {len(text)}")
            except Exception as pdf_error:
                logger.error(f"PDF parsing error: {str(pdf_error)}")
                logger.error(traceback.format_exc())
                raise pdf_error
        
        # If the file is DOCX, use python-docx to extract text
        elif filename.endswith(".docx"):
            logger.debug("Parsing DOCX file")
            try:
                document = docx.Document(BytesIO(file.read()))
                text = "\n".join([para.text for para in document.paragraphs])
                logger.debug(f"DOCX extraction successful. Text length: {len(text)}")
            except Exception as docx_error:
                logger.error(f"DOCX parsing error: {str(docx_error)}")
                logger.error(traceback.format_exc())
                raise docx_error
        
        # If the file is a PPTX, use python-pptx to extract text
        elif filename.endswith(".pptx"):
            logger.debug("Parsing PPTX file")
            try:
                # Reset file stream position to the beginning in case it was read before
                file.seek(0)
                file_bytes = BytesIO(file.read())
                text = parse_pptx(file_bytes)
                logger.debug(f"PPTX extraction successful. Text length: {len(text)}")
            except Exception as pptx_error:
                logger.error(f"PPTX parsing error: {str(pptx_error)}")
                logger.error(traceback.format_exc())
                raise pptx_error
        
        # Otherwise, assume it's a plain text file
        else:
            logger.debug("Parsing plain text file")
            try:
                file.seek(0)
                text = file.read().decode("utf-8")
                logger.debug(f"Text file extraction successful. Text length: {len(text)}")
            except UnicodeDecodeError:
                logger.debug("UTF-8 decoding failed, trying with latin-1")
                file.seek(0)
                text = file.read().decode("latin-1")
                logger.debug(f"Text file extraction with latin-1 successful. Text length: {len(text)}")
            except Exception as text_error:
                logger.error(f"Text file parsing error: {str(text_error)}")
                logger.error(traceback.format_exc())
                raise text_error
            
    except Exception as e:
        logger.error(f"Error parsing document: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

    logger.debug("Document parsed successfully")
    return jsonify({"text": text}), 200

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "iep-parse"}), 200

if __name__ == "__main__":
    logger.info("Starting IEP-parse service on port 5003")
    app.run(host="0.0.0.0", port=5003, debug=True)
