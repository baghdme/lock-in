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
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2
import imghdr  # for image format detection
import sys

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if Tesseract is installed and configure it
try:
    # Check for environment variable first
    env_tesseract_path = os.environ.get('TESSERACT_PATH')
    if env_tesseract_path and os.path.exists(env_tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = env_tesseract_path
        logger.info(f"Using Tesseract path from environment variable: {env_tesseract_path}")
    
    # Try to get Tesseract version
    tesseract_version = pytesseract.get_tesseract_version()
    logger.info(f"Tesseract OCR version: {tesseract_version}")
except Exception as e:
    logger.error(f"ERROR: Tesseract not properly installed or configured: {str(e)}")
    # Try common Windows paths
    if sys.platform.startswith('win'):
        for path in [r'C:\Program Files\Tesseract-OCR\tesseract.exe', 
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"Set Tesseract path to: {path}")
                break

def preprocess_image_for_ocr(image):
    """Preprocess image to improve OCR results"""
    try:
        # Convert to grayscale if needed
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Apply sharpening
        image = image.filter(ImageFilter.SHARPEN)
        
        # Apply adaptive thresholding with OpenCV
        img_cv = np.array(image)
        img_cv = cv2.adaptiveThreshold(
            img_cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Convert back to PIL image
        return Image.fromarray(img_cv)
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        return image

def ocr_extract_text(image_bytes):
    """Extract text from an image using OCR"""
    try:
        image = Image.open(BytesIO(image_bytes))
        logger.debug(f"Processing image: {image.format} {image.size} {image.mode}")
        
        # Preprocess the image
        processed_image = preprocess_image_for_ocr(image)
        
        # Try multiple PSM modes for best results
        text_results = []
        psm_modes = [3, 6, 11]  # Most useful PSM modes
        
        for psm in psm_modes:
            try:
                custom_config = f'--oem 3 --psm {psm}'
                text = pytesseract.image_to_string(processed_image, config=custom_config)
                if text.strip() and text.strip() not in [t.strip() for t in text_results]:
                    text_results.append(text)
            except Exception as e:
                logger.error(f"OCR with PSM {psm} failed: {str(e)}")
        
        # Try with original image as fallback
        try:
            text = pytesseract.image_to_string(image)
            if text.strip() and text.strip() not in [t.strip() for t in text_results]:
                text_results.append(text)
        except Exception as e:
            logger.error(f"OCR with original image failed: {str(e)}")
            
        # Use the longest extracted text
        if text_results:
            final_text = max(text_results, key=lambda x: len(x.strip()))
            logger.info(f"Selected OCR result (length: {len(final_text.strip())})")
            return final_text
        else:
            logger.warning("No text extracted from image")
            return ""
            
    except Exception as e:
        logger.error(f"Error during OCR: {str(e)}")
        return ""

def add_ocr_to_images(images):
    """Process OCR for a list of images"""
    logger.info(f"Processing OCR for {len(images)} images")
    
    for idx, img in enumerate(images):
        try:
            logger.debug(f"Processing image {idx+1}/{len(images)}: {img.get('filename', 'unknown')}")
            image_bytes = base64.b64decode(img['data'])
            ocr_text = ocr_extract_text(image_bytes)
            
            # Add OCR text to the image dict
            img['ocr_text'] = ocr_text
            
            if ocr_text.strip():
                logger.info(f"Extracted {len(ocr_text.strip())} chars from image {idx+1}")
            else:
                logger.warning(f"No text extracted from image {idx+1}")
                
        except Exception as e:
            logger.error(f"Error processing OCR for image {idx+1}: {str(e)}")
            img['ocr_text'] = ""
    
    return images

def extract_pdf_images(file_bytes):
    """Extract images from PDF files"""
    images = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        # Extract embedded images
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            image_list = page.get_images(full=True)
            
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
                
        # Render each page as an image (to capture text in images)
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            matrix = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            encoded_image = base64.b64encode(img_bytes).decode('utf-8')
            
            images.append({
                "filename": f"page{page_index+1}_rendered.png",
                "data": encoded_image,
                "is_rendered_page": True
            })
            
    except Exception as e:
        logger.error(f"Error extracting images from PDF: {str(e)}")
    
    return images

def extract_docx_images(docx_bytes):
    """Extract images from DOCX files"""
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
    return images

def extract_pptx_images(pptx_bytes):
    """Extract images from PPTX files"""
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
    return images

def is_image_file(file_bytes, filename):
    """Check if a file is an image"""
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
        return True
    
    try:
        img_type = imghdr.what(None, h=file_bytes)
        return img_type is not None
    except:
        pass
        
    try:
        Image.open(BytesIO(file_bytes))
        return True
    except:
        return False

def extract_images_from_generic_file(file_bytes, filename):
    """Extract images from generic files"""
    images = []
    
    if is_image_file(file_bytes, filename):
        try:
            encoded_image = base64.b64encode(file_bytes).decode('utf-8')
            images.append({
                "filename": filename,
                "data": encoded_image
            })
            logger.info(f"Added file as image: {filename}")
        except Exception as e:
            logger.error(f"Error adding file as image: {str(e)}")
    
    return images

@app.route("/parse", methods=["POST"])
def parse_document():
    """Main endpoint to parse documents"""
    if "file" not in request.files:
        logger.error("No file provided in request")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename.lower() if file.filename else "unknown"
    logger.debug(f"Received file: {filename}")

    text = ""
    images = []

    try:
        # Read the file content
        file.seek(0)
        file_bytes = file.read()
        file_content = BytesIO(file_bytes)
        
        # Process based on file type
        if filename.endswith(".pdf"):
            file_content.seek(0)
            text = pdf_extract_text(file_content)
            images = extract_pdf_images(file_bytes)

        elif filename.endswith(".docx"):
            document = docx.Document(file_content)
            text = "\n".join([para.text for para in document.paragraphs])
            images = extract_docx_images(file_bytes)

        elif filename.endswith(".pptx"):
            presentation = Presentation(file_content)
            text = "\n".join([shape.text for slide in presentation.slides 
                             for shape in slide.shapes if hasattr(shape, "text")])
            images = extract_pptx_images(file_bytes)

        else:
            # Try to read as text
            try:
                file_content.seek(0)
                try:
                    text = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text = file_bytes.decode("latin-1")
            except Exception as e:
                logger.error(f"Text file parsing error: {str(e)}")
            
            # Try image extraction for any file type
            if not images:
                images = extract_images_from_generic_file(file_bytes, filename)

        # Process OCR on images
        images = add_ocr_to_images(images)
        
        # Combine OCR text with document text
        combined_text = text if text else ""
        ocr_text_sections = []
        
        for idx, img in enumerate(images):
            ocr_text = img.get('ocr_text', '').strip()
            if ocr_text:
                source = "Page" if img.get('is_rendered_page') else "Image"
                ocr_section = f"\n\n----- OCR TEXT FROM {source} {idx+1} -----\n{ocr_text}\n"
                ocr_text_sections.append(ocr_section)
        
        # Add OCR text sections to combined text
        if ocr_text_sections:
            if combined_text:
                combined_text += "\n\n===== OCR EXTRACTED TEXT =====\n"
            else:
                combined_text = "===== OCR EXTRACTED TEXT =====\n"
            combined_text += "".join(ocr_text_sections)
        
        text = combined_text

    except Exception as e:
        logger.error(f"Error parsing document: {str(e)}")
        return jsonify({"error": str(e)}), 500

    logger.debug("Document parsed successfully")
    return jsonify({"text": text, "images": images}), 200

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "iep-parse"}), 200

@app.route("/set-tesseract-path", methods=["POST"])
def set_tesseract_path():
    """Endpoint to manually set the Tesseract path"""
    try:
        data = request.get_json()
        if not data or "path" not in data:
            return jsonify({"error": "No path provided"}), 400
            
        path = data["path"]
        if not os.path.exists(path):
            return jsonify({"error": f"Path does not exist: {path}"}), 400
            
        pytesseract.pytesseract.tesseract_cmd = path
        logger.info(f"Tesseract path manually set to: {path}")
        
        version = pytesseract.get_tesseract_version()
        return jsonify({
            "success": True, 
            "message": f"Tesseract path set successfully. Version: {version}"
        }), 200
    except Exception as e:
        logger.error(f"Error setting Tesseract path: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting IEP-parse service on port 5003")
    app.run(host="0.0.0.0", port=5003, debug=False)
