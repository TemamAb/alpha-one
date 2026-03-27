# AlphaMark Monitoring Dashboard Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy dependency definitions first
COPY frontend/package*.json ./

# Install production dependencies
RUN npm install --production

# Copy frontend app and shared registry data
COPY frontend/. .
COPY config_asset_registry ./config_asset_registry

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001
USER nodejs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

# Start the server
CMD ["node", "server-dashboard.js"]
