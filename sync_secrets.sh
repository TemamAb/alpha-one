#!/bin/bash
# AlphaMark - Secure Secret Synchronizer
# Syncs .env variables to Fly.io Secrets without committing to Git

if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found."
    exit 1
fi

echo "🚀 AlphaMark Security: Syncing Secrets to Fly.io..."

# Read .env and set fly secrets
# We skip comments and empty lines
# We use export to handle the parsing correctly then pass to flyctl

grep -v '^#' .env | grep -v '^[[:space:]]*$' | while read -r line; do
    key=$(echo $line | cut -d '=' -f 1)
    value=$(echo $line | cut -d '=' -f 2- | sed 's/^"//' | sed 's/"$//')
    
    # Skip non-sensitive vars that are already in fly.toml if you prefer
    # But setting as secret is always safer
    
    if [ ! -z "$key" ] && [ ! -z "$value" ]; then
        echo "🔒 Syncing $key..."
        flyctl secrets set "$key"="$value" --stage
    fi
done

echo "✅ All secrets staged for deployment."
echo "💡 Use 'flyctl deploy' to apply changes."
