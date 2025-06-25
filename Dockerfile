FROM python:3.11-slim

# Install system dependencies including Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy code and install Python dependencies
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Flask
EXPOSE 10000

# Run the server
CMD ["python", "main.py"]