/**
 * HooYia Market — products.js
 * Gestion du catalogue : filtres, infinite scroll, recherche live
 * Utilisé sur : /produits/ (list.html) et /produits/<slug>/ (detail.html)
 */

// ═══════════════════════════════════════════════════════════════
// CATALOGUE — Chargement & filtres
// ═══════════════════════════════════════════════════════════════

const Catalogue = (() => {

  let state = {
    search   : '',
    categorie: '',
    ordering : '-date_creation',
    promo    : false,
    en_vedette: false,
    prix_max : null,
    page     : 1,
    loading  : false,
    hasMore  : true,
  };

  let searchTimer = null;
  const PAGE_SIZE = 12;

  // ── Init depuis les paramètres URL
  function initFromURL() {
    const params = new URLSearchParams(window.location.search);
    state.search    = params.get('search')    || '';
    state.categorie = params.get('categorie') || '';
    state.ordering  = params.get('ordering')  || '-date_creation';
    state.promo     = params.get('promo')     === 'true';
    state.en_vedette = params.get('en_vedette') === 'true';

    // Synchroniser les inputs si présents
    const searchEl = document.getElementById('filter-search');
    const orderEl  = document.getElementById('filter-ordering');
    const promoEl  = document.getElementById('filter-promo');
    if (searchEl) searchEl.value = state.search;
    if (orderEl)  orderEl.value  = state.ordering;
    if (promoEl)  promoEl.checked = state.promo;
  }

  // ── Construire les params de l'API
  function buildParams() {
    const p = new URLSearchParams();
    if (state.search)     p.set('search',    state.search);
    if (state.categorie)  p.set('categorie', state.categorie);
    if (state.ordering)   p.set('ordering',  state.ordering);
    if (state.promo)      p.set('promo',     'true');
    if (state.en_vedette) p.set('en_vedette','true');
    if (state.prix_max)   p.set('prix_max',  state.prix_max);
    p.set('page', state.page);
    return p.toString();
  }

  // ── Charger les produits
  async function load(reset = true) {
    if (state.loading) return;

    const grid     = document.getElementById('products-grid');
    const skeleton = document.getElementById('skeleton-grid');
    const empty    = document.getElementById('empty-state');
    const countEl  = document.getElementById('result-count');
    const pagEl    = document.getElementById('pagination');

    if (!grid) return;

    if (reset) {
      state.page = 1;
      state.hasMore = true;
      grid.innerHTML = '';
      grid.classList.add('hidden');
      if (skeleton) skeleton.classList.remove('hidden');
      if (empty) empty.classList.add('hidden');
    }

    state.loading = true;

    try {
      const data = await API.get('/api/produits/?' + buildParams(), { silentError: true });
      const produits = data.results || data;
      const count    = data.count ?? produits.length;

      if (skeleton) skeleton.classList.add('hidden');

      if (countEl) {
        countEl.textContent = count === 0
          ? 'Aucun résultat'
          : `${count} produit${count > 1 ? 's' : ''}`;
      }

      if (produits.length === 0 && state.page === 1) {
        if (empty) empty.classList.remove('hidden');
        return;
      }

      // Ajouter les cartes
      produits.forEach(p => {
        grid.insertAdjacentHTML('beforeend', renderCard(p));
      });
      grid.classList.remove('hidden');

      // Pagination
      state.hasMore = !!data.next;
      if (pagEl) renderPagination(data, pagEl, count);

    } catch (e) {
      if (skeleton) skeleton.classList.add('hidden');
      if (empty) empty.classList.remove('hidden');
    } finally {
      state.loading = false;
    }
  }

  // ── Rendu d'une carte produit
  function renderCard(p) {
    const imgs = p.images || [];
    const img  = p.image_principale
                 || (imgs.length ? imgs[0].image : null)
                 || '/static/img/logo.svg';
    const prix = p.prix_promo || p.prix;
    const note = Math.round(parseFloat(p.note_moyenne) || 0);

    const badgePromo  = p.prix_promo
      ? `<span class="absolute top-2 left-2 bg-brand-500 text-white text-xs font-mono font-bold px-2 py-0.5 rounded-lg">-${p.pourcentage_remise}%</span>`
      : '';
    const badgeVedette = p.en_vedette
      ? `<span class="absolute top-2 right-2 bg-amber-400 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md">★</span>`
      : '';
    const prixBarre = p.prix_promo
      ? `<span class="text-xs text-ink/30 line-through ml-1 font-body">${formatPrix(p.prix)}</span>`
      : '';
    const stockBadge = p.stock > 0
      ? `<span class="text-xs text-green-600 font-body">En stock</span>`
      : `<span class="text-xs text-red-400 font-body">Épuisé</span>`;

    return `
    <a href="/produits/${p.slug}/" class="card group flex flex-col overflow-hidden animate-fade-in">
      <div class="relative overflow-hidden bg-cream-warm aspect-square">
        <img src="${img}" alt="${escapeHtml(p.nom)}"
          loading="lazy"
          class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onerror="this.src='/static/img/logo.svg'" />
        ${badgePromo}${badgeVedette}
      </div>
      <div class="p-4 flex flex-col flex-1">
        <p class="text-xs text-ink/40 font-body mb-1">${escapeHtml(p.categorie_nom || '')}</p>
        <h3 class="font-body font-semibold text-ink text-sm leading-snug line-clamp-2 flex-1">${escapeHtml(p.nom)}</h3>
        <div class="flex items-center gap-1 mt-2 mb-3">
          <span class="text-amber-400 text-xs">${'★'.repeat(note)}${'☆'.repeat(5 - note)}</span>
          <span class="text-xs text-ink/30 font-body">(${p.nombre_avis})</span>
        </div>
        <div class="flex items-center justify-between">
          <div>
            <span class="font-display font-bold text-ink text-sm">${formatPrix(prix)}</span>
            ${prixBarre}
          </div>
          ${stockBadge}
        </div>
      </div>
    </a>`;
  }

  // ── Pagination
  function renderPagination(data, container, total) {
    if (!data.next && !data.previous) {
      container.classList.add('hidden');
      return;
    }
    container.classList.remove('hidden');
    const totalPages = Math.ceil(total / PAGE_SIZE);
    container.innerHTML = '';

    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement('button');
      btn.textContent = i;
      btn.className = `px-3 py-1.5 rounded-lg text-sm font-body border transition-colors ${
        i === state.page
          ? 'bg-brand-500 text-white border-brand-500'
          : 'border-cream-border text-ink/60 hover:border-brand-400 hover:text-brand-600'
      }`;
      btn.onclick = () => {
        state.page = i;
        load(false);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      };
      container.appendChild(btn);
    }
  }

  // ── API publique du module
  return {
    init() {
      initFromURL();
      this.bindEvents();
      loadCategories();
      load();
    },

    setFilter(key, val) {
      state[key] = val;
      state.page  = 1;
      if (key === 'categorie') highlightCatButton(val);
      load();
    },

    reset() {
      state = { ...state, search: '', categorie: '', ordering: '-date_creation', promo: false, en_vedette: false, prix_max: null, page: 1 };
      const searchEl = document.getElementById('filter-search');
      const orderEl  = document.getElementById('filter-ordering');
      const promoEl  = document.getElementById('filter-promo');
      const prixEl   = document.getElementById('filter-prix');
      const prixLbl  = document.getElementById('prix-label');
      if (searchEl) searchEl.value = '';
      if (orderEl)  orderEl.value  = '-date_creation';
      if (promoEl)  promoEl.checked = false;
      if (prixEl)   prixEl.value   = prixEl.max;
      if (prixLbl)  prixLbl.textContent = parseInt(prixEl?.max || 2000000).toLocaleString('fr-FR');
      highlightCatButton('');
      load();
    },

    updatePrix(val) {
      state.prix_max = parseInt(val) < 2000000 ? parseInt(val) : null;
      const lbl = document.getElementById('prix-label');
      if (lbl) lbl.textContent = parseInt(val).toLocaleString('fr-FR');
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => load(), 500);
    },

    bindEvents() {
      const searchEl   = document.getElementById('filter-search');
      const orderEl    = document.getElementById('filter-ordering');
      const promoEl    = document.getElementById('filter-promo');
      const prixEl     = document.getElementById('filter-prix');

      if (searchEl) {
        searchEl.addEventListener('input', e => {
          clearTimeout(searchTimer);
          state.search = e.target.value.trim();
          state.page   = 1;
          searchTimer  = setTimeout(() => load(), 450);
        });
      }

      if (orderEl) {
        orderEl.addEventListener('change', e => {
          state.ordering = e.target.value;
          load();
        });
      }

      if (promoEl) {
        promoEl.addEventListener('change', e => {
          state.promo = e.target.checked;
          load();
        });
      }

      if (prixEl) {
        prixEl.addEventListener('input', e => this.updatePrix(e.target.value));
      }
    },
  };
})();


