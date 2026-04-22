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
