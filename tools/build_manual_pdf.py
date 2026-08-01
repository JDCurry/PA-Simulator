"""Build the user manual as a PDF, via XeLaTeX.

Consumes the block structure from ``manual_parse``, so the markdown file stays the
single source of truth for the in-app page, the Word build, and this.

Usage:
    python tools/build_manual_pdf.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from manual_parse import ROOT, load_blocks                      # noqa: E402

BUILD = ROOT / "build"
OUT = ROOT / "docs" / "PA_Workbench_User_Manual.pdf"

# LaTeX specials, plus the Unicode the manual uses that Latin Modern will not set
# in text mode.
_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "%": r"\%",
    "#": r"\#", "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    "≥": r"$\geq$", "≤": r"$\leq$", "×": r"$\times$",
    "→": r"$\rightarrow$", "°": r"\textdegree{}",
    "•": r"\textbullet{}", "§": r"\S{}",
}


def esc(text: str) -> str:
    return "".join(_ESCAPES.get(ch, ch) for ch in text)


def runs_to_tex(runs: list[dict], in_table: bool = False) -> str:
    out = []
    for r in runs:
        body = esc(r["text"])
        if r["code"]:
            # A long path like tools/build_training_scenario.py has no natural break
            # point, so it overflows the measure. Permit breaks after separators.
            body = (body.replace(r"\_", r"\_\allowbreak{}")
                        .replace("/", r"/\allowbreak{}")
                        .replace(".", r".\allowbreak{}"))
            body = rf"\texttt{{\small {body}}}"
        if r["bold"]:
            body = rf"\textbf{{{body}}}"
        if r["italic"]:
            body = rf"\textit{{{body}}}"
        out.append(body)
    return "".join(out)


def table_to_tex(block: dict) -> str:
    header, rows = block["header"], block["rows"]
    weights = block["weights"]
    ncols = len(header)
    size = r"\footnotesize" if ncols >= 5 else r"\small"

    # tabularx X columns scaled by \hsize so the widths reflect content.
    # Hyphenation is suppressed in cells -- a narrow column otherwise produces
    # breaks like "Code en-forcement", which reads as a typo.
    cell = (r"\raggedright\arraybackslash"
            r"\hyphenpenalty=10000\exhyphenpenalty=10000")
    spec = "".join(rf">{{\hsize={w}\hsize{cell}}}X" for w in weights)
    lines = [
        r"\begingroup", size,
        r"\setlength{\tabcolsep}{5pt}",
        r"\renewcommand{\arraystretch}{1.25}",
        rf"\begin{{tabularx}}{{\linewidth}}{{{spec}}}",
        r"\toprule",
        " & ".join(rf"\textbf{{{runs_to_tex(c, True)}}}" for c in header) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(runs_to_tex(c, True) for c in row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabularx}", r"\endgroup", ""]
    return "\n".join(lines)


def blocks_to_tex(blocks: list[dict]) -> str:
    body: list[str] = []
    seen_title = False
    skipped_toc = False

    i = 0
    while i < len(blocks):
        b = blocks[i]
        kind = b["type"]

        if kind == "heading":
            level, text = b["level"], b["text"]
            if level == 1 and not seen_title:
                seen_title = True          # the title page carries it
                i += 1
                continue
            # The markdown Contents list is replaced by a real \tableofcontents.
            if text.lower() == "contents":
                skipped_toc = True
                i += 1
                while i < len(blocks) and blocks[i]["type"] in ("list", "rule"):
                    i += 1
                continue
            cmd = {2: "section", 3: "subsection", 4: "subsubsection"}.get(level, "paragraph")
            body.append(rf"\{cmd}{{{runs_to_tex(b['runs'])}}}")

        elif kind == "paragraph":
            body.append(runs_to_tex(b["runs"]))
            body.append("")

        elif kind == "list":
            env = "enumerate" if b["ordered"] else "itemize"
            body.append(rf"\begin{{{env}}}[leftmargin=1.4em,itemsep=2pt,topsep=4pt]")
            if b["ordered"] and b.get("start", 1) != 1:
                body.append(rf"\setcounter{{enumi}}{{{b['start'] - 1}}}")
            for item in b["items"]:
                body.append(rf"\item {runs_to_tex(item)}")
            body.append(rf"\end{{{env}}}")
            body.append("")

        elif kind == "callout":
            body.append(r"\begin{callout}")
            for p in b["paragraphs"]:
                body.append(runs_to_tex(p))
                body.append("")
            body.append(r"\end{callout}")

        elif kind == "table":
            body.append(table_to_tex(b))

        elif kind == "rule":
            pass        # section headings already provide the visual breaks

        i += 1

    if not skipped_toc:
        body.insert(0, r"\tableofcontents\clearpage")
    return "\n".join(body)


PREAMBLE = r"""
\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage[letterpaper,margin=1in,headheight=14pt]{geometry}
\usepackage{tabularx,booktabs,array}
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage[most]{tcolorbox}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}

