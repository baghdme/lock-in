FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories if they don't exist
RUN mkdir -p /app/storage

EXPOSE 5005

CMD ["python", "app.py"] 