// ── Chargement des catégories dans la sidebar
async function loadCategories() {
  try {
    const data = await API.get('/api/produits/categories/', { silentError: true });
    const cats = data.results || data;
    const container = document.getElementById('categories-list');
    if (!container || !cats.length) return;

    cats.forEach(cat => {
      appendCatButton(container, cat.nom, cat.slug);
      // Sous-catégories
      (cat.sous_categories || []).forEach(sub => {
        appendCatButton(container, '↳ ' + sub.nom, sub.slug, true);
      });
    });
    highlightCatButton(new URLSearchParams(window.location.search).get('categorie') || '');
  } catch(e) {}
}

function appendCatButton(container, label, slug, isChild = false) {
  const btn = document.createElement('button');
  btn.dataset.cat = slug;
  btn.onclick = () => Catalogue.setFilter('categorie', slug);
  btn.className = `cat-btn w-full text-left px-3 py-2 text-sm font-body rounded-lg transition-colors ${isChild ? 'pl-5 text-ink/50' : 'text-ink/70'} hover:bg-cream-warm`;
  btn.textContent = label;
  container.appendChild(btn);
}

function highlightCatButton(activeSlug) {
  document.querySelectorAll('.cat-btn').forEach(btn => {
    const isActive = btn.dataset.cat === activeSlug;
    btn.className = btn.className.replace(/text-brand-600 font-medium bg-brand-50|text-ink\/70|text-ink\/50/g, '');
    btn.classList.add(isActive ? 'text-brand-600' : (btn.dataset.cat ? 'text-ink/70' : 'text-ink/70'));
    btn.classList.toggle('font-medium', isActive);
    btn.classList.toggle('bg-brand-50', isActive);
  });
}


// ═══════════════════════════════════════════════════════════════
// FICHE PRODUIT — Ajout au panier rapide depuis la liste
// ═══════════════════════════════════════════════════════════════

async function ajouterRapide(produitId, event) {
  event.preventDefault();
  event.stopPropagation();
  try {
    await API.post('/api/panier/ajouter/', { produit_id: produitId, quantite: 1 });
    window.toast && window.toast('Ajouté au panier !', 'success');
    // Mettre à jour le badge navbar
    const badge = document.getElementById('cart-badge');
    if (badge) {
      badge.classList.remove('hidden');
      badge.textContent = (parseInt(badge.textContent) || 0) + 1;
    }
  } catch(e) {}
}


// ═══════════════════════════════════════════════════════════════
// UTILITAIRES
// ═══════════════════════════════════════════════════════════════

function formatPrix(val) {
  return parseInt(val).toLocaleString('fr-FR') + ' F';
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}


// ── Auto-init si on est sur la page catalogue
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('products-grid')) {
    Catalogue.init();
  }
});

// Exposer pour les templates inline
window.Catalogue = Catalogue;
window.ajouterRapide = ajouterRapide;
window.loadCategories = loadCategories; 