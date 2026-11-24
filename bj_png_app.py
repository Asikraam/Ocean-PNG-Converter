"""
BJ PNG - Unified Desktop Converter (WMF / EMF & PDF to PNG)

Single Windows desktop application styled after BJ PDF, built with native Edge WebView2 (pywebview),
Windows GDI+ vector rasterization (WMF/EMF), and PDFium (PDF).
"""

from __future__ import annotations

import base64
import ctypes
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import winreg
import zipfile
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import webview
from webview.dom import DOMEventHandler

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from PIL import Image, ImageChops
except ImportError:
    Image = None
    ImageChops = None


APP_NAME = "Ocean PNG Converter"
APP_TITLE = "Ocean PNG Converter - Ubah WMF, EMF & PDF Jadi PNG"
APP_ID = "com.aswal.ocean-png"
SUPPORTED_EXTS = {".wmf", ".emf", ".wmz", ".emz", ".pdf"}

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))


EMBEDDED_WMF_PS_SCRIPT = r"""
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$Path,
    [float]$Scale = 4.0,
    [int]$Dpi = 96,
    [switch]$UseDpi,
    [ValidateSet('Transparent', 'White', 'Black')]
    [string]$Background = 'Transparent',
    [switch]$KeyOutWhite,
    [int]$Padding = 0,
    [string]$OutputDir,
    [switch]$Recursive
)

Add-Type -AssemblyName System.Drawing
$processedCount = 0
$successCount = 0

foreach ($item in $Path) {
    $targets = @()
    $resolvedPath = try { (Resolve-Path -Path $item -ErrorAction Stop).Path } catch { $item }
    if (Test-Path -Path $resolvedPath -PathType Container) {
        $opt = if ($Recursive) { @{ Recurse = $true } } else { @{} }
        $files = Get-ChildItem -Path $resolvedPath -File @opt | Where-Object { $_.Extension -match '^\.(wmf|emf)$' }
        $targets += $files.FullName
    } elseif (Test-Path -Path $resolvedPath -PathType Leaf) {
        $ext = [System.IO.Path]::GetExtension($resolvedPath).ToLowerInvariant()
        if ($ext -eq '.wmf' -or $ext -eq '.emf') {
            $targets += (Get-Item -Path $resolvedPath).FullName
        }
    }

    foreach ($file in $targets) {
        $processedCount++
        try {
            $rawBytes = [System.IO.File]::ReadAllBytes($file)
            if ($rawBytes.Length -eq 0) { throw "File kosong (0 bytes)." }

            $ms = New-Object System.IO.MemoryStream (,$rawBytes)
            $mf = New-Object System.Drawing.Imaging.Metafile $ms
            $header = $mf.GetMetafileHeader()
            $bounds = $header.Bounds

            $origW = $bounds.Width
            $origH = $bounds.Height
            $dpiX = $header.DpiX
            $dpiY = $header.DpiY
            if ($origW -le 0 -or $origH -le 0) { $origW = $mf.Width; $origH = $mf.Height }
            if ($dpiX -le 0) { $dpiX = 96.0 }
            if ($dpiY -le 0) { $dpiY = 96.0 }

            $effScale = if ($UseDpi) { $Dpi / $dpiX } else { $Scale }
            $targetW = [Math]::Max(1, [int][Math]::Round($origW * $effScale))
            $targetH = [Math]::Max(1, [int][Math]::Round($origH * $effScale))
            $canvasW = $targetW + ($Padding * 2)
            $canvasH = $targetH + ($Padding * 2)

            if ($canvasW -gt 16384 -or $canvasH -gt 16384) {
                $ratio = [Math]::Min(16384.0 / $canvasW, 16384.0 / $canvasH)
                $targetW = [int]($targetW * $ratio)
                $targetH = [int]($targetH * $ratio)
                $canvasW = $targetW + ($Padding * 2)
                $canvasH = $targetH + ($Padding * 2)
            }

            $bmp = New-Object System.Drawing.Bitmap $canvasW, $canvasH, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
            $bmp.SetResolution(([float]($dpiX * $effScale)), ([float]($dpiY * $effScale)))

            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
            $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
            $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

            switch ($Background) {
                'White' { $g.Clear([System.Drawing.Color]::White) }
                'Black' { $g.Clear([System.Drawing.Color]::Black) }
                default { $g.Clear([System.Drawing.Color]::Transparent) }
            }

            $destRect = New-Object System.Drawing.Rectangle $Padding, $Padding, $targetW, $targetH
            $g.DrawImage($mf, $destRect, $bounds.X, $bounds.Y, $origW, $origH, [System.Drawing.GraphicsUnit]::Pixel)
            $g.Dispose()
            $mf.Dispose()
            $ms.Dispose()

            if ($KeyOutWhite -and $Background -eq 'Transparent') {
                $bmp.MakeTransparent([System.Drawing.Color]::White)
            }

            $fileInfo = Get-Item -Path $file
            $destDir = if ($OutputDir) { $OutputDir } else { $fileInfo.DirectoryName }
            if (-not (Test-Path -Path $destDir)) {
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            }
            $outFile = Join-Path $destDir ($fileInfo.BaseName + ".png")
            $bmp.Save($outFile, [System.Drawing.Imaging.ImageFormat]::Png)
            $bmp.Dispose()
            $successCount++
        } catch {
            Write-Error "Gagal memproses $file : $_"
        }
    }
}

if ($processedCount -eq 0 -or $successCount -eq 0) { exit 1 }
"""


