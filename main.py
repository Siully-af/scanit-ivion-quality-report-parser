from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import logging
from typing import Optional, Dict, Any, Union
from functools import wraps
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
REQUEST_TIMEOUT = 30  # seconds
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/tiff', 'image/bmp'}

def handle_errors(f):
    """Decorator for consistent error handling"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in {f.__name__}: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            raise
    return decorated_function

def validate_url(url: str) -> bool:
    """Validate if URL is properly formatted"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def extract_field(text: str, label: str, field_type: str = "text", allow_xray: bool = False) -> Optional[Union[str, float, Dict[str, str]]]:
    """
    Extract field value from text using regex pattern
    
    Args:
        text: Source text to search in
        label: Field label to search for
        field_type: Type of field (text, number, duration, select, coordinate)
        allow_xray: Whether to allow XRAY MAPS in coordinate fields
    
    Returns:
        Extracted value or None if not found
    """
    try:
        # Escape special regex characters in label
        escaped_label = re.escape(label)
        pattern = rf"{escaped_label}:\s*(.+?)(?:\n|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        if not match:
            logger.debug(f"Field '{label}' not found in text")
            return None
        
        raw = match.group(1).strip()
        
        if not raw:
            return None
            
        if field_type == "number":
            try:
                # Remove common units and formatting
                cleaned = (raw.replace(",", "")
                             .replace("ft²", "")
                             .replace("m²", "")
                             .replace("GB", "")
                             .replace("MB", "")
                             .strip())
                
                # Extract first number found
                number_match = re.search(r'[\d.]+', cleaned)
                if number_match:
                    return float(number_match.group())
                return None
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse number from '{raw}': {e}")
                return None
                
        elif field_type == "duration":
            # Handle various duration formats
            duration_patterns = [
                r'(\d+):(\d+):(\d+)',  # HH:MM:SS
                r'(\d+)h\s*(\d+)m\s*(\d+)s',  # 1h 30m 45s
                r'(\d+)\s*hours?\s*(\d+)\s*minutes?\s*(\d+)\s*seconds?'  # 1 hour 30 minutes 45 seconds
            ]
            
            for pattern in duration_patterns:
                match = re.search(pattern, raw, re.IGNORECASE)
                if match:
                    try:
                        h, m, s = [int(g) for g in match.groups()]
                        return h * 3600 + m * 60 + s
                    except ValueError:
                        continue
            
            logger.warning(f"Failed to parse duration from '{raw}'")
            return None
            
        elif field_type == "select":
            return {"name": raw}
            
        elif field_type == "coordinate":
            if "XRAY MAPS" in raw.upper() and not allow_xray:
                return None
            return raw
            
        return raw
        
    except Exception as e:
        logger.error(f"Error extracting field '{label}': {e}")
        return None

@handle_errors
def extract_pdf_text(url: str) -> str:
    """
    Extract text from PDF at given URL
    
    Args:
        url: URL of the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        RuntimeError: If PDF extraction fails
    """
    if not validate_url(url):
        raise ValueError(f"Invalid PDF URL: {url}")
    
    logger.info(f"Extracting text from PDF: {url}")
    
    # Set headers to mimic browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(
        url, 
        timeout=REQUEST_TIMEOUT,
        headers=headers,
        stream=True
    )
    response.raise_for_status()
    
    # Check content type
    content_type = response.headers.get('content-type', '').lower()
    if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
        logger.warning(f"Unexpected content type: {content_type}")
    
    # Check file size
    content_length = response.headers.get('content-length')
    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise ValueError(f"PDF file too large: {content_length} bytes")
    
    try:
        pdf_content = response.content
        logger.info(f"Downloaded PDF: {len(pdf_content)} bytes")
        
        with BytesIO(pdf_content) as f:
            doc = fitz.open(stream=f, filetype="pdf")
            text = ""
            
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += page_text
                logger.debug(f"Extracted {len(page_text)} characters from page {page_num + 1}")
            
            doc.close()
            
        logger.info(f"Successfully extracted {len(text)} characters from PDF")
        return text
        
    except Exception as e:
        raise RuntimeError(f"Failed to extract PDF text: {str(e)}")

@handle_errors
def extract_image_text(url: str) -> str:
    """
    Extract text from image using OCR
    
    Args:
        url: URL of the image file
        
    Returns:
        Extracted text content
        
    Raises:
        RuntimeError: If image text extraction fails
    """
    if not validate_url(url):
        raise ValueError(f"Invalid image URL: {url}")
    
    logger.info(f"Extracting text from image: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(
        url, 
        timeout=REQUEST_TIMEOUT,
        headers=headers,
        stream=True
    )
    response.raise_for_status()
    
    # Check content type
    content_type = response.headers.get('content-type', '').lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        logger.warning(f"Unexpected image content type: {content_type}")
    
    # Check file size
    content_length = response.headers.get('content-length')
    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise ValueError(f"Image file too large: {content_length} bytes")
    
    try:
        image_content = response.content
        logger.info(f"Downloaded image: {len(image_content)} bytes")
        
        image = Image.open(BytesIO(image_content))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Configure tesseract for better accuracy
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .:,-'
        
        text = pytesseract.image_to_string(image, config=custom_config)
        
        logger.info(f"Successfully extracted {len(text)} characters from image")
        return text
        
    except Exception as e:
        raise RuntimeError(f"Failed to extract image text: {str(e)}")

