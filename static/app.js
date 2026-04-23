/* ARQA Dashboard — main.js (Part 1: State, API, Selectors, Render) */

var ARQA = (function () {

var state = {
  vacantes: [], owners: [], candidatoFields: [], etapas: [],
  filter: { group: 'none' },
  modal: { editingId: null, tempCands: [], tempSteps: [], prio: '' },
  candModal: { aplicacionId: null, candidatoId: null, candidato: {}, aplicacion: {} },
  ownerModal: { editingId: null, color: 'slate' }
};

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

var _toastTimer;
var utils = {
  toast: function (msg) {
    var el = document.getElementById('toast');
    el.textContent = msg; el.classList.add('show');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(function () { el.classList.remove('show'); }, 2800);
  },
  weekLabel: function () {
    var now = new Date(), day = now.getDay();
    var mon = new Date(now); mon.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    var sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    var o = { day: 'numeric', month: 'short' };
    return mon.toLocaleDateString('es-MX', o) + ' — ' + sun.toLocaleDateString('es-MX', o) + ' ' + sun.getFullYear();
  }
};

// ── API layer (fetch-based) ─────────────────────────────────
var api = {
  _json: function (url, opts) {
    return fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts))
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || 'Error'); return d; }); });
  },
  load: function (cb) {
    api._json('/api/data').then(function (data) {
      state.vacantes = data.vacantes || [];
      state.owners = data.owners || [];
      state.candidatoFields = data.candidatoFields || [];
      state.etapas = data.etapas || [];
      cb();
    }).catch(function (e) { utils.toast('Error: ' + e.message); });
  },
  save: function (data) {
    var btn = document.getElementById('btnSave');
    btn.textContent = 'Guardando…'; btn.disabled = true;
    api._json('/api/vacante', { method: 'POST', body: JSON.stringify(data) })
      .then(function () { btn.textContent = 'Guardar'; btn.disabled = false; utils.toast('✓ Guardado'); modal.close(); api.load(render.all); })
      .catch(function (e) { btn.textContent = 'Guardar'; btn.disabled = false; utils.toast('Error: ' + e.message); });
  },
  remove: function (id) {
    if (!confirm('¿Eliminar esta vacante y todos sus candidatos?')) return;
    api._json('/api/vacante/' + id, { method: 'DELETE' })
      .then(function () { utils.toast('Vacante eliminada'); modal.close(); api.load(render.all); })
      .catch(function (e) { utils.toast('Error: ' + e.message); });
  },
  toggleStatus: function (id, newStatus) {
    var v = state.vacantes.find(function (x) { return x.id === id; });
    if (!v) return;
    v.status = newStatus; render.all();
    api._json('/api/vacante/' + id + '/status', { method: 'PATCH', body: JSON.stringify({ status: newStatus }) })
      .then(function () { utils.toast(newStatus === 'activa' ? '✓ Activada' : 'Pausada'); })
      .catch(function (e) { v.status = newStatus === 'activa' ? 'inactiva' : 'activa'; render.all(); utils.toast('Error: ' + e.message); });
  },
  saveOwner: function (data) {
    var btn = document.getElementById('oBtnSave');
    btn.textContent = 'Guardando…'; btn.disabled = true;
    api._json('/api/owner', { method: 'POST', body: JSON.stringify(data) })
      .then(function () { btn.textContent = 'Guardar'; btn.disabled = false; utils.toast('✓ Owner guardado'); api.load(function () { render.all(); ownerModal.showList(); }); })
      .catch(function (e) { btn.textContent = 'Guardar'; btn.disabled = false; utils.toast('Error: ' + e.message); });
  },
  removeOwner: function (id) {
    if (!confirm('¿Eliminar este owner?')) return;
    api._json('/api/owner/' + id, { method: 'DELETE' })
      .then(function () { utils.toast('Owner eliminado'); api.load(function () { render.all(); ownerModal.showList(); }); })
      .catch(function (e) { utils.toast('Error: ' + e.message); });
  },
  saveCandidatoProfile: function (data) {
    var btn = document.getElementById('cBtnSave');
    btn.textContent = 'Guardando…'; btn.disabled = true;
    api._json('/api/candidato-profile', { method: 'POST', body: JSON.stringify(data) })
      .then(function () { btn.textContent = 'Guardar'; btn.disabled = false; utils.toast('✓ Perfil actualizado'); candModal.close(); api.load(render.all); })
      .catch(function (e) { btn.textContent = 'Guardar'; btn.disabled = false; utils.toast('Error: ' + e.message); });
  },
  removeCandidato: function (id) {
    if (!confirm('¿Eliminar este candidato?')) return;
    api._json('/api/candidato/' + id, { method: 'DELETE' })
      .then(function () { utils.toast('Candidato eliminado'); candModal.close(); api.load(render.all); })
      .catch(function (e) { utils.toast('Error: ' + e.message); });
  }
};

