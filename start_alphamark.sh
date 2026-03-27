#!/bin/bash

# Fail fast on any error
set -e

echo "🚀 Starting AlphaMark Dashboard..."
# Use exec to pass signals (SIGTERM) correctly to the Node process
exec node frontend/server-dashboard.js