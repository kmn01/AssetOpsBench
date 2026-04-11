#!/usr/bin/env python3
"""Citation formatter for Knowledge Plugin search results.

Formats search results with proper citations showing:
- PDF filename
- Page number
- Similarity score
- Quote excerpt
"""

from typing import Any, Dict, List


def format_citations(search_results: List[Dict[str, Any]], max_quote_length: int = 120) -> str:
    """Format search results into a readable citations section.
    
    Args:
        search_results: List of dicts with keys: text, similarity, source, page, asset_type
        max_quote_length: Maximum length of quote excerpt (chars)
    
    Returns:
        Formatted citation block as markdown-style string
    """
    if not search_results:
        return "No sources found."
    
    citation_lines = ["", "Sources & Citations:", "─" * 60]
    
    for idx, result in enumerate(search_results, 1):
        source = result.get("source", "unknown.pdf")
        page = result.get("page")
        similarity = result.get("similarity", 0)
        text = result.get("text", "")
        
        # Extract quote (first 120 chars, ellipsis if longer)
        quote = text[:max_quote_length]
        if len(text) > max_quote_length:
            quote += "..."
        
        # Format page reference
        page_ref = f" - Page {page}" if page else ""
        
        # Build citation line
        citation = f"{idx}. {source}{page_ref}"
        citation_lines.append(citation)
        citation_lines.append(f"   Match: {similarity:.0%} confidence")
        citation_lines.append(f"   \"{quote}\"")
        citation_lines.append("")
    
    return "\n".join(citation_lines)


def format_citation_inline(result: Dict[str, Any]) -> str:
    """Format single result as inline citation for use in text.
    
    Format: [PDF (Page N) - XX% match]
    
    Args:
        result: Single search result dict
    
    Returns:
        Inline citation string
    """
    source = result.get("source", "unknown.pdf")
    page = result.get("page")
    similarity = result.get("similarity", 0)
    
    # Remove .pdf extension for cleaner look
    source_name = source.replace(".pdf", "").replace("_", " ")
    
    page_str = f" (Page {page})" if page else ""
    return f"[{source_name}{page_str} - {similarity:.0%} match]"


def format_citations_with_answers(answer_text: str, search_results: List[Dict[str, Any]]) -> str:
    """Format an answer followed by citations.
    
    Args:
        answer_text: The LLM-generated answer
        search_results: Search results used to generate the answer
    
    Returns:
        Formatted string with answer and citations
    """
    output = []
    
    # Add the main answer
    output.append(answer_text)
    
    # Add citations section
    if search_results:
        output.append(format_citations(search_results))
    
    return "\n".join(output)