// ── Selectors ───────────────────────────────────────────────
var sel = {
  ownerById: function (id) {
    return state.owners.find(function (x) { return x.id === id; }) || { id: id, nombre: '—', color: 'slate' };
  },
  sorted: function () {
    var so = { 'activa': 0, 'inactiva': 1 };
    var po = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4, '': 5 };
    return state.vacantes.slice().sort(function (a, b) {
      var sa = so[a.status] ?? 2, sb = so[b.status] ?? 2;
      if (sa !== sb) return sa - sb;
      return (po[a.prioridad || ''] ?? 5) - (po[b.prioridad || ''] ?? 5);
    });
  },
  grouped: function () {
    var items = sel.sorted(), group = state.filter.group;
    if (group === 'none') return [{ key: '_all', label: null, items: items }];
    var orders = {
      owner: state.owners.map(function (o) { return o.id; }),
      prioridad: ['P0','P1','P2','P3','P4',''],
      status: ['activa','inactiva']
    };
    var labels = {
      prioridad: { 'P0':'P0 — Top','P1':'P1','P2':'P2','P3':'P3','P4':'P4','':'Sin prioridad' },
      status: { 'activa':'Activas','inactiva':'Inactivas' }
    };
    var groups = {};
    items.forEach(function (v) {
      var key = group === 'prioridad' ? (v.prioridad || '') : group === 'status' ? (v.status || 'activa') : group === 'owner' ? (v.ownerId || '') : (v[group] || '—');
      if (!groups[key]) groups[key] = [];
      groups[key].push(v);
    });
    var labelFor = function (key) {
      if (group === 'owner') return key ? sel.ownerById(key).nombre : 'Sin owner';
      return (labels[group] && labels[group][key]) || (key === '' ? 'Sin asignar' : key);
    };
    var order = orders[group] || Object.keys(groups).sort();
    var result = [];
    order.forEach(function (k) { if (groups[k]) result.push({ key: k, label: labelFor(k), items: groups[k] }); });
    Object.keys(groups).forEach(function (k) { if (order.indexOf(k) === -1) result.push({ key: k, label: labelFor(k), items: groups[k] }); });
    return result;
  },
  stats: function () {
    var active = state.vacantes.filter(function (v) { return v.status === 'activa'; });
    var tc = 0, cc = 0;
    state.vacantes.forEach(function (v) { tc += v.candidatos.length; cc += v.candidatos.filter(function (c) { return c.lado === 'Cliente'; }).length; });
    return { activeVacantes: active.length, totalVacantes: state.vacantes.length, totalCands: tc, conCliente: cc };
  }
};

