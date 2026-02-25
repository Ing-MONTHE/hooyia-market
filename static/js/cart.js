/**
 * HooYia Market — cart.js
 * Gestion complète du panier : affichage, modification quantité, suppression, vidage.
 * Endpoints utilisés :
 *   GET    /api/panier/
 *   POST   /api/panier/ajouter/
 *   PATCH  /api/panier/items/<id>/
 *   DELETE /api/panier/items/<id>/
 *   DELETE /api/panier/vider/
 */

const Cart = (() => {

  let panierData = null;

  // ── Chargement du panier
  async function load() {
    try {
      const data = await API.get('/api/panier/', { silentError: true });
      panierData = data;
      render(data);
    } catch(e) {
      // Non connecté → redirection login
      if (e && e.status === 401) {
        window.location.href = '/compte/connexion/?next=/panier/';
      }
    }
  }

  // ── Rendu complet du panier
  function render(data) {
    const skeleton = document.getElementById('skeleton');
    const empty    = document.getElementById('empty-cart');
    const content  = document.getElementById('cart-content');

    if (skeleton) skeleton.classList.add('hidden');

    if (data.est_vide || !data.items || data.items.length === 0) {
      if (empty)   empty.classList.remove('hidden');
      if (content) content.classList.add('hidden');
      updateNavBadge(0);
      return;
    }

    if (empty)   empty.classList.add('hidden');
    if (content) content.classList.remove('hidden');

    // Compte
    const countEl = document.getElementById('cart-count');
    if (countEl) {
      const n = data.nombre_articles;
      countEl.textContent = `${n} article${n > 1 ? 's' : ''}`;
    }

    // Liste des items
    const list = document.getElementById('items-list');
    if (list) list.innerHTML = data.items.map(item => renderItem(item)).join('');

    // Totaux
    const total = parseFloat(data.total);
    document.getElementById('subtotal')    && (document.getElementById('subtotal').textContent    = formatPrix(total));
    document.getElementById('total-price') && (document.getElementById('total-price').textContent = formatPrix(total));

    // Badge navbar
    updateNavBadge(data.nombre_articles);
  }

  // ── Rendu d'une ligne article
  function renderItem(item) {
    const img    = item.image_principale || '/static/img/logo.svg';
    const nom    = item.produit_nom || 'Produit supprimé';
    const slug   = item.produit_slug || '#';
    const prix   = parseFloat(item.prix_snapshot);
    const sousTotal = parseFloat(item.sous_total);
    const stockMax  = item.stock_disponible || 99;
    const epuise    = item.produit_statut === 'epuise' || stockMax === 0;

    return `
    <div class="card p-4 flex gap-4 items-start" id="item-${item.id}">

      <!-- Image -->
      <a href="/produits/${slug}/" class="flex-shrink-0">
        <img src="${img}" alt="${escapeHtml(nom)}"
          class="w-20 h-20 object-cover rounded-xl bg-cream-warm"
          onerror="this.src='/static/img/logo.svg'" />
      </a>

      <!-- Infos -->
      <div class="flex-1 min-w-0">
        <a href="/produits/${slug}/" class="font-body font-semibold text-ink text-sm leading-snug hover:text-brand-600 transition-colors line-clamp-2">
          ${escapeHtml(nom)}
        </a>
        <p class="text-xs text-ink/40 font-body mt-1">${formatPrix(prix)} / unité</p>

        ${epuise ? `<span class="inline-block mt-1 text-xs text-red-400 font-body font-medium">⚠ Produit épuisé</span>` : ''}

        <!-- Contrôle quantité -->
        <div class="flex items-center gap-3 mt-3">
          <div class="flex items-center border border-cream-border rounded-xl overflow-hidden">
            <button onclick="Cart.updateQty(${item.id}, ${item.quantite - 1})"
              class="px-3 py-1.5 text-ink/60 hover:bg-cream-warm transition-colors text-base leading-none font-body">−</button>
            <span class="px-3 py-1.5 text-sm font-body font-medium text-ink min-w-[2rem] text-center">${item.quantite}</span>
            <button onclick="Cart.updateQty(${item.id}, ${Math.min(item.quantite + 1, stockMax)})"
              class="px-3 py-1.5 text-ink/60 hover:bg-cream-warm transition-colors text-base leading-none font-body"
              ${item.quantite >= stockMax ? 'disabled' : ''}>+</button>
          </div>
          <button onclick="Cart.removeItem(${item.id})"
            class="text-xs text-ink/30 hover:text-red-400 transition-colors font-body underline underline-offset-2">
            Supprimer
          </button>
        </div>
      </div>

      <!-- Sous-total -->
      <div class="flex-shrink-0 text-right">
        <p class="font-display font-bold text-ink text-sm">${formatPrix(sousTotal)}</p>
      </div>

    </div>`;
  }

  // ── Mise à jour quantité
  async function updateQty(itemId, nouvelleQty) {
    if (nouvelleQty < 0) return;
    try {
      const data = await API.patch(`/api/panier/items/${itemId}/`, { quantite: nouvelleQty });
      // Recharger pour avoir les données fraîches
      await load();
      if (nouvelleQty === 0) window.toast && window.toast('Article supprimé.', 'success');
    } catch(e) {}
  }

  // ── Suppression d'un article
  async function removeItem(itemId) {
    try {
      await API.delete(`/api/panier/items/${itemId}/`);
      await load();
      window.toast && window.toast('Article supprimé du panier.', 'success');
    } catch(e) {}
  }

  // ── Vider le panier
  async function vider() {
    const ok = await showConfirm({ title: 'Vider le panier ?', body: 'Tous les articles seront supprimés de votre panier.', confirmText: '🗑 Vider le panier', type: 'warning' });
    if (!ok) return;
    try {
      await API.delete('/api/panier/vider/');
      await load();
      window.toast && window.toast('Panier vidé.', 'success');
    } catch(e) {}
  }

  // ── Badge navbar
  function updateNavBadge(count) {
    const badge = document.getElementById('cart-badge');
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }

  // ── Utilitaires
  function formatPrix(val) {
    return parseInt(val).toLocaleString('fr-FR') + ' FCFA';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  return { load, render, updateQty, removeItem, vider };

})();

// ── Auto-init sur la page panier
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('items-list')) {
    Cart.load();
  }
});

// ── Exposer pour usage global (ex: detail.html, list.html)
window.Cart = Cart;