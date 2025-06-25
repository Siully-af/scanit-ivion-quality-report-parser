# Use official Python image
FROM python:3.10-slim

# Install Tesseract
RUN apt-get update && \
    apt-get install -y tesseract-ocr poppler-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port Render expects (10000)
EXPOSE 10000

# Start the app
CMD ["python", "main.py"]
