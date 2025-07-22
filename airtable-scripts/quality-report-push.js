// === 1. Read recordId from button trigger ===
let inputConfig = input.config();
let recordId = inputConfig.recordId;

let table = base.getTable("Projects");
let record = await table.selectRecordAsync(recordId);

// === 2. Pull ALL PDF attachments ===
let pdfAttachments = record.getCellValue("ivion_quality_report") || [];
if (pdfAttachments.length === 0) {
    throw new Error("No PDFs found in 'ivion_quality_report'");
}

// === 3. Helper to convert European-style date to ISO ===
function convertToISO(input) {
    const parts = input.match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}) (AM|PM)/);
    if (!parts) return null;

    let [ , day, month, year, hour, minute, ampm ] = parts;
    hour = parseInt(hour);
    if (ampm === "PM" && hour !== 12) hour += 12;
    if (ampm === "AM" && hour === 12) hour = 0;

    return `${year}-${month}-${day}T${String(hour).padStart(2, '0')}:${minute}:00`;
}

let reportsTable = base.getTable("SCANIT Quality Reports");

for (let pdfAttachment of pdfAttachments) {
    let pdf_url = pdfAttachment.url;
    let pdf_filename = pdfAttachment.filename;

    // === 4. Send to Render webhook ===
    let response = await fetch("https://scanit-ivion-quality-report-parser-1.onrender.com/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf_url, pdf_filename })
    });

    let rawText = await response.text();
    console.log("Webhook raw response:", rawText);

    if (!response.ok) {
        console.error("Skipping failed PDF:", pdf_filename);
        continue;
    }

    let result = JSON.parse(rawText);
    console.log("Parsed result object:", result);

    // === 5. Write result to SCANIT Quality Reports ===
    await reportsTable.createRecordAsync({
        "Dataset name": result["Dataset name"],
        "Recorded at": convertToISO(result["Recorded at"]),
        "Duration": result["Duration"],
        "Processed at": convertToISO(result["Processed at"]),
        "Scanned area": result["Scanned area"],
        "Billed area": result["Billed area"],
        "Panoramas": result["Panoramas"],
        "Control points": result["Control points"],
        "Point cloud resolution": result["Point cloud resolution"],
        "Colorized": result["Colorized"],
        "Processing preset": { name: (result["Processing preset"] || "").trim() },
        "Person blurring": result["Person blurring"],
        "License Plate blurring": result["License Plate blurring"],
        "Floor filling": result["Floor filling"],
        "Panorama embedded e57": result["Panorama embedded e57"],
        "Surveyed control points": result["Surveyed control points"],
        "Coordinate system": result["Coordinate system"],
        "Device serial": result["Device serial"],
        "System software": result["System software"],
        "Projects": [{ id: record.id }]
    });
} // end loop

