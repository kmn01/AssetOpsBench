#!/usr/bin/env python3
"""Retriever for ChromaDB Knowledge Plugin

Provides search interface for persistent, scalable vector search.
Uses local sentence-transformers embeddings (no APIs, no keys).
Pre-indexes all collections at startup for instant queries.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .chromadb_indexer import search_vectors, ensure_initialized

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).parent
MANIFEST_FILE = _SCRIPT_DIR / "packs" / "assetopsbench" / "asset_docs_manifest.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# Main Retrieval
# ─────────────────────────────────────────────────────────────────────────────

def search_by_asset_type(
    asset_type: str,
    query: str,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """Search by asset type and query.
    
    Args:
        asset_type: pump, chiller, motor, etc.
        query: What to search for
        top_k: Number of results
        
    Returns:
        List of relevant chunks
    """
    ensure_initialized()
    logger.info(f"Searching {asset_type}: {query}")
    return search_vectors(query, asset_type=asset_type.lower(), top_k=top_k)


def search_by_keyword(keyword: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search across all asset types by keyword.
    
    Uses ChromaDB to search all collections in parallel.
    Much faster than sequential searching.
    """
    ensure_initialized()
    logger.info(f"Keyword search: {keyword} (across all assets)")
    
    # ChromaDB search_vectors handles cross-asset automatically
    results = search_vectors(keyword, asset_type=None, top_k=top_k)
    return results


def get_asset_docs(asset_type: str) -> Dict[str, Any]:
    """Get documentation for asset type."""
    manifest = _load_manifest()
    asset_type_lower = asset_type.lower().strip()
    
    if asset_type_lower in ["*", "all", "any"]:
        all_docs = set()
        for info in manifest.values():
            all_docs.update(info.get("documents", []))
        return {
            "asset_type": "all",
            "description": "All available documents",
            "documents": sorted(list(all_docs)),
            "count": len(all_docs)
        }
    
    for category, info in manifest.items():
        if asset_type_lower in [t.lower() for t in info.get("asset_types", [])]:
            return {
                "asset_type": asset_type,
                "category": category,
                "description": info.get("description", ""),
                "documents": info.get("documents", []),
                "count": len(info.get("documents", []))
            }
    
    return {"asset_type": asset_type, "documents": [], "count": 0}


def get_asset_types() -> List[Dict[str, Any]]:
    """List all asset types."""
    manifest = _load_manifest()
    
    result = []
    for category, info in manifest.items():
        if category != "general":
            result.append({
                "category": category,
                "description": info.get("description", ""),
                "asset_types": info.get("asset_types", []),
                "keywords": info.get("keywords", []),
                "document_count": len(info.get("documents", []))
            })
    
    return result


def _load_manifest() -> Dict[str, Any]:
    """Load asset manifest."""
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_FILE}")
    
    with open(MANIFEST_FILE) as f:
        return yaml.safe_load(f)
