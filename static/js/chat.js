/**
 * HooYia Market — chat.js v2.0
 * Client WebSocket pour le chat en temps réel.
 *
 * Améliorations v2 :
 *   - Support messages de type "fichier" (images, documents)
 *   - Séparateurs de date automatiques entre les messages
 *   - Meilleur rendu visuel (bulles, avatars, statut)
 *   - Nouveaux IDs DOM (messages-skeleton, messages-list)
 *   - Indicateur status-dot avec classes CSS (connected/connecting/disconnected)
 *
 * API publique :
 *   Chat.init({ conversationId, currentUserId, currentUsername })
 *   Chat.envoyer()
 */

const Chat = (() => {

  // ── Config ──────────────────────────────────────────────────
  let config = {
    conversationId  : null,
    currentUserId   : null,
    currentUsername : '',
  };

  let socket          = null;
  let reconnectDelay  = 1000;
  const MAX_DELAY     = 30000;
  let reconnectTimer  = null;
  let isDestroyed     = false;
  let lastMessageDate = null; // Pour les séparateurs de date

  // ── Éléments DOM ────────────────────────────────────────────
  const els = () => ({
    skeleton   : document.getElementById('messages-skeleton'),
    list       : document.getElementById('messages-list'),
    anchor     : document.getElementById('scroll-anchor'),
    input      : document.getElementById('message-input'),
    sendBtn    : document.getElementById('send-btn'),
    statusDot  : document.getElementById('status-dot'),
    wsStatus   : document.getElementById('ws-status-text'),
  });

  // ── Initialisation ──────────────────────────────────────────
  async function init(cfg) {
    config = { ...config, ...cfg };
    isDestroyed = false;

    const inputEl = document.getElementById('message-input');

    // Raccourci clavier : Entrée envoie, Maj+Entrée = nouvelle ligne
    inputEl?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        Chat.envoyer();
      }
      setTimeout(autoResizeTextarea, 0);
    });

    inputEl?.addEventListener('input', autoResizeTextarea);

    // Bouton envoyer — click
    const sendBtnEl = document.getElementById('send-btn');
    sendBtnEl?.addEventListener('click', () => Chat.envoyer());

    await chargerHistorique();
    connecterWebSocket();

    window.addEventListener('beforeunload', detruire);
  }

  // ── Chargement historique ────────────────────────────────────
  async function chargerHistorique() {
    const { skeleton, list } = els();
    try {
      const data = await API.get(`/api/chat/${config.conversationId}/`, { silentError: true });
      const messages = data.messages || [];

      skeleton?.classList.add('hidden');
      if (skeleton) skeleton.style.display = 'none';
      if (list) list.style.display = '';

      lastMessageDate = null; // Reset pour les séparateurs

      if (messages.length === 0) {
        list.innerHTML = `
          <div class="messages-empty">
            <div class="messages-empty-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <p style="font-size:0.875rem;font-weight:600;color:var(--text-secondary);">${gettext('Démarrez la conversation 👋')}</p>
            <p style="font-size:0.75rem;color:var(--text-muted);max-width:240px;line-height:1.5;">${gettext('Envoyez un message ou partagez un fichier.')}</p>
          </div>`;
      } else {
        list.innerHTML = messages.map(m => renderMessage(normaliserMessage(m))).join('');
      }

      scrollerBas(false);
    } catch(e) {
      if (skeleton) skeleton.style.display = 'none';
      if (list) list.style.display = '';
      if (e && e.status === 401) {
        window.location.href = '/compte/connexion/?next=/chat/';
      } else {
        const { list } = els();
        if (list) {
          list.innerHTML = `
            <div class="messages-empty">
              <p style="color:var(--text-muted);font-size:0.875rem;">${gettext('Impossible de charger les messages.')}</p>
            </div>`;
        }
      }
    }
  }

  // ── Connexion WebSocket ──────────────────────────────────────
  function connecterWebSocket() {
    if (isDestroyed) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url   = `${proto}://${window.location.host}/ws/chat/${config.conversationId}/`;

    setStatut('connecting');

    try {
      socket = new WebSocket(url);
    } catch(e) {
      scheduleReconnect();
      return;
    }

    socket.addEventListener('open', () => {
      reconnectDelay = 1000;
      setStatut('connected');
      activerSaisie(true);
    });

    socket.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        ajouterMessage(data);
      } catch(e) {
        console.warn('[Chat] Message invalide :', e);
      }
    });

    socket.addEventListener('close', () => {
      activerSaisie(false);
      if (!isDestroyed) {
        setStatut('disconnected');
        scheduleReconnect();
      }
    });

    socket.addEventListener('error', () => {
      // L'événement close suivra
    });
  }

  // ── Envoi d'un message texte ─────────────────────────────────
  function envoyer() {
    const { input } = els();
    if (!input) return;

    const contenu = input.value.trim();
    if (!contenu) return;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      window.toast && window.toast(gettext('Connexion perdue. Reconnexion en cours…'), 'warning');
      return;
    }

    socket.send(JSON.stringify({ message: contenu }));
    input.value = '';
    autoResizeTextarea();
    input.focus();
  }

  // ── Ajouter un message reçu via WS ──────────────────────────
  function ajouterMessage(data) {
    const { list } = els();
    if (!list) return;

    // Supprimer l'état vide si présent
    const emptyState = list.querySelector('.messages-empty');
    if (emptyState) emptyState.remove();

    // Normalize WS payload to API shape
    const msgObj = normaliserMessage({
      expediteur     : data.expediteur_id,
      nom_expediteur : data.expediteur,
      contenu        : data.message,
      date_envoi     : data.timestamp,
      type_message   : data.msg_type || data.type || 'text',
      fichier        : data.fichier_url ? {
        url         : data.fichier_url,
        nom_original: data.fichier_nom,
        taille      : data.fichier_taille,
        est_image   : (data.msg_type === 'image' || data.type === 'image'),
      } : null,
    });

    const html = renderMessage(msgObj);
    list.insertAdjacentHTML('beforeend', html);
    scrollerBas(true);
  }


  // ── Normalise un message (API ou WS) vers un format uniforme ──
  function normaliserMessage(m) {
    const f = m.fichier || null;
    return {
      expediteur    : m.expediteur,
      nom_expediteur: m.nom_expediteur || m.expediteur,
      contenu       : m.contenu || '',
      date_envoi    : m.date_envoi,
      type          : m.type_message || m.type || 'text',
      fichier_url   : f ? (f.url || f.fichier_url || null) : null,
      fichier_nom   : f ? (f.nom_original || f.nom || null) : null,
      fichier_taille: f ? (f.taille || null) : null,
    };
  }

  // ── Rendu HTML d'un message ──────────────────────────────────
  function renderMessage(m) {
    const isMine  = parseInt(m.expediteur) === parseInt(config.currentUserId);
    const heure   = formatHeure(m.date_envoi);
    const initiale = (m.nom_expediteur || '?')[0].toUpperCase();
    const type    = m.type || 'text';

    let separator = '';
    const msgDate = m.date_envoi ? new Date(m.date_envoi) : null;
    if (msgDate) {
      const dateKey = msgDate.toLocaleDateString('fr-FR');
      if (dateKey !== lastMessageDate) {
        lastMessageDate = dateKey;
        separator = `
          <div class="date-separator">
            <span class="date-label">${formatDateLabel(msgDate)}</span>
          </div>`;
      }
    }

    let bubbleContent = '';

    if (type === 'image' && m.fichier_url) {
      // ── Image ──
      bubbleContent = `
        <div class="msg-bubble" style="${isMine ? '' : ''}">
          ${m.contenu ? `<p style="margin-bottom:0.375rem;">${escapeHtml(m.contenu).replace(/\n/g, '<br>')}</p>` : ''}
          <img src="${escapeHtml(m.fichier_url)}" alt="${escapeHtml(m.fichier_nom || 'Image')}" class="msg-image"
               onclick="openImageModal(this.src)" loading="lazy" style="cursor:zoom-in;" />
        </div>`;
    } else if (type === 'file' && m.fichier_url) {
      // ── Document ──
      const taille = m.fichier_taille ? formatFileSize(m.fichier_taille) : '';
      bubbleContent = `
        ${m.contenu ? `<div class="msg-bubble">${escapeHtml(m.contenu).replace(/\n/g, '<br>')}</div>` : ''}
        <a href="${escapeHtml(m.fichier_url)}" class="msg-file" target="_blank" download="${escapeHtml(m.fichier_nom || 'fichier')}">
          <div class="file-icon-wrap">
            ${getFileIconSVG(m.fichier_nom)}
          </div>
          <div class="file-meta">
            <p class="file-name">${escapeHtml(m.fichier_nom || 'Document')}</p>
            ${taille ? `<p class="file-size">${taille}</p>` : ''}
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;opacity:0.6;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
        </a>`;
    } else {
      // ── Texte ──
      const contenu = escapeHtml(m.contenu || '').replace(/\n/g, '<br>');
      bubbleContent = `<div class="msg-bubble">${contenu}</div>`;
    }

    if (isMine) {
      return `${separator}
      <div class="msg-row mine">
        <div class="msg-bubble-wrap">
          ${bubbleContent}
          <p class="msg-time">${heure}</p>
        </div>
      </div>`;
    } else {
      return `${separator}
      <div class="msg-row theirs">
        <div class="msg-sender-avatar">${escapeHtml(initiale)}</div>
        <div class="msg-bubble-wrap">
          ${bubbleContent}
          <p class="msg-time">${heure}</p>
        </div>
      </div>`;
    }
  }

  // ── Icône fichier selon l'extension ─────────────────────────
  function getFileIconSVG(filename) {
    const ext = (filename || '').split('.').pop().toLowerCase();
    const colors = {
      pdf:  '#ef4444',
      doc:  '#2563eb', docx: '#2563eb',
      xls:  '#16a34a', xlsx: '#16a34a',
      zip:  '#d97706', rar: '#d97706',
      txt:  '#6b7280', csv: '#6b7280',
    };
    const color = colors[ext] || '#6b7280';

    if (['jpg','jpeg','png','gif','webp'].includes(ext)) {
      return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>`;
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/></svg>`;
  }

  // ── Taille fichier lisible ───────────────────────────────────
  function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '';
    if (bytes < 1024)        return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // ── Scroll vers le bas ───────────────────────────────────────
  function scrollerBas(smooth = true) {
    const container = document.getElementById('messages-container');
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
    }
  }

  // ── Statut de connexion ──────────────────────────────────────
  function setStatut(state) {
    const { statusDot, wsStatus } = els();
    const etats = {
      connecting   : { cls: 'connecting',   text: gettext('Connexion…') },
      connected    : { cls: 'connected',    text: gettext('Connecté') },
      disconnected : { cls: 'disconnected', text: gettext('Déconnecté — Reconnexion…') },
    };
    const s = etats[state] || etats.disconnected;

    if (statusDot) {
      statusDot.className = `status-dot ${s.cls}`;
    }
    if (wsStatus) wsStatus.textContent = s.text;
  }

  // ── Activer/désactiver la saisie ─────────────────────────────
  function activerSaisie(actif) {
    const { input, sendBtn } = els();
    if (input)   input.disabled   = !actif;
    if (sendBtn) sendBtn.disabled = !actif;
    if (actif && input) input.focus();
  }

  // ── Reconnexion automatique (backoff expo) ───────────────────
  function scheduleReconnect() {
    if (isDestroyed) return;
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY);
      connecterWebSocket();
    }, reconnectDelay);
  }

  // ── Nettoyage ────────────────────────────────────────────────
  function detruire() {
    isDestroyed = true;
    clearTimeout(reconnectTimer);
    if (socket) {
      socket.close();
      socket = null;
    }
  }

  // ── Auto-resize textarea ─────────────────────────────────────
  function autoResizeTextarea() {
    const input = document.getElementById('message-input');
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }

  // ── Utilitaires ──────────────────────────────────────────────
  function formatHeure(isoStr) {
    if (!isoStr) return '';
    const d   = new Date(isoStr);
    const now = new Date();
    const locale = document.documentElement.lang || 'fr-FR';
    if (now - d < 86400000) {
      return d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString(locale, { day: 'numeric', month: 'short' });
  }

  function formatDateLabel(date) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const msgDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

    if (msgDay.getTime() === today.getTime()) return 'Aujourd\'hui';
    if (msgDay.getTime() === yesterday.getTime()) return 'Hier';
    return date.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
  }

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
  }

  // ── API publique ─────────────────────────────────────────────
  return { init, envoyer };

})();