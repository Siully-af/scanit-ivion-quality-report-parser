from flask import Flask, request, jsonify
import requests
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from io import BytesIO
from datetime import datetime
import re

app = Flask(__name__)

def extract_text_from_pdf(url):
    response = requests.get(url)
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def extract_text_from_image(url):
    response = requests.get(url)
    image = Image.open(BytesIO(response.content))
    return pytesseract.image_to_string(image)

def parse_datetime(text):
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y %I:%M %p").isoformat()
    except:
        return None

def parse_number(text):
    try:
        return float(text.replace(",", ""))
    except:
        return None

@app.route("/parse", methods=["POST"])
def parse():
    try:
        body = request.json
        pdf_url = body["pdf_url"]
        screenshot_url = body["screenshot_url"]
        dataset_name = body["dataset_name"]

        pdf_text = extract_text_from_pdf(pdf_url)
        image_text = extract_text_from_image(screenshot_url)

        def extract(pattern, text_block, transform=lambda x: x):
            match = re.search(pattern, text_block, re.IGNORECASE)
            if match:
                return transform(match.group(1).strip())
            return None

        data = {
            "Dataset name": dataset_name,
            "Recorded at": parse_datetime(extract(r"Recorded at\s*:\s*(.+)", pdf_text)),
            "Duration": extract(r"Duration\s*:\s*(.+)", pdf_text),
            "Processed at": parse_datetime(extract(r"Processed at\s*:\s*(.+)", pdf_text)),
            "Scanned area": parse_number(extract(r"Scanned area\s*:\s*([\d,\.]+)", pdf_text)),
            "Billed area": parse_number(extract(r"Billed area\s*:\s*([\d,\.]+)", pdf_text)),
            "Panoramas": parse_number(extract(r"Panoramas\s*:\s*(\d+)", pdf_text)),
            "Control points": parse_number(extract(r"Control points\s*:\s*(\d+)", pdf_text)),
            "Point cloud resolution": extract(r"Point cloud resolution\s*:\s*(.+)", pdf_text),
            "Colorized": extract(r"Colorized\s*:\s*(Yes|No)", pdf_text),
            "Processing preset": extract(r"Processing preset selection\s*:\s*(.+)", pdf_text),
            "Person blurring": extract(r"Person blurring\s*:\s*(.+)", pdf_text),
            "License Plate blurring": extract(r"License Plate blurring\s*:\s*(.+)", pdf_text),
            "Floor filling": extract(r"Floor filling\s*:\s*(.+)", pdf_text),
            "Panorama embedded e57": extract(r"Panorama embedded e57\s*:\s*(.+)", pdf_text),
            "Surveyed control points": extract(r"Surveyed control points\s*:\s*(.+)", pdf_text),
            "Coordinate system": extract(r"Coordinate system\s*:\s*(.+)", pdf_text),
            "Units consumed": parse_number(extract(r"Units consumed\s*:\s*([\d,\.]+)", image_text)),
            "Size": parse_number(extract(r"Size\s*:\s*([\d,\.]+)", image_text)),
        }

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
