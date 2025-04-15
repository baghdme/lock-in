from flask import Flask, request, jsonify
from pdfminer.high_level import extract_text as pdf_extract_text
import docx
from pptx import Presentation
from io import BytesIO
import logging
import traceback
import base64
import fitz  # PyMuPDF for PDF image extraction
import zipfile
import os

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_pptx_text(file_stream):
    try:
        logger.debug("Inside parse_pptx_text function")
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

def extract_pdf_images(file_bytes):
    images = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            image_list = page.get_images(full=True)
            logger.debug(f"Page {page_index+1} has {len(image_list)} images.")
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                images.append({
                    "filename": f"page{page_index+1}_img{img_index+1}.{image_ext}",
                    "data": encoded_image
                })
    except Exception as e:
        logger.error(f"Error extracting images from PDF: {str(e)}")
        logger.error(traceback.format_exc())
    return images

def extract_docx_images(docx_bytes):
    images = []
    try:
        with zipfile.ZipFile(BytesIO(docx_bytes)) as docx_zip:
            for zip_info in docx_zip.infolist():
                if zip_info.filename.startswith("word/media/"):
                    image_bytes = docx_zip.read(zip_info.filename)
                    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                    images.append({
                        "filename": os.path.basename(zip_info.filename),
                        "data": encoded_image
                    })
    except Exception as e:
        logger.error(f"Error extracting images from DOCX: {str(e)}")
        logger.error(traceback.format_exc())
    return images

def extract_pptx_images(pptx_bytes):
    images = []
    try:
        with zipfile.ZipFile(BytesIO(pptx_bytes)) as pptx_zip:
            for zip_info in pptx_zip.infolist():
                if zip_info.filename.startswith("ppt/media/"):
                    image_bytes = pptx_zip.read(zip_info.filename)
                    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                    images.append({
                        "filename": os.path.basename(zip_info.filename),
                        "data": encoded_image
                    })
    except Exception as e:
        logger.error(f"Error extracting images from PPTX: {str(e)}")
        logger.error(traceback.format_exc())
    return images

@app.route("/parse", methods=["POST"])
def parse_document():
    # Check if a file is provided in the request
    if "file" not in request.files:
        logger.error("No file provided in request")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename.lower() if file.filename else "unknown"
    logger.debug(f"Received file: {filename}")
    logger.debug(f"File type: {type(file)}")
    logger.debug(f"File content type: {file.content_type}")

    text = ""
    images = []

    try:
        if filename.endswith(".pdf"):
            logger.debug("Parsing PDF file")
            # Read the entire file as bytes for both text and image extraction
            file.seek(0)
            pdf_bytes = file.read()
            file_content = BytesIO(pdf_bytes)
            text = pdf_extract_text(file_content)
            logger.debug(f"PDF text extraction successful. Text length: {len(text)}")
            images = extract_pdf_images(pdf_bytes)
            logger.debug(f"PDF image extraction found {len(images)} images.")

        elif filename.endswith(".docx"):
            logger.debug("Parsing DOCX file")
            file.seek(0)
            docx_bytes = file.read()
            # Extract text using python-docx
            document = docx.Document(BytesIO(docx_bytes))
            text = "\n".join([para.text for para in document.paragraphs])
            logger.debug(f"DOCX text extraction successful. Text length: {len(text)}")
            images = extract_docx_images(docx_bytes)
            logger.debug(f"DOCX image extraction found {len(images)} images.")

        elif filename.endswith(".pptx"):
            logger.debug("Parsing PPTX file")
            file.seek(0)
            pptx_bytes = file.read()
            # Extract text using python-pptx
            text = parse_pptx_text(BytesIO(pptx_bytes))
            logger.debug(f"PPTX text extraction successful. Text length: {len(text)}")
            images = extract_pptx_images(pptx_bytes)
            logger.debug(f"PPTX image extraction found {len(images)} images.")

        else:
            logger.debug("Parsing plain text file")
            file.seek(0)
            try:
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
    # Return both text and images in the response
    return jsonify({"text": text, "images": images}), 200

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "iep-parse"}), 200

if __name__ == "__main__":
    logger.info("Starting IEP-parse service on port 5003")
    app.run(host="0.0.0.0", port=5003, debug=True)
