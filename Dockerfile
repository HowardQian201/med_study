# Stage 1: Build React Frontend
FROM node:18 AS frontend-builder

WORKDIR /app/client

# Copy package.json and package-lock.json (or yarn.lock)
COPY client/package.json client/package-lock.json* ./

# Install frontend dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY client/ .

# Build the frontend for production
RUN npm run build

# Stage 2: Python Backend
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend app
COPY backend/ ./backend/

# Copy built frontend static assets from the frontend-builder stage
COPY --from=frontend-builder /app/client/build ./static/

# Expose the port Flask will run on
EXPOSE 5000

# Run app
CMD ["python", "backend/main.py"]