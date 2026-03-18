FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Set display (needed for headless sometimes)
ENV DISPLAY=:99

# Workdir
WORKDIR /app

# Copy files
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Run script
CMD ["python", "-u", "check.py"]
