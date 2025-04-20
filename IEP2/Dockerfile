FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt requests

# Create storage directory
RUN mkdir -p /app/storage

# Copy the rest of the application
COPY . .

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose port 5004
EXPOSE 5004

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5004", "app:app"] 