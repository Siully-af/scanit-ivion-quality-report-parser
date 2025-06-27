from flask import Flask, request, jsonify
import requests
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
import re

app = Flask(__name__)

def extract_text_from_pdf_url(url):
    response = requests.get(url)
    with BytesIO(response.content) as file:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        return text

def extract_field(text, label, type="text"):
    pattern = rf"{label}:\s*(.+)"
    match = re.search(pattern, text)
    if not match:
        return None
    raw = match.group(1).strip()
    if type == "number":
        raw = raw.replace(",", "")
        if "m²" in raw:
            return round(float(raw.replace("m²", "")) * 10.7639, 2)
        if "ft²" in raw:
            return float(raw.replace("ft²", ""))
        if "GB" in raw:
            return float(raw.replace("GB", ""))
        return float(raw)
    if type == "select":
        return {"name": raw}
    if type == "coordinate":
        return None if raw.strip().upper() == "XRAY MAPS" else raw
    return raw

def extract_table_row(screenshot_text, dataset_name):
    for line in screenshot_text.splitlines():
        if dataset_name in line:
            return line
    return ""

@app.route("/parse", methods=["POST"])
def parse():
    try:
        data = request.json
        pdf_url = data["pdf_url"]
        screenshot_url = data["screenshot_url"]
        dataset_name = data["dataset_name"]

        pdf_text = extract_text_from_pdf_url(pdf_url)
        screenshot_img = Image.open(BytesIO(requests.get(screenshot_url).content))
        screenshot_text = pytesseract.image_to_string(screenshot_img)
        row_text = extract_table_row(screenshot_text, dataset_name)

        response = {
            "Dataset name": dataset_name,
            "Recorded at": extract_field(pdf_text, "Recorded at"),
            "Duration": int(float(extract_field(pdf_text, "Duration").split()[0]) * 60),
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
            "Units consumed": extract_field(pdf_text, "Units consumed", type="number"),
            "Size": extract_field(pdf_text, "Size", type="number"),
            "Device serial": extract_field(pdf_text, "Device serial"),
            "System software": extract_field(pdf_text, "System software")
        }

        # From screenshot row — extract these if needed (in future)
        # row_parts = row_text.split()
        # response.update({
        #     "Some field": row_parts[2]
        # })

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=10000)