def set_windows_identity() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def resolve_resource(rel_path: str) -> Path:
    candidates = [
        RESOURCE_DIR / rel_path,
        BASE_DIR / rel_path,
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def get_wmf_engine_path() -> Path:
    temp_dir = Path(tempfile.gettempdir()) / "BJ_PNG"
    temp_dir.mkdir(parents=True, exist_ok=True)
    engine_file = temp_dir / "ConvertWmfToPng_Engine.ps1"
    if not engine_file.exists() or engine_file.read_text(encoding="utf-8") != EMBEDDED_WMF_PS_SCRIPT:
        engine_file.write_text(EMBEDDED_WMF_PS_SCRIPT, encoding="utf-8")
    return engine_file


def get_prefs_path() -> Path:
    local_app = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    cfg_dir = local_app / "OceanPNG"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "prefs.json"


_FONT_INDEX_CACHE: dict[str, Path] | None = None
_FONT_B64_CACHE: dict[str, str] = {}


def _build_windows_font_index() -> dict[str, Path]:
    global _FONT_INDEX_CACHE
    if _FONT_INDEX_CACHE is not None:
        return _FONT_INDEX_CACHE

    index: dict[str, Path] = {}
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        ) as key:
            count = winreg.QueryInfoKey(key)[1]
            for idx in range(count):
                name, file_val, _ = winreg.EnumValue(key, idx)
                p = Path(str(file_val))
                if not p.is_absolute():
                    p = fonts_dir / p
                if p.suffix.lower() not in {".ttf", ".otf", ".ttc"} or not p.exists():
                    continue
                clean = re.sub(r"\s*\((TrueType|OpenType|All Res)\)\s*$", "", str(name), flags=re.I).strip()
                for part in clean.split("&"):
                    fam = part.strip().lower()
                    if fam and fam not in index:
                        index[fam] = p
    except Exception:
        pass
    _FONT_INDEX_CACHE = index
    return index


def _lookup_font_bytes(names: list[str]) -> dict[str, str]:
    index = _build_windows_font_index()
    shx_fallbacks = {
        "simplex": ["isocpeur", "consolas", "arial"],
        "romans": ["isocpeur", "times new roman", "arial"],
        "isocp": ["isocpeur", "arial"],
        "txt": ["consolas", "arial"],
        "system": ["arial", "tahoma", "segoe ui"],
    }
    result: dict[str, str] = {}

    for raw_name in names[:12]:
        key = raw_name.strip().lower()
        if not key or key in result:
            continue
        candidates = [key]
        for shx, alts in shx_fallbacks.items():
            if shx in key:
                candidates.extend(alts)
        candidates.extend(["arial", "segoe ui"])

        match: Path | None = None
        for cand in candidates:
            m = index.get(cand)
            if not m:
                for k, p in index.items():
                    if k.startswith(cand):
                        m = p
                        break
            if m:
                match = m
                break

        if match:
            cache_key = str(match).lower()
            if cache_key not in _FONT_B64_CACHE:
                try:
                    # Skip oversized >15MB CJK TTC collections unless directly requested
                    if match.stat().st_size <= 15 * 1024 * 1024:
                        _FONT_B64_CACHE[cache_key] = base64.b64encode(match.read_bytes()).decode("ascii")
                    else:
                        _FONT_B64_CACHE[cache_key] = ""
                except Exception:
                    _FONT_B64_CACHE[cache_key] = ""
            if _FONT_B64_CACHE[cache_key]:
                result[key] = _FONT_B64_CACHE[cache_key]
    return result