// ── Render ───────────────────────────────────────────────────
var render = {
  all: function () { render.stats(); render.grid(); },
  stats: function () {
    var s = sel.stats();
    document.getElementById('statsBar').innerHTML =
      '<div class="stat-card"><span class="stat-val">' + s.activeVacantes + ' / ' + s.totalVacantes + '</span><span class="stat-label">Vacantes activas</span></div>' +
      '<div class="stat-card"><span class="stat-val">' + s.totalCands + '</span><span class="stat-label">Candidatos en pipe</span></div>' +
      '<div class="stat-card"><span class="stat-val">' + s.conCliente + '</span><span class="stat-label">Con cliente</span></div>';
  },
  grid: function () {
    var grid = document.getElementById('grid');
    if (!state.vacantes.length) { grid.innerHTML = '<div class="empty-state">Sin vacantes aún.<br>¡Crea la primera con el botón de arriba!</div>'; return; }
    var groups = sel.grouped();
    if (state.filter.group === 'none') { grid.innerHTML = groups[0].items.map(render.card).join(''); return; }
    grid.innerHTML = groups.map(function (g) {
      return '<div class="group-header"><span class="group-title">' + esc(g.label) + '</span><span class="group-count">' + g.items.length + '</span><div class="group-divider"></div></div>' + g.items.map(render.card).join('');
    }).join('');
  },
  _p: {
    candRow: function (c) {
      var isC = c.lado === 'Cliente';
      var ec = 'slate';
      if (c.etapa) { var e = state.etapas.find(function (x) { return x.key === c.etapa; }); if (e) ec = e.color; }
      var eh = c.etapa ? '<span class="etapa-badge c-' + ec + '">' + esc(c.etapa) + '</span>' : '';
      return '<div class="cand-row cand-row-clickable" onclick="event.stopPropagation();ARQA.openCand(\'' + esc(c.id) + '\')"><span class="cand-name"><span class="dot ' + (isC ? 'dot-c' : 'dot-a') + '"></span>' + esc(c.nombre) + '</span><span style="display:flex;gap:4px;align-items:center">' + eh + '<span class="lado-badge ' + (isC ? 'lado-c' : 'lado-a') + '">' + (isC ? 'con cliente' : 'con ARQA') + '</span></span></div>';
    },
    progClass: function (p) { return p === 0 ? 'prog-zero' : p < 50 ? 'prog-low' : p < 100 ? 'prog-mid' : 'prog-done'; },
    nextSteps: function (steps) {
      if (!steps || !steps.length) return '<div class="card-bottom"></div>';
      var done = steps.filter(function (s) { return s.d; }).length;
      return '<div class="card-nextsteps"><span class="nextsteps-icon">' + (done === steps.length ? '✓' : '→') + '</span><span class="card-nextsteps-text">Next steps (' + done + '/' + steps.length + ')' + (done === steps.length ? ' · completados' : '') + '</span></div>';
    }
  },
  card: function (v) {
    var p = render._p, owner = sel.ownerById(v.ownerId);
    var cc = v.candidatos.filter(function (c) { return c.lado === 'Cliente'; }).length;
    var pct = v.meta > 0 ? Math.min(100, Math.round((cc / v.meta) * 100)) : 0;
    var isI = v.status === 'inactiva';
    var statusBtn = '<button class="card-status-btn ' + (isI ? 'inactive-status' : 'active-status') + '" onclick="event.stopPropagation();ARQA.toggleStatus(\'' + v.id + '\',\'' + (isI ? 'activa' : 'inactiva') + '\')">' + (isI ? 'Inactiva' : 'Activa') + '</button>';
    var prioBadge = v.prioridad ? '<span class="prio-badge prio-' + esc(v.prioridad) + '">' + esc(v.prioridad) + '</span>' : '<span class="prio-badge prio-none">P—</span>';
    var candHtml = v.candidatos.length ? v.candidatos.map(p.candRow).join('') : '<span class="empty-pipe">Sin candidatos aún</span>';
    return '<div class="card' + (isI ? ' card-inactive' : '') + '" data-color="' + esc(owner.color) + '" onclick="ARQA.openEdit(\'' + v.id + '\')">' +
      '<div class="card-top"><span class="card-title">' + esc(v.rol) + '</span><div class="card-badges">' + statusBtn + prioBadge + '<span class="owner-badge bg-' + esc(owner.color) + '">' + esc(owner.nombre) + '</span></div></div>' +
      '<div class="card-meta"><span class="card-cliente">' + esc(v.cliente) + '</span><span class="meta-count">' + cc + ' / ' + v.meta + '</span></div>' +
      '<div class="prog-wrap"><div class="prog-fill ' + p.progClass(pct) + '" style="width:' + pct + '%"></div></div>' +
      '<div class="pipe-label">En pipe</div><div class="cand-list">' + candHtml + '</div>' + p.nextSteps(v.nextSteps) + '</div>';
  }
};
/* ARQA Dashboard — modals.js (Part 2: Modal, CandModal, OwnerModal, Init) */

