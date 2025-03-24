# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set pip timeout and retries
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_RETRIES=10

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install spacy model with retries
RUN for i in {1..5}; do \
        python -m spacy download en_core_web_sm && break || \
        echo "Attempt $i failed! Trying again in 10 seconds..." && \
        sleep 10; \
    done

# Copy the application code
COPY parser.py .

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "parser.py"] 