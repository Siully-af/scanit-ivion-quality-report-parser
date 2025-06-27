from flask import Flask, request, jsonify
import requests
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
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
    image = Image.open(io.BytesIO(response.content))
    return pytesseract.image_to_string(image)

def extract_field(text, label, type="string"):
    pattern = rf"{re.escape(label)}\s*[:\-]?\s*(.+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
        if type == "number":
            cleaned = re.sub(r"[^\d.,]", "", raw).replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return raw
    return None

@app.route("/parse", methods=["POST"])
def parse():
    data = request.get_json()
    pdf_url = data.get("pdf_url")
    screenshot_url = data.get("screenshot_url")
    dataset_name = data.get("dataset_name")

    if not pdf_url or not screenshot_url or not dataset_name:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        pdf_text = extract_text_from_pdf(pdf_url)
        screenshot_text = extract_text_from_image(screenshot_url)

        result = {
            "Dataset name": dataset_name,
            "Recorded at": extract_field(pdf_text, "Recorded at"),
            "Duration": extract_field(pdf_text, "Duration", type="number"),
            "Processed at": extract_field(pdf_text, "Processed at"),
            "Scanned area": extract_field(pdf_text, "Scanned area", type="number"),
            "Billed area": extract_field(pdf_text, "Billed area", type="number"),
            "Panoramas": extract_field(pdf_text, "Panoramas", type="number"),
            "Control points": extract_field(pdf_text, "Control points", type="number"),
            "Point cloud resolution": {"name": extract_field(pdf_text, "Point cloud resolution")},
            "Colorized": {"name": extract_field(pdf_text, "Colorized")},
            "Processing preset": extract_field(pdf_text, "Processing preset selection"),
            "Person blurring": {"name": extract_field(pdf_text, "Person blurring")},
            "License Plate blurring": {"name": extract_field(pdf_text, "License Plate blurring")},
            "Floor filling": {"name": extract_field(pdf_text, "Floor filling")},
            "Panorama embedded e57": {"name": extract_field(pdf_text, "Panorama embedded e57")},
            "Surveyed control points": {"name": extract_field(pdf_text, "Surveyed control points")},
            "Coordinate system": None if extract_field(pdf_text, "Coordinate system") == "XRAY MAPS" else extract_field(pdf_text, "Coordinate system"),
            "Units consumed": extract_field(pdf_text, "Units consumed", type="number"),
            "Size": extract_field(pdf_text, "Size", type="number"),
            "Device serial": extract_field(pdf_text, "Device serial"),
            "System software": extract_field(pdf_text, "System software")
        }

        # Try extracting fallback values from screenshot if missing
        for key in ["Size", "Units consumed", "Processing preset"]:
            if not result.get(key):
                result[key] = extract_field(screenshot_text, key if key != "Processing preset" else "Processing preset selection", type="number" if key != "Processing preset" else "string")

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=10000)
