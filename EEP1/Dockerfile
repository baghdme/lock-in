FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create storage directory
RUN mkdir -p /app/persistence
RUN mkdir -p /app/storage

# Copy the rest of the application
COPY . .

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV STORAGE_DIR=/app/storage

# Expose port 5000
EXPOSE 5000

# Run the application using gunicorn with 350 second timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "350", "app:app"] 