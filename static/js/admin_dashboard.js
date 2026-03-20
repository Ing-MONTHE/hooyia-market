/* ============================================================
   HooYia Market — static/js/admin_dashboard.js
   ============================================================
   Script principal du dashboard d'administration.
   Chargé via {% static 'js/admin_dashboard.js' %} dans admin_base.html,
   APRÈS la définition de window.DASH_I18N.

   SOMMAIRE :
     1.  Navigation SPA (navTo, registerSection, registerLoader)
     2.  Sidebar toggle (mobile)
     3.  Helpers globaux (fmtPrice, fmtDate, timeAgo, escHtml, debounce, renderPagination)
     4.  Badges & KPIs (setKpi, updateBadge, setText)
     5.  Recherche globale (onGlobalSearch, Ctrl+K)
     6.  Notifications dropdown
     7.  Modale de confirmation (showConfirm)
     8.  Toast de feedback (showToast)
     9.  loadOverview — vue d'ensemble
     10. loadProduits — catalogue produits
     11. loadCommandes — commandes avec FSM
     12. loadUsers — gestion comptes
     13. loadAvis — modération avis
     14. loadStocks — niveaux de stock
     15. loadCategories — arborescence MPTT
     16. loadPaniers — paniers actifs
     17. loadMessages — conversations chat
     18. loadNotifs — notifications
     19. loadAudit — journal d'audit
     20. Formulaire produit (submit, édition, suppression)
     21. Formulaire catégorie (submit, édition, suppression)
     22. Modale stock (open, close, submit)
     23. Modale catégorie rapide (openModalCat, submitModalCat)
     24. Initialisation DOMContentLoaded
   ============================================================ */

