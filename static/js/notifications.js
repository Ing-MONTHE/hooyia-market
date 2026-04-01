/**
 * HooYia Market — notifications.js
 * Client WebSocket pour les notifications in-app en temps réel.
 *
 * Fonctionnement :
 *   1. Ouvre ws://.../ws/notifications/ dès le chargement de la page
 *   2. Reçoit le badge initial (notifications non lues) à la connexion
 *   3. Affiche les nouvelles notifications via window.toast()
 *   4. Met à jour le badge navbar en temps réel
 *   5. Reconnexion automatique avec backoff exponentiel
 *
 * Endpoints API utilisés :
 *   GET  /api/notifications/             → liste
 *   PATCH /api/notifications/<id>/lire/  → marquer une notif lue
 *   POST /api/notifications/tout_lire/   → tout marquer lu
 */

const Notifications = (() => {

  let socket         = null;
  let reconnectDelay = 1000;
  const MAX_DELAY    = 30000;
  let reconnectTimer = null;
  let isDestroyed    = false;

  // ── Icônes par type ──────────────────────────────────────────
  const ICONES = {
    commande : '📦',
    avis     : '⭐',
    stock    : '⚠️',
    systeme  : 'ℹ️',
  };

  // ── Initialisation ──────────────────────────────────────────
  function init() {
    // Ne démarrer que si l'utilisateur est connecté (badge présent dans le DOM)
    if (!document.getElementById('notif-badge')) return;

    connecterWebSocket();

    // Nettoyage à la fermeture de la page
    window.addEventListener('beforeunload', detruire);
  }

  // ── Connexion WebSocket ──────────────────────────────────────
  function connecterWebSocket() {
    if (isDestroyed) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url   = `${proto}://${window.location.host}/ws/notifications/`;

    try {
      socket = new WebSocket(url);
    } catch(e) {
      scheduleReconnect();
      return;
    }

    socket.addEventListener('open', () => {
      reconnectDelay = 1000;
    });

    socket.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch(e) {
        console.warn('[Notifications] Message invalide :', e);
      }
    });

    socket.addEventListener('close', () => {
      if (!isDestroyed) scheduleReconnect();
    });

    socket.addEventListener('error', () => {
      // L'événement close suivra
    });
  }

  // ── Traitement des messages reçus ────────────────────────────
  function handleMessage(data) {
    switch (data.type) {

      // Message initial à la connexion → met à jour le badge
      case 'init':
        mettreAJourBadge(data.unread_count);
        break;

      // Nouvelle notification → toast + badge
      case 'notification':
        mettreAJourBadge(data.unread_count);
        afficherToastNotif(data);
        break;
    }
  }

  // ── Mise à jour du badge navbar ──────────────────────────────
  function mettreAJourBadge(count) {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;

    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }

  // ── Toast notification in-app ────────────────────────────────
  function afficherToastNotif(data) {
    const icone = ICONES[data.type_notif] || 'ℹ️';
    const msg   = `${icone} <strong>${escapeHtml(data.titre)}</strong><br><span class="text-xs opacity-75">${escapeHtml(data.message)}</span>`;

    // Si window.toast() existe (défini dans partials/toast.html)
    if (window.toast) {
      window.toast(msg, 'info', {
        duration : 6000,
        onClick  : data.lien ? () => { window.location.href = data.lien; marquerLue(data.id); } : null,
      });
    }
  }

  // ── Marquer une notification comme lue ──────────────────────
  async function marquerLue(notifId) {
    try {
      const data = await API.patch(`/api/notifications/${notifId}/lire/`, {});
      if (data && data.unread_count !== undefined) {
        mettreAJourBadge(data.unread_count);
      }
    } catch(e) {
      console.warn('[Notifications] Erreur marquer lue :', e);
    }
  }

  // ── Marquer toutes les notifications comme lues ──────────────
  async function toutMarquerLu() {
    try {
      const data = await API.post('/api/notifications/tout_lire/', {});
      if (data && data.unread_count !== undefined) {
        mettreAJourBadge(data.unread_count);
      }
      // Mettre à jour l'UI si on est sur une page de notifications
      document.querySelectorAll('.notif-item.non-lue').forEach(el => {
        el.classList.remove('non-lue');
      });
    } catch(e) {
      console.warn('[Notifications] Erreur tout marquer lu :', e);
    }
  }

  // ── Charger la liste des notifications (pour dropdown/page) ──
  async function chargerListe(limit = 10) {
    try {
      const data = await API.get(`/api/notifications/?page_size=${limit}`, { silentError: true });
      return data.results || data || [];
    } catch(e) {
      return [];
    }
  }

  // ── Reconnexion automatique ──────────────────────────────────
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

  // ── Utilitaire ───────────────────────────────────────────────
  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
  }

  // ── Auto-init au chargement ──────────────────────────────────
  document.addEventListener('DOMContentLoaded', init);

  // ── API publique ─────────────────────────────────────────────
  return {
    marquerLue,
    toutMarquerLu,
    chargerListe,
    mettreAJourBadge,
  };

})();
