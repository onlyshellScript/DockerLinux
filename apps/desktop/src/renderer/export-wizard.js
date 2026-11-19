// export-wizard.js: asistente unico de exportacion (PDF / XLSX) sobre el motor del backend (/api/v1/exports).
// Pasos: 1 formato · 2 plantilla · 3 configuracion · 4 vista previa · 5 generar.
// Uso: openExportWizard('orders', { status: 'completed' })  -> los filtros iniciales son opcionales.

(function () {
  const STEPS = ['Formato', 'Plantilla', 'Configuración', 'Vista previa', 'Generar'];
  const FORMATS = [
    { id: 'pdf', title: 'PDF', text: 'Documento institucional listo para imprimir o compartir.' },
    { id: 'xlsx', title: 'Excel (XLSX)', text: 'Libro con hoja de resumen y datos con tipos reales para analizar.' },
  ];
  const esc = (s) => (typeof escapeHtml === 'function' ? escapeHtml(s) : String(s ?? ''));

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
    return out;
  }

  async function openExportWizard(module, initialParams = {}) {
    const st = { step: 0, format: null, template: null, templates: [], params: { ...initialParams }, columns: null, sort: null, order: null, preview: null, options: {} };
    const m = sigosModal({ title: 'Exportar', size: 'lg', body: '<div id="xwBody"></div>', footer: '<div id="xwFoot" class="xw-foot"></div>' });
    const body = () => m.card.querySelector('#xwBody');
    const foot = () => m.card.querySelector('#xwFoot');
    const q = (sel) => m.card.querySelector(sel);
    const qa = (sel) => Array.from(m.card.querySelectorAll(sel));

    const stepper = () => `<ol class="xw-steps" aria-label="Progreso">${STEPS.map((s, i) => `<li class="${i < st.step ? 'is-done' : i === st.step ? 'is-current' : ''}" ${i === st.step ? 'aria-current="step"' : ''}><span>${i + 1}</span>${s}</li>`).join('')}</ol>`;
    const setFoot = (back, nextLabel, nextDisabled = false) => {
      foot().innerHTML = `${back ? '<button type="button" class="sigos-btn-ghost" data-xw="back">Atrás</button>' : '<span></span>'}
        <span class="xw-foot__spacer"></span>
        <button type="button" class="sigos-btn-secondary" data-xw="cancel">Cancelar</button>
        ${nextLabel ? `<button type="button" class="sigos-btn-primary" data-xw="next" ${nextDisabled ? 'disabled' : ''}>${nextLabel}</button>` : ''}`;
      foot().querySelector('[data-xw="cancel"]').addEventListener('click', () => m.close());
      foot().querySelector('[data-xw="back"]')?.addEventListener('click', () => { st.step -= 1; draw(); });
      foot().querySelector('[data-xw="next"]')?.addEventListener('click', next);
    };
    const err = (msg) => `<div class="ds-alert ds-alert--danger" role="alert">${esc(msg)}</div>`;

    async function next() {
      if (st.step === 2) { if (!readConfig()) return; }
      st.step += 1;
      draw();
    }

    // ---------- Paso 1: formato
    function drawFormat() {
      body().innerHTML = stepper() + `<p class="xw-lead">¿En qué formato necesita el documento?</p>
        <div class="xw-choices" role="radiogroup" aria-label="Formato">${FORMATS.map((f) => `
          <label class="xw-choice"><input type="radio" name="xwFormat" value="${f.id}" ${st.format === f.id ? 'checked' : ''}>
            <span class="xw-choice__body"><strong>${f.title}</strong><span>${f.text}</span></span></label>`).join('')}</div>`;
      qa('input[name="xwFormat"]').forEach((r) => r.addEventListener('change', () => { st.format = r.value; st.template = null; st.preview = null; setFoot(false, 'Continuar'); }));
      setFoot(false, 'Continuar', !st.format);
    }

    // ---------- Paso 2: plantilla
    async function drawTemplate() {
      body().innerHTML = stepper() + SigosLoading.block('Cargando plantillas de exportación…', { height: 180 });
      setFoot(true, 'Continuar', true);
      const r = await api('GET', `/api/v1/exports/templates?module=${encodeURIComponent(module)}&format=${st.format}`);
      if (!r.ok) { body().innerHTML = stepper() + err(r.body?.error || 'No se pudieron cargar las plantillas'); return; }
      st.templates = r.body || [];
      if (!st.templates.length) { body().innerHTML = stepper() + '<div class="empty-state"><div class="empty-state__title">Sin plantillas disponibles</div><div class="empty-state__text">No hay plantillas de este módulo para el formato elegido o para su rol.</div></div>'; return; }
      body().innerHTML = stepper() + `<p class="xw-lead">Elija la plantilla del documento.</p>
        <div class="xw-choices xw-choices--list" role="radiogroup" aria-label="Plantilla">${st.templates.map((t) => `
          <label class="xw-choice"><input type="radio" name="xwTpl" value="${esc(t.id)}" ${st.template?.id === t.id ? 'checked' : ''}>
            <span class="xw-choice__body"><strong>${esc(t.name)}</strong><span>${esc(t.description)}</span><small>${esc(t.module_label)} · v${esc(t.version)}</small></span></label>`).join('')}</div>`;
      qa('input[name="xwTpl"]').forEach((r2) => r2.addEventListener('change', () => {
        st.template = st.templates.find((t) => t.id === r2.value);
        st.columns = st.template.columns.filter((c) => c.default).map((c) => c.key);
        st.sort = st.template.default_sort; st.order = st.template.default_order; st.preview = null;
        setFoot(true, 'Continuar');
      }));
      setFoot(true, 'Continuar', !st.template);
    }

    // ---------- Paso 3: configuracion
    async function drawConfig() {
      const t = st.template;
      body().innerHTML = stepper() + SigosLoading.block('Preparando opciones de exportación…', { height: 180 });
      for (const f of t.filters.filter((f) => f.source && !st.options[f.source])) {
        const r = await api('GET', `/api/v1/exports/options/${f.source}`);
        st.options[f.source] = r.ok ? r.body : [];
      }
      const field = (f) => {
        const v = st.params[f.key] ?? '';
        const id = `xwf-${f.key}`;
        if (f.type === 'select') {
          const opts = f.source ? st.options[f.source] : f.options;
          return `<div class="fld"><label for="${id}">${esc(f.label)}</label><select id="${id}" class="sigos-select" data-param="${f.key}" style="width:100%"><option value="">Todos</option>${opts.map((o) => `<option value="${esc(o.value)}" ${String(v) === String(o.value) ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select></div>`;
        }
        return `<div class="fld"><label for="${id}">${esc(f.label)}</label><input id="${id}" class="sigos-input" type="${f.type === 'date' ? 'date' : 'text'}" data-param="${f.key}" value="${esc(v)}"></div>`;
      };
      body().innerHTML = stepper() + `
        <div class="xw-config">
          ${t.filters.length ? `<section><h4>Filtros</h4><div class="xw-grid">${t.filters.map(field).join('')}</div></section>` : '<section><h4>Filtros</h4><p class="xw-muted">Esta plantilla no admite filtros.</p></section>'}
          ${t.sorts.length ? `<section><h4>Orden</h4><div class="xw-grid">
            <div class="fld"><label for="xwSort">Ordenar por</label><select id="xwSort" class="sigos-select" style="width:100%">${t.sorts.map((s) => `<option value="${s.key}" ${st.sort === s.key ? 'selected' : ''}>${esc(s.label)}</option>`).join('')}</select></div>
            <div class="fld"><label for="xwOrder">Dirección</label><select id="xwOrder" class="sigos-select" style="width:100%"><option value="asc" ${st.order === 'asc' ? 'selected' : ''}>Ascendente</option><option value="desc" ${st.order === 'desc' ? 'selected' : ''}>Descendente</option></select></div>
          </div></section>` : ''}
          ${t.allow_columns ? `<section><h4>Columnas <span class="xw-muted">(${st.columns.length} de ${t.columns.length})</span></h4><div class="xw-cols">${t.columns.map((c) => `<label class="xw-col"><input type="checkbox" value="${c.key}" ${st.columns.includes(c.key) ? 'checked' : ''}> ${esc(c.label)}</label>`).join('')}</div></section>` : `<section><h4>Columnas</h4><p class="xw-muted">${t.columns.map((c) => esc(c.label)).join(' · ')}</p></section>`}
          <div id="xwCfgErr"></div>
        </div>`;
      qa('.xw-col input').forEach((c) => c.addEventListener('change', () => {
        st.columns = qa('.xw-col input').filter((x) => x.checked).map((x) => x.value);
        q('.xw-config h4 .xw-muted') && (q('.xw-cols').previousElementSibling.querySelector('.xw-muted').textContent = `(${st.columns.length} de ${t.columns.length})`);
      }));
      setFoot(true, 'Ver vista previa');
    }

    function readConfig() {
      const t = st.template;
      const errBox = q('#xwCfgErr');
      const params = {};
      qa('[data-param]').forEach((el) => { if (el.value.trim()) params[el.dataset.param] = el.value.trim(); });
      if (params.date_from && params.date_to && params.date_from > params.date_to) { errBox.innerHTML = err('La fecha «Desde» no puede ser posterior a «Hasta».'); return false; }
      if (t.allow_columns && !st.columns.length) { errBox.innerHTML = err('Seleccione al menos una columna.'); return false; }
      st.params = params;
      if (q('#xwSort')) { st.sort = q('#xwSort').value; st.order = q('#xwOrder').value; }
      st.preview = null;
      return true;
    }

    const requestBody = () => ({
      template: st.template.id, format: st.format,
      params: { ...st.params, ...(st.template.allow_columns ? { columns: st.columns } : {}), ...(st.sort ? { sort: st.sort, order: st.order } : {}) },
    });

    // ---------- Paso 4: vista previa (mismos datos que la generacion; se comprueba con hash)
    async function drawPreview() {
      body().innerHTML = stepper() + SigosLoading.block('Consultando información para la vista previa…', { height: 260 });
      setFoot(true, 'Generar', true);
      const r = await api('POST', '/api/v1/exports/preview', requestBody(), null, null, true, { loading: false }); // el cuerpo ya muestra el indicador
      if (!r.ok) { body().innerHTML = stepper() + err(r.body?.error || 'No se pudo generar la vista previa'); return; }
      const p = st.preview = r.body;
      const tooMany = (p.warnings || []).length && p.total > (p.limits?.[st.format] || Infinity);
      body().innerHTML = stepper() + `
        <div class="xw-doc">
          <div class="xw-doc__head"><span class="app-sidebar__mark" aria-hidden="true">S</span><div><strong>${esc(p.title)}</strong><small>${esc(p.filters_text)}</small></div><span class="xw-doc__fmt">${st.format.toUpperCase()}</span></div>
          ${p.summary.length ? `<dl class="xw-sum">${p.summary.map((s) => `<div><dt>${esc(s.label)}</dt><dd>${esc(s.value)}</dd></div>`).join('')}</dl>` : ''}
          ${p.total ? `<div class="table-scroll"><table class="tbl xw-table"><thead><tr>${p.columns.map((c) => `<th${['int', 'number', 'money', 'percent'].includes(c.type) ? ' style="text-align:right"' : ''}>${esc(c.label)}</th>`).join('')}</tr></thead>
            <tbody>${p.rows.map((row) => `<tr>${row.map((v, i) => `<td${['int', 'number', 'money', 'percent'].includes(p.columns[i].type) ? ' style="text-align:right"' : ''}>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
            <p class="xw-muted">Vista previa de ${p.rows.length} de ${p.total} registro${p.total === 1 ? '' : 's'}${p.groups ? ` en ${Object.keys(p.groups).length} grupo${Object.keys(p.groups).length === 1 ? '' : 's'}` : ''}. El documento incluirá todos.</p>`
            : '<div class="ds-alert ds-alert--info">No hay registros con estos filtros. Puede generar el documento igualmente; indicará que no hay datos.</div>'}
          ${tooMany ? err(`Hay ${p.total} registros y el máximo para ${st.format.toUpperCase()} es ${p.limits[st.format]}. Ajuste los filtros.`) : ''}
        </div>`;
      setFoot(true, 'Generar documento', tooMany);
    }

    // ---------- Paso 5: generar, validar y guardar
    async function drawGenerate(accept = false) {
      // Indicador localizado en el asistente: la operación pertenece a este diálogo y su pie queda deshabilitado.
      const genMsg = st.format === 'xlsx' ? 'Preparando archivo XLSX…' : st.format === 'pdf' ? 'Generando documento PDF…' : 'Exportando información…';
      body().innerHTML = stepper() + SigosLoading.block(genMsg, { height: 220 });
      setFoot(false, null);
      const res = await window.sigos.apiBinary({ method: 'POST', path: '/api/v1/exports/generate', body: { ...requestBody(), expected_hash: st.preview?.hash, accept_changes: accept }, token: state.session?.access_token });
      if (res.status === 409 && res.json?.code === 'DATA_CHANGED') {
        const ok = await confirmDialog(`Los datos cambiaron desde la vista previa (ahora hay ${res.json.total} registros). ¿Generar el documento con los datos actuales?`, { title: 'Datos actualizados', confirmLabel: 'Generar con datos actuales', cancelLabel: 'Volver a la vista previa' });
        if (ok) return drawGenerate(true);
        st.step = 3; return draw();
      }
      if (!res.ok || !res.data) {
        body().innerHTML = stepper() + err(res.json?.error || res.error || `No se pudo generar el documento (HTTP ${res.status})`);
        setFoot(true, null);
        const retry = document.createElement('button');
        retry.type = 'button'; retry.className = 'sigos-btn-primary'; retry.textContent = 'Reintentar';
        retry.addEventListener('click', () => drawGenerate(accept));
        foot().appendChild(retry);
        return;
      }
      const saved = await window.sigos.saveFile({ defaultName: res.filename, data: b64ToBytes(res.data) });
      if (!saved?.ok) { body().innerHTML = stepper() + err('No se pudo guardar el archivo.'); setFoot(true, null); return; }
      if (saved.canceled) { body().innerHTML = stepper() + '<div class="ds-alert ds-alert--info">Guardado cancelado. El documento no se guardó.</div>'; setFoot(true, null); return; }
      body().innerHTML = stepper() + `
        <div class="xw-done">
          <div class="xw-done__icon" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></div>
          <h4>Documento generado</h4>
          <dl class="xw-sum"><div><dt>Archivo</dt><dd>${esc(saved.path.split(/[\\/]/).pop())}</dd></div><div><dt>Registros</dt><dd>${res.rows}</dd></div>
            <div><dt>Código</dt><dd>${esc(res.document || '—')}</dd></div><div><dt>Tamaño</dt><dd>${Math.max(1, Math.round(res.size / 1024))} KB</dd></div></dl>
          ${accept ? '<p class="xw-muted">Se generó con datos actualizados respecto a la vista previa.</p>' : ''}
        </div>`;
      foot().innerHTML = `<span class="xw-foot__spacer"></span><button type="button" class="sigos-btn-secondary" id="xwFolder">Abrir carpeta</button><button type="button" class="sigos-btn-primary" id="xwClose">Listo</button>`;
      q('#xwFolder').addEventListener('click', () => window.sigos.openFolder(saved.path));
      q('#xwClose').addEventListener('click', () => m.close());
      notify('Documento exportado', 'success');
    }

    function draw() {
      [drawFormat, drawTemplate, drawConfig, drawPreview, drawGenerate][st.step]();
    }
    draw();
  }

  window.openExportWizard = openExportWizard;
})();
