FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the application code
COPY . .

# Set environment variables
ENV FLASK_APP=parser.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Create storage directory
RUN mkdir -p /app/storage

# Expose port 5001
EXPOSE 5001

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "parser:app"] 