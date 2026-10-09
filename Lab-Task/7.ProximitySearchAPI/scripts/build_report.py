#!/usr/bin/env python3
"""report/report.md -> report/report.html -> report/REPORT_12341680.pdf

Fills {{PLACEHOLDERS}} from results/analysis.json, report/tables, results/charts,
report/terminal_captures and the source code, then prints to PDF with headless Chrome.

  .venv/bin/python scripts/build_report.py [--api http://10.1.75.53:3270]
"""
import argparse
import base64
import datetime
import glob
import html
import json
import os
import re
import subprocess
import sys

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
REPORT = os.path.join(ROOT, "report")
ROLL = "12341680"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://10.1.75.53:3270")
args = ap.parse_args()

md_src = open(os.path.join(REPORT, "report.md")).read()
A = json.load(open(os.path.join(ROOT, "results", "analysis.json")))
formatter = HtmlFormatter(linenos="inline", cssclass="codehl", style="default")


def table(name):
    p = os.path.join(REPORT, "tables", name)
    return open(p).read() if os.path.exists(p) else "*(pending)*"


def chart(name, caption):
    p = os.path.join(ROOT, "results", "charts", name)
    if not os.path.exists(p):
        return f"*(chart {name} pending)*"
    return f'<div class="fig"><img src="../results/charts/{name}"><div class="cap">{caption}</div></div>'


def code_span(path, first, last):
    """Source excerpt located by marker lines, so it cannot drift when the file changes."""
    lines = open(os.path.join(ROOT, path)).read().split("\n")
    a = next(i for i, l in enumerate(lines) if first in l)
    b = next(i for i, l in enumerate(lines) if last in l)
    return highlight("\n".join(lines[a:b]).rstrip() + "\n", PythonLexer(), formatter)


def terminals():
    out = []
    for fn in sorted(glob.glob(os.path.join(REPORT, "terminal_captures", "*.txt"))):
        txt = open(fn).read().strip()
        out.append(f'<div class="term"><strong>{os.path.basename(fn)}</strong><pre>{html.escape(txt)}</pre></div>')
    return "\n\n".join(out) or "*(none)*"


mc = A["metric_comparison"]
public = os.path.exists(os.path.join(REPORT, "terminal_captures", "02_curl_public.txt"))
deployment = f"""The API runs on lab system **stu78_sys2** in `~/assignment7`, listening on container port 3000, which the
lab NAT publishes as **`{args.api}`**. The boxes have no internet access, cron, systemd or tmux, so
`scripts/deploy.sh` (one command from the laptop):

1. downloads Linux x86-64 / CPython 3.12 wheels on the laptop (pinned in `requirements.txt`);
2. streams code, data and wheels over SSH with `tar` (the boxes have no rsync);
3. installs offline into a virtualenv (`pip --no-index --find-links wheels`);
4. starts a small supervisor loop with `setsid nohup`. It restarts uvicorn within a second if the process ever exits,
   and keeps pid files so `deploy.sh stop|status` never needs a risky `pkill -f`.

The data (≈ 0.8 MB) is loaded once at start-up in about 25 ms; no file is read per request.
""" + ("The terminal captures `02_curl_public.txt` and `03_loadtest_public.txt` in §6 were taken against the public URL."
       if public else "")

repl = {
    "{{DATE}}": datetime.date.today().strftime("%d %B %Y"),
    "{{API_URL}}": f"{args.api}/search/?lat=&long=&cat=&rad=",
    "{{DEMO_URL}}": f"{args.api}/",
    "{{EXPLORED}}": f"{A['latency']['explored_mean']:.0f}",
    "{{P50}}": f"{A['latency']['bfs_p50']:.3f}",
    "{{ORACLE_P50}}": f"{A['latency']['oracle_p50']:.1f}",
    "{{NQ}}": f"{mc['queries']:,}",
    "{{EUC}}": f"{mc['Euclidean (straight line)'] * 10:.1f}",
    "{{MAN}}": f"{mc['Manhattan (full grid)'] * 10:.1f}",
    "{{T_DATASET}}": table("dataset.md"),
    "{{T_DETOUR}}": table("detour.md"),
    "{{T_METRICS}}": table("metric_comparison.md"),
    "{{T_EXAMPLE}}": table("example_query.md"),
    "{{T_LATENCY}}": table("latency.md"),
    "{{T_SCALING}}": table("scaling.md"),
    "{{C_DETOUR}}": chart("detour.png", "Figure 1: Left, road distance divided by Manhattan distance over all pairs up "
                          "to 15 blocks apart from 200 random starts. Right, the share of trips with no detour, by trip length."),
    "{{C_METRICS}}": chart("metric_comparison.png", "Figure 2: Expected marks if the API ranked by each measure."),
    "{{C_EXAMPLE}}": chart("example_query.png", "Figure 3: lat=0.74, long=0.6, cat=bank, rad=0.1. Grey: roads "
                           "(gaps are missing links). Orange: the 10 results and the routes driven to them. "
                           "Circled: what Manhattan ranking would return instead."),
    "{{SCREENSHOT}}": '<div class="fig"><img src="screenshots/demo_map.png"><div class="cap">Figure 4: The demo '
                      'page served at <code>/</code>, showing the same query as Figure 3. The black square is the '
                      'intersection the query snaps to; the orange path is the route to the selected result (#1).</div></div>',
    "{{DEPLOYMENT}}": deployment,
    "{{TERMINALS}}": "\x00TERMS\x00",
    "{{CODE_SEARCH}}": "\x00CODE\x00",
}
for k, v in repl.items():
    md_src = md_src.replace(k, v)
