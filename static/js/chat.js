/**
 * HooYia Market — chat.js
 * Client WebSocket pour le chat en temps réel.
 *
 * Fonctionnement :
 *   1. Charge l'historique des messages via GET /api/chat/<id>/
 *   2. Ouvre une connexion WebSocket ws://.../ws/chat/<id>/
 *   3. Envoie/reçoit des messages JSON en temps réel
 *   4. Gère les reconnexions automatiques (backoff exponentiel)
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
  let reconnectDelay  = 1000;   // ms, doublé à chaque échec
  const MAX_DELAY     = 30000;
  let reconnectTimer  = null;
  let isDestroyed     = false;

  // ── Éléments DOM ────────────────────────────────────────────
  const els = () => ({
    skeleton   : document.getElementById('skeleton'),
    list       : document.getElementById('messages-list'),
    anchor     : document.getElementById('scroll-anchor'),
    input      : document.getElementById('message-input'),
    sendBtn    : document.getElementById('send-btn'),
    statusDot  : document.getElementById('status-dot'),
    wsStatus   : document.getElementById('ws-status'),
  });

  // ── Initialisation ──────────────────────────────────────────
  async function init(cfg) {
    config = { ...config, ...cfg };
    isDestroyed = false;

    // Raccourci clavier : Entrée envoie, Maj+Entrée = nouvelle ligne
    document.getElementById('message-input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        envoyer();
      }
      // Auto-resize textarea
      setTimeout(autoResizeTextarea, 0);
    });

    document.getElementById('message-input')?.addEventListener('input', autoResizeTextarea);

    await chargerHistorique();
    connecterWebSocket();

    // Nettoyage à la fermeture de la page
    window.addEventListener('beforeunload', detruire);
  }

  // ── Chargement historique ────────────────────────────────────
  async function chargerHistorique() {
    const { skeleton, list } = els();
    try {
      const data = await API.get(`/api/chat/${config.conversationId}/`, { silentError: true });
      const messages = data.messages || [];

      skeleton?.classList.add('hidden');
      list?.classList.remove('hidden');

      if (messages.length === 0) {
        list.innerHTML = `
          <div class="text-center py-8">
            <p class="text-ink/30 font-body text-sm">${gettext('Démarrez la conversation 👋')}</p>
          </div>`;
      } else {
        list.innerHTML = messages.map(m => renderMessage(m)).join('');
      }

      scrollerBas(false);
    } catch(e) {
      skeleton?.classList.add('hidden');
      list?.classList.remove('hidden');
      if (e && e.status === 401) {
        window.location.href = '/compte/connexion/?next=/chat/';
      } else {
        list.innerHTML = `<p class="text-center text-ink/40 font-body text-sm py-8">${gettext('Impossible de charger les messages.')}</p>`;
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

    socket.addEventListener('close', (event) => {
      activerSaisie(false);
      if (!isDestroyed) {
        setStatut('disconnected');
        scheduleReconnect();
      }
    });

    socket.addEventListener('error', () => {
      // L'événement close suivra, on gère là-bas
    });
  }

  // ── Envoi d'un message ───────────────────────────────────────
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

    // Supprimer le message "Démarrez la conversation" si présent
    const placeholder = list.querySelector('.text-center');
    if (placeholder) placeholder.remove();

    // Construire l'objet message compatible avec renderMessage
    const msgObj = {
      expediteur      : data.expediteur_id,
      nom_expediteur  : data.expediteur,
      contenu         : data.message,
      date_envoi      : data.timestamp,
      message_id      : data.message_id,
    };

    const html = renderMessage(msgObj);
    list.insertAdjacentHTML('beforeend', html);
    scrollerBas(true);
  }

  // ── Rendu HTML d'un message ──────────────────────────────────
  function renderMessage(m) {
    const isMine   = parseInt(m.expediteur) === parseInt(config.currentUserId);
    const heure    = formatHeure(m.date_envoi);
    const contenu  = escapeHtml(m.contenu).replace(/\n/g, '<br>');

    if (isMine) {
      return `
      <div class="flex justify-end">
        <div class="max-w-[75%]">
          <div class="bg-brand-500 text-white px-4 py-2.5 rounded-2xl rounded-tr-sm shadow-btn text-sm font-body leading-relaxed">
            ${contenu}
          </div>
          <p class="text-right text-ink/25 font-mono text-[10px] mt-1 mr-1">${heure}</p>
        </div>
      </div>`;
    } else {
      return `
      <div class="flex justify-start gap-2.5">
        <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-300 to-brand-500 flex items-center justify-center text-white font-display font-bold text-xs flex-shrink-0 mt-auto mb-5">
          ${(m.nom_expediteur || '?')[0].toUpperCase()}
        </div>
        <div class="max-w-[75%]">
          <div class="bg-white border border-cream-border px-4 py-2.5 rounded-2xl rounded-tl-sm shadow-card text-sm font-body leading-relaxed text-ink">
            ${contenu}
          </div>
          <p class="text-ink/25 font-mono text-[10px] mt-1 ml-1">${heure}</p>
        </div>
      </div>`;
    }
  }

  // ── Scroll vers le bas ───────────────────────────────────────
  function scrollerBas(smooth = true) {
    const anchor = document.getElementById('scroll-anchor');
    if (anchor) {
      anchor.scrollIntoView({ behavior: smooth ? 'smooth' : 'instant' });
    }
  }

  // ── Statut de connexion ──────────────────────────────────────
  function setStatut(state) {
    const { statusDot, wsStatus } = els();
    const etats = {
      connecting   : { dot: 'bg-amber-400',  text: gettext('Connexion…') },
      connected    : { dot: 'bg-green-400',   text: gettext('Connecté') },
      disconnected : { dot: 'bg-red-400',     text: gettext('Déconnecté — Reconnexion…') },
    };
    const s = etats[state] || etats.disconnected;
    if (statusDot) statusDot.className = `w-2.5 h-2.5 rounded-full transition-colors duration-300 ${s.dot}`;
    if (wsStatus)  wsStatus.textContent = s.text;
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

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
  }

  // ── API publique ─────────────────────────────────────────────
  return { init, envoyer };

})();