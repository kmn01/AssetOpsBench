"""Knowledge Plugin MCP Server

Architecture: ChromaDB vector database for semantic search of maintenance PDFs

Modules:
- main.py: FastMCP entry point
- chromadb_indexer.py: PDF → ChromaDB embeddings + collections
- retriever.py: Search interface (asset-type specific and cross-collection)
"""

__version__ = "0.1.0"