left = re.findall(r"\{\{[A-Z_]+\}\}", md_src)
if left:
    sys.exit(f"unfilled placeholders: {left}")

body = markdown.markdown(md_src, extensions=["tables", "fenced_code"])
body = body.replace("<p>\x00CODE\x00</p>", code_span("app/search.py", "    def search(self, lat", "    def path(self"))
body = body.replace("<p>\x00TERMS\x00</p>", terminals())


def inline_img(m):
    src = m.group(1)
    p = os.path.normpath(os.path.join(REPORT, src))
    if not os.path.exists(p):
        return m.group(0)
    return m.group(0).replace(src, "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode())


body = re.sub(r'<img[^>]*src="([^"]+)"', inline_img, body)

page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Assignment 7 Report: Rahul Raj {ROLL}</title>
<style>
@page {{ size: A4; margin: 16mm 14mm; }}
body {{ font: 10.3pt/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a1a1e; max-width: 178mm; margin: 0 auto; }}
h1 {{ font-size: 22pt; margin: .2em 0; }}
h2 {{ font-size: 14pt; margin-top: 1.3em; border-bottom: 2px solid #e0663a; padding-bottom: 3px; page-break-after: avoid; }}
h3 {{ font-size: 11.5pt; page-break-after: avoid; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.4pt; margin: 8px 0; }}
tr {{ page-break-inside: avoid; }}
td, th {{ border: 1px solid #ccc; padding: 3px 5px; text-align: left; vertical-align: top; }}
th {{ background: #fbeee8; }}
code {{ background: #f4f4f6; padding: 1px 4px; border-radius: 3px; font-size: 8.6pt; }}
pre {{ background: #f7f7f9; border: 1px solid #e2e2e8; border-radius: 6px; padding: 9px; font-size: 7.6pt; line-height: 1.35; white-space: pre-wrap; }}
.codehl {{ font-size: 7.4pt; line-height: 1.3; }}
.codehl pre {{ background: #fafafa; }}
.codehl .linenos {{ color: #999; padding-right: 8px; }}
.fig {{ text-align: center; margin: 10px 0 14px; page-break-inside: avoid; }}
.fig img {{ max-width: 96%; border: 1px solid #e4e4e9; }}
.cap {{ font-size: 8.5pt; color: #444; margin-top: 4px; }}
.term {{ page-break-inside: avoid; margin: 10px 0; }}
.term pre {{ font-size: 6.9pt; }}
.cover {{ text-align: center; padding-top: 50mm; }}
.cover table {{ width: 80%; margin: 26px auto; font-size: 10.5pt; }}
.cover td {{ padding: 5px 10px; }}
.pagebreak {{ page-break-after: always; }}
{formatter.get_style_defs(".codehl")}
</style></head><body>{body}</body></html>"""

html_path = os.path.join(REPORT, "report.html")
open(html_path, "w").write(page)
pdf_path = os.path.join(REPORT, f"REPORT_{ROLL}.pdf")
subprocess.run([CHROME, "--headless", "--disable-gpu", f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
                "--virtual-time-budget=10000", html_path], capture_output=True, timeout=180)
if not os.path.exists(pdf_path):
    sys.exit("PDF generation failed")
print(f"wrote {html_path} and {pdf_path} ({os.path.getsize(pdf_path) // 1024} KB)")
