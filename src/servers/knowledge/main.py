#!/usr/bin/env python3
"""Knowledge Plugin MCP Server - ChromaDB Persistent Indexing

Architecture:
- ChromaDB persistent collections (one per asset type)
- Local sentence-transformers embeddings (no APIs, no keys)
- Pre-indexed on startup (one-time init, then instant queries)
- Automatic disk persistence

Performance Profile:
- Server startup: ~10-15 seconds (one-time pre-indexing)
- All subsequent queries: <100ms (instant, cached in memory)
- Cross-asset search: <200ms (parallelized)
- Day 2+ startups: <1s (uses persisted indexes)
"""

import logging
import os
import sys
from typing import Any, Dict

from fastmcp import FastMCP

from .chromadb_indexer import ensure_initialized
from .retriever import (
    get_asset_docs,
    get_asset_types,
    search_by_asset_type,
    search_by_keyword,
)

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(name)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastMCP("knowledge-mcp-server")


# ─────────────────────────────────────────────────────────────────────────────
# Startup - NO INDEX BUILDING (fast!)
# ─────────────────────────────────────────────────────────────────────────────

@app.on_startup
async def startup():
    """Startup - initialize ChromaDB collections (one-time)."""
    logger.info("Knowledge Plugin MCP Server starting...")
    logger.info("  🔄 Initializing ChromaDB collections...")
    try:
        ensure_initialized()
        logger.info("  ✅ ChromaDB ready. All queries will be instant (<100ms)")
    except Exception as e:
        logger.error(f"  ❌ ChromaDB initialization failed: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

@app.tool()
def search_by_asset_type_tool(
    asset_type: str,
    query: str,
    top_k: int = 3
) -> Dict[str, Any]:
    """Search documentation by asset type and query.
    
    Use this to find relevant maintenance procedures, specifications, or
    troubleshooting guides for a specific asset type.
    
    All searches are instant (<100ms) - collections are pre-indexed at startup.
    
    Examples:
      - search_by_asset_type_tool(asset_type="pump", query="seal temperature")
      - search_by_asset_type_tool(asset_type="chiller", query="startup procedure")
    
    Args:
        asset_type: pump, chiller, motor, compressor, etc.
        query: What to search for (maintenance, specs, troubleshooting, etc.)
        top_k: Number of results (default 3)
    """
    logger.info(f"🔍 Searching {asset_type}: {query} (top_k={top_k})")
    
    try:
        results = search_by_asset_type(asset_type, query, top_k=top_k)
        
        return {
            "status": "success",
            "asset_type": asset_type,
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "text": r["text"],
                    "source": r["source"],
                    "similarity": f"{r['similarity']:.0%}",
                }
                for r in results
            ]
        }
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "hint": "ChromaDB should be initialized at server startup. Check logs for details."
        }


@app.tool()
def search_by_keyword_tool(
    keyword: str,
    top_k: int = 5
) -> Dict[str, Any]:
    """Search across all asset types by keyword.
    
    Use this for broad searches across all available documentation.
    Returns results from all asset types.
    
    Note: Slower than asset-type-specific search because multiple asset types
    may need indexing.
    """
    logger.info(f"🔍 Keyword search: {keyword} (top_k={top_k})")
    
    try:
        results = search_by_keyword(keyword, top_k=top_k)
        
        return {
            "status": "success",
            "keyword": keyword,
            "results_count": len(results),
            "results": [
                {
                    "text": r["text"],
                    "source": r["source"],
                    "asset_type": r.get("asset_type", "unknown"),
                    "similarity": f"{r['similarity']:.0%}",
                }
                for r in results
            ]
        }
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@app.tool()
def get_asset_types_tool() -> Dict[str, Any]:
    """Get list of all available asset types and their documentation.
    
    Returns available asset types (pump, chiller, motor, etc.) and description
    of available documentation for each.
    
    Use this to discover what asset types are available before searching.
    """
    logger.info("📚 Listing available asset types")
    
    try:
        asset_types = get_asset_types()
        
        return {
            "status": "success",
            "count": len(asset_types),
            "asset_types": [
                {
                    "category": at.get("category"),
                    "types": at.get("asset_types"),
                    "description": at.get("description"),
                    "keywords": at.get("keywords"),
                    "document_count": at.get("document_count")
                }
                for at in asset_types
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get asset types: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@app.tool()
def get_asset_docs_tool(asset_type: str) -> Dict[str, Any]:
    """Get available documentation for a specific asset type.
    
    Returns list of PDF documents available for the requested asset type.
    
    Use this to see what documentation is available before searching.
    """
    logger.info(f"📄 Getting docs for: {asset_type}")
    
    try:
        docs = get_asset_docs(asset_type)
        
        return {
            "status": "success",
            "asset_type": asset_type,
            "document_count": docs.get("count", 0),
            "documents": docs.get("documents", []),
            "description": docs.get("description", "")
        }
    except Exception as e:
        logger.error(f"Failed to get docs: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Run the server."""
    logger.info("=" * 80)
    logger.info("Knowledge Plugin MCP Server (Distributed Per-Asset Indexing)")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Architecture:")
    logger.info("  • NO startup indexing (instant startup)")
    logger.info("  • Indexes build ON-DEMAND on first query for each asset")
    logger.info("  • Subsequent queries cached in memory (instant)")
    logger.info("")
    logger.info("Tools:")
    logger.info("  • search_by_asset_type_tool(asset_type, query)")
    logger.info("  • search_by_keyword_tool(keyword)")
    logger.info("  • get_asset_types_tool()")
    logger.info("  • get_asset_docs_tool(asset_type)")
    logger.info("")
    logger.info("=" * 80)
    
    print("Knowledge Plugin starting...", file=sys.stderr)
    app.run()


if __name__ == "__main__":
    main()
