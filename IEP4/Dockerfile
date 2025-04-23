FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

EXPOSE 5005

CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--timeout", "350", "app:app"] 