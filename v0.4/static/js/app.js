// Theme toggle (light/dark, persists in localStorage)
// Initial application happens in <head> inline script to prevent FOUC.
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var current = document.documentElement.getAttribute('data-theme') || 'light';
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('vaecos.theme', next); } catch (e) {}
    });
  });
})();

// Sidebar collapse toggle (persists in localStorage)
(function () {
  var STORAGE_KEY = 'vaecos.sidebarCollapsed';
  function applyState(collapsed) {
    var app = document.querySelector('.app');
    if (!app) return;
    if (collapsed) app.classList.add('sidebar-collapsed');
    else app.classList.remove('sidebar-collapsed');
  }
  // Apply saved state ASAP (before DOMContentLoaded would also work, but app.js is at end of body)
  try { applyState(localStorage.getItem(STORAGE_KEY) === '1'); } catch (e) {}

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('sidebarToggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var app = document.querySelector('.app');
      if (!app) return;
      var nowCollapsed = !app.classList.contains('sidebar-collapsed');
      applyState(nowCollapsed);
      try { localStorage.setItem(STORAGE_KEY, nowCollapsed ? '1' : '0'); } catch (e) {}
    });
  });
})();

// Guide state quick-edit (β2) — atomic write to Notion + local + audit
function _saveGuideState(selectEl, statusEl) {
  var guia = selectEl.dataset.guia;
  var newState = selectEl.value;
  var prevState = selectEl.dataset.prev;
  if (newState === prevState) return;

  selectEl.disabled = true;
  if (statusEl) statusEl.textContent = 'Guardando…';
  selectEl.style.opacity = '0.6';

  var fd = new FormData();
  fd.append('estado', newState);

  fetch('/guides/' + encodeURIComponent(guia) + '/state', {
    method: 'POST',
    body: fd,
    credentials: 'same-origin',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
    .then(function (resp) {
      if (!resp.ok || !resp.json.ok) throw new Error(resp.json.error || 'Error desconocido');
      // Update the canonical value (Notion may have case-corrected it)
      var canonical = resp.json.valor_nuevo;
      selectEl.dataset.prev = canonical;
      // If canonical differs from selected, update the option
      for (var i = 0; i < selectEl.options.length; i++) {
        if (selectEl.options[i].value.toLowerCase() === canonical.toLowerCase()) {
          selectEl.selectedIndex = i;
          break;
        }
      }
      if (statusEl) {
        statusEl.textContent = '✓ Guardado';
        statusEl.style.color = 'var(--ok)';
        setTimeout(function () { statusEl.textContent = ''; statusEl.style.color = ''; }, 2000);
      }
      // Subtle row flash for quick-edit in the table
      var row = selectEl.closest('tr');
      if (row && !statusEl) {
        row.style.transition = 'background-color 0.6s ease';
        row.style.backgroundColor = 'var(--ok-soft)';
        setTimeout(function () { row.style.backgroundColor = ''; }, 1100);
      }
    })
    .catch(function (err) {
      // Revert select to previous value
      for (var i = 0; i < selectEl.options.length; i++) {
        if (selectEl.options[i].value === prevState) {
          selectEl.selectedIndex = i;
          break;
        }
      }
      if (statusEl) {
        statusEl.textContent = '✗ ' + err.message;
        statusEl.style.color = 'var(--danger)';
      } else {
        alert('No se pudo cambiar el estado: ' + err.message);
      }
    })
    .finally(function () {
      selectEl.disabled = false;
      selectEl.style.opacity = '';
    });
}

document.addEventListener('change', function (e) {
  var el = e.target;
  if (!el || !el.classList) return;
  if (el.classList.contains('estado-quick-edit')) {
    if (!confirm('¿Cambiar estado a "' + el.value + '"? Se va a actualizar también en Notion.')) {
      // revert
      for (var i = 0; i < el.options.length; i++) {
        if (el.options[i].value === el.dataset.prev) { el.selectedIndex = i; break; }
      }
      return;
    }
    _saveGuideState(el, null);
  } else if (el.classList.contains('estado-edit-detail')) {
    if (!confirm('¿Cambiar estado a "' + el.value + '"? Se va a actualizar también en Notion.')) {
      for (var i = 0; i < el.options.length; i++) {
        if (el.options[i].value === el.dataset.prev) { el.selectedIndex = i; break; }
      }
      return;
    }
    _saveGuideState(el, document.getElementById('stateUpdateStatus'));
  }
});

// Guide notes (β1) — AJAX create + delete + Ctrl+Enter shortcut
function _fmtNoteDate(iso) {
  // Server returns local-tz ISO already. Use directly for predictability.
  return iso ? iso.replace('T', ' ').slice(0, 16) : '';
}

function _escape(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function submitNote(event, guia) {
  event.preventDefault();
  var form = event.target;
  var ta = form.querySelector('textarea[name="body"]');
  var btn = form.querySelector('button[type="submit"]');
  var body = (ta.value || '').trim();
  if (!body) return false;

  if (btn) { btn.disabled = true; btn.textContent = 'Guardando…'; }

  var fd = new FormData();
  fd.append('body', body);

  fetch('/guides/' + encodeURIComponent(guia) + '/notes', {
    method: 'POST',
    body: fd,
    credentials: 'same-origin',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
    .then(function (resp) {
      if (!resp.ok || !resp.json.ok) throw new Error(resp.json.error || 'Error desconocido');
      var note = resp.json.note;
      var list = document.getElementById('notesList');
      var empty = document.getElementById('notesEmpty');
      if (empty) empty.remove();

      var li = document.createElement('li');
      li.className = 'note-item';
      li.dataset.noteId = note.id;
      li.innerHTML =
        '<div class="note-meta">' +
        '<span class="note-author">' + _escape(note.autor) + '</span>' +
        '<span class="note-date muted">· ' + _escape(_fmtNoteDate(note.created_at)) + '</span>' +
        '<button type="button" class="note-delete-btn" title="Borrar nota" ' +
        'onclick="deleteNote(' + note.id + ', \'' + _escape(guia).replace(/'/g, '\\\'') + '\')">×</button>' +
        '</div>' +
        '<div class="note-body">' + _escape(note.body) + '</div>';
      list.insertBefore(li, list.firstChild);

      ta.value = '';
      var counter = document.getElementById('notesCount');
      if (counter) counter.textContent = '(' + list.querySelectorAll('.note-item').length + ')';
    })
    .catch(function (err) {
      alert('No se pudo guardar la nota: ' + err.message);
    })
    .finally(function () {
      if (btn) { btn.disabled = false; btn.textContent = 'Agregar nota'; }
    });
  return false;
}

function deleteNote(noteId, guia) {
  if (!confirm('¿Borrar esta nota? Esta acción no se puede deshacer.')) return;
  fetch('/guides/' + encodeURIComponent(guia) + '/notes/' + noteId, {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
    .then(function (resp) {
      if (!resp.ok || !resp.json.ok) throw new Error(resp.json.error || 'Error desconocido');
      var li = document.querySelector('.note-item[data-note-id="' + noteId + '"]');
      if (li) li.remove();
      var list = document.getElementById('notesList');
      var counter = document.getElementById('notesCount');
      if (counter && list) counter.textContent = '(' + list.querySelectorAll('.note-item').length + ')';
      if (list && list.querySelectorAll('.note-item').length === 0) {
        var empty = document.createElement('li');
        empty.id = 'notesEmpty';
        empty.className = 'note-empty muted';
        empty.textContent = 'Sin notas todavía. Agregá la primera abajo.';
        list.appendChild(empty);
      }
    })
    .catch(function (err) {
      alert('No se pudo borrar la nota: ' + err.message);
    });
}

// Ctrl+Enter inside the note textarea submits the form
document.addEventListener('keydown', function (e) {
  if (e.key !== 'Enter' || !(e.ctrlKey || e.metaKey)) return;
  var ta = e.target;
  if (!ta || ta.tagName !== 'TEXTAREA') return;
  var form = ta.closest('.note-form');
  if (!form) return;
  e.preventDefault();
  if (typeof form.requestSubmit === 'function') form.requestSubmit();
  else form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
});

function toggleNotasForm(guia) {
  var form = document.getElementById('notas-form-' + guia);
  var text = document.getElementById('notas-text-' + guia);
  if (!form) return;
  if (form.style.display === 'none' || form.style.display === '') {
    form.style.display = 'block';
    if (text) text.style.display = 'none';
    var ta = form.querySelector('textarea');
    if (ta) ta.focus();
    var cell = form.closest('td');
    if (cell) cell.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'end' });
  } else {
    form.style.display = 'none';
    if (text) text.style.display = '';
  }
}

// AJAX submit for nota forms — keeps the page from scrolling to the top.
document.addEventListener('submit', function (e) {
  var form = e.target;
  if (!form.classList || !form.classList.contains('notas-form')) return;
  e.preventDefault();

  var btn = form.querySelector('button[type="submit"]');
  var originalLabel = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Guardando…'; }

  var fd = new FormData(form);
  fetch(form.action, {
    method: 'POST',
    body: fd,
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
  })
    .then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .then(function (data) {
      var guia = data.guia;
      var note = (data.notas_operador || '').trim();
      var span = document.getElementById('notas-text-' + guia);
      if (span) {
        if (note) {
          span.textContent = note;
        } else {
          span.innerHTML = '<span class="muted">—</span>';
        }
      }
      // Close the form and restore the text (without scrolling)
      form.style.display = 'none';
      if (span) span.style.display = '';
      // Subtle visual feedback that the save succeeded
      if (span) {
        span.style.transition = 'background-color 0.6s ease';
        span.style.backgroundColor = 'rgba(34, 197, 94, 0.18)';
        setTimeout(function () { span.style.backgroundColor = ''; }, 900);
      }
    })
    .catch(function (err) {
      alert('No se pudo guardar la nota: ' + err.message);
    })
    .finally(function () {
      if (btn) { btn.disabled = false; btn.textContent = originalLabel || 'Guardar'; }
    });
});
