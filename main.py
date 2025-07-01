import fitz  # PyMuPDF
import pytesseract
import requests
from flask import Flask, request, jsonify
from PIL import Image
from io import BytesIO
import re

app = Flask(__name__)

REQUIRED_PDF_FIELDS = [
    "Dataset name", "Recorded at", "Duration", "Processed at",
    "Scanned area", "Billed area", "Panoramas", "Control points",
    "Point cloud resolution", "Colorized", "Processing preset",
    "Person blurring", "License Plate blurring", "Floor filling",
    "Panorama embedded e57", "Surveyed control points", "Coordinate system",
    "Device serial", "System software"
]

REQUIRED_SCREENSHOT_FIELDS = ["Units consumed", "Size"]

def extract_pdf_text(url):
    response = requests.get(url)
    doc = fitz.open(stream=response.content, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def extract_screenshot_text(url):
    response = requests.get(url)
    image = Image.open(BytesIO(response.content))
    return pytesseract.image_to_string(image)

def extract_field(text, label, type="text"):
    pattern = rf"{label}:\s*([^\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).strip()

    if type == "number":
        raw = raw.replace(",", "").replace("ft²", "").replace("m²", "").replace("GB", "").strip()
        try:
            return float(raw)
        except ValueError:
            return None
    elif type == "select":
        return {"name": raw}
    else:
        return raw

@app.route("/parse", methods=["POST"])
def parse():
    data = request.json
    pdf_url = data.get("pdf_url")
    screenshot_url = data.get("screenshot_url")
    dataset_name = data.get("dataset_name")

    if not pdf_url or not screenshot_url or not dataset_name:
        return jsonify({"error": "Missing URLs or dataset name"}), 400

    pdf_text = extract_pdf_text(pdf_url)
    screenshot_text = extract_screenshot_text(screenshot_url)

    extracted_data = {
        "Dataset name": dataset_name,
        "Recorded at": extract_field(pdf_text, "Recorded at"),
        "Duration": parse_duration(extract_field(pdf_text, "Duration")),
        "Processed at": extract_field(pdf_text, "Processed at"),
        "Scanned area": extract_field(pdf_text, "Scanned area", type="number"),
        "Billed area": extract_field(pdf_text, "Billed area", type="number"),
        "Panoramas": extract_field(pdf_text, "Panoramas", type="number"),
        "Control points": extract_field(pdf_text, "Control points", type="number"),
        "Point cloud resolution": extract_field(pdf_text, "Point cloud resolution", type="select"),
        "Colorized": extract_field(pdf_text, "Colorized", type="select"),
        "Processing preset": extract_field(pdf_text, "Processing preset selection"),
        "Person blurring": extract_field(pdf_text, "Person blurring", type="select"),
        "License Plate blurring": extract_field(pdf_text, "License Plate blurring", type="select"),
        "Floor filling": extract_field(pdf_text, "Floor filling", type="select"),
        "Panorama embedded e57": extract_field(pdf_text, "Panorama embedded e57", type="select"),
        "Surveyed control points": extract_field(pdf_text, "Surveyed control points", type="select"),
        "Coordinate system": clean_coordinate_system(extract_field(pdf_text, "Coordinate system")),
        "Device serial": extract_field(pdf_text, "Device serial"),
        "System software": extract_field(pdf_text, "System software"),
        "Units consumed": extract_field(screenshot_text, dataset_name, type="number"),
        "Size": extract_field(screenshot_text, f"{dataset_name} ", type="number")  # e.g., 'IPX-25002_01-00-01  110  0.04'
    }

    # Check for missing required fields
    missing_fields = [
        key for key in REQUIRED_PDF_FIELDS + REQUIRED_SCREENSHOT_FIELDS
        if extracted_data.get(key) in [None, "", {}]
    ]
    if missing_fields:
        return jsonify({"error": "Missing required fields", "fields": missing_fields}), 400

    return jsonify(extracted_data)

def parse_duration(text):
    """Parses a duration like '00:17:43' into seconds."""
    if not text or not re.match(r"\d{2}:\d{2}:\d{2}", text):
        return None
    h, m, s = map(int, text.split(":"))
    return h * 3600 + m * 60 + s

def clean_coordinate_system(value):
    if value and "XRAY" not in value.upper():
        return value
    return ""
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
