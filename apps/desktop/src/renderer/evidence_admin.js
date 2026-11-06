function evidenceStatusBadge(status) {
  const colors = {
    APPROVED: ['#DCFCE7', '#166534'],
    REJECTED: ['#FEE2E2', '#991B1B'],
    CORRECTION_REQUIRED: ['#FEF3C7', '#92400E'],
    UNDER_REVIEW: ['#DBEAFE', '#1E40AF'],
    SUBMITTED: ['#E0F2FE', '#0369A1'],
    RESUBMITTED: ['#E0F2FE', '#0369A1'],
    DRAFT: ['#F1F5F9', '#475569'],
  };
  const [bg, fg] = colors[status] || ['#F1F5F9', '#475569'];
  return `<span style="background:${bg};color:${fg};font-size:11px;font-weight:600;padding:2px 8px;border-radius:3px;letter-spacing:0.02em">${escapeHtml(status || '')}</span>`;
}

async function renderEvidenceInbox(content) {
  if (!state.evidenceInboxFilters) state.evidenceInboxFilters = { status: '', q: '', page: 1 };
  const f = state.evidenceInboxFilters;
  const params = new URLSearchParams();
  if (f.status) params.set('status', f.status);
  if (f.q) params.set('q', f.q);
  params.set('page', f.page || 1);
  params.set('page_size', 20);
  const res = await api('GET', '/api/v1/evidences/inbox?' + params.toString());
  const data = res.body || { items: [], total: 0, page: 1, page_size: 20, counts: {} };
  const items = data.items || [];

  if (state.evidenceAdminWoId) {
    const dres = await api('GET', `/api/v1/work-orders/${state.evidenceAdminWoId}/evidence-detail`);
    const detail = dres.body || {};
    const evs = detail.evidences || [];
    const sigs = detail.signatures || [];
    const checklist = detail.checklist || [];
    const events = detail.events || [];
    const reviews = detail.reviews || [];
    const wo = detail.work_order || {};
    content.innerHTML = `
      <div class="card" style="padding:20px">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
          <button id="evBackBtn" class="sigos-btn-secondary">Volver</button>
          <h2 style="font-family:Outfit;font-size:20px;color:#163028;margin:0">Expediente ${escapeHtml(orderCode(wo))}</h2>
          ${evidenceStatusBadge(detail.status)}
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:16px">
            <div style="flex:1;min-width:320px">
            <h3 style="font-family:Outfit;font-size:16px;color:#163028">Informacion general</h3>
            <div style="font-size:13px">Cliente: ${escapeHtml(wo.customer_name || '')}</div>
            <div style="font-size:13px">Tecnico: ${escapeHtml(wo.assigned_to?.username || '')}</div>
            <div style="font-size:13px">Estado orden: ${escapeHtml(wo.status || '')}</div>
            <h3 style="font-family:Outfit;font-size:16px;color:#163028;margin-top:12px">Fotografias</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px">
              ${evs.map(e => `<div class="sigos-card" style="padding:6px"><div style="font-size:11px;color:#96908A">${escapeHtml(e.category || '')}</div><img data-ev-id="${e.id}" style="width:100%;height:80px;object-fit:cover;border-radius:4px;background:#EAE6DE"><div style="font-size:11px;margin-top:4px">${escapeHtml(e.description || '')}</div><div style="font-size:10px;color:#96908A">${escapeHtml(e.mime_type || '')} ${e.size_bytes || ''} bytes</div></div>`).join('') || '<div class="empty-state__text">Sin evidencias</div>'}
            </div>
            <h3 style="font-family:Outfit;font-size:16px;color:#163028;margin-top:12px">Firma</h3>
            <div style="font-size:13px">${sigs.length ? sigs.map(s => s.refused ? 'Negativa: ' + escapeHtml(s.refusal_reason || '') : 'Firma registrada' + (s.signer_name ? ' - ' + escapeHtml(s.signer_name) : '')).join('<br>') : 'Sin firma registrada'}</div>
            </div>
            <div style="flex:1;min-width:320px">
             <h3 style="font-family:Outfit;font-size:16px;color:#163028">Checklist</h3>
            <div style="font-size:13px">${checklist.map(i => `${escapeHtml(i.label)} - ${escapeHtml(i.result || 'PENDING')}`).join('<br>') || 'Sin items'}</div>
            <h3 style="font-family:Outfit;font-size:16px;color:#163028;margin-top:12px">Historial</h3>
            <div style="font-size:12px;color:#96908A;max-height:160px;overflow:auto">${events.map(e => `<div>${escapeHtml(e.action)} ${escapeHtml(e.from_status || '')}->${escapeHtml(e.to_status || '')} ${escapeHtml(e.created_at || '')}</div>`).join('')}</div>
            <h3 style="font-family:Outfit;font-size:16px;color:#163028;margin-top:12px">Revisiones</h3>
            <div style="font-size:12px;color:#96908A">${reviews.map(r => `<div>${escapeHtml(r.decision)} ${escapeHtml(r.created_at || '')} ${escapeHtml(r.notes || '')}</div>`).join('') || 'Sin revisiones'}</div>
            <h3 style="font-family:Outfit;font-size:16px;color:#163028;margin-top:12px">Acciones</h3>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button id="evStartReviewBtn" class="sigos-btn-secondary">Iniciar revision</button>
              <button id="evCorrectBtn" class="sigos-btn-secondary">Solicitar correccion</button>
              <button id="evApproveBtn" class="sigos-btn-primary">Aprobar</button>
              <button id="evRejectBtn" class="sigos-btn-secondary">Rechazar</button>
            </div>
          </div>
        </div>
      </div>`;

    const backBtn = $('#evBackBtn');
    if (backBtn) backBtn.addEventListener('click', () => { state.evidenceAdminWoId = null; render(); });

    const action = async (path, body) => {
      const r = await api('POST', path, body || {});
      if (r.ok) { notify('Operacion realizada', 'success'); state.evidenceAdminWoId = null; render(); }
      else notify((r.body && r.body.error) || 'Error', 'error');
    };

    const sr = $('#evStartReviewBtn');
    if (sr) sr.addEventListener('click', () => action(`/api/v1/work-orders/${state.evidenceAdminWoId}/evidences/start-review`, {}));
    const corr = $('#evCorrectBtn');
    if (corr) corr.addEventListener('click', async () => {
      const notes = prompt('Motivo de correccion:');
      if (!notes) return;
      await action(`/api/v1/work-orders/${state.evidenceAdminWoId}/evidences/request-correction`, { notes });
    });
    const appr = $('#evApproveBtn');
    if (appr) appr.addEventListener('click', () => { if (confirm('Aprobar expediente?')) action(`/api/v1/work-orders/${state.evidenceAdminWoId}/evidences/approve`, {}); });
    const rej = $('#evRejectBtn');
    if (rej) rej.addEventListener('click', async () => {
      const reason = prompt('Motivo de rechazo:');
      if (!reason) return;
      await action(`/api/v1/work-orders/${state.evidenceAdminWoId}/evidences/reject`, { reason });
    });

    for (const e of evs) {
      if (!e.id) continue;
      window.sigos.downloadFile({ path: `/api/v1/evidences/${e.id}/download`, token: state.session?.access_token }).then((r) => {
        if (r.ok && r.data) {
          const img = content.querySelector(`img[data-ev-id="${e.id}"]`);
          if (img) img.src = `data:${r.contentType};base64,${r.data}`;
        }
      });
    }
    return;
  }

  content.innerHTML = `
    <div class="card" style="padding:20px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <h2 style="font-family:Outfit;font-size:22px;color:#163028;margin:0">Bandeja de Evidencias</h2>
        <input id="evInboxQ" class="sigos-input" placeholder="Buscar" value="${escapeHtml(f.q || '')}" style="max-width:240px">
        <select id="evInboxStatus" class="sigos-input">
          <option value="">Todos</option>
          ${['DRAFT','SUBMITTED','UNDER_REVIEW','CORRECTION_REQUIRED','RESUBMITTED','APPROVED','REJECTED'].map(s => `<option value="${s}" ${f.status === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
        <button id="evInboxSearch" class="sigos-btn-secondary">Filtrar</button>
      </div>
      <div style="font-size:12px;color:#96908A;margin-bottom:8px">Total: ${data.total || 0} | Pendientes: ${data.counts?.SUBMITTED || 0}</div>
      <table class="sigos-table" style="width:100%">
        <thead><tr><th>Orden</th><th>Estado</th><th>Evidencias</th><th>Accion</th></tr></thead>
        <tbody>
          ${items.map(it => `<tr><td>${escapeHtml(orderCode(it.work_order))}</td><td>${evidenceStatusBadge(it.validation_status)}</td><td>${it.evidence_count}</td><td><button class="sigos-btn-secondary ev-open-btn" data-wo="${it.work_order.id}">Abrir</button></td></tr>`).join('') || '<tr><td colspan="4" class="empty-state__text">Sin expedientes</td></tr>'}
        </tbody>
      </table>
      <div style="display:flex;gap:8px;margin-top:12px">
        <button id="evPrev" class="sigos-btn-secondary" ${f.page <= 1 ? 'disabled' : ''}>Anterior</button>
        <button id="evNext" class="sigos-btn-secondary" ${f.page * 20 >= (data.total || 0) ? 'disabled' : ''}>Siguiente</button>
      </div>
    </div>`;

  const searchBtn = $('#evInboxSearch');
  if (searchBtn) searchBtn.addEventListener('click', () => {
    state.evidenceInboxFilters.q = $('#evInboxQ').value;
    state.evidenceInboxFilters.status = $('#evInboxStatus').value;
    state.evidenceInboxFilters.page = 1;
    render();
  });
  $$('.ev-open-btn').forEach((b) => {
    b.addEventListener('click', () => { state.evidenceAdminWoId = Number(b.getAttribute('data-wo')); render(); });
  });
  const prev = $('#evPrev');
  if (prev) prev.addEventListener('click', () => { if (f.page > 1) { state.evidenceInboxFilters.page--; render(); } });
  const next = $('#evNext');
  if (next) next.addEventListener('click', () => { state.evidenceInboxFilters.page++; render(); });
}
EOF