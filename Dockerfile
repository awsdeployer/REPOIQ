# Use official Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system and Python dependencies in one layer
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends git gcc \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Expose port
EXPOSE 5000

# Start with Gunicorn (production-ready)
ENTRYPOINT ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]

