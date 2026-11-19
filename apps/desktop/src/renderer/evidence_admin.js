// evidence_admin.js: bandeja y expediente de evidencias.
const EVIDENCE_STATUS = {
  DRAFT: { label: 'Borrador', cls: 'badge-low' },
  SUBMITTED: { label: 'Enviado', cls: 'badge-inprogress' },
  UNDER_REVIEW: { label: 'En revisión', cls: 'badge-scheduled' },
  CORRECTION_REQUIRED: { label: 'Requiere corrección', cls: 'badge-pending' },
  RESUBMITTED: { label: 'Reenviado', cls: 'badge-inprogress' },
  APPROVED: { label: 'Aprobado', cls: 'badge-completed' },
  REJECTED: { label: 'Rechazado', cls: 'badge-cancelled' },
};
// Codigos de evento que emite el backend (app/evidence/service.py) -> texto en español.
const EVIDENCE_ACTIONS = {
  EVIDENCE_ADDED: 'Evidencia agregada', CHECKLIST_ITEM_ADDED: 'Ítem de checklist agregado', SIGNATURE_REGISTERED: 'Firma registrada',
  SIGNATURE_REFUSED: 'Firma rechazada por el cliente', SUBMIT: 'Enviado a revisión', EXPEDIENTE_SUBMITTED: 'Expediente enviado',
  RESUBMIT: 'Reenviado', EXPEDIENTE_RESUBMITTED: 'Expediente reenviado', REVIEW_STARTED: 'Revisión iniciada', ADMIN_REVIEW_STARTED: 'Revisión iniciada',
  EVIDENCE_REVIEWED: 'Evidencia revisada', REVIEW_DECISION: 'Decisión de revisión', CORRECTION_REQUESTED: 'Corrección solicitada',
  APPROVED: 'Aprobado', REJECTED: 'Rechazado',
};
const EVIDENCE_CATEGORIES = { BEFORE: 'Antes', DURING: 'Durante', AFTER: 'Después', ADDITIONAL: 'Adicional' };
const evLabel = (map, code) => map[code] || String(code || '').replace(/_/g, ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase());

// devuelve evidence status badge; sin efectos secundarios.
function evidenceStatusBadge(status) {
  const s = EVIDENCE_STATUS[status] || { label: status || '—', cls: 'badge-low' };
  return `<span class="${s.cls}">${escapeHtml(s.label)}</span>`;
}

