# AlphaMark Unified Production Dockerfile
# Optimized for Fly.io - Runs both Dashboard and Execution Bot

# Use a multi-language base image to avoid multiple containers for small apps
FROM nikolaik/python-nodejs:python3.11-nodejs18-slim

WORKDIR /app

# 1. Install System Dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Node Dependencies (Dashboard)
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install --production

# 3. Install Python Dependencies (Bot)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Application Code
COPY . .

# 5. Fix Permissions & Set Scripts
RUN chmod +x start_alphamark.sh

# 6. Set Environment Defaults
ENV PORT=3000
ENV PAPER_TRADING_MODE=true
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose the dashboard port
EXPOSE 3000

# 7. Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Start both services using the launcher script
CMD ["./start_alphamark.sh"]