// ── Vacante Modal ───────────────────────────────────────────
var modal = {
  open: function (v) {
    if (!v) return;
    state.modal.editingId = v.id;
    state.modal.tempCands = v.candidatos.map(function (c) { return Object.assign({}, c); });
    state.modal.tempSteps = (v.nextSteps || []).map(function (s) { return Object.assign({}, s); });
    state.modal.prio = v.prioridad || '';
    modal._populateOwners(v.ownerId);
    document.getElementById('mTitle').textContent = 'Editar vacante';
    document.getElementById('f-rol').value = v.rol;
    document.getElementById('f-cliente').value = v.cliente;
    document.getElementById('f-meta').value = v.meta;
    document.getElementById('f-status').value = v.status || 'activa';
    document.getElementById('f-notas').value = v.notas || '';
    document.getElementById('btnDelete').style.display = '';
    modal._renderPrio(); modal._renderSteps(); modal._renderCands();
    document.getElementById('overlay').classList.add('open');
  },
  openNew: function () {
    if (!state.owners.length) { utils.toast('⚠️ Crea un owner primero'); ownerModal.open(); return; }
    state.modal.editingId = null; state.modal.tempCands = []; state.modal.tempSteps = []; state.modal.prio = '';
    modal._populateOwners(state.owners[0].id);
    document.getElementById('mTitle').textContent = 'Nueva vacante';
    document.getElementById('f-rol').value = '';
    document.getElementById('f-cliente').value = '';
    document.getElementById('f-meta').value = '';
    document.getElementById('f-status').value = 'activa';
    document.getElementById('f-notas').value = '';
    document.getElementById('btnDelete').style.display = 'none';
    modal._renderPrio(); modal._renderSteps(); modal._renderCands();
    document.getElementById('overlay').classList.add('open');
  },
  _populateOwners: function (sel) {
    document.getElementById('f-owner').innerHTML = state.owners.map(function (o) {
      return '<option value="' + esc(o.id) + '"' + (o.id === sel ? ' selected' : '') + '>' + esc(o.nombre) + '</option>';
    }).join('');
  },
  close: function () { document.getElementById('overlay').classList.remove('open'); },
  save: function () {
    modal._syncCands(); modal._syncSteps();
    var rol = document.getElementById('f-rol').value.trim();
    var cliente = document.getElementById('f-cliente').value.trim();
    var ownerId = document.getElementById('f-owner').value;
    var meta = parseInt(document.getElementById('f-meta').value);
    var status = document.getElementById('f-status').value;
    var notas = document.getElementById('f-notas').value.trim();
    if (!rol || !cliente || !meta) { utils.toast('⚠️ Llena Rol, Cliente y Meta'); return; }
    api.save({ id: state.modal.editingId, rol: rol, cliente: cliente, ownerId: ownerId, meta: meta, status: status, prioridad: state.modal.prio || '', nextSteps: state.modal.tempSteps, notas: notas, candidatos: state.modal.tempCands });
  },
  remove: function () { if (state.modal.editingId) api.remove(state.modal.editingId); },
  addCand: function () {
    modal._syncCands();
    state.modal.tempCands.push({ id: null, nombre: '', lado: 'ARQA', status: 'En proceso' });
    modal._renderCands();
    var inputs = document.querySelectorAll('#cand-container input[type=text]');
    if (inputs.length) inputs[inputs.length - 1].focus();
  },
  rmCand: function (i) { modal._syncCands(); state.modal.tempCands.splice(i, 1); modal._renderCands(); },
  _syncCands: function () {
    document.querySelectorAll('#cand-container [data-i]').forEach(function (el) {
      var i = parseInt(el.dataset.i), f = el.dataset.field;
      if (state.modal.tempCands[i] !== undefined) state.modal.tempCands[i][f] = el.value;
    });
  },
  _syncSteps: function () {
    document.querySelectorAll('#ns-container [data-ns]').forEach(function (el) {
      var i = parseInt(el.dataset.ns), f = el.dataset.field;
      if (state.modal.tempSteps[i] === undefined) return;
      if (f === 'd') state.modal.tempSteps[i].d = el.checked;
      else state.modal.tempSteps[i][f] = el.value;
    });
    state.modal.tempSteps = state.modal.tempSteps.filter(function (s) { return (s.t || '').trim() !== '' || s.d || s.f; });
  },
  toggleStep: function (i) { modal._syncSteps(); if (state.modal.tempSteps[i]) { state.modal.tempSteps[i].d = !state.modal.tempSteps[i].d; modal._renderSteps(); } },
  rmStep: function (i) { modal._syncSteps(); state.modal.tempSteps.splice(i, 1); modal._renderSteps(); },
  _renderSteps: function () {
    var steps = state.modal.tempSteps, cont = document.getElementById('ns-container'), hasRoom = steps.length < 5;
    var rows = steps.map(function (s, i) {
      return '<div class="ns-row"><input type="checkbox" class="ns-check"' + (s.d ? ' checked' : '') + ' onclick="ARQA.toggleStep(' + i + ')"><input type="text" class="ns-text' + (s.d ? ' done' : '') + '" value="' + esc(s.t) + '" placeholder="Descripción del paso" data-ns="' + i + '" data-field="t"><input type="date" class="ns-date" value="' + esc(s.f) + '" data-ns="' + i + '" data-field="f"><button class="ns-rm" onclick="ARQA.rmStep(' + i + ')" title="Eliminar">×</button></div>';
    }).join('');
    var empty = hasRoom ? '<div class="ns-row empty-slot"><input type="checkbox" class="ns-check" disabled><input type="text" class="ns-text" placeholder="+ Agregar paso…" oninput="ARQA.addStep(this.value)"><input type="date" class="ns-date" disabled></div>' : '<div class="ns-limit-note">Máximo 5 pasos alcanzado</div>';
    cont.innerHTML = rows + empty;
  },
  addStep: function (text) {
    if (state.modal.tempSteps.length >= 5) return;
    modal._syncSteps();
    state.modal.tempSteps.push({ t: text, d: false, f: '' });
    modal._renderSteps();
    var inputs = document.querySelectorAll('#ns-container .ns-text');
    var idx = state.modal.tempSteps.length - 1;
    if (inputs[idx]) { inputs[idx].focus(); inputs[idx].setSelectionRange(text.length, text.length); }
  },
  setPrio: function (val) { state.modal.prio = val; modal._renderPrio(); },
  _renderPrio: function () {
    document.querySelectorAll('#f-prio-control .prio-opt').forEach(function (btn) {
      btn.classList.toggle('selected', btn.dataset.val === (state.modal.prio || ''));
    });
  },
  _renderCands: function () {
    document.getElementById('cand-container').innerHTML = state.modal.tempCands.map(function (c, i) {
      return '<div class="cand-edit-row"><input type="text" value="' + esc(c.nombre) + '" placeholder="Nombre del candidato" data-i="' + i + '" data-field="nombre"><select data-i="' + i + '" data-field="lado"><option' + (c.lado === 'ARQA' ? ' selected' : '') + '>ARQA</option><option' + (c.lado === 'Cliente' ? ' selected' : '') + '>Cliente</option></select><button class="btn-rm" onclick="ARQA.rmCand(' + i + ')">×</button></div>';
    }).join('');
  }
};

