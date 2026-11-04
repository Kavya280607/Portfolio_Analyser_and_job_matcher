FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && pip install --no-cache-dir gunicorn
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh", "-c", "gunicorn --chdir backend --bind 0.0.0.0:${PORT:-10000} app:app"]