const evFmtDate = (v) => (v ? new Date(v).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '');
const evFmtSize = (b) => (b ? (b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB') : '');

// openEvidencePreview(src, caption): visor ampliado de una fotografia (modal compartido).
function openEvidencePreview(src, caption) {
  sigosModal({
    title: caption || 'Evidencia',
    size: 'lg',
    body: `<div style="display:flex;justify-content:center;background:var(--c-surface-2);border-radius:var(--r-md);padding:8px"><img src="${src}" alt="${escapeHtml(caption || 'Evidencia')}" style="max-width:100%;max-height:70vh;object-fit:contain;border-radius:6px"></div>`,
  });
}

// ---------- Componentes compartidos: registro de evidencias, firma del técnico ----------

const EV_ICON = {
  back: '<path d="M15 18l-6-6 6-6"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
  file: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/>',
  note: '<path d="M4 4h16v12H8l-4 4z"/><path d="M8 9h8M8 12h5"/>',
  pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
  warning: '<path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  sort: '<path d="M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4"/>',
};
const evIcon = (name, size = 16) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${EV_ICON[name] || ''}</svg>`;

// evKind(e): tipo de registro según su archivo ('image' | 'file' | 'note').
function evKind(e) {
  const mime = String(e.mime_type || e.file_type || '');
  if (!(e.storage_key || e.stored_name || e.size_bytes)) return 'note';
  return mime.startsWith('image/') ? 'image' : 'file';
}
const EV_KIND_LABEL = { image: 'Fotografía', file: 'Documento', note: 'Observación' };

// evSignatureCell(e): estado de la firma histórica del técnico en un registro.
function evSignatureCell(e) {
  const sig = e.technician_signature;
  if (!sig) return '<span class="ev-muted">Sin firma</span>';
  return `<span class="ev-signed">${evIcon('pen', 14)} ${escapeHtml(sig.technician_username || 'Técnico')}</span>`;
}

// evidenceRecordsTable(evs): listado de evidencias de una orden, sin imágenes. Cada fila abre el registro.
function evidenceRecordsTable(evs) {
  if (!evs.length) {
    return '<div class="empty-state"><div class="empty-state__title">Sin evidencias</div><div class="empty-state__text">Esta orden todavía no tiene evidencias registradas.</div></div>';
  }
  return `<div class="ev-table-wrap"><table class="tbl ev-records">
    <thead><tr><th scope="col">Evidencia</th><th scope="col">Registro</th><th scope="col">Firma del técnico</th><th scope="col"><span class="sr-only">Acción</span></th></tr></thead>
    <tbody>${evs.map((e) => {
      const kind = evKind(e);
      return `<tr class="tbl-row" data-ev-record="${e.id}">
        <td class="ev-desc"><span class="ev-kind">${evIcon(kind)} <strong>${EV_KIND_LABEL[kind]} · ${escapeHtml(EVIDENCE_CATEGORIES[e.category] || e.category || '—')}</strong></span><span>${escapeHtml(e.description || e.original_name || 'Sin descripción')}</span></td>
        <td class="ev-stack"><span class="ev-num">${escapeHtml(evFmtDate(e.received_at || e.created_at))}</span><span>${escapeHtml(e.uploaded_by?.username || '—')}</span></td>
        <td>${evSignatureCell(e)}</td>
        <td style="text-align:right"><button type="button" class="sigos-btn-secondary sigos-btn-sm" data-ev-view="${e.id}">Ver</button></td>
      </tr>`;
    }).join('')}</tbody></table></div>`;
}

// bindEvidenceRecords(root, evs): abre el registro al pulsar la fila o «Ver».
function bindEvidenceRecords(root, evs) {
  const byId = new Map(evs.map((e) => [String(e.id), e]));
  root.querySelectorAll('[data-ev-record]').forEach((row) => row.addEventListener('click', (ev) => {
    const btn = ev.target instanceof Element ? ev.target.closest('[data-ev-view]') : null;
    const target = byId.get(btn ? btn.dataset.evView : row.dataset.evRecord);
    if (target) openEvidenceRecord(target, evs);
  }));
}

// openEvidenceRecord(e, list): ficha de una evidencia. La imagen y la firma se piden al abrirla, no antes.
// Con list, «Anterior» / «Siguiente» recorren las evidencias de la orden sin volver a la tabla.
function openEvidenceRecord(e, list = []) {
  const kind = evKind(e);
  const sig = e.technician_signature;
  const idx = list.findIndex((x) => x.id === e.id);
  const nav = list.length > 1 && idx >= 0
    ? `<span class="ev-muted ev-num">${idx + 1} de ${list.length}</span><span style="flex:1"></span><button type="button" class="sigos-btn-secondary" data-ev-nav="-1" ${idx === 0 ? 'disabled' : ''}>Anterior</button><button type="button" class="sigos-btn-secondary" data-ev-nav="1" ${idx === list.length - 1 ? 'disabled' : ''}>Siguiente</button>`
    : '';
  const m = sigosModal({
    footer: nav,
    title: `${EV_KIND_LABEL[kind]} · ${EVIDENCE_CATEGORIES[e.category] || e.category || 'Evidencia'}`,
    size: 'lg',
    body: `<div class="ev-record ${kind === 'note' ? 'ev-record--note' : ''}">
      ${kind === 'note' ? '' : `<div class="ev-preview" id="evPreview" aria-busy="true">${loaderBlock('Cargando archivo…', 260)}</div>`}
      <div class="ev-record__info">
      <dl class="ev-dl ev-dl--record">
        <dt>Descripción</dt><dd>${escapeHtml(e.description || '—')}</dd>
        ${kind === 'note' ? '' : `<dt>Archivo</dt><dd>${escapeHtml(e.original_name || '—')} <span class="ev-muted">${escapeHtml(evFmtSize(e.size_bytes))}</span></dd>`}
        <dt>Registrada</dt><dd class="ev-num">${escapeHtml(evFmtDate(e.received_at || e.created_at))}</dd>
        <dt>Responsable</dt><dd>${escapeHtml(e.uploaded_by?.username || '—')}</dd>
        <dt>Estado</dt><dd>${evidenceStatusBadge(e.status)}</dd>
      </dl>
      <section class="ev-record-sign" aria-labelledby="evSigTitle">
        <h4 id="evSigTitle">Firma del técnico</h4>
        ${sig ? `<div class="ev-sign-box" id="evSigBox" aria-busy="true">${SigosLoading.block('Cargando firma…', { height: 90, size: 'sm' })}</div>
          <p class="ev-sign-meta">${escapeHtml(sig.technician_username || 'Técnico')} · firmada el <span class="ev-num">${escapeHtml(evFmtDate(sig.signed_at))}</span>${sig.version ? ` · versión ${Number(sig.version)}` : ''}</p>`
        : '<p class="ev-muted" style="margin:0">Este registro no tiene firma del técnico: lo registró coordinación o es anterior a la firma obligatoria.</p>'}
      </section>
      </div></div>`,
  });
  m.card.querySelectorAll('[data-ev-nav]').forEach((b) => b.addEventListener('click', () => {
    const next = list[idx + Number(b.dataset.evNav)];
    if (next) { m.close(); openEvidenceRecord(next, list); }
  }));
  if (kind !== 'note') {
    downloadAuthed(`/api/v1/evidences/${e.id}/download`).then((r) => {
      const box = m.q('#evPreview');
      if (!box) return;
      box.removeAttribute('aria-busy');
      if (r.ok && r.data && String(r.contentType || '').startsWith('image/')) {
        box.innerHTML = `<img src="data:${r.contentType};base64,${r.data}" alt="${escapeHtml(e.description || EVIDENCE_CATEGORIES[e.category] || 'Evidencia')}">`;
      } else if (r.ok) {
        box.innerHTML = `<div class="ev-preview__empty">${evIcon('file', 20)} Vista previa no disponible para este tipo de archivo.</div>`;
      } else {
        box.innerHTML = `<div class="ev-preview__empty" role="alert">${evIcon('warning', 20)} No se pudo cargar el archivo${r.status === 404 ? ': no está en el almacenamiento' : ''}.</div>`;
      }
    });
  }
  if (sig) {
    downloadAuthed(`/api/v1/evidences/${e.id}/technician-signature`).then((r) => {
      const box = m.q('#evSigBox');
      if (!box) return;
      box.removeAttribute('aria-busy');
      box.innerHTML = r.ok && r.data
        ? `<img src="data:image/png;base64,${r.data}" alt="Firma de ${escapeHtml(sig.technician_username || 'técnico')}">`
        : `<div class="ev-preview__empty" role="alert">${evIcon('warning', 18)} ${r.status === 409 ? 'La firma no coincide con la registrada. Avise al administrador.' : 'No se pudo cargar la firma.'}</div>`;
    });
  }
}

// bindSignaturePad(canvas): recuadro de firma con ratón, lápiz o táctil. Devuelve { isEmpty, clear, toDataURL }.
function bindSignaturePad(canvas) {
  const ctx = canvas.getContext('2d');
  const ink = () => { ctx.lineWidth = 2.4; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#1B2430'; };
  ink();
  let drawing = false;
  let strokes = 0;
  const pos = (e) => {
    const r = canvas.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (canvas.width / r.width), y: (e.clientY - r.top) * (canvas.height / r.height) };
  };
  canvas.addEventListener('pointerdown', (e) => {
    drawing = true;
    try { canvas.setPointerCapture(e.pointerId); } catch { /* sin captura */ }
    const p = pos(e);
    ctx.beginPath(); ctx.moveTo(p.x, p.y);
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!drawing) return;
    const p = pos(e);
    ctx.lineTo(p.x, p.y); ctx.stroke();
    strokes++;
    canvas.dispatchEvent(new CustomEvent('sigpad:change'));
  });
  const stop = () => { drawing = false; };
  canvas.addEventListener('pointerup', stop);
  canvas.addEventListener('pointercancel', stop);
  return {
    isEmpty: () => strokes < 3,
    clear: () => { ctx.clearRect(0, 0, canvas.width, canvas.height); ink(); strokes = 0; canvas.dispatchEvent(new CustomEvent('sigpad:change')); },
    toDataURL: () => canvas.toDataURL('image/png'),
  };
}

// openMySignature(onSaved): firma de perfil del técnico. Solo se captura dibujando (no se sube un archivo);
// el servidor la asocia al usuario de la sesión y conserva las versiones anteriores para las evidencias ya firmadas.
function openMySignature(onSaved) {
  const m = sigosModal({
    title: 'Mi firma',
    size: 'md',
    body: `
      <div id="msCurrent" class="ms-current" aria-busy="true">${SigosLoading.block('Consultando su firma registrada…', { height: 96, size: 'sm' })}</div>
      <div class="fld" style="margin:16px 0 0">
        <label for="msCanvas" id="msLabel">Dibuje su firma</label>
        <canvas id="msCanvas" class="ev-sign ev-sign--wide" width="600" height="200" role="img" aria-labelledby="msLabel"></canvas>
        <div class="fld-hint">Se adjunta a cada evidencia que registre. Cambiarla no modifica las evidencias ya firmadas.</div>
      </div>
      <div class="fld-error" id="msErr" role="alert"></div>`,
    footer: '<button type="button" class="sigos-btn-ghost" id="msClear">Limpiar</button><span style="flex:1"></span><button type="button" class="sigos-btn-secondary" data-modal-close>Cancelar</button><button type="button" class="sigos-btn-primary" id="msSave" disabled>Guardar firma</button>',
  });
  const canvas = m.q('#msCanvas');
  const pad = bindSignaturePad(canvas);
  const save = m.q('#msSave');
  canvas.addEventListener('sigpad:change', () => { save.disabled = pad.isEmpty(); m.q('#msErr').textContent = ''; });
  m.q('#msClear').addEventListener('click', () => pad.clear());

  (async () => {
    const box = m.q('#msCurrent');
    const meta = await api('GET', '/api/v1/me/signature');
    if (!box.isConnected) return;
    box.removeAttribute('aria-busy');
    if (!meta.ok) { box.innerHTML = '<div class="ds-alert ds-alert--danger">No se pudo consultar su firma registrada.</div>'; return; }
    const sig = meta.body?.signature;
    if (!sig) { box.innerHTML = '<div class="ds-alert ds-alert--info">Aún no tiene una firma registrada. Regístrela para poder adjuntar evidencias.</div>'; return; }
    const img = await downloadAuthed('/api/v1/me/signature/image');
    if (!box.isConnected) return;
    box.innerHTML = `<div class="ms-current__label">Firma vigente · versión ${Number(sig.version)} · <span class="ev-num">${escapeHtml(evFmtDate(sig.created_at))}</span></div>
      <div class="ev-sign-box">${img.ok && img.data ? '<img src="data:image/png;base64,' + img.data + '" alt="Su firma registrada">' : '<div class="ev-preview__empty">No se pudo cargar la imagen.</div>'}</div>`;
  })();

  save.addEventListener('click', async () => {
    if (pad.isEmpty()) { m.q('#msErr').textContent = 'Dibuje su firma antes de guardarla.'; return; }
    save.disabled = true;
    const res = await api('POST', '/api/v1/me/signature', { image: pad.toDataURL() });
    save.textContent = 'Guardar firma';
    if (!res.ok) { save.disabled = false; m.q('#msErr').textContent = res.body?.error || 'No se pudo guardar la firma.'; return; }
    m.close();
    notify('Firma registrada', 'success');
    if (typeof onSaved === 'function') onSaved(res.body?.signature);
  });
}

// renderiza la vista evidence inbox; actualiza el DOM; comunica con Electron por IPC; realiza peticiones de red.
async function renderEvidenceInbox(content) {
  if (!state.evidenceInboxFilters) state.evidenceInboxFilters = { status: '', q: '', page: 1 };
  const f = state.evidenceInboxFilters;

  content.innerHTML = loaderBlock('Cargando bandeja de evidencias…', 240);
  const params = new URLSearchParams();
  if (f.status) params.set('status', f.status);
  if (f.q) params.set('q', f.q);
  params.set('page', f.page || 1);
  params.set('page_size', 20);
  const res = await api('GET', '/api/v1/evidences/inbox?' + params.toString());
  if (!res.ok) {
    content.innerHTML = `<div class="ds-alert ds-alert--danger">${escapeHtml(res.body?.error || 'No se pudo cargar la bandeja')}</div>`;
    return;
  }
  const data = res.body || { items: [], total: 0, counts: {} };
  const items = data.items || [];
  const total = data.total || 0;
  const pages = Math.max(1, Math.ceil(total / 20));
  content.innerHTML = `
    <div class="sigos-card filters" style="display:flex;gap:10px;align-items:end;flex-wrap:wrap">
      <div class="fld" style="flex:1 1 240px;margin:0"><label for="evInboxQ">Buscar</label><input id="evInboxQ" class="sigos-input" placeholder="Orden o cliente" value="${escapeHtml(f.q || '')}"></div>
      <div class="fld" style="flex:0 1 220px;margin:0"><label for="evInboxStatus">Estado</label>
        <select id="evInboxStatus" class="sigos-select" style="width:100%"><option value="">Todos</option>${Object.entries(EVIDENCE_STATUS).map(([k, v]) => `<option value="${k}" ${f.status === k ? 'selected' : ''}>${v.label}</option>`).join('')}</select></div>
      <button type="button" id="evInboxSearch" class="sigos-btn-secondary">Filtrar</button>
      <span style="margin-left:auto;font-size:var(--fs-sm);color:var(--c-text-3)">${total} expediente${total === 1 ? '' : 's'} · ${data.counts?.SUBMITTED || 0} pendiente${(data.counts?.SUBMITTED || 0) === 1 ? '' : 's'} de revisión</span>
    </div>
    <div class="sigos-card" style="overflow-x:auto">
      ${items.length ? `<table class="tbl">
        <thead><tr><th>Orden</th><th>Cliente</th><th>Técnico</th><th>Estado</th><th class="ev-num">Evidencias</th><th style="text-align:right">Acción</th></tr></thead>
        <tbody>${items.map((it) => `<tr class="tbl-row">
          <td><span class="mono" style="font-weight:600;color:var(--c-nav)">${escapeHtml(orderCode(it.work_order))}</span></td>
          <td>${escapeHtml(it.work_order?.customer_name || '—')}</td>
          <td>${escapeHtml(it.work_order?.assigned_to?.username || 'Sin asignar')}</td>
          <td>${evidenceStatusBadge(it.validation_status)}</td>
          <td class="ev-num">${Number(it.evidence_count || 0)}</td>
          <td style="text-align:right"><button type="button" class="sigos-btn-secondary sigos-btn-sm ev-open-btn" data-wo="${it.work_order.id}">Abrir expediente</button></td>
        </tr>`).join('')}</tbody></table>` : `<div class="empty-state"><div class="empty-state__title">Sin expedientes</div><div class="empty-state__text">${f.q || f.status ? 'Ningún expediente coincide con los filtros.' : 'Aún no hay evidencias enviadas para revisar.'}</div></div>`}
    </div>
    ${total > 20 ? `<div class="pager"><span style="font-size:var(--fs-sm);color:var(--c-text-3)">Página ${f.page} de ${pages}</span><span style="display:flex;gap:6px"><button type="button" id="evPrev" class="sigos-btn-secondary sigos-btn-sm" ${f.page <= 1 ? 'disabled' : ''}>Anterior</button><button type="button" id="evNext" class="sigos-btn-secondary sigos-btn-sm" ${f.page >= pages ? 'disabled' : ''}>Siguiente</button></span></div>` : ''}`;

  const apply = () => {
    state.evidenceInboxFilters.q = $('#evInboxQ').value.trim();
    state.evidenceInboxFilters.status = $('#evInboxStatus').value;
    state.evidenceInboxFilters.page = 1;
    render();
  };
  $('#evInboxSearch').addEventListener('click', apply);
  $('#evInboxStatus').addEventListener('change', apply);
  $('#evInboxQ').addEventListener('keydown', (e) => { if (e.key === 'Enter') apply(); });
  // El expediente se revisa en la vista de evidencias de la orden (una sola vista de verificación); «volver» regresa aquí.
  $$('.ev-open-btn').forEach((b) => b.addEventListener('click', () => {
    state.evidenceWoId = Number(b.getAttribute('data-wo'));
    state.evidenceReturn = 'evidence-inbox';
    state.view = 'evidence';
    render({ transition: 'nav' });
  }));
  $('#evPrev')?.addEventListener('click', () => { if (f.page > 1) { state.evidenceInboxFilters.page--; render(); } });
  $('#evNext')?.addEventListener('click', () => { state.evidenceInboxFilters.page++; render(); });
}
