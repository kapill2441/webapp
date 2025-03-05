#!/bin/bash

# Load environment variables if .env.production exists
if [ -f ./.env.production ]; then
  set -a
  source ./.env.production
  set +a
fi

# Restore database from S3 if litestream.yml exists
if [ -f ./litestream.yml ]; then
  # Ensure the data directory exists
  mkdir -p ./instance
  
  # Check if the replica exists before attempting restore
  litestream restore -if-replica-exists -config ./litestream.yml ./instance/priceguard.db || true

  # Start Litestream replication in the background
  litestream replicate -config ./litestream.yml &
fi

# Start the application
python app.py