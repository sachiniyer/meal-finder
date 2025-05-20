# Use Python 3.9 slim image
FROM python:3.10.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=development

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create /app/logs directory and create non-root user
RUN mkdir -p /app/logs \
    && useradd -m myuser \
    && chown -R myuser:myuser /app

# Switch to non-root user
USER myuser

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]
