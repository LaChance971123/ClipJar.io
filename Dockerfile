# Dockerfile for ClipJar.io

# 1. Base image
FROM python:3.10-slim

# 2. Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# 3. Install system dependencies
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends \
      ffmpeg libmagic1 fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

# 4. Set working directory and copy code
WORKDIR /app
COPY . /app

# 5. Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 6. Default to bash shell
CMD ["bash"]
