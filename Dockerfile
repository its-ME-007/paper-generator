# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
# (If you add liblouis later, you would install it here: apt-get install -y liblouis-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create necessary directories for runtime data
# (Note: These files are ephemeral in Render unless you use a persistent disk)
RUN mkdir -p generated_papers submissions/images submissions/completed answer_keys

# Expose the port the app runs on
EXPOSE 10000

# Command to run the application using Gunicorn
# Render usually sets the PORT env var, but we default to 10000
CMD gunicorn --bind 0.0.0.0:$PORT app:app --timeout 120 --workers 2
