#!/usr/bin/env python3
"""Generate a static dashboard HTML from a complete JSONL payload.

The dashboard layout and client-side Plotly code live in the canonical HTML
template. This module only replaces the embedded JSONL block plus the small
source/title fields, so callers can pass the full JSONL text directly.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "dashboards" / "template.html"


def _resolve_template_path(template_path: Path) -> Path:
    if template_path.exists():
        return template_path

    dashboards_dir = REPO_ROOT / "dashboards"
    if dashboards_dir.exists():
        candidates = sorted(dashboards_dir.glob("*.html"), reverse=True)
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        f"Dashboard template not found: {template_path}. "
        "Provide --template or add dashboards/template.html."
    )


def _escape_jsonl_for_js(jsonl_text: str) -> str:
    escaped = jsonl_text.replace("`", r"\`").replace("${", r"\${")
    return escaped.replace("</script>", r"<\/script>")


def _replace_jsonl_block(template_html: str, jsonl_text: str) -> str:
    pattern = re.compile(r"const jsonlData = String\.raw`.*?`;", flags=re.DOTALL)
    replacement = f"const jsonlData = String.raw`{_escape_jsonl_for_js(jsonl_text)}`;"
    updated, count = pattern.subn(lambda _: replacement, template_html, count=1)
    if count != 1:
        raise ValueError(
            "Template missing expected `const jsonlData = String.raw`...`;` block"
        )
    return updated


def _replace_title(html_text: str, title: str) -> str:
    return re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(title)}</title>",
        html_text,
        count=1,
        flags=re.DOTALL,
    )


def _replace_source_label(html_text: str, *, data_href: str, data_name: str) -> str:
    replacement = (
        '<div class="source">\n'
        f'            Data source: <a href="{html.escape(data_href, quote=True)}" target="_blank" rel="noreferrer">'
        f"{html.escape(data_name)}"
        "</a>\n"
        "        </div>"
    )
    pattern = re.compile(
        r'<div class="source">\s*Data source: <a href="[^"]*" target="_blank" rel="noreferrer">[^<]*</a>\s*</div>',
        flags=re.DOTALL,
    )
    updated, count = pattern.subn(replacement, html_text, count=1)
    if count != 1:
        raise ValueError("Template missing expected source label block")
    return updated


def generate_dashboard(
    jsonl_text: str,
    output_html: Path,
    *,
    title: str | None = None,
    data_href: str | None = None,
    data_name: str | None = None,
    template_path: Path = DEFAULT_TEMPLATE,
) -> None:
    resolved_template = _resolve_template_path(template_path)
    template_html = resolved_template.read_text(encoding="utf-8")
    html_text = _replace_jsonl_block(template_html, jsonl_text)

    display_title = title or "AssetOpsBench Evaluation Dashboard (LLM Judge)"
    html_text = _replace_title(html_text, display_title)

    resolved_name = data_name or output_html.with_suffix(".jsonl").name
    resolved_href = data_href or resolved_name
    html_text = _replace_source_label(
        html_text, data_href=resolved_href, data_name=resolved_name
    )

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html_text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jsonl-file", type=Path, required=True, help="Input JSONL file to embed."
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Output dashboard HTML path."
    )
    parser.add_argument("--title", default=None, help="Optional HTML title.")
    parser.add_argument(
        "--data-href", default=None, help="Optional data source href shown in UI."
    )
    parser.add_argument(
        "--data-name", default=None, help="Optional data source label shown in UI."
    )
    parser.add_argument(
        "--template", type=Path, default=DEFAULT_TEMPLATE, help="Template HTML path."
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    jsonl_text = args.jsonl_file.read_text(encoding="utf-8")
    generate_dashboard(
        jsonl_text,
        args.output,
        title=args.title,
        data_href=args.data_href,
        data_name=args.data_name,
        template_path=args.template,
    )
    print(f"Wrote dashboard: {args.output}")


if __name__ == "__main__":
    main()