(function () {
  'use strict';

  /* ============================================================
     1. NAVIGATION SPA
     Système SPA : chaque section est un groupe d'éléments DOM
     masqués/affichés par navTo(). Pas de rechargement de page.
     ============================================================ */

  /**
   * Registre central des sections.
   * Clé = sectionId, valeur = { ids: [...], display: { id: 'flex'|'grid'|'' } }
   * Alimenté par registerSection() depuis les scripts.
   */
  window.DA_SECTIONS = {};

  /**
   * registerSection(sectionId, ids, displayOverrides)
   * Enregistre une section et ses éléments DOM.
   * @param {string}   sectionId       identifiant (ex: 'produits')
   * @param {string[]} ids             liste des IDs à afficher/masquer
   * @param {Object}   displayOverrides valeur display pour chaque id (défaut : 'block')
   */
  window.registerSection = function (sectionId, ids, displayOverrides) {
    window.DA_SECTIONS[sectionId] = {
      ids: ids || [],
      display: displayOverrides || {}
    };
  };

  /** Registre des loaders : fonction appelée lors de l'activation d'une section */
  window.DA_LOADERS = {};
  window.registerLoader = function (sectionId, fn) {
    window.DA_LOADERS[sectionId] = fn;
  };

  /**
   * navTo(sectionId) — Navigue vers une section du dashboard.
   * 1. Masque toutes les sections enregistrées
   * 2. Masque les da-section classiques (overview)
   * 3. Affiche les éléments de la section cible
   * 4. Met à jour l'item actif dans la sidebar
   * 5. Ferme la sidebar mobile
   * 6. Met à jour l'URL (#sectionId)
   * 7. Appelle le loader de données si enregistré
   * 8. Scroll en haut du contenu
   */
  window.navTo = function (sectionId) {
    /* 1. Masquer toutes les sections enregistrées */
    Object.keys(window.DA_SECTIONS).forEach(function (sid) {
      window.DA_SECTIONS[sid].ids.forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
      });
    });

    /* 2. Masquer les da-section classiques (overview) */
    document.querySelectorAll('.da-section.shown').forEach(function (s) {
      s.classList.remove('shown');
    });

    /* 3. Afficher la section cible */
    var sec = window.DA_SECTIONS[sectionId];
    if (sec) {
      sec.ids.forEach(function (id) {
        var el = document.getElementById(id);
        if (!el) return;
        var d = sec.display[id];
        el.style.display = (d !== undefined && d !== '') ? d : 'block';
      });
    } else {
      /* Fallback : da-section classique (overview) */
      var target = document.getElementById('sec-' + sectionId);
      if (target) target.classList.add('shown');
    }

    /* 4. Sidebar : item actif */
    document.querySelectorAll('.sb-item').forEach(function (b) {
      b.classList.remove('active');
    });
    var activeItem = document.querySelector('.sb-item[data-section="' + sectionId + '"]');
    if (activeItem) activeItem.classList.add('active');

    /* 5. Fermer la sidebar mobile */
    if (window.innerWidth < 1024) closeSidebar();

    /* 6. URL history */
    if (history.pushState) {
      history.pushState({ section: sectionId }, '', '#' + sectionId);
    }

    /* 7. Loader de données */
    if (window.DA_LOADERS && window.DA_LOADERS[sectionId]) {
      window.DA_LOADERS[sectionId]();
    }

    /* 8. Scroll top du contenu */
    var main = document.getElementById('da-main-content');
    if (main) main.scrollTop = 0;
  };

  /* Restaurer la section depuis le hash URL (#commandes, #produits…) */
  function restoreSection() {
    var hash = window.location.hash.replace('#', '');
    if (hash) {
      navTo(hash);
    } else {
      /* Par défaut : charger l'overview */
      loadOverview();
    }
  }

  /* Bouton précédent du navigateur */
  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.section) navTo(e.state.section);
  });

  /* Enregistrement des sections */
  window.registerSection('produits',
    ['sec-produits-header', 'sec-produits-card'],
    { 'sec-produits-header': 'flex' });

  window.registerSection('ajouter-produit',
    ['sec-ajout-prod-header', 'ap-flash', 'ap-form-wrapper'],
    { 'sec-ajout-prod-header': 'flex' });

  window.registerSection('commandes',
    ['sec-commandes-header', 'sec-commandes-filters', 'sec-commandes-card'],
    { 'sec-commandes-header': 'flex', 'sec-commandes-filters': 'flex' });

  window.registerSection('utilisateurs',
    ['sec-users-header', 'sec-users-filters', 'sec-users-card'],
    { 'sec-users-header': 'flex', 'sec-users-filters': 'flex' });

  window.registerSection('avis',
    ['sec-avis-header', 'sec-avis-filters', 'sec-avis-card'],
    { 'sec-avis-header': 'flex', 'sec-avis-filters': 'flex' });

  window.registerSection('stocks',
    ['sec-stocks-header', 'sec-stocks-kpis', 'sec-stocks-filters', 'sec-stocks-card'],
    { 'sec-stocks-header': 'flex', 'sec-stocks-kpis': 'grid', 'sec-stocks-filters': 'flex' });

  window.registerSection('categories',
    ['sec-categories-header', 'sec-categories-card'],
    { 'sec-categories-header': 'flex' });

  window.registerSection('ajouter-categorie',
    ['sec-ajout-cat-header', 'cat-flash', 'cat-form-wrapper'],
    { 'sec-ajout-cat-header': 'flex' });

  window.registerSection('paniers',
    ['sec-paniers-header', 'sec-paniers-card'],
    { 'sec-paniers-header': 'flex' });

  window.registerSection('messages',
    ['sec-messages-header', 'sec-messages-card'],
    { 'sec-messages-header': 'flex' });

  window.registerSection('notifications',
    ['sec-notifications-header', 'sec-notifications-card'],
    { 'sec-notifications-header': 'flex' });

  window.registerSection('audit',
    ['sec-audit-header', 'sec-audit-card'],
    { 'sec-audit-header': 'flex' });

  /* Loaders enregistrés pour chaque section */
  window.registerLoader('overview',          function () { loadOverview(); });
  window.registerLoader('produits',          function () { loadProduits(1); });
  window.registerLoader('commandes',         function () { loadCommandes(1); });
  window.registerLoader('utilisateurs',      function () { loadUsers(1); });
  window.registerLoader('avis',              function () { loadAvis(1); });
  window.registerLoader('stocks',            function () { loadStocks(1); });
  window.registerLoader('categories',        function () { loadCategories(); });
  window.registerLoader('ajouter-categorie', function () { resetCatForm(); });
  window.registerLoader('ajouter-produit',   function () { resetProduitForm(); });
  window.registerLoader('paniers',           function () { loadPaniers(); });
  window.registerLoader('messages',          function () { loadMessages(); });
  window.registerLoader('notifications',     function () { loadNotifs(1); });
  window.registerLoader('audit',             function () { loadAudit(1); });


  /* ============================================================
     2. SIDEBAR TOGGLE (mobile)
     ============================================================ */

  window.toggleSidebar = function () {
    if (document.body.classList.contains('da-sidebar-open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  };

  window.openSidebar = function () {
    document.body.style.top = '-' + window.scrollY + 'px';
    document.body.classList.add('da-sidebar-open');
    var btn = document.getElementById('da-burger-btn');
    if (btn) btn.setAttribute('aria-expanded', 'true');
  };

  window.closeSidebar = function () {
    var scrollY = Math.abs(parseInt(document.body.style.top || '0', 10));
    document.body.classList.remove('da-sidebar-open');
    document.body.style.top = '';
    window.scrollTo(0, scrollY);
    var btn = document.getElementById('da-burger-btn');
    if (btn) btn.setAttribute('aria-expanded', 'false');
  };


  /* ============================================================
     3. HELPERS GLOBAUX
     ============================================================ */

  /**
   * fmtPrice(p) — Formater un nombre en prix FCFA
   * Ex: 150000 → "150 000 FCFA"
   */
  window.fmtPrice = function (p) {
    return parseFloat(p || 0).toLocaleString('fr-FR') + ' FCFA';
  };

  /**
   * fmtDate(iso) — Formater une date ISO en français court
   * Ex: "2025-03-06T14:30:00Z" → "6 mars 2025"
   */
  window.fmtDate = function (iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: 'numeric', month: 'short', year: 'numeric'
    });
  };

  /**
   * timeAgo(iso) — Temps relatif
   * Ex: "il y a 2h", "il y a 3j"
   */
  window.timeAgo = function (iso) {
    var diff = Date.now() - new Date(iso).getTime();
    if (diff < 60000) return 'À l\'instant';
    if (diff < 3600000) return Math.floor(diff / 60000) + ' min';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h';
    return Math.floor(diff / 86400000) + 'j';
  };

  /**
   * renderStatut(statut) — Badge HTML coloré selon le statut commande
   */
  window.renderStatut = function (s) {
    var map = {
      en_attente:     ['st-wait',   'En attente'],
      confirmee:      ['st-conf',   'Confirmée'],
      en_preparation: ['st-prep',   'En préparation'],
      expediee:       ['st-ship',   'Expédiée'],
      livree:         ['st-done',   'Livrée'],
      annulee:        ['st-cancel', 'Annulée']
    };
    var d = map[s] || ['st-off', s];
    return '<span class="st ' + d[0] + '">' + d[1] + '</span>';
  };

  /**
   * renderStatutProduit(statut) — Badge pour statut produit
   */
  window.renderStatutProduit = function (s) {
    var I = window.DASH_I18N || {};
    var map = {
      actif:   ['st-pub',   I.actif   || 'Actif'],
      inactif: ['st-draft', I.inactif || 'Inactif'],
      epuise:  ['st-out',   'Épuisé'],
      archive: ['st-draft', 'Archivé']
    };
    var d = map[s] || ['st-off', s];
    return '<span class="st ' + d[0] + '">' + d[1] + '</span>';
  };

  /**
   * renderStars(note) — Étoiles HTML (1-5)
   */
  window.renderStars = function (n) {
    n = parseInt(n) || 0;
    return '<span style="color:var(--yellow);font-size:13px;letter-spacing:1px;">'
      + '★'.repeat(Math.min(n, 5)) + '</span>'
      + '<span style="color:var(--border-2);font-size:13px;">'
      + '★'.repeat(Math.max(0, 5 - n)) + '</span>';
  };

  /**
   * debounce(fn, delay) — Retarder l'exécution lors de la frappe
   */
  window.debounce = function (fn, delay) {
    var t;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, delay);
    };
  };

  /**
   * escHtml(s) — Échapper le HTML pour prévenir les XSS
   */
  window.escHtml = function (s) {
    var d = document.createElement('div');
    d.textContent = String(s || '');
    return d.innerHTML;
  };

  /**
   * renderPagination(containerId, data, page, loadFnName)
   * Génère les boutons de pagination dans le conteneur.
   * @param {string}   containerId identifiant du div de pagination
   * @param {Object}   data        réponse API paginée { count, results, page_size }
   * @param {number}   page        page courante (1-indexed)
   * @param {string}   loadFnName  nom de la fonction window à appeler (ex: 'window.loadProduits')
   */
  window.renderPagination = function (containerId, data, page, loadFnName) {
    var el = document.getElementById(containerId);
    if (!el) return;

    var pageSize = data.page_size || 12;
    var totalPages = data.count ? Math.ceil(data.count / pageSize) : 1;

    if (totalPages <= 1) { el.style.display = 'none'; return; }
    el.style.display = 'flex';

    var total = data.count || 0;
    var from  = (page - 1) * pageSize + 1;
    var to    = Math.min(page * pageSize, total);

    /* Bouton précédent */
    var btns = '<button class="pag-btn" '
      + (page <= 1 ? 'disabled' : 'onclick="(' + loadFnName + ')(' + (page - 1) + ')"') + '>'
      + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>'
      + '</button>';

    /* Pages numérotées (max 5 boutons) */
    var startP = Math.max(1, page - 2);
    var endP   = Math.min(totalPages, startP + 4);
    for (var i = startP; i <= endP; i++) {
      btns += '<button class="pag-btn' + (i === page ? ' active' : '') + '" '
        + 'onclick="(' + loadFnName + ')(' + i + ')">' + i + '</button>';
    }

    /* Bouton suivant */
    btns += '<button class="pag-btn" '
      + (page >= totalPages ? 'disabled' : 'onclick="(' + loadFnName + ')(' + (page + 1) + ')"') + '>'
      + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>'
      + '</button>';

    el.innerHTML = '<span class="pag-info">' + from + '–' + to + ' sur ' + total + '</span>'
      + '<div class="pag-btns">' + btns + '</div>';
  };

  /* Récupérer le token CSRF depuis le cookie Django */
  function getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }


  /* ============================================================
     4. BADGES & KPIs
     ============================================================ */

  /** Mettre à jour une valeur KPI avec sa tendance */
  function setKpi(id, value, trendText, trendClass) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('loading');
    el.textContent = (value !== undefined && value !== null) ? value : '—';
    var tEl = document.getElementById(id + '-trend');
    if (tEl && trendText) {
      tEl.className = 'kpi-trend ' + (trendClass || '');
      tEl.textContent = trendText;
    }
  }

  /** Afficher / masquer un badge numérique */
  function updateBadge(id, count) {
    var el = document.getElementById(id);
    if (!el) return;
    if (count && count > 0) {
      el.textContent = count;
      el.style.display = 'flex';
    } else {
      el.style.display = 'none';
    }
  }

  /** Setter texte simple */
  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  /** Setter avec suppression de la classe .loading */
  function setEl(id, val) {
    var el = document.getElementById(id);
    if (el) { el.textContent = val; el.classList.remove('loading'); }
  }

  /** Afficher la date courante dans l'overview */
  function updateDateDisplay() {
    var el = document.getElementById('da-date-now');
    if (!el) return;
    el.textContent = new Date().toLocaleDateString('fr-FR', {
      weekday: 'long', day: 'numeric', month: 'long',
      year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }


  /* ============================================================
     5. RECHERCHE GLOBALE — Ctrl+K
     ============================================================ */

  window.focusSearch = function () {
    var inp = document.getElementById('global-search-input');
    if (inp) { inp.focus(); inp.select(); }
  };

  /* Raccourci Ctrl+K / Cmd+K */
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      window.focusSearch();
    }
  });

  window.closeGlobalSearch = function () {
    var el = document.getElementById('global-search-results');
    if (el) el.style.display = 'none';
  };

  window._navAndClear = function (section) {
    navTo(section);
    window.closeGlobalSearch();
    var inp = document.getElementById('global-search-input');
    if (inp) inp.value = '';
  };

  var _searchTimer = null;

  window.onGlobalSearch = function (q) {
    clearTimeout(_searchTimer);
    var el = document.getElementById('global-search-results');
    if (!q || q.length < 2) { if (el) el.style.display = 'none'; return; }
    el.style.display = 'block';
    el.innerHTML = '<div style="padding:14px 16px;font-size:12.5px;color:var(--text-muted);">Recherche…</div>';

    _searchTimer = setTimeout(async function () {
      try {
        var enc = encodeURIComponent(q);
        var results = await Promise.all([
          API.get('/api/produits/?search=' + enc + '&page_size=4'),
          API.get('/api/commandes/?search=' + enc + '&page_size=4')
        ]);
        var prods = (results[0].results || results[0]).slice(0, 4);
        var cmds  = (results[1].results || results[1]).slice(0, 4);
        var html  = '';

        if (prods.length) {
          html += '<div style="padding:6px 12px 4px;font-size:10.5px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;">Produits</div>';
          html += prods.map(function (p) {
            return '<div onclick="window._navAndClear(\'produits\')" style="display:flex;align-items:center;gap:10px;padding:8px 14px;cursor:pointer;" onmouseover="this.style.background=\'var(--surface-2)\'" onmouseout="this.style.background=\'\'">'
              + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>'
              + '<div><div style="font-size:13px;color:var(--text);">' + escHtml(p.nom) + '</div>'
              + '<div style="font-size:11px;color:var(--text-muted);">' + fmtPrice(p.prix_actuel || p.prix) + ' · stock: ' + (p.stock || 0) + '</div></div>'
              + '</div>';
          }).join('');
        }

        if (cmds.length) {
          html += '<div style="padding:6px 12px 4px;font-size:10.5px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;border-top:1px solid var(--border);margin-top:4px;">Commandes</div>';
          html += cmds.map(function (c) {
            return '<div onclick="window._navAndClear(\'commandes\')" style="display:flex;align-items:center;gap:10px;padding:8px 14px;cursor:pointer;" onmouseover="this.style.background=\'var(--surface-2)\'" onmouseout="this.style.background=\'\'">'
              + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>'
              + '<div><div style="font-size:13px;color:var(--text);">#' + escHtml((c.reference_courte || (c.reference || '').slice(0, 8)).toUpperCase()) + ' · ' + escHtml(c.client_nom || '—') + '</div>'
              + '<div style="font-size:11px;color:var(--text-muted);">' + fmtPrice(c.montant_total) + ' · ' + escHtml(c.statut || '') + '</div></div>'
              + '</div>';
          }).join('');
        }

        if (!prods.length && !cmds.length) {
          html = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:13px;">Aucun résultat pour « ' + escHtml(q) + ' »</div>';
        }

        el.innerHTML = html;
      } catch (err) {
        el.innerHTML = '<div style="padding:14px;text-align:center;color:var(--text-muted);font-size:12.5px;">Erreur de recherche</div>';
      }
    }, 300);
  };

  /* Fermer la recherche au clic extérieur */
  document.addEventListener('click', function (e) {
    var wrap = document.getElementById('global-search-wrap');
    if (wrap && !wrap.contains(e.target)) window.closeGlobalSearch();
  });


  /* ============================================================
     6. DROPDOWN NOTIFICATIONS
     ============================================================ */

  window._closeNotif = function () {
    var dd = document.getElementById('notif-dropdown');
    if (dd) dd.style.display = 'none';
  };

  window._toggleNotif = function (e) {
    e.stopPropagation();
    var dd   = document.getElementById('notif-dropdown');
    var open = dd && dd.style.display === 'block';
    if (dd) dd.style.display = open ? 'none' : 'block';
    if (!open) window._loadNotifDropdown();
  };

  window._loadNotifDropdown = async function () {
    var list = document.getElementById('notif-dropdown-list');
    if (!list) return;
    try {
      var data  = await API.get('/api/notifications/?page=1&page_size=8');
      var items = data.results || data;
      if (!items.length) {
        list.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:13px;">Aucune notification</div>';
        return;
      }
      list.innerHTML = items.map(function (n) {
        var bg = n.is_read ? '' : 'background:rgba(99,102,241,.05);';
        return '<div style="display:flex;gap:10px;padding:10px 16px;' + bg + 'border-bottom:1px solid var(--border);">'
          + '<div style="width:8px;height:8px;border-radius:50%;background:' + (n.is_read ? 'var(--text-muted)' : 'var(--brand-main)') + ';flex-shrink:0;margin-top:5px;"></div>'
          + '<div style="flex:1;">'
          + '<div style="font-size:13px;font-weight:600;color:var(--text);">' + escHtml(n.titre || '') + '</div>'
          + '<div style="font-size:12px;color:var(--text-2);margin-top:2px;">' + escHtml((n.message || '').slice(0, 70)) + '</div>'
          + '<div style="font-size:11px;color:var(--text-muted);margin-top:3px;">' + timeAgo(n.date_creation) + '</div>'
          + '</div></div>';
      }).join('');
    } catch (e) {
      list.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:13px;">Erreur de chargement</div>';
    }
  };

  document.addEventListener('click', function (e) {
    var wrap = document.getElementById('notif-wrap');
    if (wrap && !wrap.contains(e.target)) window._closeNotif();
  });


  /* ============================================================
     7. MODALE DE CONFIRMATION
     showConfirm({ title, body, confirmText, hideCancelBtn, type })
     Retourne une Promise<boolean>
     type: 'danger' | 'warning' | 'info' (défaut)
     ============================================================ */

  window.showConfirm = function (opts) {
    return new Promise(function (resolve) {
      opts = opts || {};
      var type    = opts.type || 'info';
      var colors  = { danger: 'var(--red)', warning: 'var(--yellow)', info: 'var(--brand-main)' };
      var color   = colors[type] || colors.info;

      /* Overlay */
      var overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;inset:0;z-index:500;background:rgba(9,23,71,0.5);'
        + 'backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;padding:20px;';

      /* Boîte modale */
      var box = document.createElement('div');
      box.style.cssText = 'background:var(--surface);border-radius:var(--r-xl);max-width:420px;'
        + 'width:100%;box-shadow:var(--sh-lg);overflow:hidden;animation:modal-in 200ms ease both;';

      /* Barre colorée en haut */
      var bar = '<div style="height:4px;background:' + color + ';"></div>';

      /* Contenu */
      var cancelBtn = opts.hideCancelBtn ? '' :
        '<button onclick="this.closest(\'[data-modal]\').dispatchEvent(new CustomEvent(\'cancel\'))" '
        + 'style="flex:1;padding:10px;border-radius:var(--r-md);border:1.5px solid var(--border);'
        + 'background:var(--surface);color:var(--text-2);font-size:13px;font-weight:600;cursor:pointer;'
        + 'font-family:var(--font-body);">Annuler</button>';

      box.setAttribute('data-modal', '1');
      box.innerHTML = bar
        + '<div style="padding:22px 22px 16px;">'
        + '<div style="font-family:var(--font-display);font-size:16px;font-weight:800;color:var(--brand-deep);margin-bottom:10px;">' + (opts.title || 'Confirmation') + '</div>'
        + '<div style="font-size:13px;color:var(--text-2);line-height:1.6;">' + (opts.body || '') + '</div>'
        + '</div>'
        + '<div style="padding:0 22px 20px;display:flex;gap:10px;">'
        + cancelBtn
        + '<button onclick="this.closest(\'[data-modal]\').dispatchEvent(new CustomEvent(\'confirm\'))" '
        + 'style="flex:1;padding:10px;border-radius:var(--r-md);border:none;'
        + 'background:' + color + ';color:white;font-size:13px;font-weight:700;cursor:pointer;'
        + 'font-family:var(--font-body);">' + (opts.confirmText || 'Confirmer') + '</button>'
        + '</div>';

      overlay.appendChild(box);
      document.body.appendChild(overlay);

      function cleanup(result) {
        document.body.removeChild(overlay);
        resolve(result);
      }

      box.addEventListener('confirm', function () { cleanup(true); });
      box.addEventListener('cancel',  function () { cleanup(false); });
      overlay.addEventListener('click', function (e) {
        if (e.target === overlay) cleanup(false);
      });
    });
  };


  /* ============================================================
     8. TOAST DE FEEDBACK
     showToast(message, type) — type: 'success' | 'error' | 'info'
     ============================================================ */

  window.showToast = function (msg, type) {
    var t   = type || 'info';
    var bg  = { success: 'var(--green)', error: 'var(--red)', info: 'var(--brand-main)' };
    var div = document.createElement('div');
    div.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:1000;'
      + 'background:' + (bg[t] || bg.info) + ';color:white;'
      + 'padding:12px 20px;border-radius:var(--r-md);font-size:13px;font-weight:600;'
      + 'font-family:var(--font-body);box-shadow:var(--sh-lg);'
      + 'animation:modal-in 200ms ease both;max-width:320px;word-break:break-word;';
    div.textContent = msg;
    document.body.appendChild(div);
    setTimeout(function () {
      if (div.parentNode) div.parentNode.removeChild(div);
    }, 3500);
  };

  /* Alias pour la compatibilité avec le code existant */
  window.toast = window.showToast;


  /* ============================================================
     9. LOAD OVERVIEW — Vue d'ensemble
     GET /api/stats/overview/
     ============================================================ */

  window.loadOverview = async function () {
    try {
      var data = await API.get('/api/stats/overview/');
      window._ovData = data; /* Cache pour les KPIs stocks */

      /* KPIs */
      setKpi('kpi-produits',  data.produits_actifs, '', 'info');
      setKpi('kpi-commandes', data.commandes_total, '', '');
      setKpi('kpi-users',     data.utilisateurs,    '+' + (data.nouveaux_users || 0) + ' ce mois', 'up');
      setKpi('kpi-avis',      data.avis_total,      '', '');

      /* Badges sidebar et topbar */
      updateBadge('topbar-notif-badge',  data.commandes_attente);
      updateBadge('sb-badge-commandes',  data.commandes_attente);
      updateBadge('sb-badge-avis',       data.avis_en_attente);
      updateBadge('qa-badge-attente',    data.commandes_attente);
      updateBadge('qa-badge-avis',       data.avis_en_attente);

      /* Commandes récentes */
      renderOvCommandes(data.commandes_recentes || []);

      /* Alertes stock */
      renderOvStocks(data.stocks_faibles || [], data.produits_total || 0);

      /* Activité récente */
      renderOvActivity(data.activite_recente || []);

      /* Vue système */
      setText('ms-convs',   data.conversations || 0);
      setText('ms-notifs',  data.notifications_total || 0);
      setText('ms-paniers', data.paniers_actifs || 0);

    } catch (e) {
      console.warn('loadOverview error:', e);
      ['kpi-produits', 'kpi-commandes', 'kpi-users', 'kpi-avis'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) { el.classList.remove('loading'); el.textContent = '—'; }
      });
    }
  };

  /* Rendu des 5 dernières commandes dans l'overview */
  function renderOvCommandes(commandes) {
    var tbody = document.getElementById('ov-commandes');
    if (!tbody) return;
    if (!commandes.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">Aucune commande récente</td></tr>';
      return;
    }
    tbody.innerHTML = commandes.slice(0, 5).map(function (c) {
      return '<tr>'
        + '<td><span class="mono">#' + escHtml((c.reference_courte || c.reference || '').toUpperCase().slice(0, 8)) + '</span></td>'
        + '<td><span style="font-weight:600;color:var(--text);">' + escHtml(c.client_nom || '—') + '</span></td>'
        + '<td style="font-weight:600;color:var(--brand-main);">' + fmtPrice(c.montant_total) + '</td>'
        + '<td class="hide-mobile" style="color:var(--text-muted);font-size:12px;">' + fmtDate(c.date_creation) + '</td>'
        + '<td>' + renderStatut(c.statut) + '</td>'
        + '<td style="text-align:right;"><button onclick="navTo(\'commandes\')" class="btn btn-secondary btn-xs">Voir</button></td>'
        + '</tr>';
    }).join('');
  }

  /* Rendu des alertes stock faible */
  function renderOvStocks(stocks, produitsTotal) {
    var el = document.getElementById('ov-stocks');
    if (!el) return;
    if (!stocks.length) {
      if (!produitsTotal) {
        el.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:13px;">Aucun produit enregistré</div>';
      } else {
        el.innerHTML = '<div style="padding:24px;text-align:center;color:var(--green);font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:8px;">'
          + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
          + 'Tous les stocks sont OK</div>';
      }
      return;
    }
    el.innerHTML = stocks.slice(0, 6).map(function (p) {
      var pct   = p.stock_max ? Math.round((p.stock / p.stock_max) * 100) : 0;
      var level = p.stock === 0 ? 'out' : p.stock <= (p.stock_minimum || 5) ? 'low' : 'ok';
      var label = p.stock === 0 ? 'Épuisé' : p.stock + ' restant' + (p.stock > 1 ? 's' : '');
      return '<div style="display:flex;align-items:center;gap:12px;padding:10px 18px;border-top:1px solid #F1F5FD;">'
        + '<div style="flex:1;min-width:0;"><div style="font-size:12.5px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + escHtml(p.nom) + '</div>'
        + '<div style="font-size:11px;color:var(--text-muted);">' + label + '</div></div>'
        + '<div class="stock-bar-bg" style="width:80px;"><div class="stock-bar ' + level + '" style="width:' + Math.max(pct, 5) + '%;"></div></div>'
        + '</div>';
    }).join('');
  }

  /* Rendu du feed d'activité récente */
  function renderOvActivity(items) {
    var el = document.getElementById('ov-activity');
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<div class="da-loading">Aucune activité récente</div>';
      return;
    }
    var COLORS = { commande: 'var(--blue)', user: 'var(--green)', produit: 'var(--accent)', avis: 'var(--yellow)' };
    el.innerHTML = items.slice(0, 6).map(function (item) {
      return '<div class="af-item">'
        + '<div class="af-dot" style="background:' + (COLORS[item.type] || 'var(--text-muted)') + ';"></div>'
        + '<div><div class="af-text">' + escHtml(item.description || item.action || '—') + '</div>'
        + '<div class="af-time">' + timeAgo(item.date || item.date_action) + '</div></div>'
        + '</div>';
    }).join('');
  }


  /* ============================================================
     10. LOAD PRODUITS
     GET /api/produits/ — tableau paginé + recherche
     ============================================================ */

  var produitsView = 'table';
  var prodPage = 1;

  window.loadProduits = async function (page) {
    page     = page || prodPage;
    prodPage = page;
    var search = (document.getElementById('prod-search') || {}).value || '';
    var url    = '/api/produits/?page=' + page + (search ? '&search=' + encodeURIComponent(search) : '');
    try {
      var data  = await API.get(url);
      var items = data.results || data;
      setText('prod-count', (data.count || items.length) + ' produit' + ((data.count || items.length) > 1 ? 's' : ''));
      if (produitsView === 'table') { renderProduitsTable(items); } else { renderProduitsCards(items); }
      renderPagination('pag-produits', data, page, 'window.loadProduits');
    } catch (e) {
      var tbody = document.getElementById('tbl-produits');
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--red);">Erreur de chargement</td></tr>';
    }
  };

  function renderProduitsTable(items) {
    var tbody = document.getElementById('tbl-produits');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted);">Aucun produit trouvé</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function (p) {
      var imgSrc = p.image_principale || (p.images && p.images[0] && p.images[0].image) || null;
      var img = imgSrc
        ? '<img src="' + imgSrc + '" style="width:36px;height:36px;border-radius:8px;object-fit:cover;border:1px solid var(--border);" loading="lazy" />'
        : '<div style="width:36px;height:36px;border-radius:8px;background:var(--surface-2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;">'
          + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--border-2)" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>'
          + '</div>';
      var stockColor = p.stock === 0 ? 'color:var(--red);font-weight:700;'
                     : p.stock <= (p.stock_minimum || 5) ? 'color:var(--yellow);font-weight:700;'
                     : 'color:var(--green);font-weight:600;';
      return '<tr>'
        + '<td><div style="display:flex;align-items:center;gap:10px;">' + img
        + '<div><div style="font-weight:600;color:var(--text);font-size:13px;">' + escHtml(p.nom) + '</div>'
        + '<div style="font-size:11px;color:var(--text-muted);">' + escHtml(p.slug || '') + '</div></div></div></td>'
        + '<td class="hide-mobile" style="font-size:12.5px;color:var(--text-2);">' + escHtml(p.categorie_nom || p.categorie || '—') + '</td>'
        + '<td style="font-weight:700;color:var(--brand-main);font-size:13px;">' + fmtPrice(p.prix_actuel || p.prix) + '</td>'
        + '<td style="' + stockColor + '">' + (p.stock !== undefined ? p.stock : '—') + '</td>'
        + '<td>' + renderStatutProduit(p.statut) + '</td>'
        + '<td style="text-align:right;"><div style="display:flex;gap:6px;justify-content:flex-end;">'
        + '<button onclick="editerProduit(' + p.id + ')" class="btn btn-secondary btn-xs">'
        + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
        + ' Éditer</button>'
        + '<button onclick="openStockModal(' + p.id + ',\'' + escHtml(p.nom).replace(/'/g, "\\'") + '\',' + (p.stock || 0) + ')" class="btn btn-secondary btn-xs">'
        + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
        + ' Stock</button>'
        + '</div></td></tr>';
    }).join('');
  }

  function renderProduitsCards(items) {
    var grid = document.getElementById('view-produits-cards');
    if (!grid) return;
    if (!items.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:32px;color:var(--text-muted);">Aucun produit</div>';
      return;
    }
    grid.innerHTML = items.map(function (p) {
      var imgSrc = p.image_principale || (p.images && p.images[0] && p.images[0].image) || null;
      return '<div style="border:1px solid var(--border);border-radius:var(--r-md);overflow:hidden;background:var(--surface);transition:all 200ms;" '
        + 'onmouseover="this.style.boxShadow=\'var(--sh-md)\';this.style.transform=\'translateY(-2px)\'" '
        + 'onmouseout="this.style.boxShadow=\'\';this.style.transform=\'\'">'
        + '<div style="aspect-ratio:4/3;background:var(--surface-2);display:flex;align-items:center;justify-content:center;overflow:hidden;">'
        + (imgSrc ? '<img src="' + imgSrc + '" style="width:100%;height:100%;object-fit:contain;padding:8px;" loading="lazy"/>'
                  : '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--border-2)" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>')
        + '</div>'
        + '<div style="padding:10px 12px 12px;">'
        + '<div style="font-size:12px;font-weight:700;color:var(--text);line-height:1.3;margin-bottom:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + escHtml(p.nom) + '</div>'
        + '<div style="font-size:13px;font-weight:700;color:var(--brand-main);margin-bottom:8px;">' + fmtPrice(p.prix_actuel || p.prix) + '</div>'
        + '<div style="display:flex;justify-content:space-between;align-items:center;">'
        + renderStatutProduit(p.statut)
        + '<button onclick="editerProduit(' + p.id + ')" style="font-size:11px;font-weight:600;color:var(--brand-main);background:none;border:none;cursor:pointer;padding:0;">Modifier →</button>'
        + '</div></div></div>';
    }).join('');
  }

  /* Toggle vue tableau / cartes */
  window.setProduitsView = function (mode) {
    produitsView = mode;
    var tableEl = document.getElementById('view-produits-table');
    var cardsEl = document.getElementById('view-produits-cards');
    var btnT    = document.getElementById('vt-prod-table');
    var btnC    = document.getElementById('vt-prod-card');
    if (mode === 'table') {
      if (tableEl) tableEl.style.display = '';
      if (cardsEl) cardsEl.style.display = 'none';
      if (btnT) btnT.classList.add('active');
      if (btnC) btnC.classList.remove('active');
    } else {
      if (tableEl) tableEl.style.display = 'none';
      if (cardsEl) cardsEl.style.display = 'grid';
      if (btnT) btnT.classList.remove('active');
      if (btnC) btnC.classList.add('active');
    }
    loadProduits(1);
  };


  /* ============================================================
     11. LOAD COMMANDES
     GET /api/commandes/ — avec transitions FSM
     ============================================================ */

  var cmdStatutFilter = '';
  var cmdPage = 1;

  window.filtreCommandes = function (statut, btn) {
    cmdStatutFilter = statut;
    document.querySelectorAll('#sec-commandes-filters .filter-btn').forEach(function (b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    loadCommandes(1);
  };

  window.loadCommandes = async function (page) {
    page    = page || cmdPage;
    cmdPage = page;
    var search = (document.getElementById('cmd-search') || {}).value || '';
    var url    = '/api/commandes/?page=' + page;
    if (cmdStatutFilter) url += '&statut=' + cmdStatutFilter;
    if (search) url += '&search=' + encodeURIComponent(search);
    try {
      var data  = await API.get(url);
      var items = data.results || data;
      setText('cmd-count', (data.count || items.length) + ' commande' + ((data.count || items.length) > 1 ? 's' : ''));
      renderCommandesTable(items);
      renderPagination('pag-commandes', data, page, 'window.loadCommandes');
    } catch (e) {
      var tbody = document.getElementById('tbl-commandes');
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--red);">Erreur de chargement</td></tr>';
    }
  };

  function renderCommandesTable(items) {
    var tbody = document.getElementById('tbl-commandes');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted);">Aucune commande trouvée</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function (c) {
      var actions = '';
      /* Boutons FSM selon statut courant */
      if (c.statut === 'en_attente') {
        actions += actionBtn('Confirmer', 'green', c.id, 'confirmer', false);
        actions += actionBtn('Annuler',   'red',   c.id, 'annuler',   true);
      } else if (c.statut === 'confirmee') {
        actions += actionBtn('En prép.',  'blue',  c.id, 'mettre_en_preparation', false);
        actions += actionBtn('Annuler',   'red',   c.id, 'annuler',               true);
      } else if (c.statut === 'en_preparation') {
        actions += actionBtn('Expédier',  'blue',  c.id, 'expedier', false);
        actions += actionBtn('Annuler',   'red',   c.id, 'annuler',  true);
      } else if (c.statut === 'expediee') {
        actions += actionBtn('Livrer',    'green', c.id, 'livrer', false);
      }
      actions += '<button onclick="voirDetailCommande(' + c.id + ')" class="btn btn-secondary btn-xs" title="Voir le détail">'
        + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>';

      return '<tr>'
        + '<td><span class="mono">#' + escHtml((c.reference_courte || '').toUpperCase()) + '</span></td>'
        + '<td><span style="font-weight:600;color:var(--text);">' + escHtml(c.client_nom || '—') + '</span></td>'
        + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + escHtml(c.adresse_livraison_ville || '—') + '</td>'
        + '<td style="font-weight:700;color:var(--brand-main);">' + fmtPrice(c.montant_total) + '</td>'
        + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + fmtDate(c.date_creation) + '</td>'
        + '<td>' + renderStatut(c.statut) + '</td>'
        + '<td style="text-align:right;"><div style="display:flex;gap:4px;justify-content:flex-end;flex-wrap:wrap;">' + actions + '</div></td>'
        + '</tr>';
    }).join('');
  }

  /* Générer un bouton d'action FSM */
  function actionBtn(label, color, id, action, needConfirm) {
    var styles = {
      green: 'background:var(--green-light);color:#065F46;border:1.5px solid #A7F3D0;',
      red:   'background:var(--red-light);color:#991B1B;border:1.5px solid #FECACA;',
      blue:  'background:var(--brand-light);color:var(--brand-main);border:1.5px solid #DCE7FD;'
    };
    return '<button onclick="changerStatutCommande(' + id + ',\'' + action + '\',this,' + needConfirm + ')" '
      + 'style="padding:4px 10px;border-radius:var(--r-sm);' + (styles[color] || '') + 'font-size:11px;font-weight:600;cursor:pointer;font-family:var(--font-body);">'
      + label + '</button>';
  }

  /* Changer le statut d'une commande */
  window.changerStatutCommande = async function (id, action, btn, needConfirm) {
    if (needConfirm) {
      var ok = await showConfirm({
        title: 'Annuler cette commande ?',
        body:  'Cette action est <strong>irréversible</strong>. Le stock sera remis à jour.',
        confirmText: 'Annuler la commande',
        type: 'warning'
      });
      if (!ok) return;
    }
    btn.disabled = true; btn.textContent = '…';
    try {
      await API.post('/api/commandes/' + id + '/' + action + '/', {});
      showToast('Statut mis à jour', 'success');
      loadCommandes(cmdPage);
      loadOverview();
    } catch (e) {
      showToast('Erreur : ' + (e.message || 'impossible'), 'error');
      btn.disabled = false; btn.textContent = btn.dataset.label || '?';
    }
  };

  /* Voir le détail d'une commande */
  window.voirDetailCommande = async function (id) {
    try {
      var c = await API.get('/api/commandes/' + id + '/');
      var lignes = (c.lignes || []).map(function (l) {
        return '<tr style="border-top:1px solid var(--border);">'
          + '<td style="padding:8px;">' + escHtml(l.produit_nom || '—') + '</td>'
          + '<td style="padding:8px;text-align:center;">' + l.quantite + '</td>'
          + '<td style="padding:8px;text-align:right;">' + fmtPrice(l.prix_unitaire) + '</td>'
          + '<td style="padding:8px;text-align:right;font-weight:700;">' + fmtPrice(l.quantite * l.prix_unitaire) + '</td>'
          + '</tr>';
      }).join('');

      var body = '<div style="font-size:13px;font-family:var(--font-body);">'
        + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;margin-bottom:16px;">'
        + '<div><span style="color:var(--text-muted);">Client :</span> <strong>' + escHtml(c.client_nom || '—') + '</strong></div>'
        + '<div><span style="color:var(--text-muted);">Statut :</span> ' + renderStatut(c.statut) + '</div>'
        + '<div><span style="color:var(--text-muted);">Date :</span> ' + fmtDate(c.date_creation) + '</div>'
        + '<div><span style="color:var(--text-muted);">Paiement :</span> ' + escHtml(c.mode_paiement || '—') + '</div>'
        + '<div style="grid-column:1/-1;"><span style="color:var(--text-muted);">Adresse :</span> ' + escHtml((c.adresse_livraison_ville || '') + ' — ' + (c.adresse_livraison_adresse || '—')) + '</div>'
        + '</div>'
        + '<table style="width:100%;border-collapse:collapse;">'
        + '<thead><tr style="background:var(--surface-2);">'
        + '<th style="padding:8px;text-align:left;font-size:11px;color:var(--text-muted);">Produit</th>'
        + '<th style="padding:8px;text-align:center;font-size:11px;color:var(--text-muted);">Qté</th>'
        + '<th style="padding:8px;text-align:right;font-size:11px;color:var(--text-muted);">P.U.</th>'
        + '<th style="padding:8px;text-align:right;font-size:11px;color:var(--text-muted);">Total</th>'
        + '</tr></thead>'
        + '<tbody>' + (lignes || '<tr><td colspan="4" style="padding:12px;text-align:center;color:var(--text-muted);">—</td></tr>') + '</tbody>'
        + '<tfoot><tr><td colspan="3" style="padding:8px;text-align:right;font-weight:700;">Total</td>'
        + '<td style="padding:8px;text-align:right;font-weight:800;color:var(--brand-main);">' + fmtPrice(c.montant_total) + '</td></tr></tfoot>'
        + '</table></div>';

      await showConfirm({ title: 'Commande #' + escHtml(c.reference_courte || id), body: body, confirmText: 'Fermer', hideCancelBtn: true, type: 'info' });
    } catch (e) {
      showToast('Impossible de charger le détail', 'error');
    }
  };


  /* ============================================================
     12. LOAD USERS
     GET /api/auth/utilisateurs/
     ============================================================ */

  var usersFilter = '';
  var usersPage   = 1;

  window.filtreUsers = function (filtre, btn) {
    usersFilter = filtre;
    document.querySelectorAll('#sec-users-filters .filter-btn').forEach(function (b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    loadUsers(1);
  };

  window.loadUsers = async function (page) {
    page      = page || usersPage;
    usersPage = page;
    var search = (document.getElementById('users-search') || {}).value || '';
    var url    = '/api/auth/utilisateurs/?page=' + page;
    if (usersFilter === 'vendeur') url += '&is_vendeur=true';
    if (usersFilter === 'admin')   url += '&is_admin=true';
    if (usersFilter === 'actif')   url += '&is_active=true';
    if (usersFilter === 'inactif') url += '&is_active=false';
    if (search) url += '&search=' + encodeURIComponent(search);
    try {
      var data  = await API.get(url);
      var items = data.results || data;
      setText('users-count', (data.count || items.length) + ' compte' + ((data.count || items.length) > 1 ? 's' : ''));
      renderUsersTable(items);
      renderPagination('pag-users', data, page, 'window.loadUsers');
    } catch (e) {
      var tbody = document.getElementById('tbl-users');
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--red);">Erreur de chargement</td></tr>';
    }
  };

  function renderUsersTable(items) {
    var tbody = document.getElementById('tbl-users');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted);">Aucun utilisateur trouvé</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function (u) {
      var initials = ((u.prenom || u.username || '?')[0] + (u.nom ? u.nom[0] : '')).toUpperCase();
      var avatar   = u.photo_profil
        ? '<img src="' + u.photo_profil + '" style="width:32px;height:32px;border-radius:50%;object-fit:cover;" />'
        : '<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--brand-main),var(--brand-deep));display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;color:white;">' + escHtml(initials) + '</div>';
      var role = u.is_admin
        ? '<span class="st st-conf">Admin</span>'
        : u.is_vendeur
          ? '<span class="st" style="background:#EDE9FE;color:#5B21B6;">Vendeur</span>'
          : '<span class="st st-off">Client</span>';
      var emailVerif = u.email_verifie
        ? '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>'
        : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      var statut = u.is_active
        ? '<span class="st st-active">Actif</span>'
        : '<span class="st st-off">Inactif</span>';
      return '<tr>'
        + '<td><div style="display:flex;align-items:center;gap:9px;">' + avatar
        + '<div><div style="font-weight:600;color:var(--text);font-size:13px;">' + escHtml(u.get_full_name || u.username) + '</div>'
        + '<div style="font-size:11px;color:var(--text-muted);">@' + escHtml(u.username) + '</div></div></div></td>'
        + '<td class="hide-mobile" style="font-size:12.5px;">' + escHtml(u.email || '—') + '</td>'
        + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + fmtDate(u.date_inscription) + '</td>'
        + '<td>' + role + '</td>'
        + '<td style="text-align:center;">' + emailVerif + '</td>'
        + '<td>' + statut + '</td>'
        + '<td style="text-align:right;"><button onclick="toggleUser(' + u.id + ',' + u.is_active + ',this)" class="btn btn-xs" '
        + 'style="' + (u.is_active ? 'background:var(--red-light);color:#991B1B;border:1.5px solid #FECACA;' : 'background:var(--green-light);color:#065F46;border:1.5px solid #A7F3D0;') + '">'
        + (u.is_active ? 'Désactiver' : 'Activer') + '</button></td>'
        + '</tr>';
    }).join('');
  }

  window.toggleUser = async function (id, isActive, btn) {
    var ok = await showConfirm({
      title: (isActive ? 'Désactiver' : 'Activer') + ' ce compte ?',
      body:  isActive ? "Le compte sera désactivé. L'utilisateur ne pourra plus se connecter." : 'Le compte sera réactivé.',
      confirmText: isActive ? 'Désactiver' : 'Activer',
      type: isActive ? 'warning' : 'info'
    });
    if (!ok) return;
    btn.disabled = true; btn.textContent = '…';
    try {
      await API.post('/api/auth/utilisateurs/' + id + '/toggle_actif/', {});
      showToast('Compte ' + (isActive ? 'désactivé' : 'activé'), 'success');
      loadUsers(usersPage);
    } catch (e) {
      showToast('Erreur modification compte', 'error');
      btn.disabled = false;
    }
  };


  /* ============================================================
     13. LOAD AVIS
     GET /api/avis/ — modération
     ============================================================ */

  var avisFilter = '';
  var avisPage   = 1;

  window.filtreAvis = function (filtre, btn) {
    avisFilter = filtre;
    document.querySelectorAll('#sec-avis-filters .filter-btn').forEach(function (b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    loadAvis(1);
  };

  window.loadAvis = async function (page) {
    page     = page || avisPage;
    avisPage = page;
    var url  = '/api/avis/?page=' + page;
    if (avisFilter) url += '&statut=' + avisFilter;
    try {
      var data  = await API.get(url);
      var items = data.results || data;
      setText('avis-count', (data.count || items.length) + ' avis');
      renderAvisTable(items);
      renderPagination('pag-avis', data, page, 'window.loadAvis');
    } catch (e) {
      var tbody = document.getElementById('tbl-avis');
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--red);">Erreur de chargement</td></tr>';
    }
  };

  function renderAvisTable(items) {
    var tbody = document.getElementById('tbl-avis');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted);">Aucun avis trouvé</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function (a) {
      var statBadge = a.statut === 'valide'
        ? '<span class="st st-valid">Validé</span>'
        : a.statut === 'invalide'
          ? '<span class="st st-cancel">Invalidé</span>'
          : '<span class="st st-pend">En attente</span>';
      var note  = parseInt(a.note) || 0;
      var stars = '<span style="color:var(--yellow);font-size:13px;">' + '★'.repeat(Math.min(note, 5)) + '</span>'
                + '<span style="color:var(--border-2);font-size:13px;">' + '★'.repeat(Math.max(0, 5 - note)) + '</span>';
      var btnV  = a.statut !== 'valide'
        ? '<button onclick="moderAvis(' + a.id + ',true,this)" class="btn btn-xs" style="background:var(--green-light);color:#065F46;border:1.5px solid #A7F3D0;">Valider</button>' : '';
      var btnI  = a.statut !== 'invalide'
        ? '<button onclick="moderAvis(' + a.id + ',false,this)" class="btn btn-xs" style="background:var(--red-light);color:#991B1B;border:1.5px solid #FECACA;">Invalider</button>' : '';
      var btnD  = '<button onclick="supprimerAvis(' + a.id + ',this)" class="btn btn-secondary btn-xs">'
        + '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg></button>';
      return '<tr>'
        + '<td style="font-weight:600;color:var(--text);">' + escHtml(a.produit_nom || a.produit || '—') + '</td>'
        + '<td style="font-size:12.5px;">' + escHtml(a.auteur_nom || a.auteur || '—') + '</td>'
        + '<td>' + stars + '</td>'
        + '<td class="hide-mobile" style="font-size:12px;color:var(--text-2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escHtml((a.commentaire || '—').slice(0, 80)) + '</td>'
        + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + fmtDate(a.date_creation) + '</td>'
        + '<td>' + statBadge + '</td>'
        + '<td style="text-align:right;"><div style="display:flex;gap:4px;justify-content:flex-end;">' + btnV + btnI + btnD + '</div></td>'
        + '</tr>';
    }).join('');
  }

  window.moderAvis = async function (id, valider, btn) {
    btn.disabled = true; btn.textContent = '…';
    try {
      await API.post('/api/avis/' + id + '/' + (valider ? 'valider' : 'invalider') + '/', {});
      showToast(valider ? 'Avis validé' : 'Avis invalidé', 'success');
      loadAvis(avisPage);
    } catch (e) {
      showToast('Erreur modération', 'error');
      btn.disabled = false;
    }
  };

  window.supprimerAvis = async function (id, btn) {
    var ok = await showConfirm({ title: 'Supprimer cet avis ?', body: "L'avis sera définitivement supprimé.", confirmText: 'Supprimer', type: 'danger' });
    if (!ok) return;
    btn.disabled = true;
    try {
      await API.delete('/api/avis/' + id + '/');
      showToast('Avis supprimé', 'success');
      loadAvis(avisPage);
    } catch (e) {
      showToast('Erreur suppression', 'error');
      btn.disabled = false;
    }
  };


  /* ============================================================
     14. LOAD STOCKS
     GET /api/produits/ — avec filtres stock
     ============================================================ */

  var stockFilter = '';
  var stockPage   = 1;

  window.filtreStocks = function (filtre, btn) {
    stockFilter = filtre;
    document.querySelectorAll('#sec-stocks-filters .filter-btn').forEach(function (b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    loadStocks(1);
  };

  window.loadStocks = async function (page) {
    page      = page || stockPage;
    stockPage = page;
    var search = (document.getElementById('stocks-search') || {}).value || '';
    var url    = '/api/produits/?page=' + page;
    if (stockFilter === 'faible')  url += '&stock_faible=true';
    if (stockFilter === 'rupture') url += '&statut=epuise';
    if (search) url += '&search=' + encodeURIComponent(search);
    try {
      var data  = await API.get(url);
      var items = data.results || data;
      /* KPIs depuis le cache overview ou appel API */
      if (window._ovData) {
        setEl('kpi-stock-total',   window._ovData.produits_total || '—');
        setEl('kpi-stock-faible',  window._ovData.stock_faible   || '—');
        setEl('kpi-stock-rupture', window._ovData.stock_epuise   || '—');
      } else {
        try {
          var ov = await API.get('/api/stats/overview/');
          window._ovData = ov;
          setEl('kpi-stock-total',   ov.produits_total || '—');
          setEl('kpi-stock-faible',  ov.stock_faible   || '—');
          setEl('kpi-stock-rupture', ov.stock_epuise   || '—');
        } catch (e2) { /* silencieux */ }
      }
      setText('stocks-count', (data.count || items.length) + ' produit' + ((data.count || items.length) > 1 ? 's' : ''));
      renderStocksTable(items);
      renderPagination('pag-stocks', data, page, 'window.loadStocks');
    } catch (e) {
      var tbody = document.getElementById('tbl-stocks');
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--red);">Erreur de chargement</td></tr>';
    }
  };

  function renderStocksTable(items) {
    var tbody = document.getElementById('tbl-stocks');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted);">Aucun produit</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function (p) {
      var stock = p.stock || 0;
      var seuil = p.stock_minimum || 5;
      var max   = Math.max(stock, seuil * 3, 1);
      var pct   = Math.min(Math.round((stock / max) * 100), 100);
      var level = stock === 0 ? 'out' : stock <= seuil ? 'low' : 'ok';
      var etatBadge = stock === 0
        ? '<span class="st st-out">Épuisé</span>'
        : stock <= seuil
          ? '<span class="st st-low">Faible</span>'
          : '<span class="st st-pub">OK</span>';
      var stockColor = stock === 0 ? 'color:var(--red);font-weight:700;'
                     : stock <= seuil ? 'color:var(--yellow);font-weight:700;'
                     : 'color:var(--green);font-weight:600;';
      return '<tr>'
        + '<td><span style="font-weight:600;color:var(--text);">' + escHtml(p.nom) + '</span></td>'
        + '<td class="hide-mobile" style="font-size:12.5px;color:var(--text-2);">' + escHtml(p.categorie_nom || '—') + '</td>'
        + '<td style="' + stockColor + '">' + stock + '</td>'
        + '<td><div style="display:flex;align-items:center;gap:8px;"><div class="stock-bar-bg" style="width:80px;"><div class="stock-bar ' + level + '" style="width:' + Math.max(pct, 4) + '%;"></div></div></div></td>'
        + '<td class="hide-mobile" style="font-size:12.5px;color:var(--text-muted);">' + seuil + '</td>'
        + '<td>' + etatBadge + '</td>'
        + '<td style="text-align:right;"><button onclick="openStockModal(' + p.id + ',\'' + escHtml(p.nom).replace(/'/g, "\\'") + '\',' + stock + ')" class="btn btn-secondary btn-xs">'
        + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
        + ' Ajuster</button></td>'
        + '</tr>';
    }).join('');
  }


  /* ============================================================
     15. LOAD CATEGORIES
     GET /api/categories/ — arborescence MPTT
     ============================================================ */

  window.loadCategories = async function () {
    try {
      var data  = await API.get('/api/categories/');
      var items = data.results || data;
      _catAllItems = items;
      setText('cat-count', items.length + ' catégorie' + (items.length > 1 ? 's' : ''));
      renderCategoriesTable(items);
      populateCatParentSelect(items);
    } catch (e) {
      var tbody = document.getElementById('tbl-categories');
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--red);">Erreur de chargement</td></tr>';
    }
  };

  function renderCategoriesTable(items) {
    var tbody = document.getElementById('tbl-categories');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted);">Aucune catégorie</td></tr>';
      return;
    }
    /* Grouper : parents d'abord, puis enfants indentés */
    var parents  = items.filter(function (c) { return !c.parent; });
    var html = '';
    parents.forEach(function (p) {
      html += renderCatRow(p, false);
      items.filter(function (c) { return c.parent === p.id; }).forEach(function (c) {
        html += renderCatRow(c, true);
      });
    });
    tbody.innerHTML = html;
  }

  function renderCatRow(cat, isChild) {
    var img = cat.image
      ? '<img src="' + cat.image + '" style="width:32px;height:32px;border-radius:8px;object-fit:cover;border:1px solid var(--border);" />'
      : '<div style="width:32px;height:32px;border-radius:8px;background:var(--surface-2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;">'
        + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--border-2)" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg></div>';
    var actifBadge = cat.est_active !== false
      ? '<span class="st st-active">Actif</span>'
      : '<span class="st st-off">Inactif</span>';
    return '<tr' + (isChild ? ' style="background:var(--surface-2);"' : '') + '>'
      + '<td><div style="display:flex;align-items:center;gap:10px;' + (isChild ? 'padding-left:20px;' : '') + '">'
      + img
      + '<div><div style="font-size:13px;font-weight:' + (isChild ? '500' : '600') + ';color:var(--text);">' + (isChild ? '↳ ' : '') + escHtml(cat.nom) + '</div>'
      + (cat.description ? '<div style="font-size:11px;color:var(--text-muted);">' + escHtml(cat.description.slice(0, 50)) + '</div>' : '')
      + '</div></div></td>'
      + '<td class="hide-mobile" style="font-size:12.5px;color:var(--text-muted);">' + (isChild ? escHtml(cat.parent_nom || '—') : '—') + '</td>'
      + '<td class="hide-mobile">' + (isChild ? '<span class="st st-off">Niveau 2</span>' : '<span class="st st-conf">Racine</span>') + '</td>'
      + '<td style="font-weight:600;">' + (cat.nb_produits || 0) + '</td>'
      + '<td>' + actifBadge + '</td>'
      + '<td style="text-align:right;"><button onclick="editerCategorie(' + cat.id + ')" class="btn btn-secondary btn-xs">Modifier</button></td>'
      + '</tr>';
  }

  /* Toggle vue tableau / cartes catégories */
  var _catView = 'table';
  var _catAllItems = [];

  window.setCatView = function (view) {
    _catView = view;
    var tableWrap = document.getElementById('view-cat-table');
    var cardsWrap = document.getElementById('view-cat-cards');
    var btnTable  = document.getElementById('vt-cat-table');
    var btnCard   = document.getElementById('vt-cat-card');
    if (view === 'table') {
      if (tableWrap) tableWrap.style.display = '';
      if (cardsWrap) { cardsWrap.style.display = 'none'; cardsWrap.style.gridTemplateColumns = ''; }
      if (btnTable) btnTable.classList.add('active');
      if (btnCard)  btnCard.classList.remove('active');
    } else {
      if (tableWrap) tableWrap.style.display = 'none';
      if (cardsWrap) { cardsWrap.style.display = 'grid'; }
      if (btnTable) btnTable.classList.remove('active');
      if (btnCard)  btnCard.classList.add('active');
      renderCatCards(_catAllItems);
    }
  };

  function renderCatCards(items) {
    var wrap = document.getElementById('view-cat-cards');
    if (!wrap) return;
    if (!items.length) {
      wrap.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);font-size:13px;">Aucune catégorie</div>';
      return;
    }
    wrap.innerHTML = items.map(function (cat) {
      var img = cat.image
        ? '<img src="' + cat.image + '" style="width:100%;height:100%;object-fit:cover;" />'
        : '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--border-2)" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
      var badge = cat.est_active !== false
        ? '<span class="st st-active">Actif</span>'
        : '<span class="st st-off">Inactif</span>';
      return '<div style="background:var(--surface);border:1.5px solid var(--border);border-radius:var(--r-md);overflow:hidden;cursor:pointer;transition:box-shadow 150ms;" onclick="editerCategorie(' + cat.id + ')">'
        + '<div style="height:100px;background:var(--surface-2);display:flex;align-items:center;justify-content:center;overflow:hidden;">' + img + '</div>'
        + '<div style="padding:10px 12px;">'
        + '<div style="font-size:13px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + escHtml(cat.nom) + '</div>'
        + '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:6px;">'
        + '<span style="font-size:11px;color:var(--text-muted);">' + (cat.nb_produits || 0) + ' produit' + ((cat.nb_produits||0) > 1 ? 's' : '') + '</span>'
        + badge
        + '</div>'
        + '</div>'
        + '</div>';
    }).join('');
  }

  /* Filtre local (sans appel API) sur le tableau et les cartes */
  window.filterCategoriesLocal = function (query) {
    var q = query.toLowerCase().trim();
    var filtered = q ? _catAllItems.filter(function (c) {
      return c.nom.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q);
    }) : _catAllItems;
    setText('cat-count', filtered.length + ' catégorie' + (filtered.length > 1 ? 's' : ''));
    renderCategoriesTable(filtered);
    if (_catView === 'card') renderCatCards(filtered);
  };

  function populateCatParentSelect(items) {
    var sel = document.getElementById('cat-parent');
    if (!sel) return;
    var parents = items.filter(function (c) { return !c.parent; });
    sel.innerHTML = '<option value="">— Aucun parent (racine) —</option>'
      + parents.map(function (p) {
        return '<option value="' + p.id + '">' + escHtml(p.nom) + '</option>';
      }).join('');
  }

  window.editerCategorie = async function (id) {
    navTo('ajouter-categorie');
    try {
      var cat = await API.get('/api/categories/' + id + '/');
      document.getElementById('cat-id').value  = id;
      document.getElementById('cat-nom').value = cat.nom || '';
      var descEl = document.getElementById('cat-desc');
      if (descEl) descEl.value = cat.description || '';
      var selEl = document.getElementById('cat-parent');
      if (selEl && cat.parent) selEl.value = cat.parent;
      /* Mode radio statut */
      var actifEl   = document.getElementById('cat-actif');
      var inactifEl = document.getElementById('cat-inactif');
      if (actifEl && inactifEl) {
        actifEl.checked   = cat.est_active !== false;
        inactifEl.checked = cat.est_active === false;
      }
      /* Aperçu image existante */
      if (cat.image) {
        var preview = document.getElementById('cat-img-preview');
        var icon    = document.getElementById('cat-img-placeholder-icon');
        if (preview) { preview.src = cat.image; preview.style.display = 'block'; }
        if (icon)    icon.style.display = 'none';
      }
      var titleEl  = document.getElementById('cat-form-title');
      var btnSub   = document.getElementById('cat-btn-submit');
      var btnDel   = document.getElementById('cat-btn-supprimer');
      if (titleEl)  titleEl.textContent  = 'Modifier la catégorie';
      if (btnSub)   btnSub.textContent   = 'Enregistrer';
      if (btnDel)   btnDel.style.display = '';
    } catch (e) {
      showToast('Erreur de chargement', 'error');
    }
  };

  function resetCatForm() {
    var form = document.getElementById('cat-form');
    if (form) form.reset();
    var idEl   = document.getElementById('cat-id');
    if (idEl)  idEl.value = '';
    var titleEl  = document.getElementById('cat-form-title');
    var btnSub   = document.getElementById('cat-btn-submit');
    var btnDel   = document.getElementById('cat-btn-supprimer');
    var preview  = document.getElementById('cat-img-preview');
    var icon     = document.getElementById('cat-img-placeholder-icon');
    var flash    = document.getElementById('cat-flash');
    if (titleEl)  titleEl.textContent  = 'Nouvelle catégorie';
    if (btnSub)   btnSub.textContent   = 'Créer la catégorie';
    if (btnDel)   btnDel.style.display = 'none';
    if (preview)  { preview.style.display = 'none'; preview.src = ''; }
    if (icon)     icon.style.display   = '';
    if (flash)    flash.style.display  = 'none';
  }

  window.deleteCategorie = async function () {
    var id  = document.getElementById('cat-id').value;
    if (!id) return;
    var nom = document.getElementById('cat-nom').value || 'cette catégorie';
    var ok  = await showConfirm({ title: 'Supprimer « ' + nom + ' » ?', body: 'Les produits associés perdront leur catégorie.', confirmText: 'Supprimer', type: 'danger' });
    if (!ok) return;
    try {
      await API.delete('/api/categories/' + id + '/');
      showToast('Catégorie supprimée', 'success');
      navTo('categories');
    } catch (e) {
      showToast('Erreur suppression', 'error');
    }
  };

  /* Prévisualisation image catégorie */
  window.previewCatImage = function (input) {
    if (!input.files || !input.files[0]) return;
    var reader = new FileReader();
    reader.onload = function (ev) {
      var preview = document.getElementById('cat-img-preview');
      var icon    = document.getElementById('cat-img-placeholder-icon');
      var removeBtn = document.getElementById('cat-img-remove');
      if (preview) { preview.src = ev.target.result; preview.style.display = 'block'; }
      if (icon)    icon.style.display = 'none';
      if (removeBtn) removeBtn.style.display = 'block';
    };
    reader.readAsDataURL(input.files[0]);
  };


  /* ============================================================
     16. LOAD PANIERS
     GET /api/panier/admin/ — lecture seule
     ============================================================ */

  window.loadPaniers = async function () {
    try {
      var data  = await API.get('/api/panier/admin/');
      var items = data.results || data;
      var tbody = document.getElementById('tbl-paniers');
      if (!tbody) return;
      setText('paniers-count', items.length + ' panier' + (items.length > 1 ? 's' : ''));
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted);">Aucun panier actif</td></tr>';
        return;
      }
      tbody.innerHTML = items.map(function (p) {
        var n = p.nb_articles || p.nombre_articles || 0;
        return '<tr>'
          + '<td style="font-weight:600;color:var(--text);">' + escHtml(p.utilisateur || '—') + '</td>'
          + '<td style="font-weight:600;">' + n + ' article' + (n > 1 ? 's' : '') + '</td>'
          + '<td style="font-weight:700;color:var(--brand-main);">' + fmtPrice(p.total || p.montant_total || 0) + '</td>'
          + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + fmtDate(p.date_modification) + '</td>'
          + '<td style="text-align:right;"><button onclick="navTo(\'utilisateurs\')" class="btn btn-secondary btn-xs">Client →</button></td>'
          + '</tr>';
      }).join('');
    } catch (e) {
      var tbody2 = document.getElementById('tbl-paniers');
      if (tbody2) tbody2.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">Données non disponibles</td></tr>';
    }
  };


  /* ============================================================
     17. LOAD MESSAGES
     GET /api/chat/ — conversations
     ============================================================ */

  window.loadMessages = async function () {
    try {
      var data  = await API.get('/api/chat/');
      var items = data.results || data;
      var tbody = document.getElementById('tbl-messages');
      if (!tbody) return;
      setText('messages-count', items.length + ' conversation' + (items.length > 1 ? 's' : ''));
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted);">Aucune conversation</td></tr>';
        return;
      }
      tbody.innerHTML = items.map(function (c) {
        var p1 = escHtml(c.participant1_nom || c.participant1 || '—');
        var p2 = escHtml(c.participant2_nom || c.participant2 || '—');
        var nbMsg   = c.nb_messages || 0;
        var dernMsg = c.dernier_message ? escHtml((c.dernier_message.contenu || '').slice(0, 60)) : '—';
        return '<tr>'
          + '<td style="font-weight:600;color:var(--text);">' + p1 + '</td>'
          + '<td style="font-weight:600;color:var(--text);">' + p2 + '</td>'
          + '<td>' + nbMsg + '</td>'
          + '<td class="hide-mobile" style="font-size:12px;color:var(--text-2);">' + dernMsg + '</td>'
          + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + fmtDate(c.date_creation) + '</td>'
          + '</tr>';
      }).join('');
    } catch (e) {
      var tbody2 = document.getElementById('tbl-messages');
      if (tbody2) tbody2.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">Données non disponibles</td></tr>';
    }
  };


  /* ============================================================
     18. LOAD NOTIFICATIONS
     GET /api/notifications/
     ============================================================ */

  window.loadNotifs = async function (page) {
    page = page || 1;
    try {
      var data  = await API.get('/api/notifications/?page=' + page);
      var items = data.results || data;
      var tbody = document.getElementById('tbl-notifs');
      if (!tbody) return;
      setText('notifs-count', (data.count || items.length) + ' notification' + ((data.count || items.length) > 1 ? 's' : ''));
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted);">Aucune notification</td></tr>';
        return;
      }
      var TYPE_ICONS = { commande: '🛒', avis: '⭐', stock: '⚠️', systeme: '🔔' };
      tbody.innerHTML = items.map(function (n) {
        return '<tr' + (n.is_read ? '' : ' style="background:var(--surface-2);"') + '>'
          + '<td><span style="font-size:16px;">' + (TYPE_ICONS[n.type_notif] || '🔔') + '</span></td>'
          + '<td style="font-size:12.5px;">' + escHtml(n.destinataire_nom || '—') + '</td>'
          + '<td style="font-weight:' + (n.is_read ? '500' : '600') + ';color:var(--text);">' + escHtml(n.titre || '—') + '</td>'
          + '<td class="hide-mobile" style="font-size:12px;color:var(--text-2);">' + escHtml((n.message || '').slice(0, 60)) + '</td>'
          + '<td class="hide-mobile" style="font-size:12px;color:var(--text-muted);">' + fmtDate(n.date_creation) + '</td>'
          + '<td>' + (n.is_read
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>'
            : '<span class="st st-pend">Non lu</span>') + '</td>'
          + '</tr>';
      }).join('');
      renderPagination('pag-notifs', data, page, 'window.loadNotifs');
    } catch (e) { /* silencieux */ }
  };


  /* ============================================================
     19. LOAD AUDIT
     GET /api/audit/ — journal d'activité
     ============================================================ */

  window.loadAudit = async function (page) {
    page = page || 1;
    try {
      var data  = await API.get('/api/audit/?page=' + page);
      var items = data.results || data;
      var el    = document.getElementById('tbl-audit');
      if (!el) return;

      var lastEl = document.getElementById('audit-last-update');
      if (lastEl) lastEl.textContent = 'Mis à jour : ' + new Date().toLocaleTimeString('fr-FR');

      if (!items.length) {
        el.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-muted);">Aucune activité enregistrée</div>';
        return;
      }

      var TYPE_COLORS = {
        CREATE: 'var(--green)', UPDATE: 'var(--blue)',
        DELETE: 'var(--red)',   LOGIN:  'var(--accent)',
        LOGOUT: 'var(--text-muted)', GET: 'var(--text-muted)'
      };

      el.innerHTML = items.map(function (entry) {
        var color = TYPE_COLORS[entry.action] || 'var(--text-muted)';
        return '<div class="af-item">'
          + '<div class="af-dot" style="background:' + color + ';flex-shrink:0;"></div>'
          + '<div style="flex:1;">'
          + '<div class="af-text"><strong style="color:var(--text);">' + escHtml(entry.utilisateur_nom || entry.utilisateur || '—') + '</strong>'
          + ' · ' + escHtml(entry.action || '—')
          + ' · <span style="color:var(--text-2);">' + escHtml(entry.url || entry.description || '') + '</span>'
          + (entry.status_code ? ' <span style="font-size:11px;color:var(--text-muted);">(' + entry.status_code + ')</span>' : '')
          + '</div>'
          + '<div class="af-time">' + timeAgo(entry.date || entry.date_action || entry.date_creation)
          + (entry.ip ? ' · IP: ' + escHtml(entry.ip) : '') + '</div>'
          + '</div></div>';
      }).join('');

      renderPagination('pag-audit', data, page, 'window.loadAudit');
    } catch (e) {
      var el2 = document.getElementById('tbl-audit');
      if (el2) el2.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);">Données non disponibles</div>';
    }
  };


  /* ============================================================
     20. FORMULAIRE PRODUIT
     ============================================================ */

  /* Éditer un produit existant */
  window.editerProduit = async function (id) {
    navTo('ajouter-produit');
    try {
      var p = await API.get('/api/produits/' + id + '/');
      document.getElementById('ap-produit-id').value    = id;
      document.getElementById('ap-nom').value           = p.nom || '';
      document.getElementById('ap-desc-courte').value   = p.description_courte || '';
      document.getElementById('ap-desc').value          = p.description || '';
      document.getElementById('ap-prix').value          = p.prix || '';
      document.getElementById('ap-prix-promo').value    = p.prix_promo || '';
      document.getElementById('ap-stock').value         = p.stock || 0;
      document.getElementById('ap-stock-min').value     = p.stock_minimum || 5;
      var selStatut = document.getElementById('ap-statut');
      if (selStatut) selStatut.value = p.statut || 'actif';
      var selCat = document.getElementById('ap-categorie');
      if (selCat && p.categorie) selCat.value = p.categorie;
      /* Toggle vedette */
      var chkV  = document.getElementById('ap-vedette');
      var track = document.getElementById('ap-vedette-track');
      var knob  = document.getElementById('ap-vedette-knob');
      if (chkV) chkV.checked = p.en_vedette || false;
      if (track) track.classList.toggle('on', p.en_vedette || false);
      if (knob && p.en_vedette) knob.style.transform = 'translateX(18px)';
      /* Image existante */
      var imgUrl = p.image_principale || (p.images && p.images[0] && p.images[0].image);
      if (imgUrl) {
        var existDiv = document.getElementById('ap-existing-img');
        var existImg = document.getElementById('ap-existing-img-el');
        var pholder  = document.getElementById('ap-img-placeholder');
        if (existDiv) existDiv.style.display = 'block';
        if (existImg) { existImg.src = imgUrl; existImg.alt = p.nom; }
        if (pholder)  pholder.style.display = 'none';
      }
      /* Titres */
      var titleEl  = document.getElementById('ap-title');
      var subtilEl = document.getElementById('ap-subtitle');
      var btnDel   = document.getElementById('ap-btn-supprimer');
      if (titleEl)  titleEl.textContent  = 'Modifier le produit';
      if (subtilEl) subtilEl.textContent = 'Modification de : ' + p.nom;
      if (btnDel)   btnDel.style.display = '';
    } catch (e) {
      showToast('Impossible de charger le produit', 'error');
    }
  };

  function resetProduitForm() {
    var form = document.getElementById('ap-form');
    if (form) form.reset();
    /* Charger les catégories dans le select */
    (async function () {
      try {
        var data = await API.get('/api/categories/');
        var cats = data.results || data;
        var sel  = document.getElementById('ap-categorie');
        if (!sel) return;
        sel.innerHTML = '<option value="">— Choisir une catégorie —</option>';
        cats.forEach(function (cat) {
          var opt = document.createElement('option');
          opt.value = cat.id;
          opt.textContent = cat.nom;
          sel.appendChild(opt);
          (cat.sous_categories || []).forEach(function (sub) {
            var subOpt = document.createElement('option');
            subOpt.value = sub.id;
            subOpt.textContent = '  ↳ ' + sub.nom;
            sel.appendChild(subOpt);
          });
        });
      } catch (e) { /* silencieux */ }
    })();
    var els = {
      'ap-produit-id': '', 'ap-title': 'Nouveau produit',
      'ap-subtitle': 'Remplissez le formulaire pour publier'
    };
    Object.keys(els).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) { el.tagName === 'INPUT' ? (el.value = els[id]) : (el.textContent = els[id]); }
    });
    ['ap-btn-supprimer', 'ap-existing-img'].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.style.display = 'none';
    });
    var pholder = document.getElementById('ap-img-placeholder');
    if (pholder) pholder.style.display = '';
    var grid  = document.getElementById('ap-preview-grid');
    if (grid)  grid.innerHTML = '';
    var flash = document.getElementById('ap-flash');
    if (flash) flash.style.display = 'none';
    /* Reset toggle vedette */
    var track = document.getElementById('ap-vedette-track');
    var knob  = document.getElementById('ap-vedette-knob');
    if (track) track.classList.remove('on');
    if (knob)  knob.style.transform = '';
  }

  window.supprimerProduit = async function () {
    var id  = (document.getElementById('ap-produit-id') || {}).value;
    if (!id) return;
    var nom = (document.getElementById('ap-nom') || {}).value || 'ce produit';
    var ok  = await showConfirm({ title: 'Supprimer « ' + nom + ' » ?', body: 'Action <strong>irréversible</strong>. Le produit et ses images seront supprimés.', confirmText: 'Supprimer définitivement', type: 'danger' });
    if (!ok) return;
    try {
      await API.delete('/api/produits/' + id + '/');
      showToast('Produit supprimé', 'success');
      navTo('produits');
      loadProduits(1);
    } catch (e) {
      showToast('Erreur lors de la suppression', 'error');
    }
  };

  /* Prévisualisation images */
  window.apPreviewImages = function (files) {
    var grid = document.getElementById('ap-preview-grid');
    if (!grid) return;
    grid.innerHTML = '';
    Array.from(files).forEach(function (file, i) {
      var reader = new FileReader();
      reader.onload = function (ev) {
        var div = document.createElement('div');
        div.style.cssText = 'position:relative;aspect-ratio:1;border-radius:var(--r-sm);overflow:hidden;border:1.5px solid ' + (i === 0 ? 'var(--brand-main)' : 'var(--border)') + ';';
        div.innerHTML = '<img src="' + ev.target.result + '" style="width:100%;height:100%;object-fit:cover;"/>'
          + (i === 0 ? '<span style="position:absolute;top:4px;left:4px;background:var(--brand-main);color:white;font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;">Principal</span>' : '');
        grid.appendChild(div);
      };
      reader.readAsDataURL(file);
    });
  };

  window.apHandleDrop = function (e) {
    e.preventDefault();
    e.currentTarget.style.borderColor = '';
    e.currentTarget.style.background  = 'var(--surface-2)';
    var input = document.getElementById('ap-images');
    if (!input) return;
    var dt = new DataTransfer();
    Array.from(e.dataTransfer.files).forEach(function (f) { dt.items.add(f); });
    input.files = dt.files;
    apPreviewImages(e.dataTransfer.files);
  };


  /* ============================================================
     21. FORMULAIRE CATÉGORIE (soumission)
     ============================================================ */

  document.addEventListener('DOMContentLoaded', function () {

    /* Soumission formulaire catégorie */
    var catForm = document.getElementById('cat-form');
    if (catForm) {
      catForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        var catId = document.getElementById('cat-id').value;
        var flash = document.getElementById('cat-flash');
        var btn   = document.getElementById('cat-btn-submit');
        if (btn) { btn.disabled = true; btn.textContent = 'Enregistrement…'; }

        /* Construire le payload manuellement (les inputs n'ont pas de name) */
        var fd = new FormData();
        var nomEl    = document.getElementById('cat-nom');
        var descEl   = document.getElementById('cat-desc');
        var parentEl = document.getElementById('cat-parent');
        var actifEl  = document.getElementById('cat-actif');
        var imgInput = document.getElementById('cat-image-input');
        var csrfEl   = catForm.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfEl)   fd.append('csrfmiddlewaretoken', csrfEl.value);
        if (nomEl)    fd.append('nom', nomEl.value.trim());
        if (descEl)   fd.append('description', descEl.value.trim());
        if (parentEl && parentEl.value) fd.append('parent', parentEl.value);
        fd.append('est_active', actifEl && actifEl.checked ? 'true' : 'false');
        if (imgInput && imgInput.files && imgInput.files[0]) {
          fd.append('image', imgInput.files[0]);
        }

        var url    = catId ? '/api/categories/' + catId + '/' : '/api/categories/';
        var method = catId ? 'PATCH' : 'POST';
        try {
          var resp = await fetch(url, { method: method, headers: { 'X-CSRFToken': getCsrf() }, body: fd });
          var data = await resp.json();
          if (resp.ok) {
            showToast(catId ? 'Catégorie modifiée' : 'Catégorie créée ✓', 'success');
            /* Rester sur le formulaire et le réinitialiser pour une nouvelle saisie */
            var nomEl2    = document.getElementById('cat-nom');
            var descEl2   = document.getElementById('cat-desc');
            var parentEl2 = document.getElementById('cat-parent');
            var imgInp2   = document.getElementById('cat-image-input');
            var prev2     = document.getElementById('cat-img-preview');
            var icon2     = document.getElementById('cat-img-placeholder-icon');
            var rmBtn2    = document.getElementById('cat-img-remove');
            var idEl2     = document.getElementById('cat-id');
            if (idEl2)    idEl2.value = '';
            if (nomEl2)   nomEl2.value = '';
            if (descEl2)  descEl2.value = '';
            if (parentEl2) parentEl2.value = '';
            if (imgInp2)  imgInp2.value = '';
            if (prev2)    { prev2.src = ''; prev2.style.display = 'none'; }
            if (icon2)    icon2.style.display = 'flex';
            if (rmBtn2)   rmBtn2.style.display = 'none';
            var actifEl2 = document.getElementById('cat-actif');
            if (actifEl2) actifEl2.checked = true;
            var titleEl2 = document.getElementById('cat-form-title');
            if (titleEl2) titleEl2.textContent = 'Nouvelle catégorie';
            if (flash) { flash.style.cssText = 'display:flex;background:var(--green-light);color:#065F46;border:1px solid #A7F3D0;padding:10px 14px;border-radius:var(--r-sm);font-size:12.5px;font-weight:600;'; flash.textContent = catId ? 'Catégorie modifiée !' : 'Catégorie créée ! Vous pouvez en ajouter une autre.'; }
            if (nomEl2) nomEl2.focus();
            /* Rafraîchir les données en arrière-plan sans changer de section */
            API.get('/api/categories/').then(function(data){
              var items = data.results || data;
              _catAllItems = items;
              renderCategoriesTable(items);
              populateCatParentSelect(items);
            }).catch(function(){});
          } else {
            var errs = Object.values(data).flat().join(' · ');
            if (flash) { flash.style.cssText = 'display:flex;background:var(--red-light);color:#991B1B;border:1px solid #FECACA;padding:10px 14px;border-radius:var(--r-sm);font-size:12.5px;font-weight:600;'; flash.textContent = 'Erreur : ' + errs; }
          }
        } catch (err) {
          if (flash) { flash.style.display = 'flex'; flash.textContent = 'Erreur réseau'; }
        } finally {
          if (btn) { btn.disabled = false; btn.textContent = catId ? 'Enregistrer' : 'Créer la catégorie'; }
        }
      });
    }

    /* Soumission formulaire produit */
    var apForm = document.getElementById('ap-form');
    if (apForm) {
      apForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        var produitId = document.getElementById('ap-produit-id').value;
        var flash     = document.getElementById('ap-flash');
        var btnPub    = document.getElementById('ap-btn-publier');
        var btnDraft  = document.getElementById('ap-btn-brouillon');

        /* Si brouillon → passer le statut en inactif */
        if (e.submitter && e.submitter.dataset.action === 'brouillon') {
          var selStatut = document.getElementById('ap-statut');
          if (selStatut) selStatut.value = 'inactif';
        }

        if (btnPub)   { btnPub.disabled = true; btnPub.textContent = 'Publication…'; }
        if (btnDraft) { btnDraft.disabled = true; }

        var fd     = new FormData(apForm);
        var url    = produitId ? '/api/produits/' + produitId + '/' : '/api/produits/';
        var method = produitId ? 'PATCH' : 'POST';

        try {
          var resp = await fetch(url, { method: method, headers: { 'X-CSRFToken': getCsrf() }, body: fd });
          var data = await resp.json();

          if (resp.ok) {
            if (flash) {
              flash.style.cssText = 'display:flex;background:var(--green-light);color:#065F46;border:1px solid #A7F3D0;padding:12px 16px;border-radius:var(--r-md);font-size:13px;font-weight:600;align-items:center;gap:10px;';
              flash.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> '
                + (produitId ? 'Produit modifié avec succès !' : 'Produit publié avec succès !');
            }
            showToast(produitId ? 'Produit modifié !' : 'Produit publié ✓', 'success');
            /* Rester sur le formulaire — réinitialiser sans changer la section */
            if (flash) {
              flash.style.cssText = 'display:flex;background:var(--green-light);color:#065F46;border:1px solid #A7F3D0;padding:12px 16px;border-radius:var(--r-md);font-size:13px;font-weight:600;align-items:center;gap:10px;';
              flash.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> '
                + (produitId ? 'Produit modifié ! Vous pouvez en modifier un autre.' : 'Produit publié ! Vous pouvez en ajouter un autre.');
            }
            /* Réinitialiser le formulaire sans changer de section ni toucher au hash */
            var apF = document.getElementById('ap-form');
            if (apF) apF.reset();
            document.getElementById('ap-produit-id').value = '';
            var titEl = document.getElementById('ap-title');
            if (titEl) titEl.textContent = 'Nouveau produit';
            var subEl = document.getElementById('ap-subtitle');
            if (subEl) subEl.textContent = 'Remplissez le formulaire pour publier';
            var supBtn = document.getElementById('ap-btn-supprimer');
            if (supBtn) supBtn.style.display = 'none';
            var prevGrid = document.getElementById('ap-preview-grid');
            if (prevGrid) prevGrid.innerHTML = '';
            var existDiv = document.getElementById('ap-existing-img');
            if (existDiv) existDiv.style.display = 'none';
            var pholder = document.getElementById('ap-img-placeholder');
            if (pholder) pholder.style.display = '';
            var track = document.getElementById('ap-vedette-track');
            var knob  = document.getElementById('ap-vedette-knob');
            if (track) track.classList.remove('on');
            if (knob)  knob.style.transform = '';
            /* Recharger les catégories dans le select */
            (async function(){
              try {
                var d2 = await API.get('/api/categories/');
                var c2 = d2.results || d2;
                var s2 = document.getElementById('ap-categorie');
                if (!s2) return;
                s2.innerHTML = '<option value="">— Choisir une catégorie —</option>';
                c2.forEach(function(cat){
                  var o=document.createElement('option'); o.value=cat.id; o.textContent=cat.nom; s2.appendChild(o);
                  (cat.sous_categories||[]).forEach(function(sub){ var so=document.createElement('option'); so.value=sub.id; so.textContent='  ↳ '+sub.nom; s2.appendChild(so); });
                });
              } catch(e){}
            })();
          } else {
            var errs = Object.values(data).flat().join(' · ');
            if (flash) {
              flash.style.cssText = 'display:flex;background:var(--red-light);color:#991B1B;border:1px solid #FECACA;padding:12px 16px;border-radius:var(--r-md);font-size:13px;font-weight:600;align-items:center;gap:10px;';
              flash.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> Erreur : ' + (errs || JSON.stringify(data));
            }
          }
        } catch (err) {
          if (flash) { flash.style.cssText = 'display:flex;background:var(--red-light);color:#991B1B;padding:12px 16px;border-radius:var(--r-md);font-size:13px;font-weight:600;'; flash.textContent = 'Erreur réseau : ' + err.message; }
        } finally {
          if (btnPub)   { btnPub.disabled = false; btnPub.textContent = 'Publier le produit'; }
          if (btnDraft) { btnDraft.disabled = false; }
        }
      });
    }

    /* Toggle vedette — met à jour le visuel du switch */
    var chkVedette = document.getElementById('ap-vedette');
    var trackEl    = document.getElementById('ap-vedette-track');
    var knobEl     = document.getElementById('ap-vedette-knob');
    if (chkVedette) {
      chkVedette.addEventListener('change', function () {
        if (trackEl) trackEl.classList.toggle('on', chkVedette.checked);
        if (knobEl)  knobEl.style.transform = chkVedette.checked ? 'translateX(18px)' : '';
      });
    }

    /* Calcul automatique de la remise prix promo */
    var prixEl  = document.getElementById('ap-prix');
    var promoEl = document.getElementById('ap-prix-promo');
    var remEl   = document.getElementById('ap-remise');
    if (prixEl && promoEl && remEl) {
      function updateRemise() {
        var prix  = parseFloat(prixEl.value);
        var promo = parseFloat(promoEl.value);
        if (prix && promo && promo < prix) {
          remEl.textContent    = '−' + Math.round(((prix - promo) / prix) * 100) + '% de remise';
          remEl.style.display  = 'inline-block';
        } else {
          remEl.style.display = 'none';
        }
      }
      prixEl.addEventListener('input', updateRemise);
      promoEl.addEventListener('input', updateRemise);
    }

  }); /* fin DOMContentLoaded */


  /* ============================================================
     22. MODALE STOCK
     openStockModal(id, nom, stockActuel)
     closeStockModal()
     submitStock()
     ============================================================ */

  var _stockProduitId = null;

  window.openStockModal = function (produitId, nom, stockActuel) {
    _stockProduitId = produitId;
    setText('modal-stock-nom', nom);
    setText('modal-stock-current', stockActuel + ' unité' + (stockActuel > 1 ? 's' : ''));
    var qtyEl  = document.getElementById('modal-stock-qty');
    var noteEl = document.getElementById('modal-stock-note');
    var modal  = document.getElementById('modal-stock');
    if (qtyEl)  qtyEl.value  = 10;
    if (noteEl) noteEl.value = '';
    if (modal)  modal.style.display = 'flex';
  };

  window.closeStockModal = function () {
    var modal = document.getElementById('modal-stock');
    if (modal) modal.style.display = 'none';
    _stockProduitId = null;
  };

  window.submitStock = async function () {
    if (!_stockProduitId) return;
    var type_mouvement = (document.getElementById('modal-stock-type') || {}).value;
    var quantite       = parseInt((document.getElementById('modal-stock-qty') || {}).value);
    var note           = (document.getElementById('modal-stock-note') || {}).value;
    if (!quantite || quantite <= 0) { showToast('Quantité invalide', 'error'); return; }
    try {
      await API.post('/api/produits/' + _stockProduitId + '/gerer_stock/', { type_mouvement: type_mouvement, quantite: quantite, note: note });
      closeStockModal();
      showToast('Stock mis à jour avec succès', 'success');
      if (window.loadStocks) loadStocks(stockPage);
      loadProduits(prodPage);
      loadOverview();
    } catch (e) {
      showToast('Erreur lors de la mise à jour', 'error');
    }
  };


  /* ============================================================
     23. MODALE CATÉGORIE RAPIDE
     openModalCat()  — depuis le formulaire produit
     closeModalCat()
     submitModalCat()
     ============================================================ */

  window.openModalCat = async function () {
    var modal = document.getElementById('modal-cat-quick');
    var nomEl = document.getElementById('mcat-nom');
    var flash = document.getElementById('modal-cat-flash');
    if (modal) modal.style.display = 'flex';
    if (nomEl) nomEl.focus();
    if (flash) flash.style.display = 'none';
    try {
      var data = await API.get('/api/categories/');
      var cats = data.results || data;
      var I    = window.DASH_I18N || {};
      var sel  = document.getElementById('mcat-parent');
      if (sel) {
        sel.innerHTML = '<option value="">' + (I.aucunParent || '— Aucun parent —') + '</option>'
          + cats.map(function (c) { return '<option value="' + c.id + '">' + escHtml(c.nom) + '</option>'; }).join('');
      }
    } catch (e) { /* silencieux */ }
  };

  window.closeModalCat = function () {
    var modal = document.getElementById('modal-cat-quick');
    if (modal) modal.style.display = 'none';
    ['mcat-nom', 'mcat-desc'].forEach(function (id) { var el = document.getElementById(id); if (el) el.value = ''; });
    var sel  = document.getElementById('mcat-parent');
    if (sel) sel.value = '';
    var flash = document.getElementById('modal-cat-flash');
    if (flash) flash.style.display = 'none';
  };

  window.submitModalCat = async function () {
    var I   = window.DASH_I18N || {};
    var nom = (document.getElementById('mcat-nom') || {}).value.trim();
    if (!nom) {
      var fl = document.getElementById('modal-cat-flash');
      if (fl) { fl.style.cssText = 'display:flex;background:var(--red-light);color:#991b1b;border:1px solid #fca5a5;padding:8px 12px;border-radius:var(--r-sm);font-size:12.5px;font-weight:600;'; fl.textContent = I.nomCategorieObligatoire || 'Le nom est obligatoire.'; }
      return;
    }
    var btn = document.getElementById('mcat-btn-submit');
    if (btn) { btn.disabled = true; btn.textContent = I.creation || 'Création…'; }

    var payload = { nom: nom };
    var desc    = (document.getElementById('mcat-desc')   || {}).value.trim();
    var parent  = (document.getElementById('mcat-parent') || {}).value;
    if (desc)   payload.description = desc;
    if (parent) payload.parent_id   = parseInt(parent);

    try {
      var resp = await API.post('/api/categories/', payload);
      /* Injecter la nouvelle option dans le select catégorie du formulaire produit */
      var sel = document.getElementById('ap-categorie');
      if (sel) {
        var opt     = document.createElement('option');
        opt.value   = resp.id;
        opt.textContent = resp.nom;
        opt.selected    = true;
        sel.appendChild(opt);
      }
      closeModalCat();
      showToast('Catégorie « ' + escHtml(resp.nom) + ' » créée', 'success');
    } catch (e) {
      var fl = document.getElementById('modal-cat-flash');
      if (fl) { fl.style.cssText = 'display:flex;background:var(--red-light);color:#991b1b;border:1px solid #fca5a5;padding:8px 12px;border-radius:var(--r-sm);font-size:12.5px;font-weight:600;'; fl.textContent = I.erreurCreation || 'Erreur lors de la création.'; }
    } finally {
      if (btn) {
        btn.disabled    = false;
        btn.innerHTML   = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> ' + (I.creerCategorie || 'Créer la catégorie');
      }
    }
  };


  /* ============================================================
     24. INITIALISATION DOMContentLoaded
     ============================================================ */

  document.addEventListener('DOMContentLoaded', function () {
    /* Afficher la date courante dans l'overview */
    updateDateDisplay();

    /* Restaurer la section depuis l'URL après chargement de tous les scripts */
    setTimeout(restoreSection, 0);
  });

})(); /* fin IIFE */