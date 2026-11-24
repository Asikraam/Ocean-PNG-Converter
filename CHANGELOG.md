# Changelog

All notable changes to **Ocean PNG Converter** are documented in this file.

## [1.0.0] - 2026-11-25

### Added
- **Unified Windows Desktop App (`Ocean PNG Converter.exe`)**: Combines WMF/EMF/WMZ/EMZ vector-to-PNG and multi-page PDF-to-PNG conversion in one single-window workbench powered by native Edge WebView2 (`pywebview`).
- **Vector Metafile Engine (`emf-converter` + `PDFium`)**: Renders CAD, GIS, and SACS metafiles to vector PDF with on-demand Windows font resolution (including `.shx` fallbacks) and rasterizes via PDFium, keeping thin cosmetic lines, leader arrows, and borders intact.
- **High-Speed Parallel PNG Pipeline**: Uses bounded `ThreadPoolExecutor` PNG saving (`compress_level=2`), in-memory font caching, uncompressed internal vector handoff, and `ZIP_STORED` packaging to cut 10-page 300 DPI PDF conversion time from 11.74s to 5.58s (with ZIP enabled).
- **Drafter Workbench UI**: Supports drag-and-drop for mixed files or folders, numbered action controls (`1. Mulai Konversi ke PNG`, `Stop / Batal`, `2. Buka Folder Hasil`), per-file status/duration/filter tabs (`Semua`, `Berhasil`, `Lewat`, `Gagal`), double-click / `Enter` to open output, and persistent preferences.
- **1-Click Installer & Portable Build**: Packaged as `Ocean-PNG-Converter-Setup-v1.0.0-win-x64.exe` (Inno Setup 6) and `Ocean-PNG-Converter-v1.0.0-win-x64-Portable.zip`.
