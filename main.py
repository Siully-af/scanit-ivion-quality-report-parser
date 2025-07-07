from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re
import logging
from functools import wraps
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

REQUEST_TIMEOUT = 30  # seconds
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/tiff', 'image/bmp'}

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise
    return decorated_function

def validate_url(url: str) -> bool:
    return url.startswith('http://') or url.startswith('https://')

@handle_errors
def extract_pdf_text(url: str) -> str:
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    with BytesIO(response.content) as f:
        doc = fitz.open(stream=f, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
    return text

@handle_errors
def extract_image_text(url: str) -> str:
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content)).convert('RGB')
    return pytesseract.image_to_string(image, config='--oem 3 --psm 6')

def extract_field(text, label, field_type="text"):
    pattern = rf"{re.escape(label)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).strip()
    if field_type == "number":
        raw = re.sub(r'[^\d.]', '', raw)
        return float(raw) if raw else None
    elif field_type == "duration":
        h, m, s = map(int, raw.split(':'))
        return h * 3600 + m * 60 + s
    elif field_type == "select":
        return {"name": raw}
    return raw

def extract_dataset_name(pdf_text: str) -> Optional[str]:
    """
    Attempt to extract a dataset name from the PDF text.
    Tries several patterns based on known naming formats.
    """
    patterns = [
        r'Dataset Name:\s*(.+)',  # exact label match
        r'Dataset:\s*(.+)',       # alternative label
        r'Project Name:\s*(.+)',  # sometimes it's labeled like this
        r'([A-Z]{2,5}-\d{5}[-_ ]\d{2}-\d{2}-\d{2})',  # pattern like IPX-25002_00-00-01
    ]
    for pattern in patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    logger.warning("Could not find dataset name in PDF text.")
    return None


@app.route("/parse", methods=["POST"])
def parse():
    start_time = time.time()
    data = request.get_json()
    pdf_url = data.get("pdf_url")
    screenshot_url = data.get("screenshot_url")

    if not pdf_url or not screenshot_url:
        return jsonify({"error": "Missing pdf_url or screenshot_url"}), 400

    pdf_text = extract_pdf_text(pdf_url)
    image_text = extract_image_text(screenshot_url)

    dataset_name = extract_dataset_name(pdf_text)
    if not dataset_name or dataset_name.lower() not in image_text.lower():
        return jsonify({"error": f"Dataset '{dataset_name}' not found in screenshot"}), 400

    output = {
        "Dataset name": dataset_name,
        "Recorded at": extract_field(pdf_text, "Recorded at"),
        "Duration": extract_field(pdf_text, "Duration", "duration"),
        "Processed at": extract_field(pdf_text, "Processed at"),
        "Scanned area": extract_field(pdf_text, "Scanned area", "number"),
        "Billed area": extract_field(pdf_text, "Billed area", "number"),
        "Panoramas": extract_field(pdf_text, "Panoramas", "number"),
        "Control points": extract_field(pdf_text, "Control points", "number"),
        "Point cloud resolution": extract_field(pdf_text, "Point cloud resolution", "select"),
        "Colorized": extract_field(pdf_text, "Colorized", "select"),
        "Processing preset": extract_field(pdf_text, "Processing preset selection"),
        "Person blurring": extract_field(pdf_text, "Person blurring", "select"),
        "License Plate blurring": extract_field(pdf_text, "License Plate blurring", "select"),
        "Floor filling": extract_field(pdf_text, "Floor filling", "select"),
        "Panorama embedded e57": extract_field(pdf_text, "Panorama embedded e57", "select"),
        "Surveyed control points": extract_field(pdf_text, "Surveyed control points", "select"),
        "Coordinate system": extract_field(pdf_text, "Coordinate system"),
        "Device serial": extract_field(pdf_text, "Device serial"),
        "System software": extract_field(pdf_text, "System software"),
        "Units consumed": extract_field(image_text, f"{dataset_name} Units consumed", "number"),
        "Size": extract_field(image_text, f"{dataset_name} Size", "number"),
    }

    missing = [k for k, v in output.items() if v is None]
    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    logger.info(f"Processed '{dataset_name}' in {time.time() - start_time:.2f}s")
    return jsonify(output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
