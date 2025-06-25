
from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import io
import requests
import re
from PIL import Image
import pytesseract

app = Flask(__name__)

def download_file(url):
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)

def parse_duration(duration_str):
    if not duration_str:
        return 0
    try:
        h, m, s = map(int, duration_str.strip().split(":"))
        return h * 3600 + m * 60 + s
    except:
        return 0

def extract_from_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()

    def get_val(label, pattern, cast=str, default=None):
        match = re.search(pattern, text)
        return cast(match.group(1).strip()) if match else default

    return {
        "Dataset name": get_val("Dataset name", r"Dataset name:\s+(.*)"),
        "Recorded at": get_val("Recorded at", r"Recorded at:\s+(.*)"),
        "Duration": parse_duration(get_val("Duration", r"Duration:\s+(.*)")),
        "Processed at": get_val("Processed at", r"Processed at:\s+(.*)"),
        "Scanned area": float(get_val("Scanned area", r"Scanned area:\s+([\d\.]+) m²", float, 0)),
        "Billed area": float(get_val("Billed area", r"Billed area:\s+([\d\.]+) m²", float, 0)),
        "Panoramas": int(get_val("Panoramas", r"Panoramas:\s+(\d+)", int, 0)),
        "Control points": int(get_val("Control points", r"Control points:\s+(\d+)", int, 0)),
        "Point cloud resolution": get_val("Point cloud resolution", r"Point cloud resolution:\s+(.*)"),
        "Colorized": get_val("Colorized", r"Colorized:\s+(Yes|No)"),
        "Processing preset": get_val("Processing preset", r"Processing preset:\s+(.*)"),
        "Person blurring": get_val("Person blurring", r"Person blurring:\s+(Yes|No)"),
        "License Plate blurring": get_val("License Plate blurring", r"License Plate blurring:\s+(Yes|No)"),
        "Floor filling": get_val("Floor filling", r"Floor filling:\s+(Yes|No)"),
        "Panorama embedded e57": get_val("Panorama embedded e57", r"Panorama embedded e57:\s+(Yes|No)"),
        "Surveyed control points": get_val("Surveyed control points", r"Surveyed control points:\s+(Yes|No)"),
        "Coordinate system": get_val("Coordinate system", r"Coordinate system:\s+(.*)")
    }

def extract_from_image(image_bytes, dataset_name):
    image = Image.open(image_bytes)
    text = pytesseract.image_to_string(image)

    lines = [line.strip() for line in text.splitlines() if dataset_name in line]
    if not lines:
        raise ValueError(f"No line matched dataset name: {dataset_name}")

    parts = re.split(r'\s{2,}', lines[0])

    result = {
        "Units consumed": None,
        "Size": None,
        "Status": None,
        "Processed at": None,
        "Control points": None,
        "Panoramas": None,
        "Billed area": None
    }

    if len(parts) >= 7:
        try:
            result.update({
                "Status": parts[0],
                "Processed at": parts[1],
                "Control points": int(parts[2]),
                "Panoramas": int(parts[3]),
                "Billed area": float(parts[4].replace(',', '').replace('ft²', '')),
                "Units consumed": int(parts[5].replace(',', '')),
                "Size": float(parts[6].replace('GB', '').strip())
            })
        except Exception as e:
            raise ValueError(f"Image parsing structure failed: {e}\nParts: {parts}")

    return result

@app.route('/parse', methods=['POST'])
def parse_files():
    try:
        data = request.json
        pdf_url = data.get("pdf_url")
        image_url = data.get("screenshot_url")
        dataset_name = data.get("dataset_name")

        pdf_bytes = download_file(pdf_url)
        pdf_data = extract_from_pdf(pdf_bytes)

        image_bytes = download_file(image_url)
        image_data = extract_from_image(image_bytes, dataset_name)

        combined = {**pdf_data, **image_data}
        return jsonify(combined)

    except Exception as e:
        import traceback
        return jsonify({"error": traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
