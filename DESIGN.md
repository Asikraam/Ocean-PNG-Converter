# DESIGN.md — Ocean PNG Converter (Unified WMF/EMF & PDF to PNG)

## Identity & Direction
- **Product:** `Ocean PNG Converter` — satu aplikasi desktop Windows terpadu untuk mengonversi gambar vektor CAD/SACS (`.wmf`, `.emf`) dan dokumen `.pdf` menjadi `.png` beresolusi tinggi, terpisah identitas dan ikonnya dari `BJ PDF` (WMF/EMF → PDF).
- **Reference:** Gaya visual dan alur kerja utilitas drafter mengikuti `BJ PDF` (`batch-wmf2pdf`).
- **Design Read:** Reading this as: Windows desktop engineering utility for CAD/SACS drafters, in a calm fluent-native workbench style (`BJ PDF`), dial `ENERGY 1 / RHYTHM 2 / MOTION 1`.

## Dials
- **ENERGY = 1 (Calm):** Utilitas kerja harian tanpa animasi dekoratif, tanpa gradien neon, tanpa emoji.
- **RHYTHM = 2 (Balanced):** Struktur 4-zona fungsional yang berbeda peran (I/O & Opsi → Action Bar & Counter → Tabel Antrean & Filter → Status Bar).
- **MOTION = 1 (Hover/Progress only):** Transisi warna hover 120ms dan lebar progress bar linear; tidak ada efek melayang atau bounce.

## Color Tokens (WCAG AA Verified)
- Canvas background: `#f3f3f3`
- Panel surface: `#ffffff` | Subtle bar: `#fafafa` | Hover: `#f0f4f9`
- Borders: `#e2e2e2` (panel), `#c6c6c6` (control)
- Text primary: `#1a1a1a` (>15:1 contrast) | Text secondary: `#5c5c5c` (>6:1 contrast)
- Accent (single primary): `#005fb8` (hover `#004c94`, white foreground >6.5:1)
- Semantic status: OK `#107c10` | Warn `#9d5d00` | Error `#c42b1c`

## Typography
- UI: `'Segoe UI', system-ui, -apple-system, sans-serif` (13px base, 15px title)
- Technical data (paths, types, duration `ms`, counters): `'Cascadia Mono', 'Consolas', monospace` with `font-variant-numeric: tabular-nums`

## Anti-Slop Commitments
- Satu aplikasi tunggal untuk WMF, EMF, dan PDF (tidak dipisah ke jendela/EXE terpisah).
- Tanpa emoji dekoratif, tanpa klaim hiperbola, tanpa tombol pasif/tersembunyi.
- Semua state (Empty, Loading/Progress, Error per-file) tampil eksplisit di tabel antrean.
- Navigasi keyboard lengkap (`Tab`, `Shift+Tab`, `Enter`/`Space` pada baris selesai, `Escape` untuk batal).
