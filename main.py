from flask import Flask, request, jsonify
import requests
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from io import BytesIO
import re
from datetime import datetime

app = Flask(__name__)

def download_file(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def extract_text_from_pdf(pdf_bytes):
    text = ""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_image(image_bytes):
    image = Image.open(BytesIO(image_bytes))
    return pytesseract.image_to_string(image)

def extract_field(text, label, type="string"):
    pattern = rf"{re.escape(label)}\s*[:\-]?\s*(.+)"
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
    elif type == "duration":
        return parse_duration(raw)
    elif type == "date":
        return parse_date(raw)
    else:
        return raw

def parse_date(date_str):
    try:
        # Try parsing format like "27/06/2025 03:42 PM"
        dt = datetime.strptime(date_str, "%d/%m/%Y %I:%M %p")
        return dt.isoformat()
    except ValueError:
        return None

def parse_duration(duration_str):
    try:
        h, m, s = duration_str.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except:
        return None

@app.route("/parse", methods=["POST"])
def parse():
    try:
        data = request.json
        pdf_url = data["pdf_url"]
        screenshot_url = data["screenshot_url"]
        dataset_name = data["dataset_name"]

        # Download and process PDF
        pdf_bytes = download_file(pdf_url)
        pdf_text = extract_text_from_pdf(pdf_bytes)

        # Download and OCR screenshot
        screenshot_bytes = download_file(screenshot_url)
        screenshot_text = extract_text_from_image(screenshot_bytes)

        result = {
            "Dataset name": dataset_name,
            "Recorded at": extract_field(pdf_text, "Recorded at", type="date"),
            "Duration": extract_field(pdf_text, "Duration", type="duration"),
            "Processed at": extract_field(pdf_text, "Processed at", type="date"),
            "Scanned area": extract_field(pdf_text, "Scanned area", type="number"),
            "Billed area": extract_field(pdf_text, "Billed area", type="number"),
            "Panoramas": extract_field(pdf_text, "Panoramas", type="number"),
            "Control points": extract_field(pdf_text, "Control points", type="number"),
            "Point cloud resolution": { "name": extract_field(pdf_text, "Point cloud resolution") },
            "Colorized": { "name": extract_field(pdf_text, "Colorized") },
            "Processing preset": extract_field(pdf_text, "Processing preset selection"),
            "Person blurring": { "name": extract_field(pdf_text, "Person blurring") },
            "License Plate blurring": { "name": extract_field(pdf_text, "License Plate blurring") },
            "Floor filling": { "name": extract_field(pdf_text, "Floor filling") },
            "Panorama embedded e57": { "name": extract_field(pdf_text, "Panorama embedded e57") },
            "Surveyed control points": { "name": extract_field(pdf_text, "Surveyed control points") },
            "Coordinate system": extract_field(pdf_text, "Coordinate system") if "MAPS" not in extract_field(pdf_text, "Coordinate system", "string") else "",
            "Units consumed": extract_field(screenshot_text, dataset_name + " Units consumed", type="number"),
            "Size": extract_field(screenshot_text, dataset_name + " Size", type="number"),
        }

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
