#!/usr/bin/env python3
"""
build_report.py — assemble report/report.md -> report.html -> REPORT_12341680.pdf

Fills the {{PLACEHOLDER}} markers with generated content (LB source with line
numbers, comparison table, results sections), renders Markdown to a
self-contained HTML file (images inlined as data URIs), and prints it to PDF
with headless Chrome.

Run with the analysis venv python (needs `markdown` + `pygments`):
  scratchpad/venv/bin/python scripts/build_report.py
"""
import base64
import datetime
import glob
import json
import os
import re
import subprocess
import sys

import markdown
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
REPORT = os.path.join(ROOT, "report")
ROLL = "12341680"

md_src = open(os.path.join(REPORT, "report.md")).read()

# ── {{LB_CODE}}: full loadbalancer.py, highlighted, line-numbered ───────────
lb_code = open(os.path.join(ROOT, "lb", "loadbalancer.py")).read()
formatter = HtmlFormatter(linenos="table", cssclass="codehl", style="default")
lb_html = highlight(lb_code, PythonLexer(), formatter)
pygments_css = formatter.get_style_defs(".codehl")

# ── comparison table + per-config results from processed data ───────────────
def med_rows():
    path = os.path.join(ROOT, "results", "processed", "medians.csv")
    if not os.path.exists(path):
        return []
    import csv
    with open(path) as fh:
        return list(csv.DictReader(fh))

rows = med_rows()

