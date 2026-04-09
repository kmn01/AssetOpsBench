"""Pytest configuration and fixtures for knowledge plugin tests."""

import pytest
from pathlib import Path
import tempfile
import os


@pytest.fixture
def temp_knowledge_dir():
    """Create a temporary knowledge directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def override_knowledge_path(temp_knowledge_dir, monkeypatch):
    """Override KNOWLEDGE_DIR environment variable for tests."""
    monkeypatch.setenv("KNOWLEDGE_DIR", str(temp_knowledge_dir))
    yield temp_knowledge_dir


@pytest.fixture
def sample_pdfs_path():
    """Get path to sample PDFs."""
    return Path(__file__).parent.parent / "packs" / "assetopsbench" / "pdfs"


@pytest.fixture
def asset_manifest_path():
    """Get path to asset manifest."""
    return Path(__file__).parent.parent / "packs" / "assetopsbench" / "asset_docs_manifest.yaml"