def parse_page_numbers(page_str: str, total_pages: int) -> list[int]:
    cleaned = (page_str or "").strip().lower()
    if not cleaned or cleaned in {"all", "semua", "*"}:
        return list(range(total_pages))

    pages: set[int] = set()
    for part in (p.strip() for p in cleaned.split(",") if p.strip()):
        if "-" in part:
            sub = part.split("-", 1)
            try:
                start = max(1, int(sub[0].strip()))
                end = min(total_pages, int(sub[1].strip()))
                if start <= end:
                    pages.update(range(start - 1, end))
            except ValueError:
                pass
        else:
            try:
                val = int(part)
                if 1 <= val <= total_pages:
                    pages.add(val - 1)
            except ValueError:
                pass
    return sorted(pages) if pages else list(range(total_pages))


def scan_entries(paths: list[str], recursive: bool) -> dict[str, Any]:
    collected: list[Path] = []
    folder_paths: list[Path] = []
    seen: set[str] = set()

    for raw in paths:
        p = Path(raw)
        if not p.exists():
            continue
        if p.is_dir():
            folder_paths.append(p)
            it = p.rglob("*") if recursive else p.iterdir()
            for child in it:
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTS:
                    key = str(child.resolve()).lower()
                    if key not in seen:
                        seen.add(key)
                        collected.append(child)
        elif p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key)
                collected.append(p)

    collected.sort(key=lambda x: str(x).lower())

    mode = "folder" if len(folder_paths) == 1 and len(paths) == 1 else "files"
    base_dir = folder_paths[0] if mode == "folder" else (collected[0].parent if collected else Path(paths[0]).parent)

    entries = []
    for idx, f in enumerate(collected, start=1):
        try:
            rel = str(f.relative_to(base_dir)) if mode == "folder" else f.name
        except ValueError:
            rel = f.name
        entries.append(
            {
                "id": f"row-{idx}",
                "fullPath": str(f),
                "relPath": rel,
                "format": f.suffix.lstrip(".").upper(),
            }
        )

    if mode == "folder":
        display_path = str(base_dir)
    elif len(collected) == 1:
        display_path = str(collected[0])
    elif len(collected) > 1:
        display_path = f"{len(collected)} file dipilih ({base_dir})"
    else:
        display_path = str(paths[0]) if paths else ""

    return {
        "mode": mode,
        "folderPath": str(base_dir) if mode == "folder" else "",
        "displayPath": display_path,
        "suggestedOutputDir": str(base_dir),
        "entries": entries,
    }


