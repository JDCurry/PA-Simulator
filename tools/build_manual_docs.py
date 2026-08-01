"""Build the user manual as Word and PDF from docs/USER_MANUAL.md.

One markdown source, three renderings: the in-app Manual page reads the markdown
directly, and this produces the .docx and .pdf for distribution.

Usage:
    python tools/build_manual_docs.py            # both
    python tools/build_manual_docs.py --docx     # Word only
    python tools/build_manual_docs.py --pdf      # PDF only

Requires XeLaTeX for the PDF and Node with the ``docx`` package for Word. Either can
be skipped; the script reports which outputs it produced.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from manual_parse import ROOT, load_blocks                      # noqa: E402

BUILD = ROOT / "build"
DOCS = ROOT / "docs"
DOCX_SCRIPT = ROOT / "tools" / "build_manual_docx.js"
DOCX_OUT = DOCS / "PA_Workbench_User_Manual.docx"
PDF_OUT = DOCS / "PA_Workbench_User_Manual.pdf"

#: ``docx`` is declared in package.json and installed into the project root by
#: ``npm install``. NODE_MODULES lets a caller point elsewhere if they keep it
#: somewhere unusual.
NODE_SEARCH = [
    Path(os.environ["NODE_MODULES"]) if os.environ.get("NODE_MODULES") else None,
    ROOT / "node_modules",
]


def version() -> str:
    sys.path.insert(0, str(ROOT))
    from pa import __version__
    return __version__


def write_blocks() -> Path:
    BUILD.mkdir(exist_ok=True)
    path = BUILD / "manual_blocks.json"
    path.write_text(json.dumps(load_blocks(), indent=1), encoding="utf-8")
    return path


def find_node_modules() -> Path | None:
    for candidate in NODE_SEARCH:
        if candidate is not None and (candidate / "docx").exists():
            return candidate
    return None


def build_docx(blocks: Path) -> bool:
    if not shutil.which("node"):
        print("  Word: skipped, node not on PATH")
        return False
    modules = find_node_modules()
    if modules is None:
        print("  Word: skipped, the 'docx' npm package was not found.\n"
              "        Run: npm install docx")
        return False

    env = {"NODE_PATH": str(modules)}
    import os
    env = {**os.environ, **env}
    proc = subprocess.run(
        ["node", str(DOCX_SCRIPT), str(blocks), str(DOCX_OUT), version()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    if proc.returncode != 0:
        print("  Word: FAILED")
        print("    " + (proc.stderr or proc.stdout).strip()[:1200].replace("\n", "\n    "))
        return False
    print("  Word: " + proc.stdout.strip())
    return True


def build_pdf() -> bool:
    if not shutil.which("xelatex"):
        print("  PDF: skipped, xelatex not on PATH")
        return False
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_manual_pdf.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        print("  PDF: FAILED")
        print("    " + (proc.stderr or proc.stdout).strip()[:1200].replace("\n", "\n    "))
        return False
    print("  PDF: " + proc.stdout.strip())
    return True


def main() -> None:
    args = set(sys.argv[1:])
    want_docx = not args or "--docx" in args
    want_pdf = not args or "--pdf" in args

    blocks = write_blocks()
    n = len(json.loads(blocks.read_text(encoding="utf-8")))
    print(f"Parsed docs/USER_MANUAL.md -> {n} blocks")

    ok = []
    if want_docx:
        ok.append(build_docx(blocks))
    if want_pdf:
        ok.append(build_pdf())

    if not any(ok):
        raise SystemExit("No documents were produced.")


if __name__ == "__main__":
    main()
