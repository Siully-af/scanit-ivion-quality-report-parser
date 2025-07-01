from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
from io import BytesIO
import re

app = Flask(__name__)

def extract_field(text, label, type="text", allow_xray=False):
    pattern = rf"{label}:\s*(.+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None

    raw = match.group(1).strip()
    
    if type == "number":
        try:
            return float(
                raw.replace(",", "")
                   .replace("ft²", "")
                   .replace("m²", "")
                   .replace("GB", "")
                   .strip()
            )
        except:
            return None
    elif type == "duration":
        parts = raw.split(":")
        if len(parts) == 3:
            try:
                h, m, s = [int(p) for p in parts]
                return h * 3600 + m * 60 + s
            except:
                return None
        return None
    elif type == "select":
        return { "name": raw }
    elif type == "coordinate":
        return None if ("XRAY MAPS" in raw.upper() and not allow_xray) else raw
    return raw

def extract_pdf_text(url):
    response = requests.get(url)
    with BytesIO(response.content) as f:
        doc = fitz.open(stream=f, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
    return text

def extract_image_text(url):
    response = requests.get(url)
    image = Image.open(BytesIO(response.content))
    return pytesseract.image_to_string(image)

@app.route("/parse", methods=["POST"])
def parse():
    try:
        body = request.json
        pdf_url = body.get("pdf_url")
        screenshot_url = body.get("screenshot_url")
        dataset_name = body.get("dataset_name")

        if not pdf_url or not screenshot_url or not dataset_name:
            return jsonify({ "error": "Missing required input URLs or dataset name" }), 400

        pdf_text = extract_pdf_text(pdf_url)
        image_text = extract_image_text(screenshot_url)

        if dataset_name not in image_text:
            print(f"❌ Dataset not found in screenshot: {dataset_name}")
            return jsonify({ "error": f"Dataset {dataset_name} not found in screenshot" }), 400

        output = {
            # --- From PDF ---
            "Dataset name": dataset_name,
            "Recorded at": extract_field(pdf_text, "Recorded at"),
            "Duration": extract_field(pdf_text, "Duration", type="duration"),
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
            "Coordinate system": extract_field(pdf_text, "Coordinate system", type="coordinate"),
            "Device serial": extract_field(pdf_text, "Device serial"),
            "System software": extract_field(pdf_text, "System software"),

            # --- From screenshot ---
            "Units consumed": extract_field(image_text, dataset_name + " Units consumed", type="number"),
            "Size": extract_field(image_text, dataset_name + " Size", type="number"),
        }

        # Check required fields
        required = ["Dataset name", "Recorded at", "Duration", "Processed at", "Scanned area"]
        if any(output[f] is None for f in required):
            return jsonify({ "error": "Missing required fields" }), 400

        return jsonify(output)

    except Exception as e:
        print("🔥 Error in /parse:", str(e))
        return jsonify({ "error": str(e) }), 500

@app.route("/", methods=["GET"])
def healthcheck():
    return "Parser is up and running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