class ConverterApi:
    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._cancel_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._wmf_jobs: dict[str, dict[str, Any]] = {}
        self._wmf_events: dict[str, threading.Event] = {}

    def attach_window(self, window: webview.Window) -> None:
        self._window = window

    def _emit_js(self, fn_name: str, payload: dict[str, Any]) -> None:
        if not self._window:
            return
        encoded = json.dumps(payload, ensure_ascii=False)
        try:
            self._window.evaluate_js(f"window.{fn_name}({encoded})")
        except Exception:
            pass

    def resolve_fonts_b64(self, font_names: list[str]) -> dict[str, str]:
        return _lookup_font_bytes(font_names or [])

    def submit_wmf_job(self, task_id: str, payload: dict[str, Any]) -> bool:
        self._wmf_jobs[task_id] = payload
        ev = self._wmf_events.get(task_id)
        if ev:
            ev.set()
        return True

    def get_init_info(self) -> dict[str, Any]:
        pdf_ready = bool(pdfium and Image)
        if pdf_ready:
            ver = importlib.metadata.version("pypdfium2")
            engine_label = f"Engine: Vector WMF/EMF & PDFium {ver} siap"
        else:
            engine_label = "Engine: PDFium tidak tersedia"

        prefs: dict[str, Any] = {}
        prefs_path = get_prefs_path()
        if prefs_path.exists():
            try:
                prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            except Exception:
                prefs = {}

        return {
            "engineLabel": engine_label,
            "pdfReady": pdf_ready,
            "prefs": prefs,
        }

    def save_prefs(self, prefs: dict[str, Any]) -> bool:
        try:
            get_prefs_path().write_text(json.dumps(prefs, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def select_files(self) -> dict[str, Any] | None:
        if not self._window:
            return None
        try:
            file_types = (
                "File Didukung (*.wmf;*.emf;*.wmz;*.emz;*.pdf)",
                "Vektor WMF dan EMF (*.wmf;*.emf;*.wmz;*.emz)",
                "Dokumen PDF (*.pdf)",
                "Semua File (*.*)",
            )
            res = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(Path.home()),
                allow_multiple=True,
                file_types=file_types,
            )
            if not res:
                return None
            return scan_entries(list(res), recursive=False)
        except Exception as err:
            return {"error": str(err)}

    def select_folder(self, recursive: bool = True) -> dict[str, Any] | None:
        if not self._window:
            return None
        try:
            res = self._window.create_file_dialog(
                webview.FileDialog.FOLDER,
                directory=str(Path.home()),
            )
            if not res:
                return None
            return scan_entries([res[0]], recursive=bool(recursive))
        except Exception as err:
            return {"error": str(err)}

    def select_output_dir(self, current: str = "") -> dict[str, Any] | None:
        if not self._window:
            return None
        try:
            initial = current if current and Path(current).exists() else str(Path.home())
            res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=initial)
            if not res:
                return None
            return {"path": str(res[0])}
        except Exception as err:
            return {"error": str(err)}

    def resolve_paths(self, paths: list[str], recursive: bool = True) -> dict[str, Any]:
        return scan_entries(paths, recursive=bool(recursive))

    def open_path(self, target: str) -> dict[str, str]:
        p = Path(target)
        if not p.exists():
            return {"error": f"Path tidak ditemukan: {target}"}
        try:
            os.startfile(str(p))
            return {"ok": "1"}
        except Exception as err:
            return {"error": str(err)}

    def cancel_conversion(self) -> bool:
        self._cancel_event.set()
        return True

    def start_conversion(self, config: dict[str, Any]) -> bool:
        if self._worker_thread and self._worker_thread.is_alive():
            return False
        self._cancel_event.clear()
        self._worker_thread = threading.Thread(
            target=self._run_batch,
            args=(config,),
            daemon=True,
        )
        self._worker_thread.start()
        return True

    def _key_out_solid_white(self, img: "Image.Image") -> "Image.Image":
        rgba = img.convert("RGBA")
        r, g, b, a = rgba.split()
        # Pure/near-white (#FDFDFD..#FFFFFF) becomes transparent in C speed
        min_rgb = ImageChops.darker(r, ImageChops.darker(g, b))
        non_white_mask = min_rgb.point(lambda v: 0 if v >= 253 else 255)
        rgba.putalpha(ImageChops.darker(a, non_white_mask))
        return rgba

    def _render_vector_pdf_bytes_to_png(
        self,
        pdf_bytes: bytes,
        out_png: Path,
        scale: float,
        bg: str,
        key_out_white: bool,
    ) -> tuple[bool, str]:
        if not pdfium or not Image:
            return False, "Backend pypdfium2/Pillow tidak tersedia"

        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            page = doc.get_page(0)
            w_pt, h_pt = page.get_size()
            render_scale = scale * (96.0 / 72.0)
            max_px = 10000.0
            est_w = w_pt * render_scale
            est_h = h_pt * render_scale
            if est_w > max_px or est_h > max_px:
                render_scale *= min(max_px / est_w, max_px / est_h)

            if bg == "White":
                fill_color = (255, 255, 255, 255)
            elif bg == "Black":
                fill_color = (0, 0, 0, 255)
            else:
                fill_color = (0, 0, 0, 0)

            bmp = page.render(scale=render_scale, fill_color=fill_color)
            img = bmp.to_pil()
        finally:
            doc.close()

        if key_out_white and bg == "Transparent":
            img = self._key_out_solid_white(img)

        dpi_val = max(72, int(round(96 * scale)))
        img.save(out_png, "PNG", dpi=(dpi_val, dpi_val), compress_level=2)
        return True, f"{scale:g}x {bg} ({img.width}x{img.height}) -> {out_png.name}"

    def _convert_wmf(
        self,
        src: Path,
        dest_dir: Path,
        scale: float,
        bg: str,
        key_out_white: bool,
        engine_script: Path,
    ) -> tuple[bool, str, str]:
        out_png = dest_dir / f"{src.stem}.png"

        # Primary engine: emf-converter vector PDF (identical to BJ PDF, zero missing lines) -> PDFium PNG
        if self._window is not None:
            task_id = uuid.uuid4().hex
            ev = threading.Event()
            self._wmf_events[task_id] = ev
            try:
                raw_b64 = base64.b64encode(src.read_bytes()).decode("ascii")
                self._window.evaluate_js(
                    f"window.__renderWmfToPdf({json.dumps(task_id)}, {json.dumps(raw_b64)})"
                )
                if not ev.wait(timeout=90.0):
                    return False, "Timeout merender vektor WMF/EMF", ""
                job = self._wmf_jobs.pop(task_id, None) or {}
                if not job.get("ok"):
                    return False, str(job.get("error") or "Gagal merender vektor WMF/EMF"), ""
                pdf_bytes = base64.b64decode(job["pdfB64"])
                ok, msg = self._render_vector_pdf_bytes_to_png(
                    pdf_bytes, out_png, scale, bg, key_out_white
                )
                return ok, msg, str(out_png) if ok else ""
            finally:
                self._wmf_events.pop(task_id, None)
                self._wmf_jobs.pop(task_id, None)

        # Headless fallback when running without WebView2 window
        ps_args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(engine_script),
            "-Path",
            str(src),
            "-Scale",
            str(scale),
            "-Background",
            bg,
            "-OutputDir",
            str(dest_dir),
        ]
        if key_out_white and bg == "Transparent":
            ps_args.append("-KeyOutWhite")

        res = subprocess.run(
            ps_args,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if res.returncode == 0 and out_png.exists():
            return True, f"{scale:g}x {bg} -> {out_png.name}", str(out_png)
        err_msg = (res.stderr or res.stdout or "Gagal render GDI+").strip().splitlines()
        return False, err_msg[-1] if err_msg else "Gagal render WMF/EMF", ""

    def _convert_pdf(
        self,
        src: Path,
        base_dest: Path,
        dpi: int,
        page_str: str,
        zip_output: bool,
        row_id: str = "",
        counts: dict[str, int] | None = None,
    ) -> tuple[bool, str, str]:
        if not pdfium or not Image:
            return False, "Backend pypdfium2/Pillow tidak tersedia", ""

        safe_stem = re.sub(r"[^\w\-_.]", "_", src.stem)
        out_folder = base_dest / f"{safe_stem}_PNG_{dpi}DPI"
        out_folder.mkdir(parents=True, exist_ok=True)

        workers = min(4, max(2, (os.cpu_count() or 4) // 2))
        generated: list[Path] = []
        doc = pdfium.PdfDocument(str(src))
        try:
            total_pages = len(doc)
            target_pages = parse_page_numbers(page_str, total_pages)
            total_target = len(target_pages)
            scale = dpi / 72.0

            def _save_page(img_obj: "Image.Image", out_path: Path) -> Path:
                img_obj.save(out_path, "PNG", dpi=(dpi, dpi), compress_level=2)
                return out_path

            inflight = set()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for step, p_idx in enumerate(target_pages, start=1):
                    if self._cancel_event.is_set():
                        break
                    page = doc.get_page(p_idx)
                    bmp = page.render(scale=scale)
                    img = bmp.to_pil()
                    png_file = out_folder / f"{safe_stem}_page_{p_idx + 1:04d}.png"
                    fut = pool.submit(_save_page, img, png_file)
                    inflight.add(fut)
                    generated.append(png_file)

                    if row_id and counts is not None and (step == 1 or step % 3 == 0 or step == total_target):
                        self._emit_js(
                            "__onRowUpdate",
                            {
                                "id": row_id,
                                "status": "processing",
                                "durationMs": None,
                                "detail": f"Render halaman {step}/{total_target} ({dpi} DPI)...",
                                "openTarget": "",
                                "counts": counts,
                            },
                        )

                    if len(inflight) >= workers * 2:
                        done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
                        for d in done:
                            d.result()

                for d in inflight:
                    d.result()
        finally:
            doc.close()

        if self._cancel_event.is_set():
            return False, f"Dibatalkan ({len(generated)} halaman tersimpan)", str(out_folder)

        if zip_output and generated:
            zip_path = out_folder.parent / f"{safe_stem}_PNG_{dpi}DPI.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
                for png in generated:
                    zf.write(png, arcname=png.name)
            return True, f"{len(generated)} hal @ {dpi} DPI + ZIP -> {out_folder.name}/", str(out_folder)

        return True, f"{len(generated)} hal @ {dpi} DPI -> {out_folder.name}/", str(out_folder)

    def _run_batch(self, config: dict[str, Any]) -> None:
        entries: list[dict[str, str]] = config.get("entries", [])
        custom_out = (config.get("outputDir") or "").strip()
        wmf_scale = float(config.get("wmfScale") or 3.0)
        wmf_bg = str(config.get("wmfBg") or "Transparent")
        key_out_white = bool(config.get("keyOutWhite", False))
        pdf_dpi = int(config.get("pdfDpi") or 300)
        pdf_pages = str(config.get("pdfPages") or "All")
        zip_output = bool(config.get("zipOutput", False))

        total = len(entries)
        counts = {"total": total, "ok": 0, "skip": 0, "error": 0}
        t0 = time.perf_counter()
        last_output_dir = ""
        engine_script = get_wmf_engine_path()

        for idx, item in enumerate(entries, start=1):
            if self._cancel_event.is_set():
                counts["skip"] += 1
                self._emit_js(
                    "__onRowUpdate",
                    {
                        "id": item["id"],
                        "status": "skip",
                        "durationMs": None,
                        "detail": "Dibatalkan oleh pengguna",
                        "openTarget": "",
                        "counts": counts,
                    },
                )
                continue

            src = Path(item["fullPath"])
            fmt = item["format"].upper()

            self._emit_js(
                "__onRowUpdate",
                {
                    "id": item["id"],
                    "status": "processing",
                    "durationMs": None,
                    "detail": f"Mengonversi {src.name}...",
                    "openTarget": "",
                    "counts": counts,
                },
            )
            self._emit_js(
                "__onBatchProgress",
                {
                    "done": idx - 1,
                    "total": total,
                    "etaMs": None,
                    "phaseText": f"Memproses ({idx}/{total}): {item['relPath']}",
                },
            )

            item_t0 = time.perf_counter()
            try:
                if not src.exists():
                    raise FileNotFoundError(f"File tidak ditemukan: {src}")

                dest_dir = Path(custom_out).resolve() if custom_out else src.parent
                dest_dir.mkdir(parents=True, exist_ok=True)
                last_output_dir = str(dest_dir)

                if fmt in {"WMF", "EMF", "WMZ", "EMZ"}:
                    ok, detail, open_target = self._convert_wmf(
                        src, dest_dir, wmf_scale, wmf_bg, key_out_white, engine_script
                    )
                elif fmt == "PDF":
                    ok, detail, open_target = self._convert_pdf(
                        src, dest_dir, pdf_dpi, pdf_pages, zip_output, row_id=item["id"], counts=counts
                    )
                    if open_target:
                        last_output_dir = open_target
                else:
                    ok, detail, open_target = False, f"Format tidak didukung: {fmt}", ""

                dur_ms = int((time.perf_counter() - item_t0) * 1000)
                if self._cancel_event.is_set() and not ok:
                    counts["skip"] += 1
                    status = "skip"
                elif ok:
                    counts["ok"] += 1
                    status = "ok"
                else:
                    counts["error"] += 1
                    status = "error"

                self._emit_js(
                    "__onRowUpdate",
                    {
                        "id": item["id"],
                        "status": status,
                        "durationMs": dur_ms,
                        "detail": detail,
                        "openTarget": open_target,
                        "counts": counts,
                    },
                )
            except Exception as err:
                dur_ms = int((time.perf_counter() - item_t0) * 1000)
                counts["error"] += 1
                self._emit_js(
                    "__onRowUpdate",
                    {
                        "id": item["id"],
                        "status": "error",
                        "durationMs": dur_ms,
                        "detail": str(err),
                        "openTarget": "",
                        "counts": counts,
                    },
                )

            elapsed_ms = (time.perf_counter() - t0) * 1000
            avg_ms = elapsed_ms / idx
            eta_ms = avg_ms * (total - idx)
            self._emit_js(
                "__onBatchProgress",
                {
                    "done": idx,
                    "total": total,
                    "etaMs": eta_ms,
                    "phaseText": f"Memproses ({idx}/{total}): {item['relPath']}",
                },
            )

        total_elapsed_ms = (time.perf_counter() - t0) * 1000
        self._emit_js(
            "__onBatchDone",
            {
                "done": total if not self._cancel_event.is_set() else counts["ok"] + counts["error"],
                "total": total,
                "elapsedMs": total_elapsed_ms,
                "cancelled": self._cancel_event.is_set(),
                "lastOutputDir": last_output_dir,
                "counts": counts,
            },
        )


def bind_drag_and_drop(window: webview.Window, api: ConverterApi) -> None:
    try:
        drop_zone = window.dom.get_element("#dropZone")
        if not drop_zone:
            return

        def on_drag_enter(_e):
            window.evaluate_js("window.__onDragState(true)")

        def on_drag_leave(_e):
            window.evaluate_js("window.__onDragState(false)")

        def on_drag_over(_e):
            pass

        def on_drop(e):
            files = (e or {}).get("dataTransfer", {}).get("files", [])
            paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
            if paths:
                encoded = json.dumps(paths, ensure_ascii=False)
                window.evaluate_js(f"window.__onDropPaths({encoded})")
            else:
                window.evaluate_js("window.__onDragState(false)")

        drop_zone.events.dragenter += DOMEventHandler(on_drag_enter, prevent_default=True)
        drop_zone.events.dragleave += DOMEventHandler(on_drag_leave, prevent_default=True)
        drop_zone.events.dragover += DOMEventHandler(on_drag_over, prevent_default=True, stop_propagation=True)
        drop_zone.events.drop += DOMEventHandler(on_drop, prevent_default=True, stop_propagation=True)
    except Exception:
        pass


def run_smoke_test() -> int:
    """Headless self-verification for UI assets, WMF GDI+, and PDFium conversion."""
    html_file = resolve_resource("bj_png_ui/index.html")
    css_file = resolve_resource("bj_png_ui/styles.css")
    js_file = resolve_resource("bj_png_ui/app.js")
    assert html_file.exists() and css_file.exists() and js_file.exists(), "UI assets missing"

    api = ConverterApi()
    init = api.get_init_info()
    assert init["pdfReady"], f"PDF backend not ready: {init}"

    tmp = Path(tempfile.gettempdir()) / "BJ_PNG_SmokeTest"
    tmp.mkdir(parents=True, exist_ok=True)
    sample_pdf = tmp / "smoke.pdf"
    img = Image.new("RGB", (180, 120), color=(0, 95, 184))
    img.save(sample_pdf, format="PDF")

    scanned = scan_entries([str(sample_pdf)], recursive=False)
    assert len(scanned["entries"]) == 1 and scanned["entries"][0]["format"] == "PDF"

    ok, detail, out_folder = api._convert_pdf(sample_pdf, tmp / "out", 300, "All", True)
    assert ok, f"PDF smoke failed: {detail}"
    pngs = list(Path(out_folder).glob("*.png"))
    zips = list((tmp / "out").glob("*.zip"))
    assert len(pngs) == 1 and len(zips) == 1, f"Expected 1 PNG and 1 ZIP, got {pngs}, {zips}"

    engine = get_wmf_engine_path()
    assert engine.exists() and engine.stat().st_size > 500, "WMF engine missing"

    print(
        json.dumps(
            {
                "smoke": "PASS",
                "engineLabel": init["engineLabel"],
                "pdfPngCount": len(pngs),
                "zipCount": len(zips),
                "wmfEngineBytes": engine.stat().st_size,
            }
        )
    )
    return 0


def main() -> None:
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_test())

    set_windows_identity()
    api = ConverterApi()
    html_path = resolve_resource("bj_png_ui/index.html")
    icon_path = resolve_resource("assets/ocean_png.ico")

    window = webview.create_window(
        APP_TITLE,
        url=html_path.as_uri(),
        js_api=api,
        width=900,
        height=640,
        min_size=(780, 540),
        background_color="#F3F3F3",
        text_select=True,
    )
    api.attach_window(window)

    def on_loaded():
        bind_drag_and_drop(window, api)

    webview.start(
        on_loaded,
        icon=str(icon_path) if icon_path.exists() else None,
        debug=False,
    )


if __name__ == "__main__":
    main()
