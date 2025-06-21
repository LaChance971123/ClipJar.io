# Use official Python 3.10 slim image
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends \
      ffmpeg libmagic1 fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy repository contents into container
COPY . /app

# Install Python requirements and dev tools
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir pytest

# Default command
CMD ["bash"]