// ── Candidate Profile Modal ─────────────────────────────────
var candModal = {
  _find: function (aplId) {
    for (var i = 0; i < state.vacantes.length; i++) {
      var c = state.vacantes[i].candidatos.find(function (x) { return x.id === aplId; });
      if (c) return { vacanteId: state.vacantes[i].id, aplicacion: c };
    }
    return null;
  },
  open: function (aplId) {
    var found = candModal._find(aplId);
    if (!found) { utils.toast('Candidato no encontrado'); return; }
    state.candModal.aplicacionId = aplId;
    state.candModal.candidatoId = found.aplicacion.candidatoId;
    state.candModal.candidato = { id: found.aplicacion.candidatoId, nombre: found.aplicacion.nombre };
    state.candModal.aplicacion = { id: found.aplicacion.id, lado: found.aplicacion.lado || 'ARQA', etapa: found.aplicacion.etapa || '' };
    candModal._renderForm();
    document.getElementById('candOverlay').classList.add('open');
    // Fetch full profile
    api._json('/api/candidato-profile/' + aplId).then(function (profile) {
      if (!profile || state.candModal.aplicacionId !== aplId) return;
      state.candModal.candidato = profile.candidato || state.candModal.candidato;
      state.candModal.aplicacion = profile.aplicacion || state.candModal.aplicacion;
      candModal._renderForm();
    }).catch(function () {});
  },
  close: function () { document.getElementById('candOverlay').classList.remove('open'); },
  save: function () {
    var payload = candModal._collectData();
    if (!payload.candidato.nombre || !payload.candidato.nombre.trim()) { utils.toast('⚠️ Nombre requerido'); return; }
    api.saveCandidatoProfile({ aplicacionId: state.candModal.aplicacionId, candidatoId: state.candModal.candidatoId, candidato: payload.candidato, aplicacion: { lado: payload.lado, etapa: payload.etapa } });
  },
  remove: function () { if (state.candModal.aplicacionId) api.removeCandidato(state.candModal.aplicacionId); },
  setLado: function (val) { state.candModal.aplicacion.lado = val; candModal._renderLado(); },
  _collectData: function () {
    var candidato = {};
    state.candidatoFields.forEach(function (f) { var el = document.getElementById('cf-' + f.key); if (el) candidato[f.key] = el.value; });
    var etapaEl = document.getElementById('c-etapa-select');
    var etapa = etapaEl ? etapaEl.value : (state.candModal.aplicacion.etapa || '');
    var ladoEl = document.querySelector('#c-lado-control .lado-opt.selected');
    var lado = ladoEl ? ladoEl.dataset.val : (state.candModal.aplicacion.lado || 'ARQA');
    return { candidato: candidato, etapa: etapa, lado: lado };
  },
  _renderForm: function () {
    var cand = state.candModal.candidato || {}, app = state.candModal.aplicacion || {};
    var groups = {}, groupOrder = [];
    state.candidatoFields.forEach(function (f) {
      if (!groups[f.group]) { groups[f.group] = []; groupOrder.push(f.group); }
      groups[f.group].push(f);
    });
    var fieldsHtml = groupOrder.map(function (gn) {
      return '<div class="profile-section"><div class="profile-group-title">' + esc(gn) + '</div>' + groups[gn].map(function (f) { return candModal._renderField(f, cand[f.key]); }).join('') + '</div>';
    }).join('');
    var appHtml = '<div class="profile-section"><div class="profile-group-title">Aplicación a esta vacante</div>' +
      '<div class="field"><label>Lado</label><div class="lado-control" id="c-lado-control"><button type="button" class="lado-opt" data-val="ARQA">Con ARQA</button><button type="button" class="lado-opt" data-val="Cliente">Con Cliente</button></div></div>' +
      '<div class="field"><label>Etapa del proceso</label><select id="c-etapa-select"><option value="">— sin asignar —</option>' +
      state.etapas.map(function (e) { return '<option value="' + esc(e.key) + '"' + (e.key === (app.etapa || '') ? ' selected' : '') + '>' + esc(e.label) + '</option>'; }).join('') +
      '</select></div></div>';
    document.getElementById('cand-body').innerHTML = fieldsHtml + appHtml;
    document.querySelectorAll('#c-lado-control .lado-opt').forEach(function (btn) {
      btn.addEventListener('click', function () { candModal.setLado(btn.dataset.val); });
    });
    candModal._renderLado();
  },
  _renderField: function (field, value) {
    value = value != null ? value : '';
    var id = 'cf-' + field.key, ph = field.placeholder ? ' placeholder="' + esc(field.placeholder) + '"' : '';
    if (field.type === 'textarea') return '<div class="field"><label>' + esc(field.label) + '</label><textarea id="' + id + '"' + ph + '>' + esc(value) + '</textarea></div>';
    if (field.type === 'owner-select') {
      var opts = '<option value="">— sin asignar —</option>' + state.owners.map(function (o) { return '<option value="' + esc(o.id) + '"' + (o.id === value ? ' selected' : '') + '>' + esc(o.nombre) + '</option>'; }).join('');
      return '<div class="field"><label>' + esc(field.label) + '</label><select id="' + id + '">' + opts + '</select></div>';
    }
    var t = ({ email: 'email', tel: 'tel', url: 'url', number: 'number', date: 'date' })[field.type] || 'text';
    return '<div class="field"><label>' + esc(field.label) + (field.required ? ' *' : '') + '</label><input type="' + t + '" id="' + id + '" value="' + esc(value) + '"' + ph + '></div>';
  },
  _renderLado: function () {
    var val = state.candModal.aplicacion.lado || 'ARQA';
    document.querySelectorAll('#c-lado-control .lado-opt').forEach(function (btn) { btn.classList.toggle('selected', btn.dataset.val === val); });
  }
};

