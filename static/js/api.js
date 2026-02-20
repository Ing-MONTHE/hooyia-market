/**
 * HooYia Market — api.js
 * Wrapper fetch() global avec :
 *  - JWT auto-refresh (access token expiré → refresh silencieux)
 *  - CSRF token Django pour les requêtes non-GET
 *  - Gestion erreurs centralisée
 *  - window.toast() pour les feedbacks
 *
 * Usage :
 *   const data = await API.get('/api/produits/');
 *   const result = await API.post('/api/panier/ajouter/', { produit_id: 1 });
 */

const API = (() => {

  // ── Clés stockage ──
  const KEYS = {
    access:  'hooyia_access',
    refresh: 'hooyia_refresh',
  };

  // ── Helpers tokens ──
  const getAccess  = () => localStorage.getItem(KEYS.access);
  const getRefresh = () => localStorage.getItem(KEYS.refresh);
  const setTokens  = (access, refresh) => {
    if (access)  localStorage.setItem(KEYS.access, access);
    if (refresh) localStorage.setItem(KEYS.refresh, refresh);
  };
  const clearTokens = () => {
    localStorage.removeItem(KEYS.access);
    localStorage.removeItem(KEYS.refresh);
  };

  // ── CSRF ──
  function getCsrfToken() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1].trim() : '';
  }

  // ── Refresh silencieux ──
  let _refreshing = null;  // Promise partagée si plusieurs appels simultanés

  async function refreshAccessToken() {
    if (_refreshing) return _refreshing;

    _refreshing = (async () => {
      const refresh = getRefresh();
      if (!refresh) throw new Error('No refresh token');

      const res = await fetch('/api/auth/token/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      });

      if (!res.ok) {
        clearTokens();
        throw new Error('Refresh failed');
      }

      const data = await res.json();
      setTokens(data.access, null);
      return data.access;
    })();

    _refreshing.finally(() => { _refreshing = null; });
    return _refreshing;
  }

  // ── Requête principale ──
  async function request(method, url, body = null, options = {}) {
    const makeHeaders = (token) => {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (method !== 'GET') headers['X-CSRFToken'] = getCsrfToken();
      return headers;
    };

    const makeRequest = async (token) => {
      const config = {
        method,
        headers: makeHeaders(token),
      };
      if (body && method !== 'GET') {
        config.body = JSON.stringify(body);
      }
      return fetch(url, config);
    };

    // Premier essai
    let res = await makeRequest(getAccess());

    // 401 → on tente le refresh
    if (res.status === 401) {
      try {
        const newToken = await refreshAccessToken();
        res = await makeRequest(newToken);
      } catch {
        // Refresh échoué → redirection login
        window.location.href = '/compte/connexion/?next=' + encodeURIComponent(window.location.pathname);
        return null;
      }
    }

    // Réponse 204 (No Content)
    if (res.status === 204) return null;

    // Parse JSON
    let data;
    try {
      data = await res.json();
    } catch {
      data = null;
    }

    if (!res.ok) {
      // Extraction message d'erreur lisible
      const msg = extractErrorMessage(data) || `Erreur ${res.status}`;
      if (!options.silentError) {
        window.toast && window.toast(msg, 'error');
      }
      throw Object.assign(new Error(msg), { status: res.status, data });
    }

    return data;
  }

  // ── Extraction message erreur DRF ──
  function extractErrorMessage(data) {
    if (!data) return null;
    if (typeof data === 'string') return data;
    if (data.detail) return data.detail;
    if (data.non_field_errors) return data.non_field_errors[0];
    // Prend la première erreur de champ
    for (const key of Object.keys(data)) {
      const val = data[key];
      if (Array.isArray(val) && val.length) return `${key} : ${val[0]}`;
      if (typeof val === 'string') return `${key} : ${val}`;
    }
    return null;
  }

  // ── API publique ──
  return {
    get:    (url, opts)         => request('GET',    url, null, opts),
    post:   (url, body, opts)   => request('POST',   url, body, opts),
    put:    (url, body, opts)   => request('PUT',    url, body, opts),
    patch:  (url, body, opts)   => request('PATCH',  url, body, opts),
    delete: (url, opts)         => request('DELETE', url, null, opts),

    // Gestion tokens (utilisé par login/logout)
    setTokens,
    clearTokens,
    getAccess,
    getRefresh,
  };
})();