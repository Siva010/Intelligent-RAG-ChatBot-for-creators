FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (ffmpeg is needed for yt-dlp/whisper audio processing)
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .
