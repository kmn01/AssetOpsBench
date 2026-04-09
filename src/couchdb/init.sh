#!/bin/bash -e

echo "Starting CouchDB initialization..."

# Start CouchDB in the background
/opt/couchdb/bin/couchdb &
COUCHDB_PID=$!

# Wait for CouchDB to be ready
echo "Waiting for CouchDB to be ready..."
for i in {1..30}; do
  if curl -sf -u admin:password http://localhost:5984/ > /dev/null 2>&1; then
    echo "✅ CouchDB is ready"
    break
  fi
  echo "Attempt $i/30: CouchDB not ready yet, waiting..."
  sleep 2
done

# Check if CouchDB is responding
if ! curl -sf -u admin:password http://localhost:5984/ > /dev/null 2>&1; then
  echo "❌ CouchDB failed to start"
  kill $COUCHDB_PID 2>/dev/null || true
  exit 1
fi

echo "Loading IoT sensor data..."
cd /couchdb
python3 init_asset_data.py --drop || {
  echo "⚠️ Failed to load IoT data, but continuing..."
}

echo "Loading work order data..."
python3 init_wo.py --drop || {
  echo "⚠️ Failed to load work order data, but continuing..."
}

echo "✅ All databases initialised successfully!"

# Keep CouchDB running in foreground
wait $COUCHDB_PID
