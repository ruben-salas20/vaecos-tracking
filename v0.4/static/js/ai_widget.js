/* AI Widget — lógica del chat flotante.
 *
 * Estados: collapsed (burbujita) | expanded (panel).
 * Persistencia local: el estado de apertura se guarda en localStorage
 * para que se quede como el usuario lo dejó al navegar.
 *
 * Backend endpoints:
 *   POST /ai/chat          → enviar mensaje
 *   GET  /ai/chat/history  → obtener historial al abrir
 *   POST /ai/chat/clear    → limpiar
 */
(function () {
  'use strict';

  const root = document.getElementById('aiWidget');
  if (!root) return; // sin sesión

  const bubble = document.getElementById('aiWidgetToggle');
  const panel = document.getElementById('aiWidgetPanel');
  const closeBtn = document.getElementById('aiWidgetClose');
  const clearBtn = document.getElementById('aiWidgetClear');
  const messagesEl = document.getElementById('aiWidgetMessages');
  const typingEl = document.getElementById('aiWidgetTyping');
  const form = document.getElementById('aiWidgetForm');
  const textarea = document.getElementById('aiWidgetTextarea');
  const sendBtn = document.getElementById('aiWidgetSend');

  const STORAGE_KEY = 'vaecos.aiWidget.state';
  let isOpen = localStorage.getItem(STORAGE_KEY) === 'expanded';
  let isHydrated = false;
  let isBusy = false;

  // ── Helpers de UI ──────────────────────────────────────────────────

  function setState(open) {
    isOpen = open;
    root.setAttribute('data-state', open ? 'expanded' : 'collapsed');
    panel.hidden = !open;
    localStorage.setItem(STORAGE_KEY, open ? 'expanded' : 'collapsed');
    if (open && !isHydrated) {
      hydrate();
    }
    if (open) {
      // Pequeño defer para que el panel sea visible antes del scroll
      requestAnimationFrame(scrollToBottom);
      textarea.focus();
    }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderMessageHtml(text) {
    // Markdown ligero: **bold** y *italic* (sólo después de escape, para evitar XSS).
    let html = escapeHtml(text);
    // Triple backtick inline: `code`
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    // **bold** (no greedy)
    html = html.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    // *italic* — sólo si tiene texto sin asteriscos adyacentes
    html = html.replace(/(?<![*\w])\*([^*\n]+)\*(?!\w)/g, '<em>$1</em>');
    // Saltos de línea
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  function addMessage(role, content, opts) {
    opts = opts || {};
    const placeholder = messagesEl.querySelector('.ai-widget-msg-placeholder');
    if (placeholder) placeholder.remove();

    const wrap = document.createElement('div');
    wrap.className = 'ai-widget-msg ai-widget-msg-' + role + (opts.isError ? ' ai-widget-msg-error' : '');
    const bub = document.createElement('div');
    bub.className = 'ai-widget-msg-bubble';
    bub.innerHTML = role === 'assistant' ? renderMessageHtml(content) : escapeHtml(content).replace(/\n/g, '<br>');
    wrap.appendChild(bub);
    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function setBusy(busy) {
    isBusy = busy;
    typingEl.hidden = !busy;
    sendBtn.disabled = busy;
    textarea.disabled = busy;
  }

  // ── Hidratación del historial ──────────────────────────────────────

  async function hydrate() {
    try {
      const r = await fetch('/ai/chat/history');
      if (!r.ok) return;
      const data = await r.json();
      if (!data.ok || !Array.isArray(data.messages)) return;
      if (data.messages.length === 0) return; // mantiene placeholder
      const placeholder = messagesEl.querySelector('.ai-widget-msg-placeholder');
      if (placeholder) placeholder.remove();
      data.messages.forEach(function (m) {
        addMessage(m.role === 'user' ? 'user' : 'assistant', m.content);
      });
    } catch (e) {
      console.warn('AI widget hydrate failed:', e);
    } finally {
      isHydrated = true;
    }
  }

  // ── Enviar mensaje ─────────────────────────────────────────────────

  async function sendMessage(text) {
    if (!text || isBusy) return;
    addMessage('user', text);
    textarea.value = '';
    textarea.style.height = 'auto';
    setBusy(true);
    try {
      const r = await fetch('/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await r.json();
      if (!r.ok || !data.ok) {
        addMessage('assistant', data.error || data.answer || ('Error HTTP ' + r.status), { isError: true });
      } else {
        addMessage('assistant', data.answer || '(respuesta vacía)');
      }
    } catch (e) {
      addMessage('assistant', 'Error de red: ' + e.message, { isError: true });
    } finally {
      setBusy(false);
      textarea.focus();
    }
  }

  // ── Limpiar conversación ───────────────────────────────────────────

  async function clearHistory() {
    if (!confirm('¿Borrar toda la conversación con el asistente?')) return;
    try {
      const r = await fetch('/ai/chat/clear', { method: 'POST' });
      if (!r.ok) return;
      messagesEl.innerHTML =
        '<div class="ai-widget-msg ai-widget-msg-assistant ai-widget-msg-placeholder">' +
        '<div class="ai-widget-msg-bubble">Conversación borrada. ¿En qué te ayudo?</div></div>';
      isHydrated = true; // ya no hay nada para hidratar
    } catch (e) {
      console.warn('Clear failed:', e);
    }
  }

  // ── Auto-resize del textarea ───────────────────────────────────────

  function autoResize() {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 110) + 'px';
  }

  // ── Event listeners ────────────────────────────────────────────────

  bubble.addEventListener('click', function () { setState(true); });
  closeBtn.addEventListener('click', function () { setState(false); });
  clearBtn.addEventListener('click', clearHistory);

  textarea.addEventListener('input', autoResize);
  textarea.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const text = textarea.value.trim();
    if (text) sendMessage(text);
  });

  // ── Estado inicial ─────────────────────────────────────────────────
  // No abrimos automáticamente la primera vez para no asustar al usuario.
  // Si lo dejaste abierto, lo respetamos.
  if (isOpen) {
    setState(true);
  }
})();
