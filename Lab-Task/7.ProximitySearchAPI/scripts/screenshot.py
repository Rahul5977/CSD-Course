#!/usr/bin/env python3
"""Headless-Chrome screenshot of a URL (used for the demo-map figure in the report).

    .venv/bin/python scripts/screenshot.py "http://127.0.0.1:3000/" report/screenshots/demo_map.png
"""
import os
import subprocess
import sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main(url, out, size="1400,1000"):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size}",
                    "--virtual-time-budget=5000", f"--screenshot={os.path.abspath(out)}", url],
                   check=True, capture_output=True)
    print("wrote", out)


if __name__ == "__main__":
    main(*sys.argv[1:])
