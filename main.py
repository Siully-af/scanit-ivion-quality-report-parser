import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
import io
import re
import datetime
from flask import Flask, request, jsonify
import base64

app = Flask(__name__)

def extract_text_from_pdf_url(url):
    response = requests.get(url)
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_text_from_image_url(url):
    response = requests.get(url)
    img = Image.open(io.BytesIO(response.content))
    return pytesseract.image_to_string(img)

def parse_duration(duration_str):
    match = re.match(r'(\d+)m\s+(\d+)s', duration_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds
    return None

def extract_field(text, field_label, type="text"):
    pattern = rf"{re.escape(field_label)}\s*:\s*(.+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
        if type == "number":
            return float(raw.replace(",", "").replace("ft²", "").replace("GB", "").strip())
        if type == "select":
            return { "name": raw }
        if type == "duration":
            return parse_duration(raw)
        if type == "date":
            try:
                return datetime.datetime.strptime(raw, "%d/%m/%Y %I:%M %p").isoformat()
            except:
                return None
        return raw
    return None

def find_row_in_screenshot_table(dataset_name, screenshot_text):
    # Search for the line in the screenshot that matches the dataset name
    for line in screenshot_text.splitlines():
        if dataset_name in line:
            return line
    return ""

def extract_screenshot_data(row_text):
    row_text = row_text.replace(",", "")
    parts = row_text.split()
    try:
        panoramas = int(parts[-4])
        billed_area = float(parts[-3])
        units = int(parts[-2])
        size = float(parts[-1])
        return panoramas, billed_area, units, size
    except:
        return None, None, None, None

@app.route("/parse", methods=["POST"])
def parse():
    req = request.get_json()
    pdf_url = req.get("pdf_url")
    screenshot_url = req.get("screenshot_url")
    dataset_name = req.get("dataset_name")

    pdf_text = extract_text_from_pdf_url(pdf_url)
    screenshot_text = extract_text_from_image_url(screenshot_url)

    # Screenshot table row matching
    row_text = find_row_in_screenshot_table(dataset_name, screenshot_text)
    panoramas, billed_area, units, size = extract_screenshot_data(row_text)

    data = {
        "Dataset name": dataset_name,
        "Recorded at": extract_field(pdf_text, "Recorded at", type="date"),
        "Duration": extract_field(pdf_text, "Duration", type="duration"),
        "Processed at": extract_field(pdf_text, "Processed at", type="date"),
        "Scanned area": extract_field(pdf_text, "Scanned area", type="number"),
        "Billed area": billed_area,
        "Panoramas": panoramas,
        "Control points": extract_field(pdf_text, "Control points", type="number"),
        "Point cloud resolution": extract_field(pdf_text, "Point cloud resolution", type="select"),
        "Colorized": extract_field(pdf_text, "Colorized", type="select"),
        "Processing preset": extract_field(pdf_text, "Processing preset selection", type="text"),
        "Person blurring": extract_field(pdf_text, "Person blurring", type="select"),
        "License Plate blurring": extract_field(pdf_text, "License Plate blurring", type="select"),
        "Floor filling": extract_field(pdf_text, "Floor filling", type="select"),
        "Panorama embedded e57": extract_field(pdf_text, "Panorama embedded e57", type="select"),
        "Surveyed control points": extract_field(pdf_text, "Surveyed control points", type="select"),
        "Coordinate system": (
            None if "XRAY MAPS" in extract_field(pdf_text, "Coordinate system", type="text") else extract_field(pdf_text, "Coordinate system", type="text")
        ),
        "Units consumed": units,
        "Size": size
    }

    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