def validate_request_data(data: Dict[str, Any]) -> Dict[str, str]:
    """Validate and sanitize request data"""
    required_fields = ["pdf_url", "screenshot_url", "dataset_name"]
    
    for field in required_fields:
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")
    
    # Sanitize dataset name
    dataset_name = str(data["dataset_name"]).strip()
    if not dataset_name or len(dataset_name) > 100:
        raise ValueError("Invalid dataset name")
    
    # Validate URLs
    for url_field in ["pdf_url", "screenshot_url"]:
        url = str(data[url_field]).strip()
        if not validate_url(url):
            raise ValueError(f"Invalid URL format: {url_field}")
    
    return {
        "pdf_url": data["pdf_url"],
        "screenshot_url": data["screenshot_url"],
        "dataset_name": dataset_name
    }

@app.route("/parse", methods=["POST"])
def parse():
    """Main parsing endpoint"""
    start_time = time.time()
    
    try:
        # Validate request
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        body = request.get_json()
        if not body:
            return jsonify({"error": "Empty request body"}), 400
        
        # Validate and sanitize input
        validated_data = validate_request_data(body)
        pdf_url = validated_data["pdf_url"]
        screenshot_url = validated_data["screenshot_url"]
        dataset_name = validated_data["dataset_name"]
        
        logger.info(f"Processing request for dataset: {dataset_name}")
        
        # Extract text from both sources
        pdf_text = extract_pdf_text(pdf_url)
        image_text = extract_image_text(screenshot_url)
        
        # Verify dataset name exists in screenshot
        if dataset_name.lower() not in image_text.lower():
            logger.warning(f"Dataset '{dataset_name}' not found in screenshot text")
            return jsonify({
                "error": f"Dataset '{dataset_name}' not found in screenshot",
                "available_text_sample": image_text[:200] + "..." if len(image_text) > 200 else image_text
            }), 400
        
        # Parse fields from PDF
        output = {
            "Dataset name": dataset_name,
            "Recorded at": extract_field(pdf_text, "Recorded at"),
            "Duration": extract_field(pdf_text, "Duration", field_type="duration"),
            "Processed at": extract_field(pdf_text, "Processed at"),
            "Scanned area": extract_field(pdf_text, "Scanned area", field_type="number"),
            "Billed area": extract_field(pdf_text, "Billed area", field_type="number"),
            "Panoramas": extract_field(pdf_text, "Panoramas", field_type="number"),
            "Control points": extract_field(pdf_text, "Control points", field_type="number"),
            "Point cloud resolution": extract_field(pdf_text, "Point cloud resolution", field_type="select"),
            "Colorized": extract_field(pdf_text, "Colorized", field_type="select"),
            "Processing preset": extract_field(pdf_text, "Processing preset selection"),
            "Person blurring": extract_field(pdf_text, "Person blurring", field_type="select"),
            "License Plate blurring": extract_field(pdf_text, "License Plate blurring", field_type="select"),
            "Floor filling": extract_field(pdf_text, "Floor filling", field_type="select"),
            "Panorama embedded e57": extract_field(pdf_text, "Panorama embedded e57", field_type="select"),
            "Surveyed control points": extract_field(pdf_text, "Surveyed control points", field_type="select"),
            "Coordinate system": extract_field(pdf_text, "Coordinate system", field_type="coordinate"),
            "Device serial": extract_field(pdf_text, "Device serial"),
            "System software": extract_field(pdf_text, "System software"),
        }
        
        # Parse fields from screenshot
        image_units = extract_field(image_text, f"{dataset_name} Units consumed", field_type="number")
        image_size = extract_field(image_text, f"{dataset_name} Size", field_type="number")
        
        if image_units is not None:
            output["Units consumed"] = image_units
        
        if image_size is not None:
            output["Size"] = image_size
        
        # Validate required fields
        required_fields = ["Dataset name", "Recorded at", "Duration", "Processed at", "Scanned area"]
        missing = [f for f in required_fields if output.get(f) is None]
        
        if missing:
            logger.warning(f"Missing required fields: {missing}")
            return jsonify({
                "error": "Missing required fields",
                "missing": missing,
                "extracted_data": output
            }), 400
        
        processing_time = time.time() - start_time
        logger.info(f"Successfully processed dataset '{dataset_name}' in {processing_time:.2f}s")
        
        return jsonify(output)
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": f"Validation error: {str(e)}"}), 400
        
    except RuntimeError as e:
        logger.error(f"Processing error: {str(e)}")
        return jsonify({"error": f"Processing error: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "SCANIT Quality Report Parser",
        "version": "2.0.0",
        "timestamp": time.time()
    }), 200

@app.route("/", methods=["GET"])
def root():
    """Root endpoint"""
    return jsonify({
        "message": "SCANIT Quality Report Parser API",
        "version": "2.0.0",
        "endpoints": {
            "/parse": "POST - Parse quality reports",
            "/health": "GET - Health check"
        }
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    logger.info("Starting SCANIT Quality Report Parser...")
    app.run(host="0.0.0.0", port=10000, debug=False)
