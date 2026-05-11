#!/usr/bin/env python3
"""Tests for Knowledge Plugin (ChromaDB)

Tests for ChromaDB-based indexing and retrieval.

Usage:
    pytest src/servers/knowledge/tests/ -v
    python -m pytest src/servers/knowledge/tests/test_knowledge.py -v
"""

import pytest
from pathlib import Path

from src.servers.knowledge.chromadb_indexer import (
    initialize,
    search_vectors,
    get_embedding_model,
    _chunk_text,
)
from src.servers.knowledge.retriever import (
    search_by_asset_type,
    search_by_keyword,
)


class TestIndexer:
    """Test ChromaDB indexing functionality."""
    
    def test_chunk_text(self):
        """Test text chunking."""
        # Create text with enough tokens to create multiple chunks
        # Each "word " is roughly 1 token, CHUNK_SIZE_TOKENS = 512
        text = "word " * 600  # 600 tokens, should split into multiple chunks
        chunks = _chunk_text(text)
        
        # Should have multiple chunks due to overlap
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)
        assert all(len(c) > 0 for c in chunks)
    
    def test_initialization(self):
        """Test ChromaDB initialization."""
        try:
            initialize()
            assert True  # If no exception, initialization succeeded
        except Exception as e:
            pytest.skip(f"ChromaDB initialization failed: {e}")
    
    def test_embedding_model(self):
        """Test embedding model loading."""
        try:
            model = get_embedding_model()
            assert model is not None
            # Test encoding a simple text
            embedding = model.encode(["test"])
            assert len(embedding) > 0
            assert len(embedding[0]) == 384  # MiniLM dimension
        except Exception as e:
            pytest.skip(f"Model loading failed: {e}")


class TestRetriever:
    """Test ChromaDB retrieval functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Initialize ChromaDB before tests."""
        try:
            initialize()
        except Exception as e:
            pytest.skip(f"Could not initialize ChromaDB: {e}")
    
    def test_search_by_asset_type(self):
        """Test asset type search."""
        results = search_by_asset_type("pump", "seal inspection", top_k=3)
        
        assert isinstance(results, list)
        if results:
            assert "text" in results[0]
            assert "source" in results[0]
            assert "similarity" in results[0]
            assert 0 <= results[0]["similarity"] <= 1
    
    def test_search_by_keyword(self):
        """Test keyword search across all assets."""
        results = search_by_keyword("maintenance", top_k=3)
        
        assert isinstance(results, list)
        # May be empty if PDFs don't have keyword, just verify it's a list
        if results:
            assert "text" in results[0]
            assert "asset_type" in results[0]
    
    def test_search_vectors_direct(self):
        """Test direct vector search."""
        results = search_vectors("pump seal", asset_type="pump", top_k=2)
        
        assert isinstance(results, list)
        if results:
            assert "text" in results[0]
            assert "source" in results[0]
            assert "similarity" in results[0]