// ── Owner Modal ─────────────────────────────────────────────
var OWNER_COLORS = ['teal','blue','violet','pink','amber','emerald','rose','indigo','orange','slate'];
var ownerModal = {
  open: function () { document.getElementById('ownersOverlay').classList.add('open'); ownerModal.showList(); },
  close: function () { document.getElementById('ownersOverlay').classList.remove('open'); },
  showList: function () {
    document.getElementById('owners-list-view').style.display = '';
    document.getElementById('owners-edit-view').style.display = 'none';
    ownerModal._renderList();
  },
  showEdit: function (owner) {
    state.ownerModal.editingId = owner ? owner.id : null;
    state.ownerModal.color = owner ? owner.color : 'teal';
    document.getElementById('oTitle').textContent = owner ? 'Editar owner' : 'Nuevo owner';
    document.getElementById('o-nombre').value = owner ? owner.nombre : '';
    document.getElementById('oBtnDelete').style.display = owner ? '' : 'none';
    ownerModal._renderColors();
    document.getElementById('owners-list-view').style.display = 'none';
    document.getElementById('owners-edit-view').style.display = '';
    document.getElementById('o-nombre').focus();
  },
  newOwner: function () { ownerModal.showEdit(null); },
  save: function () {
    var nombre = document.getElementById('o-nombre').value.trim();
    if (!nombre) { utils.toast('⚠️ Nombre requerido'); return; }
    api.saveOwner({ id: state.ownerModal.editingId, nombre: nombre, color: state.ownerModal.color });
  },
  remove: function () { if (state.ownerModal.editingId) api.removeOwner(state.ownerModal.editingId); },
  setColor: function (color) { state.ownerModal.color = color; ownerModal._renderColors(); },
  _renderList: function () {
    var el = document.getElementById('owners-list');
    if (!state.owners.length) { el.innerHTML = '<div class="owner-empty">Sin owners aún. Crea el primero ↓</div>'; return; }
    el.innerHTML = state.owners.map(function (o) {
      return '<div class="owner-row"><div class="owner-row-swatch sw-' + esc(o.color) + '"></div><span class="owner-row-name">' + esc(o.nombre) + '</span><div class="owner-row-actions"><button class="owner-icon-btn" onclick="ARQA.ownerEdit(\'' + esc(o.id) + '\')">Editar</button></div></div>';
    }).join('');
  },
  _renderColors: function () {
    document.getElementById('o-color-picker').innerHTML = OWNER_COLORS.map(function (c) {
      return '<div class="color-swatch sw-' + c + (c === state.ownerModal.color ? ' selected' : '') + '" onclick="ARQA.ownerSetColor(\'' + c + '\')" title="' + c + '"></div>';
    }).join('');
  }
};

