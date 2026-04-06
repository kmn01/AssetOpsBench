# AssetOpsBench Complete Setup Guide

**Last Updated:** April 5, 2026  
**Status:** ✅ Working and Tested

A comprehensive guide to set up AssetOpsBench from scratch, including all issues encountered and solutions, so anyone can replicate this setup.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Install Required Tools](#step-1-install-required-tools)
3. [Step 2: Clone/Fork the Repository](#step-2-clonefork-the-repository)
4. [Step 3: Install Project Dependencies](#step-3-install-project-dependencies)
5. [Step 4: Configure Environment Variables](#step-4-configure-environment-variables)
6. [Step 5: Start CouchDB (Database)](#step-5-start-couchdb-database)
7. [Step 6: Load Sample Data into CouchDB](#step-6-load-sample-data-into-couchdb)
8. [Step 7: Start All MCP Servers](#step-7-start-all-mcp-servers)
9. [Step 8: Test the System](#step-8-test-the-system)
10. [Run queries from Claude Desktop (optional)](#run-queries-from-claude-desktop-optional)
11. [Troubleshooting](#troubleshooting)
12. [What is AssetOpsBench?](#what-is-assetopsbench)

This guide includes **Windows**, **macOS**, and **Linux** paths. Jump to the subsection that matches your OS when steps differ.

---

## Prerequisites

- **Windows 10/11**, **macOS** (recent release), or **Linux** (x86_64/ARM64; Ubuntu 22.04+ or similar)
- **Administrator / sudo** where your OS requires it (Docker install, package managers)
- **Internet connection** (for downloads and API calls)
- **~500 MB disk space** (for Docker image, dependencies, and data)

---

## Step 1: Install Required Tools

### 1.1 Install Python 3.12+

#### Windows

1. Download: https://www.python.org/downloads/
2. Run installer
3. ⚠️ **IMPORTANT**: Check "Add Python to PATH"
4. Verify:
   ```powershell
   python --version
   # Should show: Python 3.12.x or higher
   ```

#### macOS

Pick one:

- **Homebrew** (recommended): `brew install python@3.12` — then ensure `python3.12` is on your `PATH` (Homebrew prints a `brew link` hint if needed).
- **python.org**: Download the macOS installer from https://www.python.org/downloads/ (use the universal2 or Apple Silicon build as appropriate).

Verify:

```bash
python3 --version
# Should show: Python 3.12.x or higher
```

#### Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip
python3.12 --version
```

On distributions without `python3.12` in default repos, use [pyenv](https://github.com/pyenv/pyenv) or install from your distro’s backports / [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) (Ubuntu).

### 1.2 Install uv (Package Manager)

`uv` is a fast Python package manager that replaces `pip`.

#### Windows (PowerShell — run as Administrator if the installer requests it)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Or **using pip** (if the script install fails):

```powershell
pip install uv
```

#### macOS / Linux (bash or zsh)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the terminal or `source` the shell rc file the installer mentions, then verify **on any OS**:

```bash
uv --version
# Should show: uv 0.x.x
```

(On Windows PowerShell, `uv --version` works the same once `uv` is on PATH.)

### 1.3 Install Docker

#### Windows

1. Download: https://www.docker.com/products/docker-desktop
2. Run installer
3. Launch Docker Desktop (watch for the whale icon to stop animating)
4. Verify:
   ```powershell
   docker --version
   docker compose version
   ```

#### macOS

1. Install **Docker Desktop for Mac**: https://www.docker.com/products/docker-desktop  
2. Open Docker Desktop and wait until it reports *Docker is running*.
3. Verify:

```bash
docker --version
docker compose version
```

Apple Silicon (M-series): use the Apple Silicon build from Docker.

#### Linux

Either install **Docker Desktop for Linux** (same download page as above) or the open-source **Docker Engine** + Compose plugin (common on Ubuntu):

```bash
# Example: Ubuntu — see https://docs.docker.com/engine/install/ for your distro
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
# Log out and back in so group membership applies
```

Verify:

```bash
docker --version
docker compose version
```

### 1.4 Install Git (Optional but Recommended)

#### Windows

1. Download: https://git-scm.com/download/win
2. Run installer with default settings
3. Verify: `git --version`

#### macOS

Xcode Command Line Tools: `xcode-select --install` — or `brew install git`.

#### Linux

```bash
sudo apt install -y git   # Debian/Ubuntu; use dnf/zypper on other families
git --version
```

---

## Step 2: Clone/Fork the Repository

**Option A: Clone from your fork**

#### Windows (PowerShell)

```powershell
cd C:\Users\<YourUsername>\Downloads
git clone https://github.com/Yeshitha-co/AssetOpsBench.git
cd AssetOpsBench
```

#### macOS / Linux (bash or zsh)

```bash
cd ~/Downloads   # or ~/Projects, etc.
git clone https://github.com/Yeshitha-co/AssetOpsBench.git
cd AssetOpsBench
```

**Option B: Already have the folder**

#### Windows

```powershell
cd C:\Users\yeshi\Downloads\HPML_Final_Project\AssetOpsBench
```

#### macOS / Linux

```bash
cd /path/to/AssetOpsBench
```

Verify you're in the right directory:

#### Windows (PowerShell)

```powershell
Get-ChildItem -Name pyproject.toml, README.md
# Both names should appear (no error)
```

#### macOS / Linux

```bash
ls pyproject.toml README.md
```

---

## Step 3: Install Project Dependencies

### 3.1 Install Python packages

From the repo root (`AssetOpsBench` folder) — **all platforms**:

```bash
uv sync
```

**What this does:**
- Creates a virtual environment at `.venv/`
- Installs all dependencies (fastmcp, couchdb3, pydantic, etc.)
- Registers CLI commands (`plan-execute`, `iot-mcp-server`, etc.)

**Expected output:**
```
   Resolved 45 packages in 12.34s
   Prepared 45 packages in 45.67s
   Installed 45 packages in 1.23s
```

### 3.2 Activate the virtual environment (Optional)

You can skip this if you always use `uv run`. Otherwise:

#### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
# Prompt should change to: (.venv) PS C:\...
```

If you get an execution policy error:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### macOS / Linux (bash or zsh)

```bash
source .venv/bin/activate
# Prompt should show (.venv)
```

Deactivate later with `deactivate` (any OS).

---

## Step 4: Configure Environment Variables

### 4.1 Create `.env` file from template

**Windows (PowerShell)** — `cp` works in PowerShell 5.1+; or use `Copy-Item`:

```powershell
Copy-Item .env.public .env
```

**macOS / Linux:**

```bash
cp .env.public .env
```

### 4.2 Edit `.env` with your credentials

Open `.env` in a text editor (e.g., VS Code):

```
# ── CouchDB (IoTAgent server) ────────────────────────────────────────────────
COUCHDB_URL=http://localhost:5984
COUCHDB_DBNAME=chiller
COUCHDB_USERNAME=admin
COUCHDB_PASSWORD=password

# ── IBM WatsonX (plan-execute runner) ────────────────────────────────────────
WATSONX_APIKEY=<YOUR_API_KEY_HERE>
WATSONX_PROJECT_ID=<YOUR_PROJECT_ID_HERE>
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# ── LiteLLM (plan-execute runner) ────────────────────────────────────────────
LITELLM_API_KEY=
LITELLM_BASE_URL=
```

**Required (no changes needed if using defaults):**
- `COUCHDB_URL`: Keep as `http://localhost:5984`
- `COUCHDB_DBNAME`: Keep as `chiller`
- `COUCHDB_USERNAME`: Keep as `admin`
- `COUCHDB_PASSWORD`: Keep as `password`

**Optional (needed only if using WatsonX LLM):**
- `WATSONX_APIKEY`: Your IBM WatsonX API key (or leave empty to skip)
- `WATSONX_PROJECT_ID`: Your WatsonX project ID

**If you don't have WatsonX credentials**, the system will still work with sample data but LLM-based features will fail gracefully.

---

## Step 5: Start CouchDB (Database)

### 5.1 Verify Docker is running

```bash
docker ps
# Should show no errors (empty list is OK)
```

- **Windows / macOS**: If this fails, open **Docker Desktop** and wait until it is fully started.
- **Linux**: Ensure the Docker daemon is running (`sudo systemctl start docker` on systemd, if you use Docker Engine).

### 5.2 Start CouchDB container

From the repo root — **all platforms**:

```bash
docker compose -f src/couchdb/docker-compose.yaml up -d
```

**Expected output:**
```
[+] Running 2/2
 ✔ Network couchdb_default     Created                    0.1s
 ✔ Container couchdb-couchdb-1 Started                    1.2s
```

### 5.3 Wait for CouchDB to be ready

CouchDB takes ~10 seconds to fully initialize.

#### Windows (PowerShell)

```powershell
Start-Sleep -Seconds 10
docker ps | Select-String couch
```

#### macOS / Linux

```bash
sleep 10
docker ps | grep couch
```

You should see: `couchdb-couchdb-1  ... (healthy)`

### 5.4 Test CouchDB connection

#### Windows (PowerShell)

```powershell
curl.exe -u admin:password http://localhost:5984/
```

#### macOS / Linux

```bash
curl -u admin:password http://localhost:5984/
```

**Expected output:**
```json
{"couchdb":"Welcome","version":"3.3.3",...}
```

If this fails, wait 5 more seconds and try again.

---

## Step 6: Load Sample Data into CouchDB

### ⚠️ CRITICAL FIX: Convert File Line Endings (Windows Only)

When you clone on **Windows**, Git might convert shell scripts to Windows line endings (CRLF), which breaks the CouchDB container’s shell entrypoint. **macOS and Linux** clones usually keep LF; only apply this on Windows if you hit the “unexpected end of file / expecting 'then'” error (see [Troubleshooting](#troubleshooting)).

Fix on Windows:

```powershell
# Convert the setup script from CRLF to LF
(Get-Content "src/couchdb/couchdb_setup.sh" -Raw) -replace "`r`n", "`n" | Set-Content "src/couchdb/couchdb_setup.sh" -NoNewline

"Converted"
```

### 6.1 Verify sample data exists

Sample files live under `src/couchdb/sample_data/` and are mounted into the CouchDB container as `/sample_data` (see `src/couchdb/docker-compose.yaml`).

#### Windows (PowerShell)

```powershell
Get-ChildItem -Recurse src/couchdb/sample_data | Select-Object FullName
```

#### macOS / Linux

```bash
find src/couchdb/sample_data -type f | head
```

You should have at least:

- **`sample_data/iot/chiller6_june2020_sensordata_couchdb.json`** — Chiller sensor readings (JSON array of documents for the `chiller` DB).
- **`sample_data/iot/bulk_docs_vibration.json`** — Vibration benchmark docs (optional but present in-repo for the `vibration` DB).
- **`sample_data/work_order/*.csv`** — Work-order CSVs used to build the `workorder` DB.

### 6.2 Load data into CouchDB

**You usually do not need a manual `curl` bulk upload.** Starting the stack in [Step 5](#step-5-start-couchdb-database) runs `src/couchdb/couchdb_setup.sh`, which waits for CouchDB, then:

1. Runs `init_asset_data.py` to create/load the **`chiller`** database from `sample_data/iot/chiller6_june2020_sensordata_couchdb.json`.
2. Runs `init_wo.py` to create/load the **`workorder`** database from `sample_data/work_order/`.
3. If `sample_data/iot/bulk_docs_vibration.json` exists, runs `init_asset_data.py` again for the **`vibration`** database.

Database names come from Docker env vars in `docker-compose.yaml` (`IOT_DBNAME`, `WO_DBNAME`, `VIBRATION_DBNAME`) and should match your `.env` (`COUCHDB_*`, `IOT_DBNAME`, `WO_DBNAME`).

**Confirm loading finished** (from repo root; works in PowerShell, bash, and zsh):

```bash
docker compose -f src/couchdb/docker-compose.yaml ps
docker compose -f src/couchdb/docker-compose.yaml logs couchdb --tail 60
```

Look for log lines such as `Loading IoT asset data...`, `Loading work order data...`, `Loading vibration data...` (or a skip message if the vibration file were missing), and finally `✅ All databases initialised.`

The IoT load batches documents (default batch size 500 in the scripts); **allow on the order of 1–3 minutes** on first startup before assuming failure.

**If databases are empty or stale but CouchDB is already running**, re-run the init scripts from the **repository root** (uses `.env` for URL and credentials):

```bash
uv run python src/couchdb/init_asset_data.py --drop
uv run python src/couchdb/init_wo.py --drop
uv run python src/couchdb/init_asset_data.py \
  --data-file src/couchdb/sample_data/iot/bulk_docs_vibration.json \
  --db vibration \
  --drop
```

Skip the last command if you do not need the vibration database or the file is missing.

**Nuclear option (reset container volume and reload everything):**

```bash
docker compose -f src/couchdb/docker-compose.yaml down -v
docker compose -f src/couchdb/docker-compose.yaml up -d
```

(`-v` removes the named volume; only use this if you are fine wiping local CouchDB data.)

### 6.3 Verify data was loaded

Check document counts for the three seeded databases (names must match your `.env` / compose defaults: `chiller`, `workorder`, `vibration`).

#### Windows (PowerShell)

```powershell
curl.exe -s -u admin:password http://localhost:5984/chiller | ConvertFrom-Json | Select-Object db_name, doc_count
curl.exe -s -u admin:password http://localhost:5984/workorder | ConvertFrom-Json | Select-Object db_name, doc_count
curl.exe -s -u admin:password http://localhost:5984/vibration | ConvertFrom-Json | Select-Object db_name, doc_count
```

#### macOS / Linux

With `jq`:

```bash
for db in chiller workorder vibration; do
  curl -s -u admin:password "http://localhost:5984/$db" | jq '{db_name, doc_count}'
done
```

**Rough expected `doc_count` values** (from current sample files in the repo):

| Database   | Approx. `doc_count` |
|------------|---------------------|
| `chiller`  | **2896**            |
| `workorder`| **~12,264**         |
| `vibration`| **4096**            |

If `chiller` or `workorder` shows a very small count (for example `1` or `0`), the automatic init did not finish successfully — check `docker logs` for the CouchDB service and the [Troubleshooting](#troubleshooting) section. If the `vibration` database returns HTTP 404, the vibration file was missing or that init step was skipped.

---

## Step 7: Start All MCP Servers

> **Using Claude Desktop?** You can skip this step and configure MCP there instead — see [Run queries from Claude Desktop (optional)](#run-queries-from-claude-desktop-optional). You still need CouchDB (Steps 5–6).

**CRITICAL**: You need **4 separate terminal windows or tabs**. Each server must run continuously.

- **Windows**: Open 4 **PowerShell** (or Windows Terminal) sessions.
- **macOS**: Open 4 tabs in **Terminal.app** or **iTerm2**.
- **Linux**: Open 4 terminal tabs or `tmux` / `screen` panes.

In **each** session, `cd` to your `AssetOpsBench` clone, then run one of the four commands below.

### Terminal 1: Utilities Server

#### Windows (example path — use your clone location)

```powershell
cd C:\Users\yeshi\Downloads\HPML_Final_Project\AssetOpsBench
uv run utilities-mcp-server
```

#### macOS / Linux

```bash
cd /path/to/AssetOpsBench
uv run utilities-mcp-server
```

**Expected output:**
```
Utilities MCP server running on stdio
```

✅ Leave this running!

### Terminal 2: IoT Agent Server

From the same `AssetOpsBench` directory (all platforms):

```bash
uv run iot-mcp-server
```

**Expected output:**
```
Connected to CouchDB: chiller
IoTAgent MCP server running on stdio
```

✅ Leave this running!

### Terminal 3: FMSR Agent Server

```bash
uv run fmsr-mcp-server
```

**Expected output:**
```
FMSRAgent MCP server running on stdio
```

✅ Leave this running!

### Terminal 4: TSFM Agent Server

```bash
uv run tsfm-mcp-server
```

**Expected output:**
```
TSFMAgent MCP server running on stdio
```

✅ Leave this running!

---

## Step 8: Test the System

Open a **5th** terminal, `cd` to `AssetOpsBench`, then run:

### 8.1 Simple Query: Check Current Time

```bash
uv run plan-execute "What is the current date and time?"
```

**Expected output:**
```
────────────────────────────────────────────────────────────
  Answer
────────────────────────────────────────────────────────────
Today's date is 2026-04-05 and time is 15:33:39.
```

✅ If this works, the system is ready!

### 8.2 Sensor Data Query

```bash
uv run plan-execute "What sensors does Chiller 6 have?"
```

**Expected output:**
```
────────────────────────────────────────────────────────────
  Answer
────────────────────────────────────────────────────────────
Chiller 6 has the following sensors:
- Chiller 6 Supply Temperature
- Chiller 6 Return Temperature
- Chiller 6 Condenser Water Flow
- Chiller 6 Power Input
- Chiller 6 Tonnage
[... more sensors ...]
```

### 8.3 Multi-Agent Query (Advanced)

#### Windows (PowerShell — line continuation with backtick)

```powershell
uv run plan-execute --show-plan --show-history `
  "What is the current date? List all assets at MAIN site. Get failure modes for a chiller."
```

#### macOS / Linux (bash — line continuation with backslash)

```bash
uv run plan-execute --show-plan --show-history \
  "What is the current date? List all assets at MAIN site. Get failure modes for a chiller."
```

Or as a single line (any OS):

```bash
uv run plan-execute --show-plan --show-history "What is the current date? List all assets at MAIN site. Get failure modes for a chiller."
```

This exercises all agents:
- **Utilities Agent**: Gets current date
- **IoT Agent**: Lists assets
- **FMSR Agent**: Gets failure modes

---

## Run queries from Claude Desktop (optional)

Instead of [Step 7](#step-7-start-all-mcp-servers) and [`plan-execute`](#step-8-test-the-system), you can use [**Claude Desktop**](https://claude.ai/download) as the client: it spawns each MCP server as a subprocess when needed, so you **do not** keep four separate terminals open for the AssetOpsBench servers.

You still need **CouchDB running with seeded data** ([Steps 5–6](#step-5-start-couchdb-database)) and a configured **`.env`** in the repo root ([Step 4](#step-4-configure-environment-variables)), because the IoT and work-order tools read the same environment variables as the CLI.

### Find absolute paths

1. **Repository root** — e.g. macOS `/Users/you/Documents/HPML/Project/AssetOpsBench`, Windows `C:\Users\you\Projects\AssetOpsBench`.
2. **`uv` executable** — must be an **absolute** path in the config:
   - macOS / Linux: `which uv`
   - Windows (PowerShell): `(Get-Command uv).Source`

If `which uv` prints nothing, install `uv` ([Step 1.2](#12-install-uv-package-manager)) and reopen the terminal.

### Config file location

| OS | Path |
|----|------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` (typically `C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`) |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` (if you use a build that follows the same layout) |

Quit Claude Desktop, edit or create the file, then start Claude again (changes are not reliably picked up without a full restart).

### `mcpServers` configuration

Merge the following into the top-level `"mcpServers"` object (or add these keys alongside any servers you already use). Replace **`UV_PATH`** and **`PROJECT_ROOT`** with your real absolute paths.

Using the same **`cwd`** as the repo root lets `python-dotenv` load your **`.env`** the same way as `uv run` from that directory.

```json
{
  "mcpServers": {
    "utilities": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "utilities-mcp-server"],
      "cwd": "PROJECT_ROOT"
    },
    "iot": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "iot-mcp-server"],
      "cwd": "PROJECT_ROOT"
    },
    "fmsr": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "fmsr-mcp-server"],
      "cwd": "PROJECT_ROOT"
    },
    "tsfm": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "tsfm-mcp-server"],
      "cwd": "PROJECT_ROOT"
    },
    "wo": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "wo-mcp-server"],
      "cwd": "PROJECT_ROOT"
    },
    "vibration": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "vibration-mcp-server"],
      "cwd": "PROJECT_ROOT"
    },
    "skills": {
      "command": "UV_PATH",
      "args": ["run", "--project", "PROJECT_ROOT", "skills-mcp-server"],
      "cwd": "PROJECT_ROOT"
    }
  }
}
```

**Windows note:** In JSON strings, escape backslashes in paths (for example `"C:\\Users\\you\\AssetOpsBench"`) or use forward slashes if your toolchain accepts them (`"C:/Users/you/AssetOpsBench"`).

Omit **`skills`** if you do not need the [skills MCP server](Skills_MCP_Server_Documentation.md). Omit **`tsfm`** or **`vibration`** if you want a smaller tool surface (some tools may log expected “optional dependency” warnings).

This mirrors the layout in [`INSTRUCTIONS.md`](../INSTRUCTIONS.md) (“Connect to Claude Desktop”), with **`cwd`** added so `.env` is found.

### Use Claude after configuration

1. Start **Docker / CouchDB** and confirm data is loaded ([Step 6](#step-6-load-sample-data-into-couchdb)).
2. Open **Claude Desktop** and start a new chat.
3. In **Settings → Developer** (or the MCP / connectors UI for your app version), confirm each configured server shows as connected (no persistent error state).
4. Ask in natural language and let Claude choose tools, for example:
   - “What is the current date and time?” (utilities)
   - “What sensors does Chiller 6 have?” (IoT / CouchDB)
   - “List work orders related to equipment at the MAIN site.” (work-order tools, as available)

Failures that mention CouchDB, missing env vars, or “agent” registration usually mean the database is down, `.env` does not match [Step 4](#step-4-configure-environment-variables), or an MCP server failed to start — see [Troubleshooting](#troubleshooting).

---

## Troubleshooting

### ❌ Problem: "jq command not found"

**Cause**: You ran a command with `| jq` but `jq` is not installed (common on Windows; optional on macOS/Linux).

**Solution**:

- **Windows (PowerShell)**: Prefer built-in JSON parsing:
  ```powershell
  uv run plan-execute --json "What assets exist?" | ConvertFrom-Json | Select-Object -ExpandProperty answer
  ```
- **macOS / Linux**: Install `jq` (`brew install jq`, `sudo apt install jq`) or omit `| jq` and read the raw JSON.

---

### ❌ Problem: "Unable to connect to http://localhost:5984/"

**Cause**: CouchDB container is not running (or Docker is not running).

**Solution** (adjust sleep/curl for your OS — examples below):

```bash
docker ps
docker compose -f src/couchdb/docker-compose.yaml up -d
```

Then wait ~10 seconds and test:

**Windows (PowerShell):**

```powershell
Start-Sleep -Seconds 10
curl.exe -u admin:password http://localhost:5984/
```

**macOS / Linux:**

```bash
sleep 10
curl -u admin:password http://localhost:5984/
```

If `docker ps` fails, start **Docker Desktop** (Windows/macOS) or the Docker daemon (Linux).

---

### ❌ Problem: "Syntax error: end of file unexpected (expecting 'then')"

**Cause**: CouchDB setup script has Windows line endings (CRLF). Docker expects Unix (LF). Most common after cloning on Windows with `core.autocrlf=true`.

**Solution on Windows (PowerShell)**:

```powershell
(Get-Content "src/couchdb/couchdb_setup.sh" -Raw) -replace "`r`n", "`n" | Set-Content "src/couchdb/couchdb_setup.sh" -NoNewline
docker compose -f src/couchdb/docker-compose.yaml down
docker compose -f src/couchdb/docker-compose.yaml up -d
```

**macOS** (BSD `sed` needs an empty backup suffix):

```bash
sed -i '' 's/\r$//' src/couchdb/couchdb_setup.sh
docker compose -f src/couchdb/docker-compose.yaml down
docker compose -f src/couchdb/docker-compose.yaml up -d
```

**Linux** (GNU `sed`):

```bash
sed -i 's/\r$//' src/couchdb/couchdb_setup.sh
docker compose -f src/couchdb/docker-compose.yaml down
docker compose -f src/couchdb/docker-compose.yaml up -d
```

**Prevention**: Add `.gitattributes` to repo root with:

```
*.sh text eol=lf
```

---

### ❌ Problem: "0 assets found at MAIN site" (Empty Results)

**Cause**: The `chiller` database was never seeded, init failed, or credentials/DB name in `.env` do not match the running CouchDB.

**Solution** — verify `doc_count`, then re-seed:

**Windows (PowerShell):**

```powershell
curl.exe -s -u admin:password http://localhost:5984/chiller | ConvertFrom-Json | Select-Object doc_count
```

**macOS / Linux:**

```bash
curl -s -u admin:password http://localhost:5984/chiller | jq .doc_count
```

If the count is wrong, from the **repo root** (with `.env` configured):

```bash
uv run python src/couchdb/init_asset_data.py --drop
uv run python src/couchdb/init_wo.py --drop
```

Or reset the stack and volume, then bring it up again ([section 6.2](#62-load-data-into-couchdb)):

```bash
docker compose -f src/couchdb/docker-compose.yaml down -v
docker compose -f src/couchdb/docker-compose.yaml up -d
```

After a successful init, `chiller` should be on the order of **~2896** documents (see [section 6.3](#63-verify-data-was-loaded)).

---

### ❌ Problem: "Unknown agent 'none'. Registered agents: ['IoTAgent', 'Utilities', 'FMSRAgent', 'TSFMAgent']"

**Cause**: Not all 4 MCP servers are running.

**Solution**: 
1. Open 4 separate terminals (tabs or windows)
2. From `AssetOpsBench`, run one server in each:
   ```bash
   uv run utilities-mcp-server
   uv run iot-mcp-server
   uv run fmsr-mcp-server
   uv run tsfm-mcp-server
   ```
3. Keep all 4 running
4. Run your query in a 5th terminal

---

### ❌ Problem: "Model 'granite-3-3-8b-instruct' was not found"

**Cause**: WatsonX API key is invalid or the model doesn't exist.

**Solution**:
1. Check your `.env` file has valid `WATSONX_APIKEY` and `WATSONX_PROJECT_ID`
2. Or use the default model (no need to specify `--model-id`)
3. Or switch to LiteLLM:
   ```bash
   uv run plan-execute --model-id litellm_proxy/claude-3-sonnet "Your question"
   ```

---

### ❌ Problem: "tsfm dependencies unavailable: No module named 'tsfm_public'"

**This is expected!** TSFM (Time Series Forecasting) requires heavy ML dependencies that aren't installed by default.

**Solution**: Either:
1. Ignore it (queries will skip TSFM steps)
2. Install optional dependencies:
   ```bash
   uv pip install tsfm_public torch transformers
   ```

---

### ❌ Problem: "curl.exe command not found" (Windows)

**Cause**: `curl.exe` is not on PATH (unusual on recent Windows 10/11).

**Solution**:
1. Full path:
   ```powershell
   "C:\Windows\System32\curl.exe" -u admin:password http://localhost:5984/
   ```
2. Or use `Invoke-WebRequest` in PowerShell (see earlier Windows CouchDB test examples in this guide).

---

### ❌ Problem: Docker permission denied (Linux)

**Cause**: Your user is not in the `docker` group.

**Solution**:

```bash
sudo usermod -aG docker "$USER"
# Log out and back in, then: docker ps
```

Or prefix commands with `sudo` (less convenient).

---

## What is AssetOpsBench?

**AssetOpsBench** is a unified framework for developing, orchestrating, and evaluating AI agents in **industrial asset operations and maintenance**.

### Key Components:

**4 Domain-Specific Agents:**
1. **IoT Agent**: Queries sensor data (temperature, flow rates, etc.)
2. **FMSR Agent**: Maps failures to sensors
3. **TSFM Agent**: Forecasting & anomaly detection on time-series data
4. **WO Agent**: Generates work orders

**2 Orchestration Frameworks:**
1. **MetaAgent**: Single agent that uses other agents as tools
2. **AgentHive**: Sequential workflow execution

**Data:**
- 141 industrial scenarios
- Real building sensor data (Chiller 6 from June 2020)
- Stored in CouchDB (NoSQL database)

### How It Works:

```
User: "What sensors does Chiller 6 have?"
            ↓
    Plan-Execute Orchestrator
            ↓
    1. DISCOVER: Query available agents/tools
    2. PLAN: Break question into steps
    3. EXECUTE: Call agents in order
    4. SUMMARIZE: Combine results
            ↓
    Answer: "Chiller 6 has Supply Temperature, Return Temperature, ..."
```

### Where to Learn More:

- 📄 **Paper**: https://arxiv.org/pdf/2506.03828
- 📊 **Dataset**: https://huggingface.co/datasets/ibm-research/AssetOpsBench
- 📖 **Blog**: https://research.ibm.com/blog/asset-ops-benchmark
- 🎥 **YouTube**: https://www.youtube.com/watch?v=kXmBDMrKFjs

---

## Quick Reference: Commands

Paths below are from the **repository root**. Use `curl.exe` on Windows where noted; on macOS/Linux use `curl`.

**Start CouchDB:**
```bash
docker compose -f src/couchdb/docker-compose.yaml up -d
```

**Load / refresh sample data:** Usually automatic when the CouchDB service starts (`couchdb_setup.sh`). To re-run in-place from the repo root:

```bash
uv run python src/couchdb/init_asset_data.py --drop
uv run python src/couchdb/init_wo.py --drop
uv run python src/couchdb/init_asset_data.py \
  --data-file src/couchdb/sample_data/iot/bulk_docs_vibration.json \
  --db vibration \
  --drop
```

Or reset data volume and restart: `docker compose -f src/couchdb/docker-compose.yaml down -v` then `up -d`. See [Step 6](#step-6-load-sample-data-into-couchdb).

**Start servers (4 separate terminals):**
```bash
uv run utilities-mcp-server
uv run iot-mcp-server
uv run fmsr-mcp-server
uv run tsfm-mcp-server
```

**Run queries (5th terminal):**
```bash
uv run plan-execute "What sensors does Chiller 6 have?"
uv run plan-execute --show-plan "List all assets at MAIN site"
uv run plan-execute --show-history "What is the current date?"
```

**Stop CouchDB:**
```bash
docker compose -f src/couchdb/docker-compose.yaml down
```

**View logs:**
```bash
docker logs couchdb-couchdb-1
```

---

## Summary

✅ **You have successfully set up AssetOpsBench with:**
- Python 3.12+ environment
- `uv` package manager
- Docker with CouchDB
- Sample CouchDB data (IoT / work order / vibration, loaded by the container init scripts)
- 4 running MCP servers
- Working plan-execute orchestrator

**Next steps:**
1. Run more complex queries
2. Explore the codebase in `src/`
3. Modify agents for your HPML project
4. Add new scenarios to the benchmark
5. Integrate with your own data sources

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-05 | 1.0 | Initial complete setup guide with all fixes |
| 2026-04-05 | 1.1 | Added macOS and Linux setup paths; kept Windows instructions; expanded troubleshooting and quick reference per OS |
| 2026-04-05 | 1.2 | Added Claude Desktop MCP section (`claude_desktop_config.json`, `cwd`, optional skills); Step 7 cross-link; troubleshooting for Claude MCP |