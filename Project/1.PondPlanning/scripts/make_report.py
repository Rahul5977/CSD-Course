"""Render docs/report/REPORT.md to REPORT.pdf: Markdown → HTML (python-markdown) → Chrome headless.

No pandoc/LaTeX on the build machine; Chrome's print engine gives a faithful, paginated
PDF from the same Markdown that GitHub renders. Images are inlined as data URIs so the
PDF is self-contained.
"""

from __future__ import annotations

import base64
import mimetypes
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "report" / "REPORT.md"
HTML = ROOT / "docs" / "report" / "REPORT.html"
PDF = ROOT / "docs" / "report" / "REPORT.pdf"
CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
]

CSS = (Path(__file__).with_name("report.css")).read_text(encoding="utf-8")


def inline_images(html: str, base: Path) -> str:
    """Replace every <img src> that points at a local file with a data URI."""

    def repl(match: re.Match[str]) -> str:
        src = match.group(1)
        path = (base / src).resolve()
        if not path.exists():
            return match.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode()
        return f'src="data:{mime};base64,{data}"'

    return re.sub(r'src="([^"]+)"', repl, html)


def main() -> None:
    """Markdown → HTML → PDF; exits with a hint if no Chrome is installed."""
    body = markdown.markdown(
        SRC.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    # Markdown images render as <img alt=...>; turn the alt into a visible caption.
    body = re.sub(
        r'<p><img alt="([^"]*)" src="([^"]+)" /></p>',
        r'<figure><img alt="\1" src="\2" /><figcaption>\1</figcaption></figure>',
        body,
    )
    body = inline_images(body, SRC.parent)
    HTML.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Technical report</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>",
        encoding="utf-8",
    )
    chrome = next((c for c in CHROME if shutil.which(c) or Path(c).exists()), None)
    if chrome is None:
        sys.exit("No Chrome/Chromium found — open docs/report/REPORT.html and print to PDF")
    subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={PDF}",
            HTML.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    HTML.unlink()
    print(f"wrote {PDF.relative_to(ROOT)} ({PDF.stat().st_size // 1024} kB)")


if __name__ == "__main__":
    main()
