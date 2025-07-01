import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
import io
from flask import Flask, request, jsonify

app = Flask(__name__)

def extract_pdf_text(pdf_url):
    response = requests.get(pdf_url)
    response.raise_for_status()
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_screenshot_text(screenshot_url):
    response = requests.get(screenshot_url)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content))
    return pytesseract.image_to_string(image)

def extract_field(text, label, type="text"):
    for line in text.splitlines():
        if label in line:
            raw = line.split(label)[-1].strip(": ").strip()
            if type == "number":
                raw = raw.replace(",", "").replace("ft²", "").replace("m²", "").replace("GB", "").strip()
                try:
                    return float(raw)
                except:
                    return None
            elif type == "duration":
                parts = raw.split(":")
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
            elif type == "select":
                return {"name": raw}
            else:
                return raw
    return None

@app.route("/parse", methods=["POST"])
def parse():
    data = request.json
    pdf_url = data.get("pdf_url")
    screenshot_url = data.get("screenshot_url")
    dataset_name = data.get("dataset_name")

    if not pdf_url or not screenshot_url or not dataset_name:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        pdf_text = extract_pdf_text(pdf_url)
        screenshot_text = extract_screenshot_text(screenshot_url)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Extract from PDF (quality report)
    result = {
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
        "Coordinate system": None if "XRAY MAPS" in pdf_text else extract_field(pdf_text, "Coordinate system"),
    }

    # Extract from screenshot (file summary)
    result.update({
        "Units consumed": extract_field(screenshot_text, "Units consumed", type="number"),
        "Size": extract_field(screenshot_text, "Size", type="number"),
        "Device serial": extract_field(pdf_text, "Device serial"),
        "System software": extract_field(pdf_text, "System software"),
    })

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