\definecolor{navy}{HTML}{1F3A5F}
\definecolor{rule}{HTML}{C9D2DB}
\definecolor{calloutbg}{HTML}{F4F6F8}

\titleformat{\section}{\Large\bfseries\color{navy}}{\thesection}{0.7em}{}
\titleformat{\subsection}{\large\bfseries\color{navy}}{\thesubsection}{0.6em}{}
\titleformat{\subsubsection}{\normalsize\bfseries}{\thesubsubsection}{0.5em}{}
\titlespacing*{\section}{0pt}{18pt}{8pt}
\titlespacing*{\subsection}{0pt}{14pt}{6pt}
\setcounter{tocdepth}{2}
\setcounter{secnumdepth}{2}

\newtcolorbox{callout}{
  breakable, enhanced, colback=calloutbg, colframe=navy,
  boxrule=0pt, leftrule=3pt, arc=0pt, outer arc=0pt,
  left=10pt, right=10pt, top=8pt, bottom=8pt,
  before skip=10pt, after skip=10pt,
}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\headrule}{\hbox to\headwidth{\color{rule}\leaders\hrule height \headrulewidth\hfill}}
\fancyhead[L]{\small\color{navy}Public Assistance Workbench}
\fancyhead[R]{\small\color{navy}User Manual}
\fancyfoot[C]{\small\thepage}

\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\raggedbottom
\renewcommand{\arraystretch}{1.2}
"""

TITLE_PAGE = r"""
\begin{titlepage}
\centering
\vspace*{1.4in}
{\color{navy}\rule{\linewidth}{2pt}}\\[10pt]
{\Huge\bfseries\color{navy} Public Assistance Workbench}\\[10pt]
{\Large User Manual}\\[8pt]
{\color{navy}\rule{\linewidth}{2pt}}\\[26pt]
{\large A FEMA Public Assistance reimbursement workbench\\and training simulator}\\[34pt]
\begin{minipage}{0.84\linewidth}
\small
Built against the FEMA Public Assistance Program and Policy Guide, Version 5 Amended
(January 2025); FEMA Policy FP-104-23-001, Public Assistance Simplified Procedures
(January 2023); 44 CFR Part 206; 2 CFR Part 200; and the Disaster Recovery Reform Act
of 2018.
\end{minipage}\\[26pt]
\begin{minipage}{0.84\linewidth}
\centering\small\itshape
Not affiliated with FEMA. This is a planning and training aid. Dollar thresholds are
indexed annually and cost shares are set by each declaration. Verify every figure
against the current PAPPG and your own award before relying on it.
\end{minipage}
\vfill
{\small VERSION\_LINE}\\[4pt]
{\small BUILD\_DATE}
\end{titlepage}
"""


def build_tex(blocks: list[dict], version: str) -> str:
    title = TITLE_PAGE.replace(
        "VERSION\\_LINE", f"Application version {esc(version)}"
    ).replace("BUILD\\_DATE", date.today().strftime("%B %d, %Y"))
    return "\n".join([
        PREAMBLE,
        r"\begin{document}",
        title,
        r"\tableofcontents",
        r"\clearpage",
        blocks_to_tex(blocks),
        r"\end{document}",
    ])


def main() -> None:
    if not shutil.which("xelatex"):
        raise SystemExit("xelatex not found on PATH.")

    sys.path.insert(0, str(ROOT))
    from pa import __version__

    BUILD.mkdir(exist_ok=True)
    tex = BUILD / "manual.tex"
    tex.write_text(build_tex(load_blocks(), __version__), encoding="utf-8")

    for run in (1, 2):      # twice, so the table of contents resolves
        proc = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory", str(BUILD), str(tex)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            log = BUILD / "manual.log"
            tail = ""
            if log.exists():
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
                errs = [l for l in lines if l.startswith("!")]
                tail = "\n".join(errs[:10] or lines[-30:])
            raise SystemExit(f"xelatex failed on pass {run}:\n{tail}")

    produced = BUILD / "manual.pdf"
    OUT.parent.mkdir(exist_ok=True)
    shutil.copyfile(produced, OUT)
    print(f"Wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
