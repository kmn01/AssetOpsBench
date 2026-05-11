#!/usr/bin/env python3
"""
Cross-platform setup script for CouchDB + data loading
Works on Windows, Mac, and Linux
"""

import subprocess
import sys
import time
import requests
import os
from pathlib import Path

def run_command(cmd, shell=False):
    """Run a command and return success status"""
    try:
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def print_status(message, status="info"):
    """Print colored status messages"""
    colors = {
        "info": "\033[94m",      # Blue
        "success": "\033[92m",   # Green
        "warning": "\033[93m",   # Yellow
        "error": "\033[91m",     # Red
    }
    reset = "\033[0m"
    
    color = colors.get(status, "")
    print(f"{color}{message}{reset}")

def main():
    repo_root = Path(__file__).parent.absolute()
    couchdb_dir = repo_root / "src" / "couchdb"
    
    os.chdir(repo_root)
    
    # Step 1: Start CouchDB
    print_status("Starting CouchDB...", "info")
    os.chdir(couchdb_dir)
    success, output = run_command("docker compose up -d", shell=True)
    if not success:
        print_status(f"Failed to start CouchDB: {output}", "error")
        return 1
    print_status("CouchDB container started", "success")
    
    # Step 2: Wait for CouchDB to be ready
    print_status("Waiting for CouchDB to be ready...", "info")
    os.chdir(repo_root)
    
    for attempt in range(1, 31):
        try:
            response = requests.get(
                "http://localhost:5984/",
                auth=("admin", "password"),
                timeout=2
            )
            if response.status_code == 200:
                print_status("CouchDB is ready!", "success")
                break
        except:
            pass
        
        if attempt < 30:
            print(f"   Attempt {attempt}/30...")
        time.sleep(2)
    else:
        print_status("CouchDB did not become ready in time", "error")
        return 1
    
    # Step 3: Load IoT sensor data
    print_status("Loading IoT sensor data...", "info")
    success, output = run_command(
        f"uv run python -m src.couchdb.init_asset_data --drop",
        shell=True
    )
    if success:
        print_status("IoT sensor data loaded", "success")
    else:
        print_status(f"Failed to load IoT data: {output}", "error")
        return 1
    
    # Step 4: Load work order data
    print_status("Loading work order data...", "info")
    success, output = run_command(
        f"uv run python -m src.couchdb.init_wo --drop",
        shell=True
    )
    if success:
        print_status("Work order data loaded", "success")
    else:
        print_status(f"Failed to load work order data: {output}", "error")
        return 1
    
    # Done!
    print("\n" + "="*60)
    print_status("All done! CouchDB is ready with data.", "success")
    print("="*60)
    print("\n📊 Databases loaded:")
    print("   - chiller: 2,900 IoT sensor documents")
    print("   - workorder: 12,272 work order documents")
    print("   - TOTAL: 15,172 documents\n")
    print_status("Ready to start the 6 MCP servers!", "success")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
