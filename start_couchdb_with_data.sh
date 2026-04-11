#!/bin/bash
# One-command setup for CouchDB + Data Loading

echo "Starting CouchDB..."
cd "$(dirname "$0")/src/couchdb"
docker compose down -d
docker compose up -d

echo "Waiting for CouchDB to be ready..."
for i in {1..30}; do
  if curl -sf -u admin:password http://localhost:5984/ > /dev/null 2>&1; then
    echo "CouchDB is ready!"
    break
  fi
  echo "   Attempt $i/30..."
  sleep 2
done

echo "Loading IoT sensor data..."
cd "$(dirname "$0")"
uv run python src/couchdb/init_asset_data.py --drop

echo "Loading work order data..."
uv run python src/couchdb/init_wo.py --drop

echo "All done! CouchDB is ready with 15,172 documents."
echo ""
echo "Databases:"
echo "  - chiller: 2,900 IoT sensor documents"
echo "  - workorder: 12,272 work order documents"
