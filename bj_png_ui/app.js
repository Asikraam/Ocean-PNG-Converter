(() => {
  const dropZone = document.getElementById('dropZone');
  const inputPathEl = document.getElementById('inputPath');
  const outputDirEl = document.getElementById('outputDir');
  const browseFilesBtn = document.getElementById('browseFilesBtn');
  const browseFolderBtn = document.getElementById('browseFolderBtn');
  const browseOutputBtn = document.getElementById('browseOutputBtn');

  const wmfOptGroup = document.getElementById('wmfOptGroup');
  const pdfOptGroup = document.getElementById('pdfOptGroup');
  const wmfScaleSelect = document.getElementById('wmfScaleSelect');
  const wmfBgSelect = document.getElementById('wmfBgSelect');
  const keyOutWhiteCheck = document.getElementById('keyOutWhiteCheck');
  const pdfDpiSelect = document.getElementById('pdfDpiSelect');
  const pdfPagesInput = document.getElementById('pdfPagesInput');
  const zipCheck = document.getElementById('zipCheck');
  const recursiveCheck = document.getElementById('recursiveCheck');

  const startBtn = document.getElementById('startBtn');
  const cancelBtn = document.getElementById('cancelBtn');
  const openOutputBtn = document.getElementById('openOutputBtn');

  const engineStatusText = document.getElementById('engineStatusText');
  const statTotal = document.getElementById('statTotal');
  const statOk = document.getElementById('statOk');
  const statSkip = document.getElementById('statSkip');
  const statError = document.getElementById('statError');

  const queueBody = document.getElementById('queueBody');
  const filterTabs = Array.from(document.querySelectorAll('.filter-tab'));

  const progressTrack = document.getElementById('progressTrack');
  const progressBar = document.getElementById('progressBar');
  const phaseText = document.getElementById('phaseText');
  const progressMeta = document.getElementById('progressMeta');

  let isRunning = false;
  let activeFilter = 'all';
  let selectionMode = 'files'; // 'folder' | 'files'
  let currentFolderPath = '';
  let lastOutputDir = '';

  const queueOrder = [];
  const queueMap = new Map();
  const fontCache = new Map();

  function formatEta(ms) {
    if (ms === null || ms === undefined || ms < 0) return '-';
    const totalSec = Math.ceil(ms / 1000);
    if (totalSec < 60) return `~${totalSec} dtk`;
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    return `~${min} mnt ${sec} dtk`;
  }

  function formatStatusLabel(status) {
    switch (status) {
      case 'waiting':
        return 'Siap';
      case 'processing':
        return 'Proses...';
      case 'ok':
        return 'Berhasil';
      case 'skip':
        return 'Dilewati';
      case 'error':
        return 'Gagal';
      default:
        return status;
    }
  }

  function matchesFilter(status) {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'ok') return status === 'ok';
    if (activeFilter === 'warn') return status === 'skip';
    if (activeFilter === 'error') return status === 'error';
    return true;
  }

  function setPhase(text, isError = false) {
    phaseText.textContent = text;
    phaseText.classList.toggle('is-error', isError);
  }

  function updateCounters(counts) {
    const c = counts || { total: queueOrder.length, ok: 0, skip: 0, error: 0 };
    statTotal.textContent = String(c.total);
    statOk.textContent = String(c.ok);
    statSkip.textContent = String(c.skip);
    statError.textContent = String(c.error);
  }

  function updateOptionGroupEmphasis() {
    if (queueOrder.length === 0) {
      wmfOptGroup.classList.remove('is-muted');
      pdfOptGroup.classList.remove('is-muted');
      return;
    }
    const hasWmf = queueOrder.some((r) => ['WMF', 'EMF', 'WMZ', 'EMZ'].includes(r.format));
    const hasPdf = queueOrder.some((r) => r.format === 'PDF');
    wmfOptGroup.classList.toggle('is-muted', !hasWmf);
    pdfOptGroup.classList.toggle('is-muted', !hasPdf);
  }

  function setRunningState(running) {
    isRunning = running;
    browseFilesBtn.disabled = running;
    browseFolderBtn.disabled = running;
    browseOutputBtn.disabled = running;
    outputDirEl.disabled = running;
    wmfScaleSelect.disabled = running;
    wmfBgSelect.disabled = running;
    keyOutWhiteCheck.disabled = running;
    pdfDpiSelect.disabled = running;
    pdfPagesInput.disabled = running;
    zipCheck.disabled = running;
    recursiveCheck.disabled = running;
    startBtn.disabled = running || queueOrder.length === 0;
    cancelBtn.disabled = !running;
    openOutputBtn.disabled = running || !lastOutputDir;
  }

  async function openRowOutput(row) {
    if (!row.openTarget) return;
    setPhase(`Membuka hasil: ${row.relPath}...`);
    const res = await window.pywebview.api.open_path(row.openTarget);
    if (res && res.error) {
      setPhase(`Gagal membuka hasil: ${res.error}`, true);
    }
  }

  function updateRowCells(row) {
    if (!row.tr) return;
    const cells = row.tr.cells;
    cells[1].textContent = row.format;

    const badge = cells[2].firstElementChild;
    badge.className = `status-badge status-${row.status}`;
    badge.textContent = formatStatusLabel(row.status);

    cells[3].textContent =
      typeof row.durationMs === 'number' ? `${row.durationMs} ms` : '-';
    cells[4].textContent = row.detail;
    cells[4].title = row.detail;

    const canOpen = Boolean(row.openTarget);
    row.tr.classList.toggle('clickable-row', canOpen);
    if (canOpen) {
      row.tr.tabIndex = 0;
      row.tr.title = `Klik 2x atau tekan Enter untuk membuka ${row.openTarget}`;
    } else {
      row.tr.removeAttribute('tabindex');
      row.tr.title = '';
    }
    row.tr.classList.toggle('hidden', !matchesFilter(row.status));
  }

  function buildRowElement(row) {
    const tr = document.createElement('tr');
    tr.addEventListener('dblclick', () => {
      void openRowOutput(row);
    });
    tr.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        void openRowOutput(row);
      }
    });

    const tdName = document.createElement('td');
    tdName.className = 'cell-mono';
    tdName.textContent = row.relPath;
    tdName.title = row.fullPath;

    const tdType = document.createElement('td');
    tdType.className = 'cell-mono';

    const tdStatus = document.createElement('td');
    const badge = document.createElement('span');
    tdStatus.appendChild(badge);

    const tdDur = document.createElement('td');
    tdDur.className = 'cell-mono cell-dur';

    const tdDetail = document.createElement('td');
    tdDetail.className = 'cell-mono';

    tr.append(tdName, tdType, tdStatus, tdDur, tdDetail);
    row.tr = tr;
    updateRowCells(row);
    return tr;
  }

  function renderEmptyRow(messageHtml) {
    queueBody.innerHTML = '';
    const tr = document.createElement('tr');
    tr.className = 'empty-row';
    const td = document.createElement('td');
    td.colSpan = 5;
    td.innerHTML = messageHtml;
    tr.appendChild(td);
    queueBody.appendChild(tr);
  }

  function applyFilterVisibility() {
    let visibleCount = 0;
    for (const row of queueOrder) {
      if (!row.tr) continue;
      const show = matchesFilter(row.status);
      row.tr.classList.toggle('hidden', !show);
      if (show) visibleCount += 1;
    }
    const existingEmpty = queueBody.querySelector('.empty-filter-row');
    if (existingEmpty) existingEmpty.remove();
    if (queueOrder.length > 0 && visibleCount === 0) {
      const tr = document.createElement('tr');
      tr.className = 'empty-row empty-filter-row';
      const td = document.createElement('td');
      td.colSpan = 5;
      td.textContent = 'Tidak ada item pada filter status ini.';
      tr.appendChild(td);
      queueBody.appendChild(tr);
    }
  }

  function loadEntries(res) {
    if (!res) return;
    queueOrder.length = 0;
    queueMap.clear();
    queueBody.innerHTML = '';

    selectionMode = res.mode || 'files';
    currentFolderPath = res.folderPath || '';
    inputPathEl.value = res.displayPath || '';
    if (res.suggestedOutputDir && !outputDirEl.value.trim()) {
      outputDirEl.placeholder = `Otomatis di folder asal (${res.suggestedOutputDir})`;
    }

    const entries = res.entries || [];
    if (entries.length === 0) {
      renderEmptyRow('Tidak ditemukan file <code>.wmf</code>, <code>.emf</code>, atau <code>.pdf</code> di sumber yang dipilih.');
      updateCounters({ total: 0, ok: 0, skip: 0, error: 0 });
      updateOptionGroupEmphasis();
      startBtn.disabled = true;
      setPhase('Tidak ada file didukung yang ditemukan.');
      return;
    }

    const frag = document.createDocumentFragment();
    for (const item of entries) {
      const model = {
        id: item.id,
        fullPath: item.fullPath,
        relPath: item.relPath,
        format: item.format,
        status: 'waiting',
        durationMs: undefined,
        detail: 'Menunggu proses',
        openTarget: '',
        tr: null,
      };
      queueOrder.push(model);
      queueMap.set(model.id, model);
      frag.appendChild(buildRowElement(model));
    }
    queueBody.appendChild(frag);
    updateCounters({ total: queueOrder.length, ok: 0, skip: 0, error: 0 });
    updateOptionGroupEmphasis();
    progressBar.style.width = '0%';
    progressTrack.setAttribute('aria-valuenow', '0');
    progressMeta.textContent = `0 / ${queueOrder.length} (0%) | Sisa waktu: -`;
    startBtn.disabled = false;
    setPhase(`Siap mengonversi ${queueOrder.length} file.`);
  }

  function saveCurrentPrefs() {
    if (!window.pywebview || !window.pywebview.api) return;
    void window.pywebview.api.save_prefs({
      outputDir: outputDirEl.value.trim(),
      wmfScale: wmfScaleSelect.value,
      wmfBg: wmfBgSelect.value,
      keyOutWhite: keyOutWhiteCheck.checked,
      pdfDpi: pdfDpiSelect.value,
      pdfPages: pdfPagesInput.value.trim() || 'All',
      zipOutput: zipCheck.checked,
      recursive: recursiveCheck.checked,
      lastFolder: currentFolderPath,
    });
  }

  // Callbacks invoked by Python backend
  window.__onRowUpdate = (payload) => {
    const row = queueMap.get(payload.id);
    if (!row) return;
    row.status = payload.status;
    row.durationMs = payload.durationMs;
    row.detail = payload.detail;
    row.openTarget = payload.openTarget || '';
    updateRowCells(row);
    if (payload.counts) {
      updateCounters(payload.counts);
    }
    if (row.status === 'processing' && row.tr && !row.tr.classList.contains('hidden')) {
      row.tr.scrollIntoView({ block: 'nearest' });
    }
  };

  window.__onBatchProgress = (p) => {
    const pct = p.total > 0 ? Math.min(100, Math.round((p.done / p.total) * 100)) : 0;
    progressBar.style.width = `${pct}%`;
    progressTrack.setAttribute('aria-valuenow', String(pct));
    progressMeta.textContent = `${p.done} / ${p.total} (${pct}%) | Sisa waktu: ${formatEta(p.etaMs)}`;
    if (p.phaseText) {
      setPhase(p.phaseText);
    }
  };

  window.__onBatchDone = (summary) => {
    if (summary.lastOutputDir) {
      lastOutputDir = summary.lastOutputDir;
    }
    setRunningState(false);
    if (summary.counts) {
      updateCounters(summary.counts);
    }
    const pct = summary.total > 0 ? Math.min(100, Math.round((summary.done / summary.total) * 100)) : 0;
    progressBar.style.width = `${pct}%`;
    progressTrack.setAttribute('aria-valuenow', String(pct));
    progressMeta.textContent = `${summary.done} / ${summary.total} (${pct}%) | Selesai dalam ${(summary.elapsedMs / 1000).toFixed(2)} dtk`;

    if (summary.cancelled) {
      setPhase(`Dibatalkan pengguna (${summary.counts.ok} berhasil, ${summary.counts.skip} dilewati).`);
    } else if (summary.counts.error > 0) {
      setPhase(`Selesai dengan ${summary.counts.error} error. Klik tab Gagal untuk detail.`, true);
    } else {
      setPhase(`Selesai! ${summary.counts.ok} file berhasil dikonversi ke PNG.`);
    }
  };

  window.__onDropPaths = async (paths) => {
    if (isRunning || !paths || paths.length === 0) return;
    dropZone.classList.remove('drag-over');
    setPhase('Memindai file/folder yang ditarik...');
    const res = await window.pywebview.api.resolve_paths(paths, recursiveCheck.checked);
    loadEntries(res);
  };

  window.__onDragState = (active) => {
    if (isRunning) return;
    dropZone.classList.toggle('drag-over', Boolean(active));
  };

  // UI Event Bindings
  browseFilesBtn.addEventListener('click', async () => {
    try {
      const res = await window.pywebview.api.select_files();
      if (res && res.error) {
        setPhase(`Gagal memilih file: ${res.error}`, true);
        return;
      }
      loadEntries(res);
    } catch (err) {
      setPhase(`Gagal membuka dialog file: ${err}`, true);
    }
  });

  browseFolderBtn.addEventListener('click', async () => {
    try {
      const res = await window.pywebview.api.select_folder(recursiveCheck.checked);
      if (res && res.error) {
        setPhase(`Gagal memilih folder: ${res.error}`, true);
        return;
      }
      loadEntries(res);
    } catch (err) {
      setPhase(`Gagal membuka dialog folder: ${err}`, true);
    }
  });

  browseOutputBtn.addEventListener('click', async () => {
    try {
      const res = await window.pywebview.api.select_output_dir(outputDirEl.value.trim());
      if (res && res.error) {
        setPhase(`Gagal memilih folder tujuan: ${res.error}`, true);
        return;
      }
      if (res && res.path) {
        outputDirEl.value = res.path;
        saveCurrentPrefs();
      }
    } catch (err) {
      setPhase(`Gagal memilih folder tujuan: ${err}`, true);
    }
  });

  recursiveCheck.addEventListener('change', async () => {
    saveCurrentPrefs();
    if (selectionMode === 'folder' && currentFolderPath && !isRunning) {
      const res = await window.pywebview.api.resolve_paths([currentFolderPath], recursiveCheck.checked);
      loadEntries(res);
    }
  });

  [wmfScaleSelect, wmfBgSelect, keyOutWhiteCheck, pdfDpiSelect, pdfPagesInput, zipCheck, outputDirEl].forEach((el) => {
    el.addEventListener('change', saveCurrentPrefs);
  });

  filterTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      activeFilter = tab.dataset.filter || 'all';
      filterTabs.forEach((t) => {
        const isAct = t === tab;
        t.classList.toggle('active', isAct);
        t.setAttribute('aria-selected', isAct ? 'true' : 'false');
      });
      applyFilterVisibility();
    });
  });

  startBtn.addEventListener('click', async () => {
    if (isRunning || queueOrder.length === 0) return;
    saveCurrentPrefs();

    for (const row of queueOrder) {
      row.status = 'waiting';
      row.durationMs = undefined;
      row.detail = 'Menunggu proses';
      row.openTarget = '';
      updateRowCells(row);
    }
    updateCounters({ total: queueOrder.length, ok: 0, skip: 0, error: 0 });
    progressBar.style.width = '0%';
    progressTrack.setAttribute('aria-valuenow', '0');
    setRunningState(true);
    setPhase('Memulai konversi ke PNG...');

    await window.pywebview.api.start_conversion({
      entries: queueOrder.map((r) => ({ id: r.id, fullPath: r.fullPath, relPath: r.relPath, format: r.format })),
      outputDir: outputDirEl.value.trim(),
      wmfScale: parseFloat(wmfScaleSelect.value) || 4.0,
      wmfBg: wmfBgSelect.value,
      keyOutWhite: keyOutWhiteCheck.checked,
      pdfDpi: parseInt(pdfDpiSelect.value, 10) || 300,
      pdfPages: pdfPagesInput.value.trim() || 'All',
      zipOutput: zipCheck.checked,
    });
  });

  cancelBtn.addEventListener('click', async () => {
    if (!isRunning) return;
    cancelBtn.disabled = true;
    setPhase('Membatalkan proses...');
    await window.pywebview.api.cancel_conversion();
  });

  openOutputBtn.addEventListener('click', async () => {
    if (!lastOutputDir) return;
    const res = await window.pywebview.api.open_path(lastOutputDir);
    if (res && res.error) {
      setPhase(`Gagal membuka folder: ${res.error}`, true);
    }
  });

  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && isRunning) {
      ev.preventDefault();
      cancelBtn.click();
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'o' && !isRunning) {
      ev.preventDefault();
      browseFilesBtn.click();
    }
  });

  async function initApp() {
    try {
      const info = await window.pywebview.api.get_init_info();
      engineStatusText.textContent = info.engineLabel;
      engineStatusText.classList.add(info.pdfReady ? 'ready' : 'error');

      const prefs = info.prefs || {};
      if (prefs.outputDir) outputDirEl.value = prefs.outputDir;
      if (prefs.wmfScale) wmfScaleSelect.value = String(prefs.wmfScale);
      if (prefs.wmfBg) wmfBgSelect.value = prefs.wmfBg;
      if (typeof prefs.keyOutWhite === 'boolean') keyOutWhiteCheck.checked = prefs.keyOutWhite;
      if (prefs.pdfDpi) pdfDpiSelect.value = String(prefs.pdfDpi);
      if (prefs.pdfPages) pdfPagesInput.value = prefs.pdfPages;
      if (typeof prefs.zipOutput === 'boolean') zipCheck.checked = prefs.zipOutput;
      if (typeof prefs.recursive === 'boolean') recursiveCheck.checked = prefs.recursive;
    } catch (err) {
      engineStatusText.textContent = 'Engine: gagal memuat';
      engineStatusText.classList.add('error');
      setPhase(`Gagal inisialisasi: ${err}`, true);
    }
  }

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const len = bin.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = bin.charCodeAt(i);
    }
    return bytes;
  }

  function bytesToB64(bytes) {
    const chunk = 0x8000;
    let binary = '';
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  window.__renderWmfToPdf = async (taskId, wmfB64) => {
    try {
      if (!window.EmfConverter || !window.EmfConverter.convertMetafileToPdf) {
        throw new Error('EmfConverter JS engine belum termuat');
      }
      const bytes = b64ToBytes(wmfB64);
      const info = await window.EmfConverter.getMetafileInfo(bytes, { maxRecords: 1000000 });
      if (!info) {
        await window.pywebview.api.submit_wmf_job(taskId, {
          ok: false,
          error: 'File WMF/EMF tidak valid atau kosong',
        });
        return;
      }

      const fontNames = (info.fonts || []).map((f) => f.name).filter(Boolean);
      const missingNames = fontNames.filter((n) => !fontCache.has(n.toLowerCase()));
      if (missingNames.length > 0) {
        const fetchedMap = await window.pywebview.api.resolve_fonts_b64(missingNames);
        if (fetchedMap && typeof fetchedMap === 'object') {
          for (const [k, fb64] of Object.entries(fetchedMap)) {
            fontCache.set(k.toLowerCase(), fb64 ? b64ToBytes(fb64) : null);
          }
        }
        for (const n of missingNames) {
          if (!fontCache.has(n.toLowerCase())) fontCache.set(n.toLowerCase(), null);
        }
      }

      const fonts = [];
      const seenFontBufs = new Set();
      for (const n of fontNames) {
        const buf = fontCache.get(n.toLowerCase());
        if (buf && !seenFontBufs.has(buf)) {
          seenFontBufs.add(buf);
          fonts.push(buf);
        }
      }

      const pageWidthPt = Math.max(1, info.width * 0.75);
      const pageHeightPt = Math.max(1, info.height * 0.75);
      const pdfBytes = await window.EmfConverter.convertMetafileToPdf(bytes, {
        fonts,
        dpiScale: 2,
        maxCanvasDimension: 16384,
        maxRecords: 1000000,
        pageSize: { width: pageWidthPt, height: pageHeightPt },
        compress: false,
        gdiAntialias: true,
        exactRasterOps: true,
        imageResampling: 'renderer',
        fontSmoothing: 'cleartype',
      });

      if (!pdfBytes || pdfBytes.length === 0) {
        await window.pywebview.api.submit_wmf_job(taskId, {
          ok: false,
          error: 'Hasil konversi vektor kosong',
        });
        return;
      }

      await window.pywebview.api.submit_wmf_job(taskId, {
        ok: true,
        pdfB64: bytesToB64(pdfBytes),
        width: info.width,
        height: info.height,
      });
    } catch (err) {
      await window.pywebview.api.submit_wmf_job(taskId, {
        ok: false,
        error: err && err.message ? err.message : String(err),
      });
    }
  };

  window.addEventListener('pywebviewready', () => {
    void initApp();
  });
})();