def results_section(cfg, chart_files):
    out = []
    sel = [r for r in rows if r["config"] == cfg]
    if not sel:
        return "*(experiment pending)*"
    out.append("| Concurrency | Throughput (req/s) | Mean ms | p50 | p95 | p99 | Err % | Distribution |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(sel, key=lambda r: int(r["concurrency"])):
        dist = json.loads(r["dist_pct"])
        d = " / ".join(f"{k}:{v}%" for k, v in dist.items())
        out.append(f"| {r['concurrency']} | **{r['rps']}** ({r['rps_min']}–{r['rps_max']}) "
                   f"| {r['mean']} | {r['p50']} | {r['p95']} | {r['p99']} | {r['error_pct']} | {d} |")
    for cf in chart_files:
        p = os.path.join(ROOT, "results", "charts", cf)
        if os.path.exists(p):
            out.append(f"\n![{cf}](../results/charts/{cf})")
    return "\n".join(out)

comparison = "*(experiment pending)*"
ct_path = os.path.join(REPORT, "comparison_table.md")
if os.path.exists(ct_path):
    comparison = open(ct_path).read()

analysis_path = os.path.join(REPORT, "analysis.md")
analysis = open(analysis_path).read() if os.path.exists(analysis_path) else "*(analysis pending)*"
failover_path = os.path.join(REPORT, "failover.md")
failover = open(failover_path).read() if os.path.exists(failover_path) else "*(failover run pending)*"

# ── {{SCREENSHOTS}}: embed the checklist shots that exist, list the rest ────
SHOT_CAPTIONS = {
    "01_ssh_all_systems.png": "All four assigned systems answering over SSH",
    "02_backends_running_ps.png": "Backend listeners on sys2/sys3/sys4 (port 3000)",
    "03_lb_running.png": "Load balancer running on sys1",
    "04_lb_stats_dashboard.png": "Live LB dashboard — three healthy backends",
    "05_chat_ui_login.png": "Messaging app login screen (served through the LB)",
    "06_chat_ui_conversation.png": "Two users exchanging encrypted messages",
    "07_ciphertext_in_store.png": "The on-disk store holds ciphertext only",
    "08_backend_id_badge.png": "X-Backend-Id badge — which instance served you",
    "09_loadgen_run_1backend.png": "Load generator summary — Config B (LB×1)",
    "10_loadgen_run_3backends.png": "Load generator summary — Config C (LB×3)",
    "11_charts.png": "Throughput vs concurrency",
    "12_failover_demo.png": "/lb/stats during the failover demo (one backend DOWN)",
    "13_integrated_url_working.png": "Previous URL serving the app through the LB",
}
shots, missing = [], []
for fn, cap in SHOT_CAPTIONS.items():
    if os.path.exists(os.path.join(REPORT, "screenshots", fn)):
        shots.append(f"**{cap}**\n\n![{cap}](screenshots/{fn})\n")
    else:
        missing.append(fn.split("_")[0])
shots_md = "\n".join(shots) if shots else ""
if missing:
    shots_md += ("\n*Pending screenshots (see `report/SCREENSHOT_CHECKLIST.md`): "
                 + ", ".join(missing) + ". Real terminal output for these is in "
                 "`report/terminal_captures/`.*")

md_src = (md_src
          .replace("{{DATE}}", datetime.date.today().strftime("%d %B %Y"))
          .replace("{{LB_CODE}}", "\x00LBCODE\x00")
          .replace("{{RESULTS_B}}", results_section("B", ["p95_vs_concurrency.png"]))
          .replace("{{RESULTS_C}}", results_section("C", ["backend_distribution_C.png"]))
          .replace("{{COMPARISON_TABLE}}", comparison +
                   "\n\n![throughput](../results/charts/throughput_vs_concurrency.png)\n" +
                   "\n![cdf](../results/charts/latency_cdf_c100.png)\n")
          .replace("{{ANALYSIS}}", analysis)
          .replace("{{FAILOVER}}", failover)
          .replace("{{SCREENSHOTS}}", shots_md))

body = markdown.markdown(md_src, extensions=["tables", "fenced_code"])
body = body.replace("\x00LBCODE\x00", lb_html)

# the 15-column comparison table needs a smaller face to fit portrait width
body = re.sub(
    r'(Comparison table — LB with one backend[^<]*</h2>\s*(?:<p>.*?</p>\s*)?)<table>',
    r'\1<table class="cmp">', body, count=1, flags=re.S)

# inline images as data URIs so the HTML is self-contained
def inline_img(m):
    src = m.group(1)
    p = os.path.normpath(os.path.join(REPORT, src))
    if not os.path.exists(p):
        return m.group(0)
    b64 = base64.b64encode(open(p, "rb").read()).decode()
    return m.group(0).replace(src, f"data:image/png;base64,{b64}")

body = re.sub(r'<img[^>]*src="([^"]+)"', inline_img, body)

html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Assignment 5 Report — Rahul Raj {ROLL}</title>
<style>
@page {{ size: A4; margin: 18mm 15mm; }}
body {{ font: 10.5pt/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a1a1e;
       max-width: 175mm; margin: 0 auto; }}
h1 {{ font-size: 21pt; margin: .2em 0; }} h2 {{ font-size: 14pt; margin-top: 1.4em;
     border-bottom: 2px solid #4f6df5; padding-bottom: 3px; }}
h3 {{ font-size: 11.5pt; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 8px 0;
        page-break-inside: avoid; }}
td, th {{ border: 1px solid #ccc; padding: 3px 6px; text-align: left; }}
table.cmp {{ font-size: 6.6pt; }}
table.cmp td, table.cmp th {{ padding: 2px 3px; }}
th {{ background: #eef1fe; }}
code {{ background: #f4f4f6; padding: 1px 4px; border-radius: 3px; font-size: 8.5pt; }}
pre {{ background: #f7f7f9; border: 1px solid #e2e2e8; border-radius: 6px; padding: 10px;
      font-size: 8pt; line-height: 1.35; overflow-x: hidden; white-space: pre-wrap; }}
pre code {{ background: none; padding: 0; }}
.codehl {{ font-size: 6.9pt; line-height: 1.3; }}
.codehl pre {{ border: none; background: none; padding: 0; white-space: pre-wrap; }}
.codehl table, .codehl td {{ border: none; }}
.codehl .linenos {{ color: #999; padding-right: 8px; user-select: none; }}
img {{ max-width: 100%; page-break-inside: avoid; }}
.cover {{ text-align: center; padding-top: 60mm; }}
.cover table {{ width: 70%; margin: 30px auto; font-size: 11pt; }}
.pagebreak {{ page-break-after: always; }}
blockquote {{ border-left: 3px solid #4f6df5; margin-left: 0; padding-left: 14px;
             color: #444; }}
{pygments_css}
</style></head><body>{body}</body></html>"""

html_path = os.path.join(REPORT, "report.html")
open(html_path, "w").write(html)
print(f"wrote {html_path} ({len(html)//1024} KB)")

chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
pdf_path = os.path.join(REPORT, f"REPORT_{ROLL}.pdf")
r = subprocess.run([chrome, "--headless", "--disable-gpu",
                    f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
                    "--virtual-time-budget=10000", html_path],
                   capture_output=True, text=True, timeout=120)
if os.path.exists(pdf_path):
    print(f"wrote {pdf_path} ({os.path.getsize(pdf_path)//1024} KB)")
else:
    print("Chrome PDF failed:", r.stderr[-400:])
    sys.exit(1)