// ── Filter listeners & Init ─────────────────────────────────
function setupFilters() {
  document.getElementById('groupBy').addEventListener('change', function (e) { state.filter.group = e.target.value; render.all(); });
  document.querySelectorAll('#f-prio-control .prio-opt').forEach(function (btn) {
    btn.addEventListener('click', function () { modal.setPrio(btn.dataset.val); });
  });
  document.getElementById('overlay').addEventListener('click', function (e) { if (e.target === this) modal.close(); });
  document.getElementById('ownersOverlay').addEventListener('click', function (e) { if (e.target === this) ownerModal.close(); });
  document.getElementById('candOverlay').addEventListener('click', function (e) { if (e.target === this) candModal.close(); });
}

document.getElementById('weekBadge').textContent = utils.weekLabel();
setupFilters();
api.load(render.all);

// ── Public API ──────────────────────────────────────────────
return {
  openNew: modal.openNew,
  openEdit: function (id) { modal.open(state.vacantes.find(function (v) { return v.id === id; })); },
  closeModal: modal.close, saveModal: modal.save, deleteModal: modal.remove,
  addCand: modal.addCand, rmCand: modal.rmCand,
  toggleStatus: function (id, s) { api.toggleStatus(id, s); },
  addStep: modal.addStep, rmStep: modal.rmStep, toggleStep: modal.toggleStep,
  openCand: candModal.open, closeCand: candModal.close, candSave: candModal.save, candDelete: candModal.remove,
  openOwners: ownerModal.open, closeOwners: ownerModal.close,
  ownerNew: ownerModal.newOwner,
  ownerEdit: function (id) { ownerModal.showEdit(state.owners.find(function (o) { return o.id === id; })); },
  ownerBack: ownerModal.showList, ownerSave: ownerModal.save, ownerDelete: ownerModal.remove, ownerSetColor: ownerModal.setColor
};
})();
