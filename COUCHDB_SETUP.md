# CouchDB Setup Script

**One-command setup for Windows, Mac, and Linux**

## Quick Start

### Any Platform (Windows, Mac, Linux):
```bash
uv run python start_couchdb_with_data.py
```

That's it! This will:
1. ✅ Start CouchDB container
2. ✅ Wait for CouchDB to be ready
3. ✅ Load 2,900 IoT sensor documents
4. ✅ Load 12,272 work order documents
5. ✅ Display success message

## What It Does

| Step | Command | Result |
|------|---------|--------|
| 1 | `docker compose up -d` | Starts CouchDB container in background |
| 2 | Waits for readiness | Polls CouchDB until it responds (max 60s) |
| 3 | Loads IoT data | 2,900 chiller + pump sensor documents |
| 4 | Loads work orders | 12,272 work order documents |
| ✅ | Done | 15,172 total documents ready to use |

## Databases Created

- **chiller**: 2,900 IoT sensor documents (chiller + pump)
- **workorder**: 12,272 work order documents

Both databases are indexed and ready for querying.

## System Requirements

- Docker running
- Python 3.8+
- `uv` package manager installed
- `requests` package (auto-installed by uv)

## Troubleshooting

**Docker not running?**
```bash
docker ps  # Should show running containers
```

**CouchDB won't start?**
```bash
docker compose -f src/couchdb/docker-compose.yaml logs
```

**Data didn't load?**
```bash
# Check if databases exist:
curl -u admin:password http://localhost:5984/_all_dbs

# Check document counts:
curl -u admin:password http://localhost:5984/chiller | python -m json.tool | grep doc_count
```

## Manual Steps (if needed)

If the script fails, run these separately:

```bash
# 1. Start CouchDB
cd src/couchdb
docker compose up -d
cd ../..

# 2. Wait 5 seconds

# 3. Load data
uv run python src/couchdb/init_asset_data.py --drop
uv run python src/couchdb/init_wo.py --drop
```

## Next Steps

After running this script, proceed with starting the 6 MCP servers:
- Skills
- Knowledge
- TSFM
- IoT
- Vibration
- WO (Work Order)

See the main README for MCP server setup instructions.
