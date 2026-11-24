"""Automated CI & local smoke verification for Ocean PNG Converter."""

import sys
from pathlib import Path
import webview.util as wv_util

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bj_png_app


def main() -> int:
    # 1. Verify UI & bundled emf-converter assets
    for rel in (
        "bj_png_ui/index.html",
        "bj_png_ui/styles.css",
        "bj_png_ui/app.js",
        "bj_png_ui/emf_engine.js",
        "assets/ocean_png.ico",
    ):
        p = ROOT / rel
        assert p.exists() and p.stat().st_size > 0, f"Missing asset: {p}"

    # 2. Verify all WinForms file dialog filters match pywebview parser
    filters = (
        "File Didukung (*.wmf;*.emf;*.wmz;*.emz;*.pdf)",
        "Vektor WMF dan EMF (*.wmf;*.emf;*.wmz;*.emz)",
        "Dokumen PDF (*.pdf)",
        "Semua File (*.*)",
    )
    for flt in filters:
        wv_util.parse_file_type(flt)

    # 3. Run built-in PDFium + WMF engine smoke test
    return bj_png_app.run_smoke_test()


if __name__ == "__main__":
    raise SystemExit(main())
