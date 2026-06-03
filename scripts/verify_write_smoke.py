#!/usr/bin/env python3
"""Verify Obsidian wiki shape after write-smoke stock analysis."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from config import Config


REQUIRED_SECTIONS = [
    "\u8bc1\u636e\u8868",
    "\u4e94\u7ef4\u6253\u5206",
    "\u4ea4\u6613\u65f6\u673a\u72b6\u6001",
    "\u4e0e\u4e0a\u6b21\u5206\u6790\u76f8\u6bd4",
    "\u5206\u6790\u65f6\u95f4\u7ebf",
    "\u7814\u7a76\u7b14\u8bb0",
    "\u8d22\u62a5\u9884\u671f",
    "\u6d41\u52a8\u6027\u5206\u6790",
    "\u671f\u6743\u5e02\u573a",
    "\u4ea4\u53c9\u5f15\u7528",
]
RESEARCH_NOTES = "\u7814\u7a76\u7b14\u8bb0"


def wiki_file_for(ticker: str) -> Path:
    safe_ticker = ticker.replace(".", "_").replace("/", "_")
    return Config.get_wiki_dir() / f"{safe_ticker}.md"


def chart_file_for(ticker: str) -> Path:
    safe_ticker = ticker.replace(".", "_")
    return Config.WIKI_BASE_DIR / "Charts" / f"{safe_ticker}_wyckoff.png"


def section_body(content: str, section: str) -> str:
    pattern = rf"(?ms)^##\s+{re.escape(section)}\s*$([\s\S]*?)(^##\s+|\Z)"
    match = re.search(pattern, content)
    return match.group(1) if match else ""


def verify_ticker(ticker: str, require_chart: bool = False) -> None:
    wiki_path = wiki_file_for(ticker)
    if not wiki_path.exists():
        raise SystemExit(f"Expected wiki file not found: {wiki_path}")

    content = wiki_path.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        count = len(re.findall(rf"(?m)^##\s+{re.escape(section)}\s*$", content))
        if count != 1:
            raise SystemExit(
                f"{ticker} section '{section}' expected once, found {count}: {wiki_path}"
            )

    notes = section_body(content, RESEARCH_NOTES)
    if not notes:
        raise SystemExit(f"{ticker} missing research notes body: {wiki_path}")
    if re.search(r"(?m)^##\s+", notes):
        raise SystemExit(f"{ticker} research notes contain top-level ## headings: {wiki_path}")

    chart_path = chart_file_for(ticker)
    if chart_path.exists():
        chart_status = f"chart={chart_path}"
    elif require_chart:
        raise SystemExit(f"Expected chart file not found: {chart_path}")
    else:
        chart_status = f"chart-missing-allowed={chart_path}"

    print(f"verified {ticker}: wiki={wiki_path}; {chart_status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify write-smoke wiki output")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--require-chart", action="store_true")
    args = parser.parse_args()

    for ticker in args.tickers:
        verify_ticker(ticker, require_chart=args.require_chart)


if __name__ == "__main__":
    main()
