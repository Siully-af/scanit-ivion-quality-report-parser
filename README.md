# scanit-ivion-quality-report-parser

```markdown
# IVION Quality Report Parser

This service extracts structured data from NavVis IVION-generated quality report PDFs and project-wide file summary screenshots. The extracted data is sent back to Airtable for storage and reporting.

## 🔗 System Overview

- **Trigger**: Button click from Airtable Interface (`Quality Report Data Pull`)
- **Input**: 
  - One or more PDF quality reports per project (uploaded manually)
  - One shared screenshot with a summary of all datasets
- **Output**: Structured records created in the `SCANIT Quality Reports` table in Airtable
- **Backend**: Python + Flask app deployed on Render
- **OCR**: Tesseract for screenshot parsing (in progress)
- **PDF Parsing**: PyMuPDF

---

## 📁 Project Structure

```

├── main.py                # Flask API: handles /parse request
├── Dockerfile             # Defines dependencies and system environment
├── requirements.txt       # Python dependencies
├── render.yaml            # Render service definition
├── template.pdf           # (Optional) Sample report for testing
└── airtable-scripts/
└── quality-report-push.js  # Airtable automation script

````

---

## 🛠 Setup & Deployment

### 1. Local Dev Setup (optional)
```bash
git clone https://github.com/<your-org>/scanit-ivion-quality-report-parser.git
cd scanit-ivion-quality-report-parser
pip install -r requirements.txt
python main.py
````

Ensure you have `tesseract-ocr` and `poppler-utils` installed for full functionality.

### 2. Deploy on Render

This project uses [Render](https://render.com) for hosting.

* Deployment type: **Web Service**
* Runtime: **Docker**
* Healthcheck URL: `/health`

---

## 🔄 API Reference

### `POST /parse`

Accepts:

```json
{
  "pdf_urls": ["<PDF_URL_1>", "<PDF_URL_2>", "..."],
  "screenshot_url": "<Screenshot_URL>",
  "project_name": "Project ABC"
}
```

Returns:

```json
[
  {
    "Dataset name": "Level 1 Core",
    "Recorded at": "2024-06-10T10:12:00",
    "Duration": 1560,
    "Panoramas": 62,
    ...
  }
]
```

Fields returned match those expected by the Airtable schema.

---

## 🧩 Airtable Integration

### Airtable Base

**Name:** SCANIT Project Management App
**Interface:** Quality Report Data Pull
**Tables:** `Projects`, `SCANIT Quality Reports`

### Trigger Flow

1. User uploads PDFs + screenshot to a project record
2. User clicks the `Quality Report Data Pull` button
3. Airtable Automation calls the Render endpoint with attachments
4. Returned data is used to create linked records in `SCANIT Quality Reports`

### Airtable Script

Script is located in:

```
/airtable-scripts/quality-report-push.js
```

This handles:

* Sending attachments to the webhook
* Creating records in the `SCANIT Quality Reports` table
* Linking them back to the source project

---

## ⚠️ Current Status

* ✅ PDF extraction: Complete
* 🚧 Screenshot extraction: In progress

  * Screenshot contains a table with all datasets
  * We are building logic to match each row to the correct dataset record

---

## 🧪 Testing

Use `test_payload.json` or a manual POST to `/parse` via Postman with sample IVION report files.

---

## 📋 Maintenance Notes

* Update PDF parsing rules if IVION changes format
* Monitor OCR accuracy with real-world screenshots
* Test with mixed datasets and different project sizes
* Re-deploy to Render after any code updates using `git push`

---

## 📎 Resources

* [IVION API Docs](https://ivion-api.docs.navvis.com/)
* [Render Docs](https://render.com/docs)
* [PyMuPDF](https://pymupdf.readthedocs.io/)
* [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

---

## 🧑‍💻 Maintainer

**Siully Fernandez**
Director of Operations, Integrated Projects
Contact: [siully.ip@yourdomain.com](mailto:siully.ip@yourdomain.com)

```

---
