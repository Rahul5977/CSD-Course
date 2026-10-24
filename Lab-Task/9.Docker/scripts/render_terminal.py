#!/usr/bin/env python3
"""Render a captured terminal log (report/captures/*.txt) as a terminal-style PNG.

    python3 scripts/render_terminal.py report/captures/03_up.txt report/figures/term_up.png "title"
"""
import html
import os
import subprocess
import sys
import tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = """<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#1e1f24}
.win{margin:0;border-radius:8px;overflow:hidden;font:13px/1.45 Menlo,monospace}
.bar{background:#2d2f36;color:#a8acb8;padding:6px 12px;font:12px system-ui}
.bar i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px;vertical-align:-1px}
pre{margin:0;padding:12px 14px;color:#d7dae0;white-space:pre-wrap;word-break:break-all}
.c{color:#7ec699}.h{color:#8a8f9c}
</style><div class="win"><div class="bar"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i>
<i style="background:#28c840"></i>&nbsp; zsh &mdash; TITLE</div><pre>BODY</pre></div>"""


def main(src, out, title="9.Docker"):
    lines = []
    for raw in open(src).read().rstrip("\n").splitlines():
        esc = html.escape(raw)
        if raw.startswith("$ "):
            esc = f'<span class="c">{esc}</span>'
        elif raw.startswith("#"):
            esc = f'<span class="h">{esc}</span>'
        lines.append(esc)
    page = PAGE.replace("TITLE", html.escape(title)).replace("BODY", "\n".join(lines))
    height = 60 + 19 * sum(1 + len(l) // 130 for l in open(src).read().splitlines())
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size=1100,{height}", f"--screenshot={os.path.abspath(out)}",
                    "file://" + f.name], check=True, capture_output=True)
    os.unlink(f.name)
    print("wrote", out)


if __name__ == "__main__":
    main(*sys.argv[1:])
