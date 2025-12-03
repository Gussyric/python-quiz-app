# Dockerfile

# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
# If you don’t have a requirements.txt, list packages like:
# RUN pip install flask requests difflib

# Expose the port your Flask app runs on
EXPOSE 5001

# Start the Flask app
CMD ["python", "app.py"]